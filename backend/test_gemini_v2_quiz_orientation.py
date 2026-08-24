from __future__ import annotations

import py_compile
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent
SEP = "=" * 120


def main_test() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print(SEP)
    print("GEMINI V2 - QUIZ + ORIENTATION INTEGRATION")
    print(SEP)

    for relative in (
        "main.py",
        "services/quiz_service.py",
        "services/orientation_service.py",
        "services/gemini_service.py",
    ):
        py_compile.compile(str(ROOT / relative), doraise=True)

    print("PY_COMPILE ALL => PASS")

    import main
    from services.orientation_service import reset_orientation_results_v2

    client = TestClient(main.app, raise_server_exceptions=False)

    health = client.get("/health")
    assert health.status_code == 200
    print("HEALTH => PASS")

    student_id = "gemini-v2-integration-student"
    reset_orientation_results_v2(student_id)

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

    print("QUIZ GENERATE HTTP:", generate.status_code)

    if generate.status_code != 200:
        print("QUIZ GENERATE BODY:", generate.text)
        return 1

    quiz = generate.json()

    assert len(quiz.get("questions", [])) == 9

    print("GEMINI STATUS:", quiz.get("gemini_status"))
    print("GENERATION ENGINE:", quiz.get("generation_engine"))
    print(
        "GEMINI QUESTIONS GENERATED:",
        quiz.get("gemini_questions_generated"),
    )

    if quiz.get("gemini_status") != "success":
        print("Gemini did not generate safe question wording.")
        return 2

    if int(quiz.get("gemini_questions_generated", 0) or 0) < 1:
        print("No Gemini question was generated.")
        return 3

    print("GEMINI QUIZ GENERATION => PASS")

    quiz_id = str(quiz.get("quiz_id", "") or "")

    submit = client.post(
        "/quiz/submit",
        json={
            "quiz_id": quiz_id,
            "student_id": student_id,
            "answers": [],
        },
    )

    assert submit.status_code == 200
    assert submit.json().get("score") == 0
    assert submit.json().get("total") == 9

    print("QUIZ SUBMIT => PASS")

    orientation = client.get(f"/orientation/{student_id}")

    print("ORIENTATION HTTP:", orientation.status_code)

    if orientation.status_code != 200:
        print("ORIENTATION BODY:", orientation.text)
        return 4

    output = orientation.json()

    assert output["attempt_count"] == 1
    assert output["weak_areas"]

    print("ORIENTATION AI STATUS:", output.get("ai_status"))
    print("ORIENTATION AI ENGINE:", output.get("ai_engine"))
    print("ORIENTATION AI GUIDANCE:", output.get("ai_guidance"))

    if output.get("ai_status") != "success":
        return 5

    if not str(output.get("ai_guidance", "") or "").strip():
        return 6

    print("GEMINI ORIENTATION GUIDANCE => PASS")

    print()
    print(SEP)
    print("GEMINI V2 FINAL SUMMARY")
    print(SEP)
    print("PY_COMPILE ALL => PASS")
    print("HEALTH => PASS")
    print("GEMINI QUIZ GENERATION => PASS")
    print("QUIZ SUBMIT => PASS")
    print("ORIENTATION RESULT => PASS")
    print("GEMINI ORIENTATION GUIDANCE => PASS")
    print()
    print("FINAL => PASS")
    print(SEP)

    return 0


if __name__ == "__main__":
    raise SystemExit(main_test())
