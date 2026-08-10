import argparse
import json
import re
import unicodedata
from pathlib import Path

import test_batch_histoire_geographique as base


API_BASE_URL = "http://127.0.0.1:8000"

PROGRAM = "Programme marocain"

SUBJECT = "SVT arabe"

NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 1


base.API_BASE_URL = API_BASE_URL
base.PROGRAM = PROGRAM
base.SUBJECT = SUBJECT
base.NUMBER_OF_RESULTS = NUMBER_OF_RESULTS
base.TIMEOUT_SECONDS = TIMEOUT_SECONDS
base.MAX_ATTEMPTS = MAX_ATTEMPTS


def normalize_svt_arabe_text(value):
    value = (
        value
        or ""
    )

    value = unicodedata.normalize(
        "NFKD",
        value.casefold(),
    )

    # Remove combining marks / Arabic diacritics.
    value = "".join(
        char
        for char in value
        if not unicodedata.combining(
            char
        )
    )

    # Remove bidi controls produced by OCR/PDF extraction.
    value = re.sub(
        r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]",
        "",
        value,
    )

    replacements = {
        "\u0623": "\u0627",
        "\u0625": "\u0627",
        "\u0622": "\u0627",
        "\u0671": "\u0627",
        "\u0649": "\u064a",
        "\u0624": "\u0648",
        "\u0626": "\u064a",
        "\u0640": "",
        "\u00d7": "*",
        "\u00f7": "/",
        "\u2212": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u00b2": "^2",
        "\u00b3": "^3",
    }

    for old, new in replacements.items():
        value = value.replace(
            old,
            new,
        )

    # Ignore punctuation spacing during validation.
    value = re.sub(
        r"[\u060c\u061b\u061f,.;:]+",
        " ",
        value,
    )

    value = re.sub(
        r"[()\[\]{}]+",
        " ",
        value,
    )

    value = re.sub(
        r"[^\w+\-*/=<>!^%]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def token_coverage(
    actual,
    expected,
):
    actual_tokens = set(
        normalize_svt_arabe_text(
            actual
        ).split()
    )

    expected_tokens = (
        normalize_svt_arabe_text(
            expected
        ).split()
    )

    if not expected_tokens:
        return 1.0

    matched = sum(
        token in actual_tokens
        for token in expected_tokens
    )

    return (
        matched
        / len(expected_tokens)
    )


def missing_groups(
    text,
    required_groups,
):
    normalized_text = (
        normalize_svt_arabe_text(
            text
        )
    )

    missing = []

    for group in required_groups:

        matched = False

        for expected in group:

            normalized_expected = (
                normalize_svt_arabe_text(
                    expected
                )
            )

            if (
                normalized_expected
                and normalized_expected
                in normalized_text
            ):
                matched = True
                break

            expected_tokens = (
                normalized_expected
                .split()
            )

            coverage = token_coverage(
                text,
                expected,
            )

            if (
                len(expected_tokens) >= 5
                and coverage >= 0.90
            ):
                matched = True
                break

        if not matched:
            missing.append(
                group
            )

    return missing


base.missing_groups = missing_groups

request_api = base.request_api
run_document = base.run_document


def load_specs():
    return json.loads(
        Path(
            "mega_svt_arabe_specs.json"
        ).read_text(
            encoding="utf-8"
        )
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--start",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--end",
        type=int,
        default=17,
    )

    args = parser.parse_args()

    spec = load_specs()

    documents = spec[
        "documents"
    ][
        args.start - 1:
        args.end
    ]

    total_passed = 0
    total_tests = 0
    all_failures = []

    for pdf_index, doc in enumerate(
        documents,
        start=args.start,
    ):

        print()
        print("=" * 100)

        print(
            f"PDF {pdf_index}/12"
        )

        print(
            doc["source"]
        )

        print(
            "OCR:",
            doc.get(
                "ocr",
                False,
            )
        )

        print("=" * 100)

        passed, failures = (
            run_document(
                doc
            )
        )

        test_count = len(
            doc["tests"]
        )

        total_passed += passed
        total_tests += test_count

        print(
            f"RESULT: "
            f"{passed}/{test_count}"
        )

        for failure in failures:

            failure[
                "pdf_index"
            ] = pdf_index

            failure[
                "source"
            ] = doc["source"]

            all_failures.append(
                failure
            )

    print()
    print("=" * 100)
    print(
        "SVT ARABE BATCH RESULT"
    )
    print("=" * 100)

    print(
        f"PASSED: "
        f"{total_passed}/{total_tests}"
    )

    print(
        f"FAILED: "
        f"{len(all_failures)}"
    )

    if all_failures:

        print()
        print("=" * 100)
        print("FAILURES")
        print("=" * 100)

        for failure in all_failures:

            print()
            print("-" * 100)

            print(
                json.dumps(
                    failure,
                    ensure_ascii=False,
                    indent=2,
                )
            )


if __name__ == "__main__":
    main()
