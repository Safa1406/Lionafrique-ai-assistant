from collections import defaultdict
from pathlib import Path
import csv
import json
import re
import unicodedata

from services.retrieval_service import (
    search_similar_chunks,
)


PROGRAM = "Programme marocain"
SUBJECT = "Physique-Chimie"

OUT_JSON = Path(
    "pc_inventory.json"
)

OUT_CSV = Path(
    "pc_inventory.csv"
)


def clean_text(text):
    text = unicodedata.normalize(
        "NFKC",
        text or "",
    )

    text = text.replace(
        "\u00a0",
        " ",
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def candidate_lines(text):
    text = clean_text(
        text
    )

    raw_lines = []

    for line in text.splitlines():
        line = re.sub(
            r"\s+",
            " ",
            line,
        ).strip()

        if line:
            raw_lines.append(
                line
            )

    candidates = []

    seen = set()

    for line in raw_lines:

        # Avoid tiny headings, page numbers and giant paragraphs.
        if len(line) < 35:
            continue

        if len(line) > 280:
            continue

        words = re.findall(
            r"[A-Za-zÀ-ÿ0-9]+",
            line,
        )

        if len(words) < 6:
            continue

        normalized = re.sub(
            r"\W+",
            " ",
            line.lower(),
            flags=re.UNICODE,
        ).strip()

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        candidates.append(
            line
        )

    return candidates


collection = (
    search_similar_chunks
    .__globals__[
        "get_document_collection"
    ]()
)

data = collection.get(
    include=[
        "documents",
        "metadatas",
    ]
)

documents = data.get(
    "documents",
    []
)

metadatas = data.get(
    "metadatas",
    []
)

groups = defaultdict(
    list
)

for document, metadata in zip(
    documents,
    metadatas,
):

    if not metadata:
        continue

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

    source = metadata.get(
        "source"
    )

    if not source:
        continue

    groups[source].append(
        {
            "text": clean_text(
                document
            ),
            "page": metadata.get(
                "page"
            ),
            "semester": metadata.get(
                "semester"
            ),
            "relative_path": metadata.get(
                "relative_path"
            ),
        }
    )


inventory = []

for source in sorted(
    groups
):

    chunks = groups[
        source
    ]

    semester = next(
        (
            chunk.get(
                "semester"
            )
            for chunk in chunks
            if chunk.get(
                "semester"
            )
        ),
        "",
    )

    relative_path = next(
        (
            chunk.get(
                "relative_path"
            )
            for chunk in chunks
            if chunk.get(
                "relative_path"
            )
        ),
        "",
    )

    all_candidates = []

    seen_candidates = set()

    for chunk in chunks:

        for candidate in candidate_lines(
            chunk["text"]
        ):

            key = candidate.lower()

            if key in seen_candidates:
                continue

            seen_candidates.add(
                key
            )

            all_candidates.append(
                candidate
            )

    inventory.append(
        {
            "source": source,
            "semester": semester,
            "relative_path": relative_path,
            "segments": len(
                chunks
            ),
            "candidate_count": len(
                all_candidates
            ),
            "candidates": all_candidates[
                :20
            ],
        }
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
    encoding="utf-8-sig",
    newline="",
) as handle:

    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "source",
            "semester",
            "segments",
            "candidate_count",
            "relative_path",
        ],
    )

    writer.writeheader()

    for item in inventory:

        writer.writerow(
            {
                "source": item[
                    "source"
                ],
                "semester": item[
                    "semester"
                ],
                "segments": item[
                    "segments"
                ],
                "candidate_count": item[
                    "candidate_count"
                ],
                "relative_path": item[
                    "relative_path"
                ],
            }
        )


print(
    "=" * 100
)

print(
    "PHYSIQUE-CHIMIE INVENTORY"
)

print(
    "=" * 100
)

print(
    "DOCUMENTS:",
    len(
        inventory
    )
)

print(
    "TOTAL SEGMENTS:",
    sum(
        item[
            "segments"
        ]
        for item in inventory
    )
)

print()


weak = []

for index, item in enumerate(
    inventory,
    start=1,
):

    print(
        f"[{index:02d}/17] "
        f"{item['semester']} | "
        f"segments={item['segments']} | "
        f"candidates={item['candidate_count']} | "
        f"{item['source']}"
    )

    if (
        item[
            "candidate_count"
        ]
        < 6
    ):
        weak.append(
            item[
                "source"
            ]
        )


print()

print(
    "=" * 100
)

print(
    "QUALITY CHECK"
)

print(
    "=" * 100
)

print(
    "PDFS:",
    len(
        inventory
    )
)

print(
    "PDFS WITH >= 6 CANDIDATES:",
    sum(
        1
        for item in inventory
        if item[
            "candidate_count"
        ]
        >= 6
    )
)

print(
    "WEAK PDFS:",
    len(
        weak
    )
)

if weak:

    print()

    for source in weak:
        print(
            " -",
            source
        )


print()

print(
    "JSON:",
    OUT_JSON.resolve()
)

print(
    "CSV:",
    OUT_CSV.resolve()
)
