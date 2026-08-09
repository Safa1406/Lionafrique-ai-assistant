import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
import difflib
from pathlib import Path

API_BASE_URL = "http://127.0.0.1:8000"
PROGRAM = "Programme marocain"
SUBJECT = "Histoire-G\u00e9ographie"
SEMESTER = None
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 90
MAX_ATTEMPTS = 2


def normalize_text(text):
    s = unicodedata.normalize(
        "NFKC",
        (text or "").lower(),
    )

    s = (
        s.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )

    # Arabic normalization.
    s = re.sub(
        r"[\u064B-\u065F\u0670]",
        "",
        s,
    )

    s = (
        s.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
        .replace("ـ", "")
    )

    s = re.sub(
        r"[^\w\s\-]",
        " ",
        s,
        flags=re.UNICODE,
    )

    return re.sub(
        r"\s+",
        " ",
        s,
    ).strip()


def _token_close(expected, actual):
    if expected == actual:
        return True

    if min(len(expected), len(actual)) < 3:
        return False

    if abs(len(expected) - len(actual)) > 1:
        return False

    return (
        difflib.SequenceMatcher(
            None,
            expected,
            actual,
        ).ratio()
        >= 0.80
    )


def group_present(text, group):
    haystack = normalize_text(text)

    for expected in group:
        needle = normalize_text(expected)

        if not needle:
            continue

        if needle in haystack:
            return True

        expected_tokens = needle.split()
        actual_tokens = haystack.split()

        if not expected_tokens:
            continue

        matched = 0
        used = set()

        for expected_token in expected_tokens:
            for idx, actual_token in enumerate(actual_tokens):
                if idx in used:
                    continue

                if _token_close(
                    expected_token,
                    actual_token,
                ):
                    matched += 1
                    used.add(idx)
                    break

        coverage = matched / len(expected_tokens)

        if coverage >= 0.90:
            return True

    return False


def missing_groups(text, required_groups):
    return [
        group
        for group in required_groups
        if not group_present(text, group)
    ]


def request_api(endpoint, source, question):
    payload = {
        "question": question,
        "number_of_results": NUMBER_OF_RESULTS,
        "program": PROGRAM,
        "subject": SUBJECT,
        "semester": SEMESTER,
        "source": source,
    }

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(
            API_BASE_URL + endpoint,
            data=json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json"
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                req,
                timeout=TIMEOUT_SECONDS,
            ) as response:
                return json.loads(
                    response.read().decode("utf-8")
                )

        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
        ) as exc:
            last_error = exc

            if attempt < MAX_ATTEMPTS:
                time.sleep(1)
                continue

            raise

    raise last_error


def run_document(doc):
    source = doc["source"]
    passed = 0
    failures = []

    for i, tc in enumerate(doc["tests"], start=1):
        try:
            data = request_api(
                tc["endpoint"],
                source,
                tc["question"],
            )
            error = ""
        except Exception as exc:
            data = {}
            error = repr(exc)

        actual_status = data.get("status", "")

        text = (
            data.get("summary", "")
            if tc["endpoint"] == "/summarize"
            else data.get("answer", "")
        )

        sources = data.get("sources", [])

        missing = missing_groups(
            text,
            tc["required_groups"],
        )

        source_ok = True

        if tc["expected_status"] == "success":
            source_ok = (
                bool(sources)
                and all(
                    item.get("file", "") == source
                    for item in sources
                )
            )

        ok = (
            not error
            and actual_status
            == tc["expected_status"]
            and not missing
            and source_ok
        )

        if ok:
            passed += 1
        else:
            failures.append(
                {
                    "test": i,
                    "category": tc["category"],
                    "question": tc["question"],
                    "expected_status":
                        tc["expected_status"],
                    "actual_status":
                        actual_status,
                    "missing": missing,
                    "source_ok": source_ok,
                    "error": error,
                    "response": text[:3000],
                }
            )

    return passed, failures


