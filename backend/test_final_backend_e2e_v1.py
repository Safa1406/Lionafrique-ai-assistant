from __future__ import annotations

import py_compile
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent
SEP = "=" * 120


def setup_console():
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


def main_test() -> int:
    setup_console()

    print(SEP)
    print("LIONAFRIQUE - FINAL BACKEND E2E V1")
    print(SEP)

    main_file = ROOT / "main.py"
    quiz_file = ROOT / "services" / "quiz_service.py"
    orientation_file = ROOT / "services" / "orientation_service.py"

    for path in (
        main_file,
        quiz_file,
        orientation_file,
    ):
        py_compile.compile(
            str(path),
            doraise=True,
        )

    print("PY_COMPILE ALL => PASS")

    import main
    import services.quiz_service as qs
    from services.orientation_service import (
        reset_orientation_results_v2,
    )

    client = TestClient(
        main.app,
        raise_server_exceptions=False,
    )

    # ==============================================================================================
    # HEALTH
    # ==============================================================================================

    health = client.get("/health")

    print(
        "HEALTH HTTP:",
        health.status_code,
    )

    assert health.status_code == 200

    print("HEALTH => PASS")

    # ==============================================================================================
    # METADATA
    # ==============================================================================================

    metadata = client.get(
        "/metadata/options"
    )

    print(
        "METADATA HTTP:",
        metadata.status_code,
    )

    assert metadata.status_code == 200

    print("METADATA => PASS")

    # ==============================================================================================
    # QUIZ GENERATION
    # ==============================================================================================

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

    payload = generate.json()

    quiz_id = str(
        payload.get("quiz_id", "")
        or ""
    )

    questions = (
        payload.get("questions", [])
        or []
    )

    assert quiz_id
    assert len(questions) == 9

    type_counts = {
        "mcq": 0,
        "true_false": 0,
        "short_answer": 0,
    }

    for item in questions:
        qtype = str(
            item.get("type", "")
            or ""
        )

        if qtype in type_counts:
            type_counts[qtype] += 1

        for forbidden in (
            "correct_answer",
            "answer",
            "expected_answer",
        ):
            assert forbidden not in item

    assert type_counts == {
        "mcq": 3,
        "true_false": 3,
        "short_answer": 3,
    }

    print("QUIZ GENERATE 9 => PASS")
    print("QUIZ TYPE MIX => PASS")
    print("QUIZ PUBLIC ANSWER LEAK => PASS")

    # ==============================================================================================
    # ORIENTATION AUTO-RECORD FROM QUIZ
    # ==============================================================================================

    student_id = "lionafrique-final-e2e-student"

    reset_orientation_results_v2(
        student_id
    )

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

    submit_payload = submit.json()

    assert submit_payload.get("score") == 0
    assert submit_payload.get("total") == 9

    print("QUIZ SUBMIT 0/9 => PASS")

    orientation_after_quiz = client.get(
        f"/orientation/{student_id}"
    )

    print(
        "ORIENTATION GET HTTP:",
        orientation_after_quiz.status_code,
    )

    assert (
        orientation_after_quiz.status_code
        == 200
    )

    orientation_payload = (
        orientation_after_quiz.json()
    )

    assert (
        orientation_payload["attempt_count"]
        == 1
    )

    assert (
        orientation_payload["diagnostics"][0][
            "subject"
        ]
        == "Arabe"
    )

    assert (
        orientation_payload["diagnostics"][0][
            "mastery"
        ]
        == 0.0
    )

    print("QUIZ -> ORIENTATION AUTO RECORD => PASS")

    # ==============================================================================================
    # EXERCISE -> ORIENTATION
    # ==============================================================================================

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

    print("EXERCISE -> ORIENTATION => PASS")

    # ==============================================================================================
    # ANALYSIS
    # ==============================================================================================

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

    analysis = analyze.json()

    assert analysis["attempt_count"] == 2
    assert len(
        analysis["diagnostics"]
    ) == 2
    assert len(
        analysis["weak_areas"]
    ) == 2
    assert len(
        analysis["revision_plan"]
    ) == 2

    first = analysis[
        "revision_plan"
    ][0]

    second = analysis[
        "revision_plan"
    ][1]

    assert first["subject"] == "Arabe"
    assert first["current_mastery"] == 0.0
    assert first["priority"] == "high"

    assert second["subject"] == "Mathématiques"
    assert second["current_mastery"] == 40.0
    assert second["priority"] == "high"

    print("WEAKNESS DETECTION => PASS")
    print("PRIORITY RANKING => PASS")
    print("REVISION PLAN => PASS")

    # ==============================================================================================
    # DIRTY MATH-AR SOURCE SAFETY
    # ==============================================================================================

    dirty_math = client.post(
        "/quiz/generate",
        json={
            "program": "Programme marocain",
            "subject": "Mathématiques arabe",
            "semester": "S2",
            "source": "alihsaa-aldrs-1-2.pdf",
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
        "DIRTY MATH-AR HTTP:",
        dirty_math.status_code,
    )

    assert dirty_math.status_code != 200

    dirty_body = dirty_math.text

    assert (
        "QUIZ_SOURCE_QUALITY_INSUFFICIENT_V25W"
        in dirty_body
    )

    print("DIRTY MATH-AR SAFE REJECTION => PASS")

    # ==============================================================================================
    # INVALID QUIZ
    # ==============================================================================================

    invalid = client.post(
        "/quiz/submit",
        json={
            "quiz_id": "__INVALID_FINAL_E2E__",
            "student_id": student_id,
            "answers": [],
        },
    )

    print(
        "INVALID QUIZ HTTP:",
        invalid.status_code,
    )

    assert invalid.status_code == 404

    print("INVALID QUIZ SAFE FAILURE => PASS")

    # ==============================================================================================
    # EMPTY STUDENT
    # ==============================================================================================

    empty = client.get(
        "/orientation/final-empty-student"
    )

    assert empty.status_code == 200
    assert (
        empty.json()["attempt_count"]
        == 0
    )

    print("EMPTY STUDENT SAFE => PASS")

    # ==============================================================================================
    # FINAL
    # ==============================================================================================

    print()
    print(SEP)
    print("FINAL BACKEND E2E SUMMARY")
    print(SEP)

    print("PY_COMPILE ALL => PASS")
    print("HEALTH => PASS")
    print("METADATA => PASS")
    print("QUIZ GENERATE 9 => PASS")
    print("QUIZ TYPE MIX => PASS")
    print("QUIZ PUBLIC ANSWER LEAK => PASS")
    print("QUIZ SUBMIT => PASS")
    print("QUIZ -> ORIENTATION => PASS")
    print("EXERCISE -> ORIENTATION => PASS")
    print("WEAKNESS DETECTION => PASS")
    print("PRIORITY RANKING => PASS")
    print("REVISION PLAN => PASS")
    print("DIRTY MATH-AR SAFE REJECTION => PASS")
    print("INVALID QUIZ SAFE FAILURE => PASS")
    print("EMPTY STUDENT SAFE => PASS")

    print()
    print("FINAL => PASS")
    print(SEP)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main_test()
    )
