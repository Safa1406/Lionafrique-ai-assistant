from __future__ import annotations

import py_compile
import re
import sys
import traceback
import unicodedata
from collections import Counter
from pathlib import Path

SEP = "=" * 120
SUBSEP = "-" * 120

ROOT = Path(__file__).resolve().parent
SERVICE = ROOT / "services" / "quiz_service.py"

MIXED_TYPES = ["mcq", "true_false", "short_answer"] * 3

CASES = [
    {
        "name": "FR-FRANCAIS",
        "program": "Programme français",
        "subject": "Français",
        "semester": "Non défini",
        "source": "recc81visions-brevet-franccca7ais.pdf",
        "language": "fr",
        "require_false_tf": True,
        "require_numeric": False,
    },
    {
        "name": "FR-MATH",
        "program": "Programme français",
        "subject": "Mathématiques",
        "semester": "Non défini",
        "source": "theoreme-de-thales-cours.pdf",
        "language": "fr",
        "require_false_tf": False,
        "require_numeric": True,
    },
    {
        "name": "FR-PC",
        "program": "Programme français",
        "subject": "Physique-Chimie",
        "semester": "Non défini",
        "source": "puissance-et-energie-electrique-cours-1.pdf",
        "language": "fr",
        "require_false_tf": False,
        "require_numeric": False,
    },
    {
        "name": "FR-SVT",
        "program": "Programme français",
        "subject": "SVT",
        "semester": "Non défini",
        "source": "genetique-fiche-brevet.pdf",
        "language": "fr",
        "require_false_tf": False,
        "require_numeric": True,
    },
    {
        "name": "MA-ARABE",
        "program": "Programme marocain",
        "subject": "Arabe",
        "semester": "Non défini",
        "source": "alnsba (1).pdf",
        "language": "ar",
        "require_false_tf": False,
        "require_numeric": False,
    },
]

EXPECTED_PER_CASE = {
    "mcq": 3,
    "true_false": 3,
    "short_answer": 3,
}

ARABIC_DIACRITICS = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
)

NUMERIC_RE = re.compile(
    r"^[+\-−]?\d+(?:[.,]\d+)?(?:\s*[%°])?$"
)


def console_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = ARABIC_DIACRITICS.sub("", text)
    text = text.replace("ـ", "")
    text = (
        text.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ٱ", "ا")
        .replace("ى", "ي")
    )
    text = re.sub(
        r"[^\w\u0600-\u06FF]+",
        " ",
        text,
        flags=re.UNICODE,
    )
    return re.sub(r"\s+", " ", text).strip().lower()


def is_numeric_answer(value: object) -> bool:
    return bool(NUMERIC_RE.fullmatch(str(value or "").strip()))


def compile_service() -> bool:
    try:
        py_compile.compile(str(SERVICE), doraise=True)
        return True
    except Exception:
        traceback.print_exc()
        return False


def get_internal(qs, quiz_id: str) -> list[dict]:
    store = getattr(qs, "QUIZ_STORE", {})
    quiz = store.get(quiz_id)
    if not isinstance(quiz, dict):
        raise RuntimeError("Quiz absent from QUIZ_STORE.")
    questions = quiz.get("questions", [])
    if not isinstance(questions, list):
        raise RuntimeError("Internal questions are not a list.")
    return questions


def exact_one_option(options: list, correct_answer: str) -> bool:
    target = normalize(correct_answer)
    return sum(
        1 for option in options if normalize(option) == target
    ) == 1


def public_answer_leak(question: dict) -> list[str]:
    leaked = []
    for key in (
        "correct_answer",
        "answer",
        "expected_answer",
        "explanation",
        "evidence_quote",
        "is_true",
    ):
        if key in question:
            leaked.append(key)
    return leaked


