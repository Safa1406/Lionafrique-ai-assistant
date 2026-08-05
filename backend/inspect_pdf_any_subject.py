import argparse
import sys
from pathlib import Path

import chromadb


BACKEND_ROOT = Path(__file__).resolve().parent
CHROMA_PATH = BACKEND_ROOT / "chroma_db"
COLLECTION_NAME = "lionafrique_documents"


def configure_console() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def safe_integer(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Affiche les segments ChromaDB d'un PDF, "
            "quelle que soit sa matière."
        )
    )
    parser.add_argument(
        "source",
        help="Nom exact du fichier PDF dans les métadonnées.",
    )
    parser.add_argument(
        "--program",
        default=None,
        help='Filtre optionnel, par exemple "Programme marocain".',
    )
    parser.add_argument(
        "--subject",
        default=None,
        help='Filtre optionnel, par exemple "Informatique".',
    )
    return parser.parse_args()


def build_where(
    source: str,
    program: str | None,
    subject: str | None,
) -> dict:
    filters = [
        {
            "source": {
                "$eq": source,
            }
        }
    ]

    if program:
        filters.append(
            {
                "program": {
                    "$eq": program,
                }
            }
        )

    if subject:
        filters.append(
            {
                "subject": {
                    "$eq": subject,
                }
            }
        )

    if len(filters) == 1:
        return filters[0]

    return {
        "$and": filters,
    }


def main() -> None:
    configure_console()
    arguments = parse_arguments()

    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH)
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    results = collection.get(
        where=build_where(
            source=arguments.source,
            program=arguments.program,
            subject=arguments.subject,
        ),
        include=[
            "metadatas",
            "documents",
        ],
    )

    metadatas = results.get("metadatas") or []
    documents = results.get("documents") or []

    chunks = []

    for index, (metadata, document) in enumerate(
        zip(metadatas, documents),
        start=1,
    ):
        metadata = metadata or {}

        chunks.append(
            {
                "original_index": index,
                "page": safe_integer(
                    metadata.get("page", 0)
                ),
                "chunk_number": safe_integer(
                    metadata.get(
                        "chunk_number",
                        index,
                    )
                ),
                "program": metadata.get(
                    "program",
                    "Non défini",
                ),
                "subject": metadata.get(
                    "subject",
                    "Non définie",
                ),
                "semester": metadata.get(
                    "semester",
                    "Non défini",
                ),
                "relative_path": metadata.get(
                    "relative_path",
                    "",
                ),
                "text": (document or "").strip(),
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
    print("Inspection d'un PDF dans ChromaDB")
    print("=" * 100)
    print("Fichier :", arguments.source)
    print("Programme filtré :", arguments.program or "Aucun")
    print("Matière filtrée :", arguments.subject or "Aucune")
    print("Nombre de segments :", len(chunks))

    if not chunks:
        print()
        print(
            "Aucun segment correspondant n'a été trouvé "
            "dans ChromaDB."
        )
        raise SystemExit(2)

    print("Programme :", chunks[0]["program"])
    print("Matière :", chunks[0]["subject"])
    print("Semestre :", chunks[0]["semester"])

    if chunks[0]["relative_path"]:
        print("Chemin :", chunks[0]["relative_path"])

    output_lines = [
        "=" * 100,
        "Inspection d'un PDF dans ChromaDB",
        "=" * 100,
        f"Fichier : {arguments.source}",
        f"Nombre de segments : {len(chunks)}",
        f"Programme : {chunks[0]['program']}",
        f"Matière : {chunks[0]['subject']}",
        f"Semestre : {chunks[0]['semester']}",
        f"Chemin : {chunks[0]['relative_path']}",
        "",
    ]

    for number, chunk in enumerate(
        chunks,
        start=1,
    ):
        separator = "-" * 100
        header = (
            f"[{number}/{len(chunks)}] "
            f"Page {chunk['page']} "
            f"| Segment {chunk['chunk_number']}"
        )

        print()
        print(separator)
        print(header)
        print(separator)
        print(chunk["text"] or "[Segment vide]")

        output_lines.extend(
            [
                separator,
                header,
                separator,
                chunk["text"] or "[Segment vide]",
                "",
            ]
        )

    safe_stem = (
        Path(arguments.source)
        .stem
        .replace(" ", "_")
    )
    report_path = Path(
        f"inspection_{safe_stem}.txt"
    )
    report_path.write_text(
        "\n".join(output_lines),
        encoding="utf-8",
    )

    print()
    print("=" * 100)
    print("Rapport enregistré :", report_path.resolve())


if __name__ == "__main__":
    main()
