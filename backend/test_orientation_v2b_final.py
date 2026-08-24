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
        sys.stderr.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    print(SEP)
    print("ORIENTATION V2B - REAL QUIZ INTEGRATION FINAL TEST")
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
    from services.orientation_service import (
        reset_orientation_results_v2,
    )

    client = TestClient(
        main.app,
        raise_server_exceptions=False,
    )

    student_id = "orientation-v2b-final-test"
    reset_orientation_results_v2(student_id)

    health = client.get("/health")
    assert health.status_code == 200
    print("HEALTH => PASS")

    # Stable regression case already validated by the Quiz module:
    # Arabe / alnsba (1).pdf / 3 MCQ + 3 TF + 3 short answers.
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

    print(
        "QUIZ GENERATE HTTP:",
        generate.status_code,
    )

    if generate.status_code != 200:
        print(
            "QUIZ GENERATE BODY:",
            generate.text,
        )
        return 1

    generated = generate.json()

    quiz_id = str(
        generated.get("quiz_id", "")
        or ""
    )

    questions = (
        generated.get("questions", [])
        or []
    )

    assert quiz_id
    assert len(questions) == 9

    print("QUIZ GENERATE 9 => PASS")

    # Empty answers are intentionally used here.
    # Quiz V25X already proved that 0/9 submission is valid.
    # This gives Orientation a real weak result to diagnose.
    submit = client.post(
        "/quiz/submit",
        json={
            "quiz_id": quiz_id,
            "student_id": student_id,
            "answers": [],
        },
    )

    print(
        "QUIZ SUBMIT HTTP:",
        submit.status_code,
    )

    if submit.status_code != 200:
        print(
            "QUIZ SUBMIT BODY:",
            submit.text,
        )
        return 1

    submitted = submit.json()

    assert submitted.get("score") == 0
    assert submitted.get("total") == 9

    print("QUIZ SUBMIT 0/9 => PASS")

    after_quiz = client.get(
        f"/orientation/{student_id}"
    )

    print(
        "ORIENTATION AFTER QUIZ HTTP:",
        after_quiz.status_code,
    )

    if after_quiz.status_code != 200:
        print(
            "ORIENTATION BODY:",
            after_quiz.text,
        )
        return 1

    quiz_orientation = after_quiz.json()

    assert quiz_orientation["attempt_count"] == 1
    assert len(quiz_orientation["diagnostics"]) == 1
    assert (
        quiz_orientation["diagnostics"][0]["subject"]
        == "Arabe"
    )
    assert (
        quiz_orientation["diagnostics"][0]["mastery"]
        == 0.0
    )
    assert (
        quiz_orientation["diagnostics"][0]["priority"]
        == "high"
    )

    print("QUIZ AUTO-RECORD => PASS")
    print("QUIZ METADATA => PASS")
    print("QUIZ WEAKNESS DETECTION => PASS")

    # Simulate a real exercise result.
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

    if exercise.status_code != 200:
        print(
            "EXERCISE BODY:",
            exercise.text,
        )
        return 1

    print("EXERCISE RECORD => PASS")

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

    if analyze.status_code != 200:
        print(
            "ANALYZE BODY:",
            analyze.text,
        )
        return 1

    output = analyze.json()

    assert output["status"] == "success"
    assert output["attempt_count"] == 2
    assert len(output["diagnostics"]) == 2
    assert len(output["weak_areas"]) == 2
    assert len(output["revision_plan"]) == 2

    # Arabe 0% must be first, then Math 40%.
    first = output["revision_plan"][0]
    second = output["revision_plan"][1]

    assert first["subject"] == "Arabe"
    assert first["current_mastery"] == 0.0
    assert first["priority"] == "high"

    assert second["subject"] == "Mathématiques"
    assert second["current_mastery"] == 40.0
    assert second["priority"] == "high"

    print("QUIZ + EXERCISE MIX => PASS")
    print("WEAKNESS RANKING => PASS")
    print("REVISION PLAN => PASS")
    print("ORIENTATION API => PASS")

    empty_student = client.get(
        "/orientation/student-with-no-results-v2b"
    )

    assert empty_student.status_code == 200
    assert empty_student.json()["attempt_count"] == 0

    print("EMPTY STUDENT SAFE => PASS")

    print()
    print(SEP)
    print("ORIENTATION V2B FINAL SUMMARY")
    print(SEP)
    print("PY_COMPILE => PASS")
    print("HEALTH => PASS")
    print("QUIZ GENERATE 9 => PASS")
    print("QUIZ SUBMIT 0/9 => PASS")
    print("QUIZ AUTO-RECORD => PASS")
    print("QUIZ METADATA => PASS")
    print("EXERCISE RECORD => PASS")
    print("WEAKNESS RANKING => PASS")
    print("REVISION PLAN => PASS")
    print("ORIENTATION API => PASS")
    print("EMPTY STUDENT SAFE => PASS")
    print()
    print("FINAL => PASS")
    print(SEP)

    return 0


if __name__ == "__main__":
    raise SystemExit(main_test())