def audit_case(qs, config: dict) -> tuple[bool, list[str], int]:
    failures = []

    print()
    print(SEP)
    print(config["name"])
    print("PROGRAM:", config["program"])
    print("SUBJECT:", config["subject"])
    print("SOURCE:", config["source"])
    print(SEP)

    try:
        result = qs.generate_quiz(
            program=config["program"],
            subject=config["subject"],
            semester=config["semester"],
            source=config["source"],
            difficulty="medium",
            count=9,
            question_types=MIXED_TYPES,
        )
    except Exception as exc:
        traceback.print_exc()
        failures.append("generation_error=" + repr(exc))
        return False, failures, 0

    quiz_id = str(result.get("quiz_id", "") or "").strip()
    public = result.get("questions", []) or []

    try:
        internal = get_internal(qs, quiz_id)
    except Exception as exc:
        failures.append("internal_store_error=" + repr(exc))
        return False, failures, len(public)

    internal_by_id = {}
    for item in internal:
        try:
            qid = int(item.get("id"))
        except Exception:
            continue
        internal_by_id[qid] = item

    if len(public) != 9:
        failures.append(f"public_count={len(public)} expected=9")
    if len(internal) != 9:
        failures.append(f"internal_count={len(internal)} expected=9")
    if result.get("question_count") != 9:
        failures.append(
            "question_count_contract=" + repr(result.get("question_count"))
        )

    counts = Counter(
        str(item.get("type", "") or "") for item in public
    )
    for qtype, expected in EXPECTED_PER_CASE.items():
        if counts.get(qtype, 0) != expected:
            failures.append(
                f"type_count_{qtype}={counts.get(qtype, 0)} expected={expected}"
            )

    normalized_questions = [
        normalize(item.get("question", "")) for item in public
    ]
    duplicates = [
        value
        for value, count in Counter(normalized_questions).items()
        if value and count > 1
    ]
    if duplicates:
        failures.append("duplicate_questions=" + repr(duplicates))

    false_tf_count = 0
    numeric_answers = []

    for public_item in public:
        try:
            qid = int(public_item.get("id"))
        except Exception:
            failures.append(
                "invalid_public_id=" + repr(public_item.get("id"))
            )
            continue

        qtype = str(public_item.get("type", "") or "").strip()
        question = str(public_item.get("question", "") or "").strip()
        source = str(public_item.get("source", "") or "").strip()
        page = public_item.get("page")
        options = public_item.get("options", []) or []

        print()
        print(SUBSEP)
        print(f"Q{qid} | {qtype}")
        print("Q:", repr(question))
        print("PAGE:", page)
        print("OPTIONS:", repr(options))

        if not question:
            failures.append(f"Q{qid}: empty_question")
        if source != config["source"]:
            failures.append(f"Q{qid}: source={source!r}")

        leaks = public_answer_leak(public_item)
        if leaks:
            failures.append(
                f"Q{qid}: public_answer_leak=" + repr(leaks)
            )

        internal_item = internal_by_id.get(qid)
        if not isinstance(internal_item, dict):
            failures.append(f"Q{qid}: missing_internal")
            continue

        internal_question = str(
            internal_item.get("question", "") or ""
        ).strip()
        if normalize(internal_question) != normalize(question):
            failures.append(
                f"Q{qid}: public_internal_mismatch"
            )

        answer = str(
            internal_item.get("correct_answer", "") or ""
        ).strip()
        evidence = str(
            internal_item.get("evidence_quote", "") or ""
        ).strip()
        explanation = str(
            internal_item.get("explanation", "") or ""
        ).strip()

        print("INTERNAL ANSWER:", repr(answer))

        if not answer:
            failures.append(f"Q{qid}: empty_internal_answer")
        if not evidence:
            failures.append(f"Q{qid}: missing_evidence")
        if not explanation:
            failures.append(f"Q{qid}: missing_explanation")

        try:
            round_trip = bool(
                qs.answer_matches(
                    submitted=answer,
                    expected=answer,
                    question_type=qtype,
                )
            )
        except Exception:
            round_trip = False

        if not round_trip:
            failures.append(f"Q{qid}: answer_round_trip_fail")

        if qtype == "mcq":
            if len(options) != 4:
                failures.append(
                    f"Q{qid}: mcq_option_count={len(options)}"
                )

            normalized_options = [normalize(option) for option in options]
            if len(set(normalized_options)) != len(normalized_options):
                failures.append(
                    f"Q{qid}: duplicate_mcq_options"
                )

            if not exact_one_option(options, answer):
                failures.append(
                    f"Q{qid}: correct_mcq_not_exactly_once"
                )

        elif qtype == "true_false":
            if config["language"] == "fr":
                expected_options = {"vrai", "faux"}
            else:
                expected_options = {
                    normalize("صحيح"),
                    normalize("خطأ"),
                }

            actual_options = {normalize(option) for option in options}
            normalized_expected_options = {
                normalize(option) for option in expected_options
            }

            if actual_options != normalized_expected_options:
                failures.append(
                    f"Q{qid}: tf_options={options!r}"
                )

            if normalize(answer) in {
                normalize("Faux"),
                normalize("خطأ"),
                "false",
            }:
                false_tf_count += 1

        elif qtype == "short_answer":
            if options:
                failures.append(
                    f"Q{qid}: short_answer_has_options"
                )

        else:
            failures.append(
                f"Q{qid}: unknown_type={qtype!r}"
            )

        if is_numeric_answer(answer):
            numeric_answers.append(answer)

        if (
            config["language"] == "ar"
            and qtype in {"mcq", "short_answer"}
        ):
            answer_n = normalize(answer)
            evidence_n = normalize(evidence)
            if not answer_n or answer_n not in evidence_n:
                failures.append(
                    f"Q{qid}: arabic_answer_not_in_source_span"
                )

        q_fail = any(
            item.startswith(f"Q{qid}:") for item in failures
        )
        print("QUALITY:", "FAIL" if q_fail else "PASS")

    if config.get("require_false_tf") and false_tf_count < 1:
        failures.append("required_deterministic_false_tf_missing")

    if config.get("require_numeric") and not numeric_answers:
        failures.append("required_exact_numeric_answer_missing")

    if numeric_answers:
        print()
        print("NUMERIC ANSWERS:", numeric_answers)

    print("FALSE TF COUNT:", false_tf_count)

    passed = not failures
    print()
    print("CASE RESULT:", "PASS" if passed else "FAIL")

    if failures:
        print("FAILURES:")
        for failure in failures:
            print("-", failure)

    return passed, failures, len(public)


