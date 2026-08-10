from pathlib import Path
from collections import Counter, defaultdict
import json
import csv

from services.vector_store_service import (
    get_document_collection,
    build_metadata_filter,
)


PROGRAM = "Programme marocain"
SUBJECT = "SVT arabe"

RAW_ROOT = (
    Path("..")
    / "data"
    / "raw"
    / "Programme Marocain"
    / "SVT arabe"
)

EXPECTED_OCR_SIDECARS = 9


def discover_ocr_expected():

    raw_subject = (
        Path(__file__)
        .resolve()
        .parent
        .parent
        / "data"
        / "raw"
        / "Programme Marocain"
        / "SVT arabe"
    )

    expected = set()

    for semester in (
        "S1",
        "S2",
    ):

        folder = (
            raw_subject
            / semester
        )

        for sidecar in sorted(
            folder.glob(
                "*.ocr.txt"
            )
        ):

            base_name = (
                sidecar.name[
                    :-len(
                        ".ocr.txt"
                    )
                ]
            )

            pdf_path = (
                folder
                / (
                    base_name
                    + ".pdf"
                )
            )

            if not pdf_path.exists():

                raise RuntimeError(
                    "OCR sidecar has no matching PDF: "
                    + str(
                        sidecar
                    )
                )

            expected.add(
                (
                    semester,
                    pdf_path.name,
                )
            )

    return expected


OCR_EXPECTED = (
    discover_ocr_expected()
)
JSON_OUT = Path(
    "svt_arabe_inventory.json"
)

CSV_OUT = Path(
    "svt_arabe_inventory.csv"
)


print("=" * 110)
print("SVT ARABE CHROMA AUDIT")
print("=" * 110)


# ------------------------------------------------------------
# RAW corpus
# ------------------------------------------------------------

raw_pairs = set()

for semester in ("S1", "S2"):

    folder = RAW_ROOT / semester

    for pdf in sorted(
        folder.glob("*.pdf")
    ):
        raw_pairs.add(
            (
                semester,
                pdf.name,
            )
        )


print(
    "RAW PDFs:",
    len(raw_pairs)
)

print(
    "RAW S1:",
    sum(
        1
        for semester, _ in raw_pairs
        if semester == "S1"
    )
)

print(
    "RAW S2:",
    sum(
        1
        for semester, _ in raw_pairs
        if semester == "S2"
    )
)


# ------------------------------------------------------------
# Chroma collection
# ------------------------------------------------------------

collection = get_document_collection()

print()
print(
    "TOTAL COLLECTION RECORDS:",
    collection.count()
)

metadata_filter = build_metadata_filter(
    program=PROGRAM,
    subject=SUBJECT,
)

print(
    "FILTER:",
    metadata_filter
)


results = collection.get(
    where=metadata_filter,
    include=[
        "metadatas",
        "documents",
    ],
)


metadatas = (
    results.get(
        "metadatas"
    )
    or []
)

documents = (
    results.get(
        "documents"
    )
    or []
)


print()
print(
    "SVT ARABE SEGMENTS:",
    len(metadatas)
)


if not metadatas:
    raise RuntimeError(
        "No indexed SVT arabe segments found."
    )


# ------------------------------------------------------------
# Aggregate
# ------------------------------------------------------------

records = defaultdict(
    lambda: {
        "semester": "",
        "source": "",
        "pages": set(),
        "chunks": 0,
        "chars": 0,
        "relative_paths": set(),
        "document_ids": set(),
    }
)


semester_segments = Counter()


for metadata, document in zip(
    metadatas,
    documents,
):

    metadata = metadata or {}
    document = document or ""

    semester = str(
        metadata.get(
            "semester",
            ""
        )
        or ""
    ).strip()

    source = str(
        metadata.get(
            "source",
            ""
        )
        or ""
    ).strip()

    if not semester or not source:
        continue

    key = (
        semester,
        source,
    )

    item = records[key]

    item["semester"] = semester
    item["source"] = source
    item["chunks"] += 1
    item["chars"] += len(
        document
    )

    semester_segments[
        semester
    ] += 1

    page = metadata.get(
        "page"
    )

    try:
        page = int(
            page
        )
    except Exception:
        page = 0

    if page > 0:
        item["pages"].add(
            page
        )

    relative_path = str(
        metadata.get(
            "relative_path",
            ""
        )
        or ""
    ).strip()

    if relative_path:
        item[
            "relative_paths"
        ].add(
            relative_path
        )

    document_id = str(
        metadata.get(
            "document_id",
            ""
        )
        or ""
    ).strip()

    if document_id:
        item[
            "document_ids"
        ].add(
            document_id
        )


indexed_pairs = set(
    records.keys()
)


# ------------------------------------------------------------
# Source audit
# ------------------------------------------------------------

print()
print("=" * 110)
print("INDEXED SOURCE AUDIT")
print("=" * 110)

for key in sorted(
    records
):

    item = records[
        key
    ]

    pages = sorted(
        item["pages"]
    )

    print(
        item["semester"],
        "|",
        item["source"],
        "| segments:",
        item["chunks"],
        "| chars:",
        item["chars"],
        "| pages:",
        pages,
    )


# ------------------------------------------------------------
# Compare raw vs Chroma
# ------------------------------------------------------------

missing = sorted(
    raw_pairs
    - indexed_pairs
)

