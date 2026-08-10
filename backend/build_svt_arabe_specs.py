import csv
import json
import re
import unicodedata
from pathlib import Path

import services.retrieval_service as retrieval


BACKEND = Path(__file__).resolve().parent

RAW_ROOT = (
    BACKEND.parent
    / "data"
    / "raw"
    / "Programme Marocain"
    / "SVT arabe"
)

OUT_SPECS = (
    BACKEND
    / "mega_svt_arabe_specs.json"
)

OUT_JSON = (
    BACKEND
    / "svt_arabe_inventory.json"
)

OUT_CSV = (
    BACKEND
    / "svt_arabe_inventory.csv"
)


PROGRAM = "Programme marocain"
SUBJECT = "SVT arabe"


def clean_text(value):
    value = (
        value
        or ""
    )

    # Remove bidi / zero-width controls.
    value = re.sub(
        r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]",
        "",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalize_arabic(value):
    value = clean_text(
        value
    )

    value = value.casefold()

    # Arabic diacritics.
    value = re.sub(
        r"[\u064b-\u065f\u0670\u06d6-\u06ed]",
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
    }

    for old, new in replacements.items():
        value = value.replace(
            old,
            new,
        )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def arabic_count(value):
    return len(
        re.findall(
            r"[\u0600-\u06ff]",
            value or "",
        )
    )


def meaningful_count(value):
    return len(
        re.findall(
            r"[\u0600-\u06ffA-Za-z0-9]",
            value or "",
        )
    )


def is_good_candidate(value):
    value = clean_text(
        value
    )

    if not (
        18
        <= len(value)
        <= 260
    ):
        return False

    if arabic_count(value) < 8:
        return False

    meaningful = meaningful_count(
        value
    )

    if meaningful < 10:
        return False

    arabic_ratio = (
        arabic_count(value)
        / max(
            1,
            meaningful,
        )
    )

    if arabic_ratio < 0.45:
        return False

    normalized = normalize_arabic(
        value
    )

    weak_exact = {
        "\u062a\u0639\u0631\u064a\u0641",
        "\u062e\u0627\u0635\u064a\u0629",
        "\u0642\u0627\u0639\u062f\u0629",
        "\u0645\u062b\u0627\u0644",
        "\u0627\u0645\u062b\u0644\u0629",
        "\u062a\u0637\u0628\u064a\u0642",
        "\u062a\u0645\u0631\u064a\u0646",
        "\u062a\u0645\u0627\u0631\u064a\u0646",
        "\u0645\u0644\u0627\u062d\u0638\u0629",
        "\u0646\u0634\u0627\u0637",
        "\u062d\u0644",
    }

    if normalized in weak_exact:
        return False

    # Reject obvious labels / fragments.
    if re.fullmatch(
        r"[\d\s\-./():]+",
        normalized,
    ):
        return False

    words = re.findall(
        r"[\u0600-\u06ffA-Za-z0-9]+",
        value,
    )

    if len(words) < 4:
        return False

    weak_endings = {
        "\u0641\u064a",
        "\u0645\u0646",
        "\u0627\u0644\u0649",
        "\u0639\u0644\u0649",
        "\u0647\u0648",
        "\u0647\u064a",
        "\u0648",
        "\u0627\u0648",
        "\u0627\u0646",
        "\u0645\u0639",
    }

    if (
        words
        and normalize_arabic(
            words[-1]
        )
        in weak_endings
    ):
        return False

    return True


def evenly_select(items, count):
    if not items:
        return []

    count = min(
        count,
        len(items),
    )

    if count == 1:
        return [
            items[
                len(items) // 2
            ]
        ]

    indexes = []

    for i in range(count):

        index = round(
            i
            * (len(items) - 1)
            / (count - 1)
        )

        if index not in indexes:
            indexes.append(
                index
            )

    return [
        items[i]
        for i in indexes
    ]


def make_partial(value):
    words = value.split()

    if len(words) <= 6:
        return value

    size = max(
        5,
        round(
            len(words) * 0.65
        ),
    )

    start = max(
        0,
        (
            len(words)
            - size
        ) // 2,
    )

    return " ".join(
        words[
            start:
            start + size
        ]
    )


