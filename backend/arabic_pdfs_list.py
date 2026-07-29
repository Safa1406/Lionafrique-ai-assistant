import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from services.vector_store_service import (
    get_document_collection,
)


PROGRAM = "Programme marocain"
SUBJECT = "Arabe"

JSON_REPORT = Path(
    "arabic_pdfs_inventory.json"
)

CSV_REPORT = Path(
    "arabic_pdfs_inventory.csv"
)


def configure_console() -> None:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8"
        )
    except AttributeError:
        pass


def main() -> None:
    configure_console()

    collection = get_document_collection()

    results = collection.get(
        where={
            "$and": [
                {
                    "program": {
                        "$eq": PROGRAM
                    }
                },
                {
                    "subject": {
                        "$eq": SUBJECT
                    }
                },
            ]
        },
        include=[
            "metadatas",
            "documents",
        ],
    )

    metadatas = (
        results.get("metadatas")
        or []
    )

    documents = (
        results.get("documents")
        or []
    )

    grouped = defaultdict(
        lambda: {
            "source": "",
            "relative_paths": set(),
            "document_ids": set(),
            "semesters": set(),
            "pages": set(),
            "chunk_count": 0,
            "character_count": 0,
        }
    )

    for metadata, document in zip(
        metadatas,
        documents,
    ):
        metadata = metadata or {}

        source = metadata.get(
            "source",
            "Source inconnue",
        )

        item = grouped[source]

        item["source"] = source
        item["chunk_count"] += 1
        item["character_count"] += len(
            document or ""
        )

        relative_path = metadata.get(
            "relative_path",
            "",
        )

        if relative_path:
            item["relative_paths"].add(
                relative_path
            )

        document_id = metadata.get(
            "document_id",
            "",
        )

        if document_id:
            item["document_ids"].add(
                document_id
            )

        semester = metadata.get(
            "semester",
            "Non défini",
        )

        item["semesters"].add(
            semester
        )

        page = metadata.get(
            "page",
            0,
        )

        try:
            page_number = int(page)
        except (
            TypeError,
            ValueError,
        ):
            page_number = 0

        if page_number > 0:
            item["pages"].add(
                page_number
            )

    inventory = []

    for source, item in grouped.items():
        pages = sorted(
            item["pages"]
        )

        inventory.append(
            {
                "source": source,
                "semesters": sorted(
                    item["semesters"]
                ),
                "page_count": len(pages),
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
                    item["chunk_count"]
                ),
                "character_count": (
                    item[
                        "character_count"
                    ]
                ),
                "relative_paths": sorted(
                    item["relative_paths"]
                ),
                "document_ids": sorted(
                    item["document_ids"]
                ),
            }
        )

    inventory.sort(
        key=lambda item: (
            item["source"].lower()
        )
    )

    report = {
        "program": PROGRAM,
        "subject": SUBJECT,
        "total_pdf_files": len(
            inventory
        ),
        "total_chunks": sum(
            item["chunk_count"]
            for item in inventory
        ),
        "files": inventory,
    }

    JSON_REPORT.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with CSV_REPORT.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        fieldnames = [
            "number",
            "source",
            "semesters",
            "page_count",
            "first_page",
            "last_page",
            "chunk_count",
            "character_count",
            "relative_paths",
        ]

        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for index, item in enumerate(
            inventory,
            start=1,
        ):
            writer.writerow(
                {
                    "number": index,
                    "source": (
                        item["source"]
                    ),
                    "semesters": ", ".join(
                        item[
                            "semesters"
                        ]
                    ),
                    "page_count": (
                        item[
                            "page_count"
                        ]
                    ),
                    "first_page": (
                        item[
                            "first_page"
                        ]
                    ),
                    "last_page": (
                        item[
                            "last_page"
                        ]
                    ),
                    "chunk_count": (
                        item[
                            "chunk_count"
                        ]
                    ),
                    "character_count": (
                        item[
                            "character_count"
                        ]
                    ),
                    "relative_paths": (
                        " ; ".join(
                            item[
                                "relative_paths"
                            ]
                        )
                    ),
                }
            )

    print("=" * 96)
    print(
        "جرد جميع ملفات PDF "
        "الخاصة بمادة العربية"
    )
    print("=" * 96)

    print(
        "البرنامج:",
        PROGRAM,
    )
    print(
        "المادة:",
        SUBJECT,
    )
    print(
        "عدد الملفات:",
        len(inventory),
    )
    print(
        "عدد المقاطع:",
        report["total_chunks"],
    )

    if not inventory:
        print()
        print(
            "لم يتم العثور على أي ملف "
            "مسجل تحت مادة Arabe."
        )
        return

    for index, item in enumerate(
        inventory,
        start=1,
    ):
        print()
        print("-" * 96)
        print(
            f"[{index}] "
            f"{item['source']}"
        )
        print(
            "السداسي:",
            ", ".join(
                item["semesters"]
            ),
        )
        print(
            "عدد الصفحات:",
            item["page_count"],
        )
        print(
            "الصفحات:",
            (
                f"{item['first_page']}"
                f" إلى "
                f"{item['last_page']}"
                if item[
                    "page_count"
                ]
                else "غير محددة"
            ),
        )
        print(
            "عدد المقاطع:",
            item["chunk_count"],
        )

        if item["relative_paths"]:
            print(
                "المسار:",
                item[
                    "relative_paths"
                ][0],
            )

    print()
    print("=" * 96)
    print("تم حفظ التقريرين")
    print("=" * 96)
    print(
        JSON_REPORT.resolve()
    )
    print(
        CSV_REPORT.resolve()
    )


if __name__ == "__main__":
    main()