import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader


BACKEND = Path(__file__).resolve().parent

DATA_ROOT = (
    BACKEND.parent
    / "data"
    / "raw"
)

MATH_ROOT = (
    DATA_ROOT
    / "Programme Marocain"
    / "Math"
)

HISTORY_SPECS = (
    BACKEND
    / "mega_histoire_geographique_specs.json"
)

OUT_SPECS = (
    BACKEND
    / "mega_math_specs.json"
)

OUT_JSON = (
    BACKEND
    / "math_inventory.json"
)

OUT_CSV = (
    BACKEND
    / "math_inventory.csv"
)


def clean_text(value):
    return re.sub(
        r"\s+",
        " ",
        (value or "").replace(
            "\u00a0",
            " ",
        ),
    ).strip()


def normalize_key(value):
    value = unicodedata.normalize(
        "NFKD",
        (value or "").casefold(),
    )

    value = "".join(
        c
        for c in value
        if not unicodedata.combining(c)
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def sha256_file(path):
    digest = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            block = f.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def extract_pages(path):
    reader = PdfReader(
        str(path)
    )

    pages = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        pages.append(
            {
                "page": page_number,
                "text": (
                    page.extract_text()
                    or ""
                ),
            }
        )

    return pages


def is_good_candidate(line):
    line = clean_text(line)

    if not (
        20
        <= len(line)
        <= 240
    ):
        return False

    lower = line.casefold()

    if lower.startswith(
        (
            "math\u00e9matiques",
            "s\u00e9ance ",
            "professeur",
        )
    ):
        return False

    if lower in {
        "sommaire",
        "exemple",
        "exemples",
        "exercice",
        "exercices",
        "solution",
        "solutions",
        "application",
        "remarque",
        "remarque importante",
        "d\u00e9finition",
        "propri\u00e9t\u00e9",
        "propri\u00e9t\u00e9s",
    }:
        return False

    # Section / exercise labels.
    if re.match(
        r"^(?:[ivx]+|\d+(?:-\d+)*)\s*[-/.]",
        lower,
    ):
        return False

    words = re.findall(
        r"[A-Za-z\u00c0-\u024f0-9]+",
        line,
    )

    if len(words) < 5:
        return False

    # Obvious broken fragments.
    weak_start = (
        "sont ",
        "est ",
        "sous ",
    )

    if lower.startswith(
        weak_start
    ):
        return False

    weak_end = {
        "le",
        "la",
        "les",
        "de",
        "des",
        "du",
        "un",
        "une",
        "deux",
        "et",
        "ou",
        "que",
    }

    if (
        words
        and words[-1].casefold()
        in weak_end
    ):
        return False

    # A colon usually indicates that the formula
    # which follows is an image and was not extracted.
    if lower.endswith(":"):
        return False

    return True


def build_candidates(pages):
    candidates = []
    seen = set()

    for page in pages:

        for raw_line in (
            page["text"]
            or ""
        ).splitlines():

            line = clean_text(
                raw_line
            )

            if not is_good_candidate(
                line
            ):
                continue

            key = normalize_key(
                line
            )

            if key in seen:
                continue

            seen.add(key)

            candidates.append(
                {
                    "page": page["page"],
                    "text": line,
                }
            )

    return candidates


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


def make_partial(text):
    words = text.split()

    if len(words) <= 6:
        return text

    size = max(
        5,
        round(
            len(words) * 0.65
        ),
    )

    start = max(
        0,
        (len(words) - size) // 2,
    )

    return " ".join(
        words[
            start:
            start + size
        ]
    )


def make_typo(text):
    words = re.findall(
        r"[A-Za-z\u00c0-\u024f]{5,}",
        text,
    )

    if not words:
        return text

    word = max(
        words,
        key=len,
    )

    if len(word) < 5:
        return text

    position = max(
        2,
        len(word) // 2,
    )

    typo = (
        word[:position]
        + word[position + 1:]
    )

    return text.replace(
        word,
        typo,
        1,
    )


def remove_accents_and_punctuation(
    text,
):
    value = unicodedata.normalize(
        "NFKD",
        text,
    )

    value = "".join(
        c
        for c in value
        if not unicodedata.combining(c)
    )

    value = re.sub(
        r"[,:;.!?()]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def make_question(
    prefix,
    anchor,
):
    return (
        prefix
        + " \u00ab"
        + anchor
        + "\u00bb."
    )


history = json.loads(
    HISTORY_SPECS.read_text(
        encoding="utf-8"
    )
)

sample = (
    history["documents"][0]["tests"]
)

answer_endpoint = (
    sample[0]["endpoint"]
)

summary_endpoint = (
    sample[28]["endpoint"]
)

oos_endpoint = (
    sample[29]["endpoint"]
)


pdfs = []

for semester in [
    "S1",
    "S2",
]:
    pdfs.extend(
        sorted(
            (
                MATH_ROOT
                / semester
            ).glob("*.pdf")
        )
    )


if len(pdfs) != 17:
    raise SystemExit(
        "EXPECTED 17 PDFS, FOUND "
        + str(len(pdfs))
    )


documents = []
inventory = []


for pdf_index, path in enumerate(
    pdfs,
    start=1,
):
    pages = extract_pages(
        path
    )

    candidates = build_candidates(
        pages
    )

    if len(candidates) < 3:
        raise SystemExit(
            f"PDF {pdf_index}: "
            f"ONLY {len(candidates)} "
            "GOOD TEXTUAL CANDIDATES"
        )

    # Up to nine different factual anchors.
    anchors = evenly_select(
        candidates,
        9,
    )

    tests = []
    test_number = 1

    # ==================================================
    # TESTS 1-9
    # Exact evidence with varied wording.
    # ==================================================

    exact_templates = [
        (
            "Selon le document, "
            "recopie exactement "
            "le passage"
        ),
        (
            "Retrouve dans le document "
            "l'information suivante"
        ),
        (
            "Quelle information du "
            "document correspond au passage"
        ),
    ]

    for index in range(9):

        item = anchors[
            index
            % len(anchors)
        ]

        template = exact_templates[
            index
            % len(exact_templates)
        ]

        tests.append(
            {
                "test": test_number,
                "category": (
                    "Document evidence"
                ),
                "endpoint": (
                    answer_endpoint
                ),
                "question": make_question(
                    template,
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

    # ==================================================
    # TESTS 10-15
    # Partial quote retrieval.
    # ==================================================

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
                "endpoint": (
                    answer_endpoint
                ),
                "question": make_question(
                    (
                        "Retrouve le passage "
                        "complet correspondant "
                        "\u00e0 cet extrait"
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

    # ==================================================
    # TESTS 16-21
    # Typo tolerance.
    # ==================================================

    for index in range(6):

        item = anchors[
            index
            % len(anchors)
        ]

        typo = make_typo(
            item["text"]
        )

        tests.append(
            {
                "test": test_number,
                "category": (
                    "Spelling tolerance"
                ),
                "endpoint": (
                    answer_endpoint
                ),
                "question": make_question(
                    (
                        "Retrouve l'information "
                        "malgr\u00e9 la faute "
                        "dans cet extrait"
                    ),
                    typo,
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

    # ==================================================
    # TESTS 22-28
    # Accent / punctuation / formatting tolerance.
    # ==================================================

    for index in range(7):

        item = anchors[
            index
            % len(anchors)
        ]

        noisy = (
            remove_accents_and_punctuation(
                item["text"]
            )
        )

        tests.append(
            {
                "test": test_number,
                "category": (
                    "Formatting tolerance"
                ),
                "endpoint": (
                    answer_endpoint
                ),
                "question": make_question(
                    (
                        "Selon le document, "
                        "retrouve le passage "
                        "m\u00eame si les accents "
                        "ou la ponctuation ont chang\u00e9"
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

    # ==================================================
    # TEST 29
    # Summary coverage.
    # ==================================================

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
            "endpoint": (
                summary_endpoint
            ),
            "question": (
                "R\u00e9sume le contenu "
                "de cette le\u00e7on en "
                "conservant les informations "
                "math\u00e9matiques importantes."
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

    # ==================================================
    # TEST 30
    # Out-of-scope refusal.
    # ==================================================

    tests.append(
        {
            "test": 30,
            "category": (
                "Out of scope refusal"
            ),
            "endpoint": (
                oos_endpoint
            ),
            "question": (
                "Selon cette le\u00e7on, "
                "explique les causes de "
                "la Premi\u00e8re Guerre mondiale."
            ),
            "expected_status": (
                "insufficient_context"
            ),
            "required_groups": [],
        }
    )

    if len(tests) != 30:
        raise RuntimeError(
            f"PDF {pdf_index}: "
            f"{len(tests)} TESTS"
        )

    documents.append(
        {
            "index": pdf_index,
            "source": path.name,
            "semester": (
                path.parent.name
            ),
            "tests": tests,
        }
    )

    inventory.append(
        {
            "index": pdf_index,
            "source": path.name,
            "semester": (
                path.parent.name
            ),
            "pages": len(pages),
            "text_pages": sum(
                bool(
                    clean_text(
                        p["text"]
                    )
                )
                for p in pages
            ),
            "strong_candidates": (
                len(candidates)
            ),
            "sha256": sha256_file(
                path
            ),
        }
    )

    print(
        f"PDF {pdf_index:02d}: "
        f"{path.name} | "
        f"candidates={len(candidates)} | "
        "tests=30"
    )


spec = {
    "program": (
        "Programme marocain"
    ),
    "subject": (
        "Math\u00e9matiques"
    ),
    "pdf_count": 17,
    "tests_per_pdf": 30,
    "total_tests": 510,
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
            "pages",
            "text_pages",
            "strong_candidates",
            "sha256",
        ],
    )

    writer.writeheader()
    writer.writerows(
        inventory
    )


print()
print("=" * 100)
print("MATH SPECS V4 CREATED")
print("=" * 100)

print("PDFS: 17")
print("TESTS: 510")
print(
    "MIN STRONG CANDIDATES:",
    min(
        item["strong_candidates"]
        for item in inventory
    )
)