def main() -> int:
    console_utf8()

    print(SEP)
    print("QUIZ V25O - FINAL CROSS-LANGUAGE REGRESSION")
    print(SEP)
    print("5 CASES x 9 QUESTIONS = 45")
    print(
        "EXPECTED EACH: 3 MCQ + 3 TRUE_FALSE + 3 SHORT_ANSWER"
    )

    compile_pass = compile_service()
    print()
    print("PY_COMPILE:", "PASS" if compile_pass else "FAIL")
    if not compile_pass:
        print("FINAL => FAIL")
        return 1

    try:
        import services.quiz_service as qs
        import_pass = True
    except Exception:
        traceback.print_exc()
        qs = None
        import_pass = False

    print("IMPORT:", "PASS" if import_pass else "FAIL")
    if not import_pass:
        print("FINAL => FAIL")
        return 1

    case_results = []
    total_questions = 0
    all_failures = []

    for config in CASES:
        passed, failures, count = audit_case(qs, config)
        total_questions += count
        case_results.append((config["name"], passed))
        all_failures.extend(
            (config["name"], failure)
            for failure in failures
        )

    final_pass = (
        compile_pass
        and import_pass
        and total_questions == 45
        and all(passed for _, passed in case_results)
    )

    print()
    print(SEP)
    print("QUIZ V25O FINAL REGRESSION SUMMARY")
    print(SEP)

    for name, passed in case_results:
        print(name, "=>", "PASS" if passed else "FAIL")

    print()
    print(
        "SUCCESSFUL CASES:",
        sum(1 for _, passed in case_results if passed),
        "/",
        len(case_results),
    )
    print(
        "TOTAL QUESTIONS:",
        total_questions,
        "/ expected 45",
    )
    print(
        "PY_COMPILE:",
        "PASS" if compile_pass else "FAIL",
    )
    print(
        "IMPORT:",
        "PASS" if import_pass else "FAIL",
    )

    if all_failures:
        print()
        print("GLOBAL FAILURE DETAILS")
        for case_name, failure in all_failures:
            print(f"- {case_name}: {failure}")

    print()
    print("FINAL =>", "PASS" if final_pass else "FAIL")
    print(SEP)

    return 0 if final_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
