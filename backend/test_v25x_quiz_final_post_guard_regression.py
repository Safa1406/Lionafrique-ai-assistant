from __future__ import annotations

import json
import py_compile
import sys
import traceback
from collections import Counter
from pathlib import Path

SEP = "=" * 120
SUBSEP = "-" * 120

ROOT = Path(__file__).resolve().parent
QUIZ_SERVICE = ROOT / "services" / "quiz_service.py"
MAIN_FILE = ROOT / "main.py"

AR_PROGRAM = "Programme marocain"
AR_SUBJECT = "Arabe"
AR_SEMESTER = "Non défini"
AR_SOURCE = "alnsba (1).pdf"

MATH_PROGRAM = "Programme marocain"
MATH_SUBJECT = "Mathématiques arabe"
MATH_SEMESTER = "S2"
MATH_SOURCE = "alihsaa-aldrs-1-2.pdf"

QUESTION_TYPES = [
    "mcq",
    "true_false",
    "short_answer",
] * 3

FORBIDDEN_PUBLIC_FIELDS = {
    "correct_answer",
    "answer",
    "expected_answer",
    "explanation",
    "evidence_quote",
    "is_true",
}


def setup_console() -> None:
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


def print_json(value) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> int:
    setup_console()

    failures: list[str] = []

    print(SEP)
    print("QUIZ V25X - FINAL POST-V25W REGRESSION")
    print(SEP)

    # ==============================================================================================
    # STATIC
    # ==============================================================================================

    compile_quiz = False
    compile_main = False
    import_pass = False

    try:
        py_compile.compile(
            str(QUIZ_SERVICE),
            doraise=True,
        )
        compile_quiz = True
    except Exception:
        traceback.print_exc()

    try:
        py_compile.compile(
            str(MAIN_FILE),
            doraise=True,
        )
        compile_main = True
    except Exception:
        traceback.print_exc()

    print(
        "quiz_service.py PY_COMPILE:",
        "PASS" if compile_quiz else "FAIL",
    )
    print(
        "main.py PY_COMPILE:",
        "PASS" if compile_main else "FAIL",
    )

    if not compile_quiz:
        failures.append("quiz_service_compile")
    if not compile_main:
        failures.append("main_compile")

    try:
        from fastapi.testclient import TestClient
        import services.quiz_service as qs
        import main as app_main
        import_pass = True
    except Exception:
        traceback.print_exc()
        qs = None
        app_main = None
        TestClient = None

    print(
        "IMPORTS:",
        "PASS" if import_pass else "FAIL",
    )

    if not import_pass:
        failures.append("imports")
        print()
        print("FINAL => FAIL")
        return 1

    # ==============================================================================================
    # MARKERS
    # ==============================================================================================

    service_text = QUIZ_SERVICE.read_text(
        encoding="utf-8",
        errors="replace",
    )

    helper_count = service_text.count(
        "# QUIZ_MATH_AR_SOURCE_QUALITY_GUARD_V25W"
    )
    call_count = service_text.count(
        "# QUIZ_MATH_AR_SOURCE_QUALITY_GUARD_CALL_V25W"
    )

    marker_pass = (
        helper_count == 1
        and call_count == 1
    )

    print(
        "V25W MARKERS:",
        f"helper={helper_count}",
        f"call={call_count}",
        "=>",
        "PASS" if marker_pass else "FAIL",
    )

    if not marker_pass:
        failures.append(
            f"v25w_markers helper={helper_count} call={call_count}"
        )

    # ==============================================================================================
    # DIRECT MATH-AR QUALITY GUARD
    # ==============================================================================================

    print()
    print(SEP)
    print("MATH-AR DIRTY SOURCE GUARD")
    print(SEP)

    math_guard_pass = False

    try:
        qs.generate_quiz(
            program=MATH_PROGRAM,
            subject=MATH_SUBJECT,
            semester=MATH_SEMESTER,
            source=MATH_SOURCE,
            difficulty="medium",
            count=9,
            question_types=QUESTION_TYPES,
        )

        print(
            "UNEXPECTED: dirty Math-Ar source generated a 9-question quiz."
        )

    except RuntimeError as exc:
        message = str(exc)

        print("REJECTION:", message)

        math_guard_pass = (
            "QUIZ_SOURCE_QUALITY_INSUFFICIENT_V25W"
            in message
            and "clean="
            in message
            and "/9"
            in message
        )

    except Exception as exc:
        print(
            "WRONG EXCEPTION TYPE:",
            repr(exc),
        )

    print(
        "MATH-AR DIRTY SOURCE REJECTED:",
        "PASS" if math_guard_pass else "FAIL",
    )

    if not math_guard_pass:
        failures.append("math_ar_guard")

    # ==============================================================================================
    # ARABIC NORMAL GENERATION REGRESSION
    # ==============================================================================================

    print()
    print(SEP)
    print("ARABE NORMAL GENERATION REGRESSION")
    print(SEP)

    ar_result = None
    ar_questions = []

    try:
        ar_result = qs.generate_quiz(
            program=AR_PROGRAM,
            subject=AR_SUBJECT,
            semester=AR_SEMESTER,
            source=AR_SOURCE,
            difficulty="medium",
            count=9,
            question_types=QUESTION_TYPES,
        )

        ar_questions = (
            ar_result.get("questions", [])
            or []
        )

    except Exception:
        traceback.print_exc()

    ar_count_pass = (
        isinstance(ar_result, dict)
        and len(ar_questions) == 9
    )

    counts = Counter(
        str(item.get("type", "") or "")
        for item in ar_questions
    )

    ar_type_pass = (
        counts.get("mcq", 0) == 3
        and counts.get("true_false", 0) == 3
        and counts.get("short_answer", 0) == 3
    )

    print(
        "ARABE QUESTION COUNT:",
        len(ar_questions),
        "=>",
        "PASS" if ar_count_pass else "FAIL",
    )
    print(
        "ARABE TYPE COUNTS:",
        dict(counts),
        "=>",
        "PASS" if ar_type_pass else "FAIL",
    )

    if not ar_count_pass:
        failures.append(
            f"arabe_count={len(ar_questions)}"
        )

    if not ar_type_pass:
        failures.append(
            f"arabe_type_counts={dict(counts)}"
        )

    # ==============================================================================================
    # PUBLIC LEAK AUDIT
    # ==============================================================================================

    print()
    print(SEP)
    print("PUBLIC ANSWER LEAK AUDIT")
    print(SEP)

    leak_pass = True

    for question in ar_questions:
        qid = question.get("id")
        leaked = sorted(
            FORBIDDEN_PUBLIC_FIELDS.intersection(
                question.keys()
            )
        )

        if leaked:
            leak_pass = False
            print(
                f"Q{qid}: FAIL leaked={leaked}"
            )
        else:
            print(
                f"Q{qid}: PASS"
            )

    print(
        "PUBLIC ANSWER LEAK:",
        "PASS" if leak_pass else "FAIL",
    )

    if not leak_pass:
        failures.append("public_answer_leak")

    # ==============================================================================================
    # INTERNAL STORE + ANSWER ROUND-TRIP
    # ==============================================================================================

    quiz_id = str(
        (ar_result or {}).get("quiz_id", "")
        or ""
    ).strip()

    internal_quiz = (
        getattr(qs, "QUIZ_STORE", {})
        .get(quiz_id)
        if quiz_id
        else None
    )

    internal_questions = (
        internal_quiz.get("questions", [])
        if isinstance(internal_quiz, dict)
        else []
    )

    store_pass = (
        quiz_id
        and len(internal_questions) == 9
    )

    round_trip_pass = True

    if store_pass:
        for item in internal_questions:
            answer = str(
                item.get("correct_answer", "")
                or ""
            )
            qtype = str(
                item.get("type", "")
                or ""
            )

            try:
                matched = bool(
                    qs.answer_matches(
                        submitted=answer,
                        expected=answer,
                        question_type=qtype,
                    )
                )
            except Exception:
                matched = False

            if not matched:
                round_trip_pass = False
                print(
                    "ROUND-TRIP FAIL:",
                    item.get("id"),
                    qtype,
                    repr(answer),
                )
    else:
        round_trip_pass = False

    print(
        "QUIZ STORE:",
        "PASS" if store_pass else "FAIL",
    )
    print(
        "ANSWER ROUND-TRIP:",
        "PASS" if round_trip_pass else "FAIL",
    )

    if not store_pass:
        failures.append("quiz_store")
    if not round_trip_pass:
        failures.append("answer_round_trip")

    # ==============================================================================================
    # API HEALTH + SUBMIT
    # ==============================================================================================

    print()
    print(SEP)
    print("API END-TO-END")
    print(SEP)

    client = TestClient(
        app_main.app,
        raise_server_exceptions=False,
    )

    health_pass = False
    api_generate_pass = False
    api_submit_pass = False
    api_empty_pass = False
    invalid_id_pass = False

    try:
        health_response = client.get(
            "/health"
        )

        print(
            "HEALTH HTTP:",
            health_response.status_code,
        )

        health_pass = (
            health_response.status_code == 200
        )

    except Exception:
        traceback.print_exc()

    # Generate a fresh API quiz so submit is tested through HTTP.
    api_quiz_id = ""
    api_public_questions = []

    try:
        generate_response = client.post(
            "/quiz/generate",
            json={
                "program": AR_PROGRAM,
                "subject": AR_SUBJECT,
                "semester": AR_SEMESTER,
                "source": AR_SOURCE,
                "difficulty": "medium",
                "count": 9,
                "question_types": QUESTION_TYPES,
            },
        )

        print(
            "GENERATE HTTP:",
            generate_response.status_code,
        )

        if generate_response.status_code == 200:
            payload = generate_response.json()

            api_quiz_id = str(
                payload.get("quiz_id", "")
                or ""
            )

            api_public_questions = (
                payload.get("questions", [])
                or []
            )

            api_counts = Counter(
                str(item.get("type", "") or "")
                for item in api_public_questions
            )

            api_generate_pass = (
                len(api_public_questions) == 9
                and api_counts.get("mcq", 0) == 3
                and api_counts.get("true_false", 0) == 3
                and api_counts.get("short_answer", 0) == 3
            )

    except Exception:
        traceback.print_exc()

    print(
        "API GENERATE 9:",
        "PASS" if api_generate_pass else "FAIL",
    )

    if api_generate_pass:
        api_internal = (
            getattr(qs, "QUIZ_STORE", {})
            .get(api_quiz_id, {})
            .get("questions", [])
        )

        correct_answers = [
            {
                "question_id": int(item.get("id")),
                "answer": "  "
                + str(item.get("correct_answer", "") or "")
                + "  ",
            }
            for item in api_internal
        ]

        try:
            submit_response = client.post(
                "/quiz/submit",
                json={
                    "quiz_id": api_quiz_id,
                    "answers": correct_answers,
                },
            )

            print(
                "SUBMIT ALL-CORRECT HTTP:",
                submit_response.status_code,
            )

            if submit_response.status_code == 200:
                payload = submit_response.json()

                api_submit_pass = (
                    payload.get("score") == 9
                    and payload.get("total") == 9
                    and float(
                        payload.get("score_percent", 0)
                    ) == 100.0
                    and payload.get("correct") == 9
                    and payload.get("incorrect") == 0
                )

        except Exception:
            traceback.print_exc()

        try:
            empty_response = client.post(
                "/quiz/submit",
                json={
                    "quiz_id": api_quiz_id,
                    "answers": [],
                },
            )

            print(
                "SUBMIT EMPTY HTTP:",
                empty_response.status_code,
            )

            if empty_response.status_code == 200:
                payload = empty_response.json()

                api_empty_pass = (
                    payload.get("score") == 0
                    and payload.get("total") == 9
                    and payload.get("correct") == 0
                    and payload.get("incorrect") == 9
                )

        except Exception:
            traceback.print_exc()

    try:
        invalid_response = client.post(
            "/quiz/submit",
            json={
                "quiz_id": "__V25X_INVALID_QUIZ_ID__",
                "answers": [],
            },
        )

        print(
            "INVALID QUIZ ID HTTP:",
            invalid_response.status_code,
        )

        invalid_id_pass = (
            invalid_response.status_code != 200
        )

    except Exception:
        traceback.print_exc()

    print(
        "HEALTH:",
        "PASS" if health_pass else "FAIL",
    )
    print(
        "API SUBMIT 9/9:",
        "PASS" if api_submit_pass else "FAIL",
    )
    print(
        "API SUBMIT 0/9:",
        "PASS" if api_empty_pass else "FAIL",
    )
    print(
        "INVALID QUIZ ID SAFE FAILURE:",
        "PASS" if invalid_id_pass else "FAIL",
    )

    if not health_pass:
        failures.append("health")
    if not api_generate_pass:
        failures.append("api_generate")
    if not api_submit_pass:
        failures.append("api_submit_9_9")
    if not api_empty_pass:
        failures.append("api_submit_0_9")
    if not invalid_id_pass:
        failures.append("invalid_quiz_id")

    # ==============================================================================================
    # FINAL
    # ==============================================================================================

    final_pass = not failures

    print()
    print(SEP)
    print("QUIZ V25X FINAL SUMMARY")
    print(SEP)

    print(
        "V25W MARKERS =>",
        "PASS" if marker_pass else "FAIL",
    )
    print(
        "MATH-AR DIRTY SOURCE REJECTED =>",
        "PASS" if math_guard_pass else "FAIL",
    )
    print(
        "ARABE NORMAL GENERATION =>",
        "PASS"
        if ar_count_pass and ar_type_pass
        else "FAIL",
    )
    print(
        "PUBLIC ANSWER LEAK =>",
        "PASS" if leak_pass else "FAIL",
    )
    print(
        "ANSWER ROUND-TRIP =>",
        "PASS" if round_trip_pass else "FAIL",
    )
    print(
        "HEALTH =>",
        "PASS" if health_pass else "FAIL",
    )
    print(
        "API GENERATE 9 =>",
        "PASS" if api_generate_pass else "FAIL",
    )
    print(
        "API SUBMIT 9/9 =>",
        "PASS" if api_submit_pass else "FAIL",
    )
    print(
        "API SUBMIT 0/9 =>",
        "PASS" if api_empty_pass else "FAIL",
    )
    print(
        "INVALID QUIZ ID SAFE FAILURE =>",
        "PASS" if invalid_id_pass else "FAIL",
    )

    print()
    print(
        "FAILURE COUNT:",
        len(failures),
    )

    if failures:
        print("FAILURES:")
        for failure in failures:
            print(" -", failure)

    print()
    print(
        "FINAL =>",
        "PASS" if final_pass else "FAIL",
    )
    print(SEP)

    return 0 if final_pass else 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