extra = sorted(
    indexed_pairs
    - raw_pairs
)


print()
print("=" * 110)
print("RAW VS CHROMA")
print("=" * 110)

print(
    "RAW SOURCES:",
    len(raw_pairs)
)

print(
    "INDEXED SOURCES:",
    len(indexed_pairs)
)

print(
    "MISSING SOURCES:",
    len(missing)
)

for item in missing:
    print(
        " MISSING:",
        item
    )

print(
    "EXTRA SOURCES:",
    len(extra)
)

for item in extra:
    print(
        " EXTRA:",
        item
    )


# ------------------------------------------------------------
# OCR verification
# ------------------------------------------------------------

print()
print("=" * 110)
print("OCR SOURCE CHECK")
print("=" * 110)

ocr_ok = 0

for key in sorted(
    OCR_EXPECTED
):

    item = records.get(
        key
    )

    if not item:

        print(
            "MISSING:",
            key
        )

        continue

    status = (
        "OK"
        if (
            item["chars"] > 0
            and item["chunks"] > 0
        )
        else "EMPTY"
    )

    print(
        status,
        "|",
        key[0],
        "|",
        key[1],
        "| segments:",
        item["chunks"],
        "| chars:",
        item["chars"],
    )

    if status == "OK":
        ocr_ok += 1


# ------------------------------------------------------------
# Build inventory
# ------------------------------------------------------------

inventory = []

for key in sorted(
    records
):

    item = records[
        key
    ]

    pages = sorted(
        item["pages"]
    )

    inventory.append(
        {
            "semester": (
                item["semester"]
            ),
            "source": (
                item["source"]
            ),
            "page_count": len(
                pages
            ),
            "first_page": (
                pages[0]
                if pages
                else 0
            ),
            "last_page": (
                pages[-1]
                if pages
                else 0
            ),
            "chunk_count": (
                item["chunks"]
            ),
            "character_count": (
                item["chars"]
            ),
            "relative_paths": sorted(
                item["relative_paths"]
            ),
            "document_ids": sorted(
                item["document_ids"]
            ),
        }
    )


JSON_OUT.write_text(
    json.dumps(
        inventory,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


with CSV_OUT.open(
    "w",
    encoding="utf-8-sig",
    newline="",
) as handle:

    writer = csv.writer(
        handle
    )

    writer.writerow(
        [
            "semester",
            "source",
            "page_count",
            "first_page",
            "last_page",
            "chunk_count",
            "character_count",
        ]
    )

    for item in inventory:

        writer.writerow(
            [
                item[
                    "semester"
                ],
                item[
                    "source"
                ],
                item[
                    "page_count"
                ],
                item[
                    "first_page"
                ],
                item[
                    "last_page"
                ],
                item[
                    "chunk_count"
                ],
                item[
                    "character_count"
                ],
            ]
        )


# ------------------------------------------------------------
# Final
# ------------------------------------------------------------

print()
print("=" * 110)
print("FINAL")
print("=" * 110)

print(
    "TOTAL SEGMENTS:",
    len(metadatas)
)

print(
    "S1 SEGMENTS:",
    semester_segments.get(
        "S1",
        0
    )
)

print(
    "S2 SEGMENTS:",
    semester_segments.get(
        "S2",
        0
    )
)

print(
    "S1 SOURCES:",
    sum(
        1
        for semester, _ in indexed_pairs
        if semester == "S1"
    )
)

print(
    "S2 SOURCES:",
    sum(
        1
        for semester, _ in indexed_pairs
        if semester == "S2"
    )
)

print(
    "TOTAL SOURCES:",
    len(indexed_pairs)
)

print(
    "OCR SOURCES WITH TEXT:",
    ocr_ok,
    f"/ {len(OCR_EXPECTED)}"
)

print(
    "MISSING:",
    len(missing)
)

print(
    "EXTRA:",
    len(extra)
)

print(
    "JSON:",
    JSON_OUT
)

print(
    "CSV:",
    CSV_OUT
)


if len(raw_pairs) != 12:
    raise RuntimeError(
        f"Expected 12 raw PDFs, found {len(raw_pairs)}."
    )

if len(indexed_pairs) != 12:
    raise RuntimeError(
        f"Expected 12 indexed sources, found {len(indexed_pairs)}."
    )

if missing:
    raise RuntimeError(
        "Some raw PDFs are missing from Chroma."
    )

if extra:
    raise RuntimeError(
        "Unexpected SVT arabe sources found in Chroma."
    )

if (
    len(OCR_EXPECTED)
    != EXPECTED_OCR_SIDECARS
):
    raise RuntimeError(
        "Expected "
        f"{EXPECTED_OCR_SIDECARS} "
        "OCR sidecars, found "
        f"{len(OCR_EXPECTED)}."
    )


if ocr_ok != len(
    OCR_EXPECTED
):
    raise RuntimeError(
        "Not all OCR sidecar sources "
        "contain indexed text."
    )

if sum(
    1
    for semester, _ in indexed_pairs
    if semester == "S1"
) != 5:
    raise RuntimeError(
        "Expected 5 S1 sources."
    )

if sum(
    1
    for semester, _ in indexed_pairs
    if semester == "S2"
) != 7:
    raise RuntimeError(
        "Expected 7 S2 sources."
    )


print()
print(
    "SVT ARABE CHROMA AUDIT: PASS"
)
