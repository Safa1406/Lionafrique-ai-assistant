import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from services.pdf_service import (
    extract_pdf_pages,
)
from services.text_splitter import (
    split_pages_into_chunks,
)
from services.vector_store_service import (
    build_metadata_filter,
    get_document_collection,
    store_chunks,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

DATA_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
)

REPORT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "processed"
)


PROGRAM_ALIASES = {
    "programme francais": (
        "Programme français"
    ),
    "programme marocain": (
        "Programme marocain"
    ),
}


SUBJECT_ALIASES = {
    "francais": "Français",
    "anglais": "Anglais",
    "arabe": "Arabe",
    "education islamique": (
        "Éducation islamique"
    ),
    "histoire geographique": (
        "Histoire-Géographie"
    ),
    "informatique": "Informatique",
    "math": "Mathématiques",
    "math arabe": (
        "Mathématiques arabe"
    ),
    "pc": "Physique-Chimie",
    "phisique chimie": (
        "Physique-Chimie"
    ),
    "physique chimie": (
        "Physique-Chimie"
    ),
    "pc arabe": (
        "Physique-Chimie arabe"
    ),
    "svt": "SVT",
    "svt arabe": "SVT arabe",
}


def parse_arguments() -> argparse.Namespace:
    """
    Lit les options de la commande d'ingestion.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Analyse les fichiers PDF "
            "et les enregistre dans ChromaDB."
        )
    )

    parser.add_argument(
        "--program",
        default=None,
        help=(
            "Programme à traiter, par exemple "
            "\"Programme marocain\"."
        ),
    )

    parser.add_argument(
        "--subject",
        default=None,
        help=(
            "Matière à traiter, par exemple "
            "\"Arabe\"."
        ),
    )

    parser.add_argument(
        "--semester",
        default=None,
        help=(
            "Semestre à traiter, par exemple "
            "\"S1\"."
        ),
    )

    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help=(
            "Nombre maximal de fichiers "
            "à traiter."
        ),
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "Supprime les anciens segments "
            "correspondant aux filtres avant l'ingestion."
        ),
    )

    return parser.parse_args()


def calculate_file_hash(
    file_path: Path,
) -> str:
    """
    Calcule l'empreinte SHA-256 d'un fichier.
    """

    digest = hashlib.sha256()

    with file_path.open(
        "rb"
    ) as file:
        while True:
            file_chunk = file.read(
                1024 * 1024
            )

            if not file_chunk:
                break

            digest.update(
                file_chunk
            )

    return digest.hexdigest()


def normalize_label(
    value: str,
) -> str:
    """
    Normalise une valeur
    pour comparer les noms de dossiers.
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
        if not unicodedata.combining(
            character
        )
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
    avant le dossier du programme.
    """

    parts = list(
        relative_path.parts
    )

    for index, part in enumerate(
        parts
    ):
        normalized_part = normalize_label(
            part
        )

        if normalized_part in PROGRAM_ALIASES:
            return parts[
                index:
            ]

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

    return "/".join(
        clean_parts
    )


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

    for index, part in enumerate(
        parts
    ):
        normalized_part = normalize_label(
            part
        )

        if normalized_part in PROGRAM_ALIASES:
            program = PROGRAM_ALIASES[
                normalized_part
            ]

            if index + 1 < len(
                parts
            ):
                subject_key = normalize_label(
                    parts[
                        index + 1
                    ]
                )

                subject = SUBJECT_ALIASES.get(
                    subject_key,
                    parts[
                        index + 1
                    ],
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

    if (
        subject == "Non définie"
        and len(parts) >= 2
    ):
        possible_subject = parts[
            -2
        ]

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


def matches_filters(
    metadata: dict,
    program: str | None,
    subject: str | None,
    semester: str | None,
) -> bool:
    """
    Vérifie si un document
    correspond aux filtres demandés.
    """

    if (
        program
        and metadata["program"]
        != program
    ):
        return False

    if (
        subject
        and metadata["subject"]
        != subject
    ):
        return False

    if (
        semester
        and metadata["semester"]
        != semester
    ):
        return False

    return True


def build_report_path(
    program: str | None,
    subject: str | None,
    semester: str | None,
) -> Path:
    """
    Construit un nom de rapport
    adapté aux filtres utilisés.
    """

    filter_values = [
        value
        for value in (
            program,
            subject,
            semester,
        )
        if value
    ]

    if not filter_values:
        return (
            REPORT_DIRECTORY
            / "ingestion_report.json"
        )

    normalized_suffix = "_".join(
        normalize_label(
            value
        ).replace(
            " ",
            "_",
        )
        for value in filter_values
    )

    return (
        REPORT_DIRECTORY
        / (
            "ingestion_report_"
            f"{normalized_suffix}.json"
        )
    )


def delete_existing_chunks(
    program: str | None,
    subject: str | None,
    semester: str | None,
) -> int:
    """
    Supprime les anciens segments
    correspondant aux filtres demandés.
    """

    metadata_filter = build_metadata_filter(
        program=program,
        subject=subject,
        semester=semester,
    )

    if metadata_filter is None:
        raise ValueError(
            "L'option --replace nécessite "
            "au moins un filtre."
        )

    collection = get_document_collection()

    count_before = collection.count()

    collection.delete(
        where=metadata_filter
    )

    count_after = collection.count()

    return max(
        0,
        count_before - count_after,
    )



def load_ocr_sidecar_pages(
    pdf_path: Path,
    original_pages: list[dict],
) -> list[dict]:
    """
    Charge le fichier OCR associ? ? un PDF scann?.

    Convention:
        lesson.pdf
        lesson.ocr.txt

    Le fichier OCR contient des s?parateurs:
        === PAGE 1 ===
        ...
        === PAGE 2 ===
        ...

    Les m?tadonn?es des pages extraites du PDF sont
    conserv?es quand elles existent.
    """

    sidecar_path = (
        pdf_path.with_suffix(
            ".ocr.txt"
        )
    )

    if not sidecar_path.exists():
        return original_pages

    try:
        content = (
            sidecar_path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        print(
            f"[OCR] Impossible de lire "
            f"{sidecar_path.name}: {exc}"
        )
        return original_pages

    page_pattern = re.compile(
        r"(?m)^===\s*PAGE\s+(\d+)\s*===\s*$"
    )

    matches = list(
        page_pattern.finditer(
            content
        )
    )

    if not matches:
        print(
            f"[OCR] Aucun marqueur PAGE "
            f"dans {sidecar_path.name}"
        )
        return original_pages

    ocr_by_page = {}

    for index, match in enumerate(
        matches
    ):
        page_number = int(
            match.group(1)
        )

        start = match.end()

        if index + 1 < len(matches):
            end = matches[
                index + 1
            ].start()
        else:
            end = len(content)

        text = (
            content[
                start:end
            ]
            .strip()
        )

        ocr_by_page[
            page_number
        ] = text

    if not ocr_by_page:
        return original_pages

    rebuilt_pages = []

    # Preserve the exact page structure expected by
    # split_pages_into_chunks whenever extract_pdf_pages()
    # already returned page dictionaries.
    if original_pages:

        for index, original_page in enumerate(
            original_pages,
            start=1,
        ):
            page = dict(
                original_page
            )

            page_number = (
                page.get(
                    "page",
                    None,
                )
                or page.get(
                    "page_number",
                    None,
                )
                or index
            )

            try:
                page_number = int(
                    page_number
                )
            except Exception:
                page_number = index

            ocr_text = (
                ocr_by_page.get(
                    page_number,
                    ""
                )
                or ""
            ).strip()

            if ocr_text:
                page["text"] = (
                    ocr_text
                )
                page["has_text"] = True

            rebuilt_pages.append(
                page
            )

    else:

        # Defensive fallback in case the PDF extractor
        # returns no page objects at all.
        for page_number in sorted(
            ocr_by_page
        ):
            text = (
                ocr_by_page[
                    page_number
                ]
                or ""
            ).strip()

            rebuilt_pages.append(
                {
                    "page": page_number,
                    "page_number": (
                        page_number
                    ),
                    "text": text,
                    "has_text": bool(
                        text
                    ),
                }
            )

    pages_with_text = sum(
        1
        for page in rebuilt_pages
        if (
            page.get(
                "text",
                ""
            )
            or ""
        ).strip()
    )

    if pages_with_text:
        print(
            f"[OCR] {pdf_path.name}: "
            f"{pages_with_text} page(s) "
            f"charg?e(s) depuis "
            f"{sidecar_path.name}"
        )

    return rebuilt_pages


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

    document_id = file_hash[
        :20
    ]

    pages = extract_pdf_pages(
        pdf_path
    )

    native_pages_with_text = sum(
        1
        for page in pages
        if page.get(
            "has_text",
            False,
        )
    )

    # --------------------------------------------------------
    # OCR fallback for scanned PDFs.
    # Native text always has priority.
    # --------------------------------------------------------
    if native_pages_with_text == 0:
        pages = load_ocr_sidecar_pages(
            pdf_path=pdf_path,
            original_pages=pages,
        )

    pages_with_text = sum(
        1
        for page in pages
        if page.get(
            "has_text",
            False,
        )
    )

    empty_pages = (
        len(pages)
        - pages_with_text
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
        chunk["document_id"] = (
            document_id
        )

        chunk["relative_path"] = (
            relative_path_text
        )

        chunk["program"] = (
            document_metadata[
                "program"
            ]
        )

        chunk["subject"] = (
            document_metadata[
                "subject"
            ]
        )

        chunk["semester"] = (
            document_metadata[
                "semester"
            ]
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


def find_pdf_files(
    program: str | None,
    subject: str | None,
    semester: str | None,
) -> tuple[
    list[Path],
    list[Path],
]:
    """
    Retourne tous les PDF
    et ceux correspondant aux filtres.
    """

    all_pdf_files = sorted(
        DATA_ROOT.rglob(
            "*.pdf"
        ),
        key=lambda file_path: (
            str(
                file_path
            ).lower()
        ),
    )

    selected_pdf_files = []

    for pdf_path in all_pdf_files:
        relative_path = (
            pdf_path.relative_to(
                DATA_ROOT
            )
        )

        metadata = (
            extract_document_metadata(
                relative_path
            )
        )

        if matches_filters(
            metadata=metadata,
            program=program,
            subject=subject,
            semester=semester,
        ):
            selected_pdf_files.append(
                pdf_path
            )

    return (
        all_pdf_files,
        selected_pdf_files,
    )


def ingest_dataset(
    program: str | None = None,
    subject: str | None = None,
    semester: str | None = None,
    max_files: int | None = None,
    replace: bool = False,
) -> None:
    """
    Analyse les PDF sélectionnés
    et les enregistre dans ChromaDB.
    """

    if not DATA_ROOT.exists():
        raise FileNotFoundError(
            "Le dossier des données est introuvable : "
            f"{DATA_ROOT}"
        )

    (
        all_pdf_files,
        selected_pdf_files,
    ) = find_pdf_files(
        program=program,
        subject=subject,
        semester=semester,
    )

    if max_files is not None:
        if max_files <= 0:
            raise ValueError(
                "Le nombre maximal de fichiers "
                "doit être supérieur à zéro."
            )

        selected_pdf_files = (
            selected_pdf_files[
                :max_files
            ]
        )

    if not selected_pdf_files:
        print(
            "Aucun fichier PDF ne correspond "
            "aux filtres demandés."
        )
        return

    report_path = build_report_path(
        program=program,
        subject=subject,
        semester=semester,
    )

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    removed_chunks = 0

    if replace:
        removed_chunks = (
            delete_existing_chunks(
                program=program,
                subject=subject,
                semester=semester,
            )
        )

        print(
            "Anciens segments supprimés : "
            f"{removed_chunks}"
        )

    report = {
        "filters": {
            "program": program,
            "subject": subject,
            "semester": semester,
        },
        "replacement_enabled": (
            replace
        ),
        "removed_chunks": (
            removed_chunks
        ),
        "total_files_available": len(
            all_pdf_files
        ),
        "total_files_detected": len(
            selected_pdf_files
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

    seen_hashes: dict[
        str,
        str,
    ] = {}

    for index, pdf_path in enumerate(
        selected_pdf_files,
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
            f"\n[{index}/"
            f"{len(selected_pdf_files)}] "
            f"Traitement : {displayed_path}"
        )

        try:
            file_hash = calculate_file_hash(
                pdf_path
            )

            if file_hash in seen_hashes:
                report[
                    "duplicate_files"
                ] += 1

                report[
                    "duplicates"
                ].append(
                    {
                        "file": displayed_path,
                        "duplicate_of": (
                            seen_hashes[
                                file_hash
                            ]
                        ),
                    }
                )

                print(
                    "Fichier ignoré : copie exacte "
                    "d'un document déjà traité."
                )

                continue

            seen_hashes[
                file_hash
            ] = displayed_path

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

            report[
                "errors"
            ].append(
                {
                    "file": displayed_path,
                    "error": str(
                        error
                    ),
                }
            )

            print(
                "Erreur pendant le traitement : "
                f"{error}"
            )

    with report_path.open(
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
        f"{report_path}"
    )


if __name__ == "__main__":
    arguments = parse_arguments()

    ingest_dataset(
        program=arguments.program,
        subject=arguments.subject,
        semester=arguments.semester,
        max_files=(
            arguments.max_files
        ),
        replace=arguments.replace,
    )