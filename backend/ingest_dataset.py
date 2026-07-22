import hashlib
import json
import re
import unicodedata
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

# Utiliser None pour traiter tous les fichiers PDF.
# Utiliser un nombre, par exemple 5, pour effectuer un test limité.
MAX_FILES: int | None = None


PROGRAM_ALIASES = {
    "programme francais": "Programme français",
    "programme marocain": "Programme marocain",
}


SUBJECT_ALIASES = {
    "francais": "Français",
    "anglais": "Anglais",
    "arabe": "Arabe",
    "education islamique": "Éducation islamique",
    "histoire geographique": "Histoire-Géographie",
    "informatique": "Informatique",
    "math": "Mathématiques",
    "math arabe": "Mathématiques arabe",
    "pc": "Physique-Chimie",
    "phisique chimie": "Physique-Chimie",
    "physique chimie": "Physique-Chimie",
    "pc arabe": "Physique-Chimie arabe",
    "svt": "SVT",
    "svt arabe": "SVT arabe",
}


def calculate_file_hash(file_path: Path) -> str:
    """
    Calcule l'empreinte SHA-256 d'un fichier.
    """

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        while True:
            file_chunk = file.read(
                1024 * 1024
            )

            if not file_chunk:
                break

            digest.update(file_chunk)

    return digest.hexdigest()


def normalize_label(value: str) -> str:
    """
    Normalise une valeur pour comparer les noms
    de dossiers sans tenir compte des accents,
    des majuscules et des séparateurs.
    """

    if not value:
        return ""

    normalized_value = unicodedata.normalize(
        "NFKD",
        value.lower(),
    )

    normalized_value = "".join(
        character
        for character in normalized_value
        if not unicodedata.combining(character)
    )

    normalized_value = normalized_value.replace(
        "-",
        " ",
    )

    normalized_value = normalized_value.replace(
        "_",
        " ",
    )

    normalized_value = re.sub(
        r"\s+",
        " ",
        normalized_value,
    )

    return normalized_value.strip()


def get_clean_path_parts(
    relative_path: Path,
) -> list[str]:
    """
    Supprime les dossiers racines inutiles
    ou mal encodés avant le dossier du programme.
    """

    parts = list(relative_path.parts)

    for index, part in enumerate(parts):
        normalized_part = normalize_label(part)

        if normalized_part in PROGRAM_ALIASES:
            return parts[index:]

    return parts


def build_clean_relative_path(
    relative_path: Path,
) -> str:
    """
    Construit un chemin relatif propre
    pour les métadonnées.
    """

    clean_parts = get_clean_path_parts(
        relative_path
    )

    return "/".join(clean_parts)


