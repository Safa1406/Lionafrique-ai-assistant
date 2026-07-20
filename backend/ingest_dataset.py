import hashlib
import json
from pathlib import Path

from services.pdf_service import extract_pdf_pages
from services.text_splitter import split_pages_into_chunks
from services.vector_store_service import store_chunks


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data" / "raw"
REPORT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "ingestion_report.json"
)

# Utiliser 5 pour le premier test.
# Remplacer par None pour traiter tous les fichiers.
MAX_FILES: int | None = 5


def calculate_file_hash(file_path: Path) -> str:
    """
    Calcule l'empreinte SHA-256 d'un fichier.
    """

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def extract_document_metadata(
    relative_path: Path,
) -> dict:
    """
    Déduit les métadonnées principales depuis le chemin du fichier.
    """

    parts = list(relative_path.parts)

    program = "Non défini"
    subject = "Non définie"
    semester = "Non défini"

    for index, part in enumerate(parts):
        normalized_part = part.lower()

        if normalized_part in {
            "programme francais",
            "programme français",
            "programme marocain",
        }:
            program = part

            if index + 1 < len(parts):
                subject = parts[index + 1]

        if normalized_part in {
            "s1",
            "s2",
            "semestre 1",
            "semestre 2",
        }:
            semester = part

    if subject == "Non définie" and len(parts) >= 2:
        subject = parts[-2]

    return {
        "program": program,
        "subject": subject,
        "semester": semester,
    }


def prepare_document_chunks(
    pdf_path: Path,
    file_hash: str,
) -> tuple[list[dict], int, int]:
    """
    Extrait, découpe et enrichit un document PDF.
    """

    relative_path = pdf_path.relative_to(DATA_ROOT)
    relative_path_text = relative_path.as_posix()
    document_id = file_hash[:20]

    pages = extract_pdf_pages(pdf_path)

    pages_with_text = sum(
        1 for page in pages
        if page["has_text"]
    )

    empty_pages = len(pages) - pages_with_text

    if pages_with_text == 0:
        return [], pages_with_text, empty_pages

    document_metadata = extract_document_metadata(
        relative_path
    )

    chunks = split_pages_into_chunks(
        pages,
        chunk_size=800,
        chunk_overlap=120,
    )

    for chunk in chunks:
        chunk["document_id"] = document_id
        chunk["relative_path"] = relative_path_text
        chunk["program"] = document_metadata["program"]
        chunk["subject"] = document_metadata["subject"]
        chunk["semester"] = document_metadata["semester"]

        chunk["chunk_id"] = (
            f"{document_id}"
            f"-page-{chunk['page']}"
            f"-segment-{chunk['chunk_number']}"
        )

    return chunks, pages_with_text, empty_pages


def ingest_dataset() -> None:
    """
    Analyse et enregistre les fichiers PDF dans ChromaDB.
    """

    if not DATA_ROOT.exists():
        raise FileNotFoundError(
            f"Le dossier des données est introuvable : {DATA_ROOT}"
        )

    pdf_files = sorted(
        DATA_ROOT.rglob("*.pdf")
    )

    if MAX_FILES is not None:
        pdf_files = pdf_files[:MAX_FILES]

    if not pdf_files:
        print(
            "Aucun fichier PDF n'a été trouvé "
            "dans le dossier des données."
        )
        return

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = {
        "total_files_detected": len(pdf_files),
        "processed_files": 0,
        "duplicate_files": 0,
        "scanned_or_empty_files": 0,
        "failed_files": 0,
        "total_pages_with_text": 0,
        "total_empty_pages": 0,
        "total_chunks": 0,
        "duplicates": [],
        "scanned_or_empty": [],
        "errors": [],
    }

    seen_hashes: dict[str, str] = {}

    for index, pdf_path in enumerate(
        pdf_files,
        start=1,
    ):
        relative_path = pdf_path.relative_to(
            DATA_ROOT
        ).as_posix()

        print(
            f"\n[{index}/{len(pdf_files)}] "
            f"Traitement : {relative_path}"
        )

        try:
            file_hash = calculate_file_hash(pdf_path)

            if file_hash in seen_hashes:
                report["duplicate_files"] += 1
                report["duplicates"].append(
                    {
                        "file": relative_path,
                        "duplicate_of": seen_hashes[file_hash],
                    }
                )

                print(
                    "Fichier ignoré : copie exacte "
                    "d'un document déjà traité."
                )
                continue

            seen_hashes[file_hash] = relative_path

            (
                chunks,
                pages_with_text,
                empty_pages,
            ) = prepare_document_chunks(
                pdf_path,
                file_hash,
            )

            report["total_pages_with_text"] += (
                pages_with_text
            )
            report["total_empty_pages"] += empty_pages

            if not chunks:
                report["scanned_or_empty_files"] += 1
                report["scanned_or_empty"].append(
                    relative_path
                )

                print(
                    "Fichier ignoré : aucun texte "
                    "exploitable n'a été détecté."
                )
                continue

            stored_chunks = store_chunks(
                chunks,
                batch_size=32,
            )

            report["processed_files"] += 1
            report["total_chunks"] += stored_chunks

            print(
                f"Document enregistré : "
                f"{stored_chunks} segment(s)."
            )

        except Exception as error:
            report["failed_files"] += 1
            report["errors"].append(
                {
                    "file": relative_path,
                    "error": str(error),
                }
            )

            print(
                "Erreur pendant le traitement : "
                f"{error}"
            )

    with REPORT_PATH.open(
        "w",
        encoding="utf-8",
    ) as report_file:
        json.dump(
            report,
            report_file,
            ensure_ascii=False,
            indent=2,
        )

    print("\n=== RAPPORT FINAL ===")
    print(
        f"Fichiers détectés : "
        f"{report['total_files_detected']}"
    )
    print(
        f"Fichiers traités : "
        f"{report['processed_files']}"
    )
    print(
        f"Doublons ignorés : "
        f"{report['duplicate_files']}"
    )
    print(
        f"Fichiers sans texte : "
        f"{report['scanned_or_empty_files']}"
    )
    print(
        f"Fichiers en erreur : "
        f"{report['failed_files']}"
    )
    print(
        f"Segments enregistrés : "
        f"{report['total_chunks']}"
    )
    print(
        f"Rapport enregistré dans : "
        f"{REPORT_PATH}"
    )


if __name__ == "__main__":
    ingest_dataset()