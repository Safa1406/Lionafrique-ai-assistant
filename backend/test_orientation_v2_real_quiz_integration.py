
from __future__ import annotations

import py_compile
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent
SEP = "=" * 120


def main_test() -> int:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    print(SEP)
    print("ORIENTATION V2 - REAL QUIZ INTEGRATION TEST")
    print(SEP)

    py_compile.compile(
        str(ROOT / "main.py"),
        doraise=True,
    )
    py_compile.compile(
        str(ROOT / "services" / "orientation_service.py"),
        doraise=True,
    )

    print("PY_COMPILE => PASS")

    import main
    import services.quiz_service as qs
    from services.orientation_service import (
        reset_orientation_results_v2,
    )

    client = TestClient(
        main.app,
        raise_server_exceptions=False,
    )

    student_id = "orientation-v2-real-test"
    reset_orientation_results_v2(student_id)

    health = client.get("/health")
    assert health.status_code == 200
    print("HEALTH => PASS")

    generate = client.post(
        "/quiz/generate",
        json={
            "program": "Programme marocain",
            "subject": "Arabe",
            "semester": "Non défini",
            "source": "alnsba (1).pdf",
            "difficulty": "medium",
            "count": 1,
            "question_types": [
                "short_answer"
            ],
        },
    )

    print(
        "QUIZ GENERATE HTTP:",
        generate.status_code,
    )

    assert generate.status_code == 200

    generated = generate.json()
    quiz_id = str(
        generated.get("quiz_id", "")
        or ""
    )

    assert quiz_id
    assert quiz_id in qs.QUIZ_STORE

    stored_questions = (
        qs.QUIZ_STORE[quiz_id]
        .get("questions", [])
    )

    assert len(stored_questions) == 1

    correct_answer = str(
        stored_questions[0].get(
            "correct_answer",
            "",
        )
        or ""
    )

    question_id = int(
        stored_questions[0].get(
            "id",
            1,
        )
    )

    assert correct_answer

    submit = client.post(
        "/quiz/submit",
        json={
            "quiz_id": quiz_id,
            "student_id": student_id,
            "answers": [
                {
                    "question_id": question_id,
                    "answer": correct_answer,
                }
            ],
        },
    )

    print(
        "QUIZ SUBMIT HTTP:",
        submit.status_code,
    )

    assert submit.status_code == 200

    submitted = submit.json()
    assert submitted.get("score") == 1
    assert submitted.get("total") == 1

    after_quiz = client.get(
        f"/orientation/{student_id}"
    )

    print(
        "ORIENTATION AFTER QUIZ HTTP:",
        after_quiz.status_code,
    )

    assert after_quiz.status_code == 200

    quiz_orientation = after_quiz.json()

    assert quiz_orientation["attempt_count"] == 1
    assert (
        quiz_orientation["diagnostics"][0]["subject"]
        == "Arabe"
    )

    exercise = client.post(
        "/orientation/result",
        json={
            "student_id": student_id,
            "subject": "Mathématiques",
            "lesson": "Équations",
            "concept": "Équations du premier degré",
            "score": 4,
            "total": 10,
            "activity_type": "exercise",
            "source": "equations.pdf",
        },
    )

    print(
        "EXERCISE RECORD HTTP:",
        exercise.status_code,
    )

    assert exercise.status_code == 200

    analyze = client.post(
        "/orientation/analyze",
        json={
            "student_id": student_id,
            "target_mastery": 85,
            "max_plan_items": 5,
        },
    )

    print(
        "ORIENTATION ANALYZE HTTP:",
        analyze.status_code,
    )

    assert analyze.status_code == 200

    output = analyze.json()

    assert output["attempt_count"] == 2
    assert len(output["diagnostics"]) == 2
    assert output["revision_plan"]
    assert (
        output["revision_plan"][0]["subject"]
        == "Mathématiques"
    )
    assert (
        output["revision_plan"][0]["current_mastery"]
        == 40.0
    )
    assert (
        output["revision_plan"][0]["priority"]
        == "high"
    )

    print("QUIZ AUTO-RECORD => PASS")
    print("QUIZ METADATA => PASS")
    print("EXERCISE RECORD => PASS")
    print("WEAKNESS DETECTION => PASS")
    print("REVISION PRIORITY => PASS")
    print("ORIENTATION API => PASS")
    print()
    print("FINAL => PASS")
    print(SEP)

    return 0


if __name__ == "__main__":
    raise SystemExit(main_test())
