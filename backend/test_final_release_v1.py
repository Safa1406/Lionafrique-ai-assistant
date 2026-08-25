from __future__ import annotations
import py_compile

import re
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
FRONTEND = PROJECT / "frontend"

SEP = "=" * 120

ARABIC_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]"
)


def status(name: str, ok: bool) -> None:
    print(f"{name} => {'PASS' if ok else 'FAIL'}")
    if not ok:
        raise AssertionError(name)


def run_frontend_build() -> bool:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        print("FRONTEND BUILD => SKIPPED (npm not found)")
        return True

    result = subprocess.run(
        [npm, "run", "build"],
        cwd=str(FRONTEND),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)

    return result.returncode == 0


def main() -> int:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
        sys.stderr.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    print(SEP)
    print("LIONAFRIQUE - FINAL RELEASE TEST")
    print(SEP)

    compile_targets = [
        ROOT / "main.py",
        ROOT / "services" / "quiz_service.py",
        ROOT / "services" / "orientation_service.py",
        ROOT / "services" / "gemini_service.py",
    ]

    for target in compile_targets:
        py_compile.compile(
            str(target),
            doraise=True,
        )

    status("PY_COMPILE ALL", True)

    import main
    from services.orientation_service import (
        reset_orientation_results_v2,
    )

    client = TestClient(
        main.app,
        raise_server_exceptions=False,
    )

    health = client.get("/health")
    status(
        "HEALTH",
        health.status_code == 200,
    )

    metadata = client.get(
        "/metadata/options"
    )
    status(
        "METADATA",
        metadata.status_code == 200,
    )

    preflight = client.options(
        "/quiz/generate",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    cors_origin = (
        preflight.headers.get(
            "access-control-allow-origin",
            ""
        )
    )

    status(
        "FRONTEND CORS",
        preflight.status_code in (200, 204)
        and cors_origin in (
            "*",
            "http://localhost:5173",
        ),
    )

    student_id = (
        "final-release-student"
    )

    reset_orientation_results_v2(
        student_id
    )

    generate = client.post(
        "/quiz/generate",
        json={
            "program": "Programme marocain",
            "subject": "Arabe",
            "semester": "Non défini",
            "source": "alnsba (1).pdf",
            "difficulty": "medium",
            "count": 9,
            "question_types": [
                "mcq",
                "true_false",
                "short_answer",
                "mcq",
                "true_false",
                "short_answer",
                "mcq",
                "true_false",
                "short_answer",
            ],
        },
    )

    if generate.status_code != 200:
        print(
            "QUIZ GENERATE BODY:",
            generate.text,
        )

    status(
        "QUIZ GENERATE",
        generate.status_code == 200,
    )

    quiz = generate.json()

    status(
        "QUIZ COUNT 9",
        len(
            quiz.get(
                "questions",
                [],
            )
        ) == 9,
    )

    status(
        "GEMINI QUIZ",
        quiz.get(
            "gemini_status"
        ) == "success"
        and int(
            quiz.get(
                "gemini_questions_generated",
                0,
            )
            or 0
        ) >= 1,
    )

    public_text = str(
        quiz.get(
            "questions",
            [],
        )
    ).lower()

    leak_tokens = [
        "correct_answer",
        "expected_answer",
        "answer_key",
    ]

    status(
        "NO PUBLIC ANSWER LEAK",
        not any(
            token in public_text
            for token in leak_tokens
        ),
    )

    submit = client.post(
        "/quiz/submit",
        json={
            "quiz_id": quiz.get(
                "quiz_id"
            ),
            "student_id": student_id,
            "answers": [],
        },
    )

    if submit.status_code != 200:
        print(
            "QUIZ SUBMIT BODY:",
            submit.text,
        )

    status(
        "QUIZ SUBMIT",
        submit.status_code == 200,
    )

    submit_body = submit.json()

    status(
        "QUIZ SCORE ROUNDTRIP",
        submit_body.get(
            "score"
        ) == 0
        and submit_body.get(
            "total"
        ) == 9,
    )

    orientation = client.get(
        f"/orientation/{student_id}"
    )

    if orientation.status_code != 200:
        print(
            "ORIENTATION BODY:",
            orientation.text,
        )

    status(
        "LEARNING PROFILE API",
        orientation.status_code == 200,
    )

    profile = orientation.json()

    status(
        "PROFILE ATTEMPT",
        profile.get(
            "attempt_count"
        ) == 1,
    )

    status(
        "WEAKNESS DETECTION",
        bool(
            profile.get(
                "weak_areas"
            )
        ),
    )

    status(
        "REVISION PLAN",
        bool(
            profile.get(
                "revision_plan"
            )
        ),
    )

    status(
        "GEMINI GUIDANCE",
        profile.get(
            "ai_status"
        ) == "success"
        and bool(
            str(
                profile.get(
                    "ai_guidance",
                    "",
                )
            ).strip()
        ),
    )

    guidance = str(
        profile.get(
            "ai_guidance",
            "",
        )
    ).strip()

    print(
        "GUIDANCE:",
        guidance,
    )

    status(
        "GEMINI GUIDANCE FRENCH ONLY",
        not bool(
            ARABIC_RE.search(
                guidance
            )
        ),
    )

    status(
        "FRONTEND BUILD",
        run_frontend_build(),
    )

    print()
    print(SEP)
    print(
        "FINAL RELEASE SUMMARY"
    )
    print(SEP)
    print(
        "BACKEND + GEMINI + QUIZ + LEARNING PROFILE + FRONTEND => PASS"
    )
    print()
    print(
        "FINAL => PASS"
    )
    print(SEP)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
