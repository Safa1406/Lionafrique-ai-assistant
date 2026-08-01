import sys
from pathlib import Path

import chromadb


BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parent
)

CHROMA_PATH = (
    BACKEND_ROOT
    / "chroma_db"
)

COLLECTION_NAME = (
    "lionafrique_documents"
)

PROGRAM = "Programme marocain"
SUBJECT = "Arabe"


def configure_console() -> None:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8"
        )
    except AttributeError:
        pass


def safe_integer(value) -> int:
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0


def main() -> None:
    configure_console()

    if len(sys.argv) < 2:
        print(
            "الاستعمال:"
        )
        print(
            "python inspect_pdf_light.py "
            "اسم-الملف.pdf"
        )
        raise SystemExit(1)

    source_name = " ".join(
        sys.argv[1:]
    ).strip()

    client = chromadb.PersistentClient(
        path=str(
            CHROMA_PATH
        )
    )

    collection = (
        client.get_or_create_collection(
            name=COLLECTION_NAME
        )
    )

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
                {
                    "source": {
                        "$eq": source_name
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

    chunks = []

    for index, (
        metadata,
        document,
    ) in enumerate(
        zip(
            metadatas,
            documents,
        ),
        start=1,
    ):
        metadata = metadata or {}

        chunks.append(
            {
                "original_index": index,
                "page": safe_integer(
                    metadata.get(
                        "page",
                        0,
                    )
                ),
                "chunk_number": (
                    safe_integer(
                        metadata.get(
                            "chunk_number",
                            index,
                        )
                    )
                ),
                "semester": metadata.get(
                    "semester",
                    "Non défini",
                ),
                "relative_path": (
                    metadata.get(
                        "relative_path",
                        "",
                    )
                ),
                "text": (
                    document
                    or ""
                ).strip(),
            }
        )

    chunks.sort(
        key=lambda item: (
            item["page"],
            item["chunk_number"],
            item["original_index"],
        )
    )

    print("=" * 100)
    print(
        "فحص محتوى PDF عربي"
    )
    print("=" * 100)
    print(
        "الملف:",
        source_name,
    )
    print(
        "عدد المقاطع:",
        len(chunks),
    )

    if not chunks:
        print()
        print(
            "لم يتم العثور على الملف "
            "داخل ChromaDB."
        )
        raise SystemExit(2)

    print(
        "السداسي:",
        chunks[0]["semester"],
    )

    if chunks[0]["relative_path"]:
        print(
            "المسار:",
            chunks[0][
                "relative_path"
            ],
        )

    output_lines = [
        "=" * 100,
        "فحص محتوى PDF عربي",
        "=" * 100,
        f"الملف: {source_name}",
        (
            "عدد المقاطع: "
            f"{len(chunks)}"
        ),
        (
            "السداسي: "
            f"{chunks[0]['semester']}"
        ),
        "",
    ]

    for number, chunk in enumerate(
        chunks,
        start=1,
    ):
        separator = "-" * 100

        header = (
            f"[{number}/{len(chunks)}] "
            f"الصفحة {chunk['page']} "
            f"| المقطع "
            f"{chunk['chunk_number']}"
        )

        print()
        print(separator)
        print(header)
        print(separator)
        print(
            chunk["text"]
            or "[مقطع فارغ]"
        )

        output_lines.extend(
            [
                separator,
                header,
                separator,
                (
                    chunk["text"]
                    or "[مقطع فارغ]"
                ),
                "",
            ]
        )

    safe_stem = (
        Path(source_name)
        .stem
        .replace(
            " ",
            "_",
        )
    )

    report_path = Path(
        f"inspection_{safe_stem}.txt"
    )

    report_path.write_text(
        "\n".join(
            output_lines
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 100)
    print(
        "تم حفظ التقرير:"
    )
    print(
        report_path.resolve()
    )


if __name__ == "__main__":
    main()