def extract_document_metadata(
    relative_path: Path,
) -> dict:
    """
    Déduit et normalise les métadonnées
    principales depuis le chemin du fichier.
    """

    parts = get_clean_path_parts(
        relative_path
    )

    program = "Non défini"
    subject = "Non définie"
    semester = "Non défini"

    for index, part in enumerate(parts):
        normalized_part = normalize_label(part)

        if normalized_part in PROGRAM_ALIASES:
            program = PROGRAM_ALIASES[
                normalized_part
            ]

            if index + 1 < len(parts):
                subject_key = normalize_label(
                    parts[index + 1]
                )

                subject = SUBJECT_ALIASES.get(
                    subject_key,
                    parts[index + 1],
                )

        if normalized_part in {
            "s1",
            "semestre 1",
        }:
            semester = "S1"

        if normalized_part in {
            "s2",
            "semestre 2",
        }:
            semester = "S2"

    if subject == "Non définie" and len(parts) >= 2:
        possible_subject = parts[-2]

        subject_key = normalize_label(
            possible_subject
        )

        subject = SUBJECT_ALIASES.get(
            subject_key,
            possible_subject,
        )

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
    Extrait, découpe et enrichit
    un document PDF.
    """

    relative_path = pdf_path.relative_to(
        DATA_ROOT
    )

    relative_path_text = (
        build_clean_relative_path(
            relative_path
        )
    )

    document_id = file_hash[:20]

    pages = extract_pdf_pages(
        pdf_path
    )

    pages_with_text = sum(
        1
        for page in pages
        if page.get("has_text", False)
    )

    empty_pages = (
        len(pages) - pages_with_text
    )

    if pages_with_text == 0:
        return (
            [],
            pages_with_text,
            empty_pages,
        )

    document_metadata = (
        extract_document_metadata(
            relative_path
        )
    )

    chunks = split_pages_into_chunks(
        pages,
        chunk_size=800,
        chunk_overlap=120,
    )

    for chunk in chunks:
        chunk["document_id"] = document_id

        chunk["relative_path"] = (
            relative_path_text
        )

        chunk["program"] = (
            document_metadata["program"]
        )

        chunk["subject"] = (
            document_metadata["subject"]
        )

        chunk["semester"] = (
            document_metadata["semester"]
        )

        chunk["chunk_id"] = (
            f"{document_id}"
            f"-page-{chunk['page']}"
            f"-segment-{chunk['chunk_number']}"
        )

    return (
        chunks,
        pages_with_text,
        empty_pages,
    )


def ingest_dataset() -> None:
    """
    Analyse tous les fichiers PDF
    et les enregistre dans ChromaDB.
    """

    if not DATA_ROOT.exists():
        raise FileNotFoundError(
            "Le dossier des données est introuvable : "
            f"{DATA_ROOT}"
        )

    all_pdf_files = sorted(
        DATA_ROOT.rglob("*.pdf"),
        key=lambda file_path: (
            str(file_path).lower()
        ),
    )

    pdf_files = all_pdf_files

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
        "total_files_available": len(
            all_pdf_files
        ),
        "total_files_detected": len(
            pdf_files
        ),
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
        original_relative_path = (
            pdf_path.relative_to(
                DATA_ROOT
            )
        )

        displayed_path = (
            build_clean_relative_path(
                original_relative_path
            )
        )

        print(
            f"\n[{index}/{len(pdf_files)}] "
            f"Traitement : {displayed_path}"
        )

        try:
            file_hash = calculate_file_hash(
                pdf_path
            )

            if file_hash in seen_hashes:
                report["duplicate_files"] += 1

                report["duplicates"].append(
                    {
                        "file": displayed_path,
                        "duplicate_of": (
                            seen_hashes[file_hash]
                        ),
                    }
                )

                print(
                    "Fichier ignoré : copie exacte "
                    "d'un document déjà traité."
                )

                continue

            seen_hashes[file_hash] = (
                displayed_path
            )

            (
                chunks,
                pages_with_text,
                empty_pages,
            ) = prepare_document_chunks(
                pdf_path=pdf_path,
                file_hash=file_hash,
            )

            report[
                "total_pages_with_text"
            ] += pages_with_text

            report[
                "total_empty_pages"
            ] += empty_pages

            if not chunks:
                report[
                    "scanned_or_empty_files"
                ] += 1

                report[
                    "scanned_or_empty"
                ].append(
                    displayed_path
                )

                print(
                    "Fichier ignoré : aucun texte "
                    "exploitable n'a été détecté."
                )

                continue

            stored_chunks = store_chunks(
                chunks=chunks,
                batch_size=32,
            )

            report[
                "processed_files"
            ] += 1

            report[
                "total_chunks"
            ] += stored_chunks

            print(
                "Document enregistré : "
                f"{stored_chunks} segment(s)."
            )

        except Exception as error:
            report[
                "failed_files"
            ] += 1

            report["errors"].append(
                {
                    "file": displayed_path,
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

    print(
        "\n=== RAPPORT FINAL ==="
    )

    print(
        "Fichiers disponibles : "
        f"{report['total_files_available']}"
    )

    print(
        "Fichiers détectés : "
        f"{report['total_files_detected']}"
    )

    print(
        "Fichiers traités : "
        f"{report['processed_files']}"
    )

    print(
        "Doublons ignorés : "
        f"{report['duplicate_files']}"
    )

    print(
        "Fichiers sans texte : "
        f"{report['scanned_or_empty_files']}"
    )

    print(
        "Fichiers en erreur : "
        f"{report['failed_files']}"
    )

    print(
        "Pages avec du texte : "
        f"{report['total_pages_with_text']}"
    )

    print(
        "Pages sans texte : "
        f"{report['total_empty_pages']}"
    )

    print(
        "Segments enregistrés : "
        f"{report['total_chunks']}"
    )

    print(
        "Rapport enregistré dans : "
        f"{REPORT_PATH}"
    )


if __name__ == "__main__":
    ingest_dataset()