if __name__ == "__main__":
    spec = json.loads(
        Path(
            "mega_histoire_geographique_specs.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    grand_passed = 0
    grand_total = 0
    all_results = []

    for doc in spec["documents"]:
        passed, failures = run_document(doc)

        total = len(doc["tests"])
        grand_passed += passed
        grand_total += total

        all_results.append(
            {
                "lesson_number":
                    doc["lesson_number"],
                "source": doc["source"],
                "passed": passed,
                "failed": total - passed,
                "failures": failures,
            }
        )

        print(
            f"PDF {doc['lesson_number']:02d}: "
            f"{passed}/{total} | "
            f"{doc['source']}"
        )

        for failure in failures:
            print(
                f"  FAIL TEST "
                f"{failure['test']}: "
                f"{failure['category']}"
            )
            print(
                "    STATUS:",
                failure["actual_status"],
            )
            print(
                "    MISSING:",
                failure["missing"],
            )

    result = {
        "passed": grand_passed,
        "failed": grand_total - grand_passed,
        "total": grand_total,
        "pdfs_valid": sum(
            1
            for item in all_results
            if item["failed"] == 0
        ),
        "documents": all_results,
    }

    Path(
        "histoire_geographique_test_results.json"
    ).write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 90)
    print("FINAL RESULT")
    print("=" * 90)
    print("REUSSIS:", grand_passed)
    print("ECHOUE:", grand_total - grand_passed)
    print("TOTAL:", grand_total)
    print(
        "PDFs VALIDES:",
        result["pdfs_valid"],
        "/",
        len(spec["documents"]),
    )


# HISTOIRE_RTL_DATE_VALIDATION_V1
#
# Arabic PDF extraction can move a four-digit year around
# the surrounding Arabic token:
#
#     "1920????? ?"
#     "????? ?1920"
#
# For long evidence groups containing a year, allow a
# high token-coverage fallback after the normal strict
# validator has already failed.

_original_missing_groups = missing_groups


def _rtl_validation_normalize(
    value,
):
    import re
    import unicodedata

    value = unicodedata.normalize(
        "NFKC",
        value or "",
    )

    value = value.casefold()

    value = re.sub(
        r"[\u064b-\u065f\u0670]",
        "",
        value,
    )

    value = value.replace(
        "\u0640",
        "",
    )

    value = re.sub(
        r"[\u0622\u0623\u0625]",
        "\u0627",
        value,
    )

    value = value.replace(
        "\u0649",
        "\u064a",
    )

    value = value.replace(
        "\u0624",
        "\u0648",
    )

    value = value.replace(
        "\u0626",
        "\u064a",
    )

    # Separate Arabic letters and numbers.
    value = re.sub(
        r"(?<=[\u0600-\u06ff])(?=\d)",
        " ",
        value,
    )

    value = re.sub(
        r"(?<=\d)(?=[\u0600-\u06ff])",
        " ",
        value,
    )

    # Punctuation is irrelevant for this fallback.
    # \w already preserves Arabic letters and digits.
    value = value.replace(
        "_",
        " ",
    )

    value = re.sub(
        r"[^\w]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value


def _rtl_year_token_match(
    text,
    expected,
):
    import re
    import difflib

    expected_normalized = (
        _rtl_validation_normalize(
            expected
        )
    )

    text_normalized = (
        _rtl_validation_normalize(
            text
        )
    )

    expected_tokens = (
        expected_normalized.split()
    )

    text_tokens = (
        text_normalized.split()
    )

    # Keep this fallback intentionally narrow.
    if len(expected_tokens) < 6:
        return False

    if not any(
        re.fullmatch(
            r"\d{2,4}",
            token,
        )
        for token in expected_tokens
    ):
        return False

    matched = 0

    for expected_token in expected_tokens:

        if expected_token in text_tokens:
            matched += 1
            continue

        if len(expected_token) < 3:
            continue

        fuzzy = any(
            abs(
                len(expected_token)
                - len(text_token)
            )
            <= 1
            and difflib.SequenceMatcher(
                None,
                expected_token,
                text_token,
            ).ratio()
            >= 0.86
            for text_token in text_tokens
            if len(text_token) >= 3
        )

        if fuzzy:
            matched += 1

    coverage = (
        matched
        / max(
            1,
            len(expected_tokens),
        )
    )

    return coverage >= 0.90


def missing_groups(
    text,
    required_groups,
):
    missing = (
        _original_missing_groups(
            text,
            required_groups,
        )
    )

    if not missing:
        return []

    remaining = []

    for group in missing:

        recovered = any(
            _rtl_year_token_match(
                text,
                option,
            )
            for option in group
        )

        if not recovered:
            remaining.append(
                group
            )

    return remaining