def make_arabic_typo(value):
    words = re.findall(
        r"[\u0621-\u064a]{5,}",
        value,
    )

    if not words:
        return value

    word = max(
        words,
        key=len,
    )

    position = max(
        2,
        len(word) // 2,
    )

    typo = (
        word[:position]
        + word[position + 1:]
    )

    return value.replace(
        word,
        typo,
        1,
    )


def make_format_noise(value):
    value = (
        value
        .replace(
            "\u060c",
            " ",
        )
        .replace(
            "\u061b",
            " ",
        )
        .replace(
            ".",
            " ",
        )
        .replace(
            ":",
            " ",
        )
        .replace(
            "(",
            " ",
        )
        .replace(
            ")",
            " ",
        )
    )

    value = re.sub(
        r"[\u064b-\u065f\u0670]",
        "",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def quote_question(prefix, anchor):
    return (
        prefix
        + " \u00ab"
        + anchor
        + "\u00bb."
    )


# ------------------------------------------------------------
# Get the exact Chroma collection used by retrieval.
# ------------------------------------------------------------

getter = (
    retrieval.search_similar_chunks
    .__globals__
    .get(
        "get_document_collection"
    )
)

if getter is None:
    raise RuntimeError(
        "CHROMA COLLECTION GETTER NOT FOUND"
    )

collection = getter()


pdfs = []

for semester in (
    "S1",
    "S2",
):
    for path in sorted(
        (
            RAW_ROOT
            / semester
        ).glob(
            "*.pdf"
        )
    ):
        pdfs.append(
            (
                semester,
                path,
            )
        )


if len(pdfs) != 12:
    raise SystemExit(
        "EXPECTED 14 PDFS, FOUND "
        + str(
            len(pdfs)
        )
    )


documents = []
inventory = []


for pdf_index, (
    semester,
    pdf_path,
) in enumerate(
    pdfs,
    start=1,
):

    stored = collection.get(
        where={
            "source": pdf_path.name
        },
        include=[
            "documents",
            "metadatas",
        ],
    )

    records = []

    for text, metadata in zip(
        stored.get(
            "documents",
            [],
        )
        or [],
        stored.get(
            "metadatas",
            [],
        )
        or [],
    ):

        metadata = (
            metadata
            or {}
        )

        if (
            metadata.get(
                "program"
            )
            != PROGRAM
        ):
            continue

        if (
            metadata.get(
                "subject"
            )
            != SUBJECT
        ):
            continue

        if (
            metadata.get(
                "semester"
            )
            != semester
        ):
            continue

        records.append(
            {
                "page": metadata.get(
                    "page",
                    0,
                ),
                "chunk_number": (
                    metadata.get(
                        "chunk_number",
                        0,
                    )
                ),
                "text": text or "",
            }
        )

    records.sort(
        key=lambda item: (
            item["page"],
            item["chunk_number"],
        )
    )

    if not records:
        raise SystemExit(
            f"NO CHROMA RECORDS FOR "
            f"{pdf_path.name}"
        )

    candidates = []
    seen = set()

    for record in records:

        for raw_line in (
            record["text"]
            .splitlines()
        ):

            line = clean_text(
                raw_line
            )

            if not is_good_candidate(
                line
            ):
                continue

            key = normalize_arabic(
                line
            )

            if (
                not key
                or key in seen
            ):
                continue

            seen.add(
                key
            )

            candidates.append(
                {
                    "page": record[
                        "page"
                    ],
                    "text": line,
                }
            )

    # If OCR line splitting leaves too few strong units,
    # add adjacent lines from the same chunk.
    if len(candidates) < 3:

        for record in records:

            lines = [
                clean_text(
                    line
                )
                for line in (
                    record["text"]
                    .splitlines()
                )
                if clean_text(
                    line
                )
            ]

            for i in range(
                len(lines) - 1
            ):

                combined = clean_text(
                    lines[i]
                    + " "
                    + lines[i + 1]
                )

                if not is_good_candidate(
                    combined
                ):
                    continue

                key = normalize_arabic(
                    combined
                )

                if (
                    not key
                    or key in seen
                ):
                    continue

                seen.add(
                    key
                )

                candidates.append(
                    {
                        "page": record[
                            "page"
                        ],
                        "text": combined,
                    }
                )

    if len(candidates) < 3:
        raise SystemExit(
            f"PDF {pdf_index} "
            f"HAS ONLY "
            f"{len(candidates)} "
            "USABLE CANDIDATES"
        )

    anchors = evenly_select(
        candidates,
        9,
    )

    tests = []
    test_number = 1

    # ========================================================
    # 1-9: Document evidence
    # ========================================================

    exact_prompts = [
        (
            "\u062d\u0633\u0628 "
            "\u0627\u0644\u0648\u062b\u064a\u0642\u0629\u060c "
            "\u0627\u0646\u0633\u062e "
            "\u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0629 "
            "\u0627\u0644\u0645\u0631\u062a\u0628\u0637\u0629 "
            "\u0628\u0627\u0644\u0645\u0642\u0637\u0639"
        ),
        (
            "\u0627\u0639\u062b\u0631 "
            "\u0641\u064a "
            "\u0627\u0644\u0648\u062b\u064a\u0642\u0629 "
            "\u0639\u0644\u0649 "
            "\u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0629 "
            "\u0627\u0644\u062a\u0627\u0644\u064a\u0629"
        ),
        (
            "\u0645\u0627 "
            "\u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0629 "
            "\u0627\u0644\u062a\u064a "
            "\u062a\u0648\u0627\u0641\u0642 "
            "\u0647\u0630\u0627 "
            "\u0627\u0644\u0645\u0642\u0637\u0639"
        ),
    ]

    for index in range(9):

        item = anchors[
            index
            % len(anchors)
        ]

        tests.append(
            {
                "test": test_number,
                "category": (
                    "Document evidence"
                ),
                "endpoint": "/ask",
                "question": quote_question(
                    exact_prompts[
                        index
                        % len(
                            exact_prompts
                        )
                    ],
                    item["text"],
                ),
                "expected_status": (
                    "success"
                ),
                "required_groups": [
                    [
                        item["text"]
                    ]
                ],
                "expected_page": (
                    item["page"]
                ),
            }
        )

        test_number += 1

    # ========================================================
    # 10-15: Partial evidence
    # ========================================================

    for index in range(6):

        item = anchors[
            index
            % len(anchors)
        ]

        partial = make_partial(
            item["text"]
        )

        tests.append(
            {
                "test": test_number,
                "category": (
                    "Partial evidence retrieval"
                ),
                "endpoint": "/ask",
                "question": quote_question(
                    (
                        "\u0627\u0639\u062b\u0631 "
                        "\u0639\u0644\u0649 "
                        "\u0627\u0644\u0645\u0642\u0637\u0639 "
                        "\u0627\u0644\u0643\u0627\u0645\u0644 "
                        "\u0627\u0644\u0645\u0648\u0627\u0641\u0642 "
                        "\u0644\u0647\u0630\u0627 "
                        "\u0627\u0644\u062c\u0632\u0621"
                    ),
                    partial,
                ),
                "expected_status": (
                    "success"
                ),
                "required_groups": [
                    [
                        item["text"]
                    ]
                ],
                "expected_page": (
                    item["page"]
                ),
            }
        )

        test_number += 1

    # ========================================================
    # 16-21: Typo tolerance
    # ========================================================

    for index in range(6):

        item = anchors[
            index
            % len(anchors)
        ]

        noisy = make_arabic_typo(
            item["text"]
        )

        tests.append(
            {
                "test": test_number,
                "category": (
                    "Spelling tolerance"
                ),
                "endpoint": "/ask",
                "question": quote_question(
                    (
                        "\u0627\u0639\u062b\u0631 "
                        "\u0639\u0644\u0649 "
                        "\u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0629 "
                        "\u0631\u063a\u0645 "
                        "\u0648\u062c\u0648\u062f "
                        "\u062e\u0637\u0623 "
                        "\u0641\u064a "
                        "\u0647\u0630\u0627 "
                        "\u0627\u0644\u0645\u0642\u0637\u0639"
                    ),
                    noisy,
                ),
                "expected_status": (
                    "success"
                ),
                "required_groups": [
                    [
                        item["text"]
                    ]
                ],
                "expected_page": (
                    item["page"]
                ),
            }
        )

        test_number += 1

    # ========================================================
    # 22-28: Formatting tolerance
    # ========================================================

    for index in range(7):

        item = anchors[
            index
            % len(anchors)
        ]

        noisy = make_format_noise(
            item["text"]
        )

        tests.append(
            {
                "test": test_number,
                "category": (
                    "Formatting tolerance"
                ),
                "endpoint": "/ask",
                "question": quote_question(
                    (
                        "\u062d\u0633\u0628 "
                        "\u0627\u0644\u0648\u062b\u064a\u0642\u0629\u060c "
                        "\u0627\u0639\u062b\u0631 "
                        "\u0639\u0644\u0649 "
                        "\u0627\u0644\u0645\u0642\u0637\u0639 "
                        "\u062d\u062a\u0649 "
                        "\u0625\u0646 "
                        "\u062a\u063a\u064a\u0631 "
                        "\u0627\u0644\u062a\u0646\u0633\u064a\u0642 "
                        "\u0623\u0648 "
                        "\u0639\u0644\u0627\u0645\u0627\u062a "
                        "\u0627\u0644\u062a\u0631\u0642\u064a\u0645"
                    ),
                    noisy,
                ),
                "expected_status": (
                    "success"
                ),
                "required_groups": [
                    [
                        item["text"]
                    ]
                ],
                "expected_page": (
                    item["page"]
                ),
            }
        )

        test_number += 1

    # ========================================================
    # 29: Full lesson summary
    # ========================================================

    summary_items = evenly_select(
        candidates,
        3,
    )

    tests.append(
        {
            "test": 29,
            "category": (
                "Summary coverage"
            ),
            "endpoint": "/summarize",
            "question": (
                "\u0644\u062e\u0635 "
                "\u0645\u062d\u062a\u0648\u0649 "
                "\u0647\u0630\u0627 "
                "\u0627\u0644\u062f\u0631\u0633 "
                "\u0645\u0639 "
                "\u0627\u0644\u062d\u0641\u0627\u0638 "
                "\u0639\u0644\u0649 "
                "\u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0627\u062a "
                "\u0627\u0644\u0631\u064a\u0627\u0636\u064a\u0629 "
                "\u0627\u0644\u0645\u0647\u0645\u0629."
            ),
            "expected_status": (
                "success"
            ),
            "required_groups": [
                [
                    item["text"]
                ]
                for item
                in summary_items
            ],
        }
    )

    # ========================================================
    # 30: Out-of-scope refusal
    # ========================================================

    tests.append(
        {
            "test": 30,
            "category": (
                "Out of scope refusal"
            ),
            "endpoint": "/ask",
            "question": (
                "\u062d\u0633\u0628 "
                "\u0647\u0630\u0627 "
                "\u0627\u0644\u062f\u0631\u0633\u060c "
                "\u0645\u0627 "
                "\u0623\u0633\u0628\u0627\u0628 "
                "\u0627\u0644\u062d\u0631\u0628 "
                "\u0627\u0644\u0639\u0627\u0644\u0645\u064a\u0629 "
                "\u0627\u0644\u0623\u0648\u0644\u0649\u061f"
            ),
            "expected_status": (
                "insufficient_context"
            ),
            "required_groups": [],
        }
    )


    # ========================================================
    # SVT ARABE SOURCE-SPECIFIC PARTIAL TEST FIXES
    # ========================================================
    #
    # Some extracted Arabic worksheet lines contain repeated
    # prefixes or enumeration markers split onto their own
    # lines. Keep partial-evidence tests unambiguous and focused
    # on substantive document content.
    # ========================================================

    for test_case in tests:

        if (
            test_case.get("test") == 13
            and test_case.get("question")
            == (
                "\u0627\u0639\u062b\u0631 "
                "\u0639\u0644\u0649 "
                "\u0627\u0644\u0645\u0642\u0637\u0639 "
                "\u0627\u0644\u0643\u0627\u0645\u0644 "
                "\u0627\u0644\u0645\u0648\u0627\u0641\u0642 "
                "\u0644\u0647\u0630\u0627 "
                "\u0627\u0644\u062c\u0632\u0621 "
                "\u00ab"
                "\u0623\u062d\u0633\u0628 "
                "\u0627\u0644\u0642\u062f\u0631\u0629 "
                "\u0627\u0644\u0643\u0647\u0631\u0628\u0627\u0626\u064a\u0629 "
                "\u0627\u0644\u0645\u0633\u062a\u0647\u0644\u0643\u0629 "
                "\u0645\u0646 \u0637\u0631\u0641"
                "\u00bb."
            )
            and test_case.get(
                "required_groups"
            )
            == [[
                "2 - "
                "\u0623\u062d\u0633\u0628 "
                "\u0627\u0644\u0642\u062f\u0631\u0629 "
                "\u0627\u0644\u0643\u0647\u0631\u0628\u0627\u0626\u064a\u0629 "
                "\u0627\u0644\u0645\u0633\u062a\u0647\u0644\u0643\u0629 "
                "\u0645\u0646 \u0637\u0631\u0641 "
                "\u062c\u0647\u0627\u0632 "
                "\u0627\u0644\u062a\u0633\u062e\u064a\u0646\u061f"
            ]]
        ):

            test_case[
                "question"
            ] = (
                "\u0627\u0639\u062b\u0631 "
                "\u0639\u0644\u0649 "
                "\u0627\u0644\u0645\u0642\u0637\u0639 "
                "\u0627\u0644\u0643\u0627\u0645\u0644 "
                "\u0627\u0644\u0645\u0648\u0627\u0641\u0642 "
                "\u0644\u0647\u0630\u0627 "
                "\u0627\u0644\u062c\u0632\u0621 "
                "\u00ab"
                "\u0623\u062d\u0633\u0628 "
                "\u0627\u0644\u0642\u062f\u0631\u0629 "
                "\u0627\u0644\u0643\u0647\u0631\u0628\u0627\u0626\u064a\u0629 "
                "\u0627\u0644\u0645\u0633\u062a\u0647\u0644\u0643\u0629 "
                "\u0645\u0646 \u0637\u0631\u0641 "
                "\u062c\u0647\u0627\u0632 "
                "\u0627\u0644\u062a\u0633\u062e\u064a\u0646"
                "\u00bb."
            )


        if (
            test_case.get("test") == 11
            and test_case.get(
                "required_groups"
            )
            == [[
                "\u0628- "
                "\u062d\u062f\u062f "
                "\u0645\u0645\u064a\u0632\u0627\u062a "
                "\u0627\u0644\u0642\u0648\u0649 "
                "\u0627\u0644\u0645\u0637\u0628\u0642\u0629 "
                "\u0639\u0644\u0649 "
                "\u0627\u0644\u062c\u0633\u0645 (S)"
            ]]
        ):

            test_case[
                "required_groups"
            ] = [[
                (
                    "\u0628- "
                    "\u062d\u062f\u062f "
                    "\u0645\u0645\u064a\u0632\u0627\u062a "
                    "\u0627\u0644\u0642\u0648\u0649 "
                    "\u0627\u0644\u0645\u0637\u0628\u0642\u0629 "
                    "\u0639\u0644\u0649 "
                    "\u0627\u0644\u062c\u0633\u0645 (S)"
                ),
                (
                    "\u062d\u062f\u062f "
                    "\u0645\u0645\u064a\u0632\u0627\u062a "
                    "\u0627\u0644\u0642\u0648\u0649 "
                    "\u0627\u0644\u0645\u0637\u0628\u0642\u0629 "
                    "\u0639\u0644\u0649 "
                    "\u0627\u0644\u062c\u0633\u0645 (S)"
                ),
            ]]

    if len(tests) != 30:
        raise RuntimeError(
            f"PDF {pdf_index}: "
            f"{len(tests)} TESTS"
        )

    ocr_sidecar = (
        pdf_path.with_suffix(
            ".ocr.txt"
        )
    )

    documents.append(
        {
            "index": pdf_index,
            "source": pdf_path.name,
            "semester": semester,
            "ocr": (
                ocr_sidecar.exists()
            ),
            "tests": tests,
        }
    )

    inventory.append(
        {
            "index": pdf_index,
            "source": pdf_path.name,
            "semester": semester,
            "ocr": (
                ocr_sidecar.exists()
            ),
            "chunks": len(
                records
            ),
            "strong_candidates": (
                len(candidates)
            ),
        }
    )

    print(
        f"PDF {pdf_index:02d}/12 | "
        f"{semester} | "
        f"ocr={ocr_sidecar.exists()} | "
        f"chunks={len(records)} | "
        f"candidates={len(candidates)} | "
        f"{pdf_path.name}"
    )



# SVT_ARABE_FINAL_QUALITY_OVERRIDES
#
# These replacements remove three known non-learning candidates:
# - an exercise instruction,
# - corrupted OCR text,
# - document navigation/reference noise.
#
# They keep the regression specification deterministic and
# reproducible after rebuilding.

def apply_svt_arabe_quality_overrides(
    documents,
):

    def find_document(
        source,
    ):

        for document in documents:

            if (
                document.get(
                    "source"
                )
                == source
            ):
                return document

        raise RuntimeError(
            "SVT quality override source not found: "
            + source
        )


    def find_test(
        document,
        number,
    ):

        for test in document.get(
            "tests",
            []
        ):

            try:
                current = int(
                    test.get(
                        "test"
                    )
                )
            except Exception:
                continue

            if current == number:
                return test

        raise RuntimeError(
            "SVT quality override test not found: "
            + str(number)
        )


    def patch(
        document,
        number,
        question,
        expected,
        page,
    ):

        test = find_test(
            document,
            number,
        )

        test[
            "question"
        ] = question

        test[
            "required_groups"
        ] = [
            [
                expected
            ]
        ]

        test[
            "expected_page"
        ] = page


    # --------------------------------------------------------
    # PDF 5: nutrition
    # --------------------------------------------------------

    pdf5 = find_document(
        "altrbia-alghthaiia-aldrs-1.pdf"
    )

    pdf5_full = (
        "\u0633\u0628\u0628 "
        "\u0627\u0644\u0625\u0635\u0627\u0628\u0629 "
        "\u0628\u062f\u0627\u0621 "
        "\u0627\u0644\u062d\u0641\u0631 "
        "\u0647\u0648 "
        "\u0646\u0642\u0635 "
        "\u0641\u064a "
        "\u0627\u0644\u0641\u064a\u062a\u0627\u0645\u064a\u0646 "
        "C."
    )

    pdf5_partial = (
        "\u0627\u0644\u0625\u0635\u0627\u0628\u0629 "
        "\u0628\u062f\u0627\u0621"
        "\u0627\u0644\u062d\u0641\u0631"
    )

    patch(
        pdf5,
        1,
        (
            "\u062d\u0633\u0628 "
            "\u0627\u0644\u0648\u062b\u064a\u0642\u0629\u060c "
            "\u0627\u0646\u0633\u062e "
            "\u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0629 "
            "\u0627\u0644\u0645\u0631\u062a\u0628\u0637\u0629 "
            "\u0628\u0627\u0644\u0645\u0642\u0637\u0639 "
            "\u00ab"
            + pdf5_full
            + "\u00bb."
        ),
        pdf5_full,
        3,
    )

    patch(
        pdf5,
        10,
        (
            "\u0627\u0639\u062b\u0631 "
            "\u0639\u0644\u0649 "
            "\u0627\u0644\u0645\u0642\u0637\u0639 "
            "\u0627\u0644\u0643\u0627\u0645\u0644 "
            "\u0627\u0644\u0645\u0648\u0627\u0641\u0642 "
            "\u0644\u0647\u0630\u0627 "
            "\u0627\u0644\u062c\u0632\u0621 "
            "\u00ab"
            + pdf5_partial
            + "\u00bb."
        ),
        pdf5_full,
        3,
    )

    patch(
        pdf5,
        22,
        (
            "\u062d\u0633\u0628 "
            "\u0627\u0644\u0648\u062b\u064a\u0642\u0629\u060c "
            "\u0627\u0639\u062b\u0631 "
            "\u0639\u0644\u0649 "
            "\u0627\u0644\u0645\u0642\u0637\u0639 "
            "\u062d\u062a\u0649 "
            "\u0625\u0646 "
            "\u062a\u063a\u064a\u0631 "
            "\u0627\u0644\u062a\u0646\u0633\u064a\u0642 "
            "\u0623\u0648 "
            "\u0639\u0644\u0627\u0645\u0627\u062a "
            "\u0627\u0644\u062a\u0631\u0642\u064a\u0645 "
            "\u00ab"
            + pdf5_full.rstrip(".")
            + "\u00bb."
        ),
        pdf5_full,
        3,
    )


    # --------------------------------------------------------
    # PDF 7: muscular system
    # --------------------------------------------------------

    pdf7 = find_document(
        "aljhaz-aladhli-aldrs-1.pdf"
    )

    pdf7_full_a = (
        "\u062a\u062b\u0628\u062a "
        "\u0627\u0644\u0639\u0636\u0644\u0627\u062a "
        "\u0639\u0644\u0649 "
        "\u0627\u0644\u0639\u0638\u0627\u0645 "
        "\u0628\u0648\u0627\u0633\u0637\u0629 "
        "\u0627\u0644\u0623\u0648\u062a\u0627\u0631"
    )

    pdf7_full_b = (
        "\u062a\u0631\u062a\u0628\u0637 "
        "\u0627\u0644\u0639\u0638\u0627\u0645 "
        "\u0641\u064a\u0645\u0627 "
        "\u0628\u064a\u0646\u0647\u0627 "
        "\u0628\u0648\u0627\u0633\u0637\u0629 "
        "\u0631\u0627\u0628\u0637\u0627\u062a "
        "\u0627\u0644\u0639\u0638\u0627\u0645"
    )

    pdf7_partial_b = (
        "\u0627\u0644\u0639\u0638\u0627\u0645 "
        "\u0641\u064a\u0645\u0627 "
        "\u0628\u064a\u0646\u0647\u0627 "
        "\u0628\u0648\u0627\u0633\u0637\u0629"
    )

    patch(
        pdf7,
        7,
        (
            "\u062d\u0633\u0628 "
            "\u0627\u0644\u0648\u062b\u064a\u0642\u0629\u060c "
            "\u0627\u0646\u0633\u062e "
            "\u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0629 "
            "\u0627\u0644\u0645\u0631\u062a\u0628\u0637\u0629 "
            "\u0628\u0627\u0644\u0645\u0642\u0637\u0639 "
            "\u00ab"
            + pdf7_full_a
            + "\u00bb."
        ),
        pdf7_full_a,
        1,
    )

    patch(
        pdf7,
        11,
        (
            "\u0627\u0639\u062b\u0631 "
            "\u0639\u0644\u0649 "
            "\u0627\u0644\u0645\u0642\u0637\u0639 "
            "\u0627\u0644\u0643\u0627\u0645\u0644 "
            "\u0627\u0644\u0645\u0648\u0627\u0641\u0642 "
            "\u0644\u0647\u0630\u0627 "
            "\u0627\u0644\u062c\u0632\u0621 "
            "\u00ab"
            + pdf7_partial_b
            + "\u00bb."
        ),
        pdf7_full_b,
        1,
    )

    patch(
        pdf7,
        28,
        (
            "\u062d\u0633\u0628 "
            "\u0627\u0644\u0648\u062b\u064a\u0642\u0629\u060c "
            "\u0627\u0639\u062b\u0631 "
            "\u0639\u0644\u0649 "
            "\u0627\u0644\u0645\u0642\u0637\u0639 "
            "\u062d\u062a\u0649 "
            "\u0625\u0646 "
            "\u062a\u063a\u064a\u0631 "
            "\u0627\u0644\u062a\u0646\u0633\u064a\u0642 "
            "\u0623\u0648 "
            "\u0639\u0644\u0627\u0645\u0627\u062a "
            "\u0627\u0644\u062a\u0631\u0642\u064a\u0645 "
            "\u00ab"
            + pdf7_full_a
            + "\u00bb."
        ),
        pdf7_full_a,
        1,
    )


    return documents


documents = apply_svt_arabe_quality_overrides(
    documents
)


spec = {
    "program": PROGRAM,
    "subject": SUBJECT,
    "pdf_count": 12,
    "tests_per_pdf": 30,
    "total_tests": 360,
    "documents": documents,
}


OUT_SPECS.write_text(
    json.dumps(
        spec,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


OUT_JSON.write_text(
    json.dumps(
        inventory,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


with OUT_CSV.open(
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "index",
            "source",
            "semester",
            "ocr",
            "chunks",
            "strong_candidates",
        ],
    )

    writer.writeheader()
    writer.writerows(
        inventory
    )


print()
print("=" * 100)
print("SVT ARABE SPECS CREATED")
print("=" * 100)

print("PDFS: 12")
print("TESTS: 360")
print(
    "OCR PDFS:",
    sum(
        1
        for item in inventory
        if item["ocr"]
    )
)

print(
    "MIN STRONG CANDIDATES:",
    min(
        item[
            "strong_candidates"
        ]
        for item in inventory
    )
)
