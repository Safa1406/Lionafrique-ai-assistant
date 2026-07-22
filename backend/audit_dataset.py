import json
from collections import Counter
from pathlib import Path

from services.vector_store_service import (
    get_document_collection,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

REPORT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "ingestion_report.json"
)


def display_counter(
    title: str,
    counter: Counter,
) -> None:
    """
    Affiche les valeurs d'un compteur.
    """

    print(f"\n=== {title} ===")

    if not counter:
        print("Aucune donnée disponible.")
        return

    for value, count in counter.most_common():
        print(f"{value} : {count}")


def audit_collection() -> None:
    """
    Analyse les métadonnées enregistrées dans ChromaDB.
    """

    collection = get_document_collection()

    collection_count = collection.count()

    print("=== AUDIT DE LA BASE DOCUMENTAIRE ===")
    print(
        f"Nombre total de segments dans ChromaDB : "
        f"{collection_count}"
    )

    if collection_count == 0:
        print(
            "La collection ne contient aucun segment."
        )
        return

    results = collection.get(
        include=["metadatas"],
    )

    metadatas = results.get(
        "metadatas",
        [],
    )

    programs = Counter()
    subjects = Counter()
    semesters = Counter()

    document_ids = set()
    suspicious_values = set()

    missing_program = 0
    missing_subject = 0
    missing_document_id = 0
    missing_relative_path = 0

    for metadata in metadatas:
        if not metadata:
            continue

        program = metadata.get(
            "program",
            "Non défini",
        )

        subject = metadata.get(
            "subject",
            "Non définie",
        )

        semester = metadata.get(
            "semester",
            "Non défini",
        )

        document_id = metadata.get(
            "document_id",
        )

        relative_path = metadata.get(
            "relative_path",
            "",
        )

        programs[program] += 1
        subjects[subject] += 1
        semesters[semester] += 1

        if document_id:
            document_ids.add(document_id)
        else:
            missing_document_id += 1

        if not relative_path:
            missing_relative_path += 1

        if program == "Non défini":
            missing_program += 1

        if subject == "Non définie":
            missing_subject += 1

        values_to_check = (
            program,
            subject,
            semester,
            relative_path,
        )

        for value in values_to_check:
            if not isinstance(value, str):
                continue

            if "Ã" in value or "�" in value:
                suspicious_values.add(value)

    print(
        f"Nombre de documents uniques : "
        f"{len(document_ids)}"
    )

    print(
        f"Segments sans programme : "
        f"{missing_program}"
    )

    print(
        f"Segments sans matière : "
        f"{missing_subject}"
    )

    print(
        f"Segments sans identifiant de document : "
        f"{missing_document_id}"
    )

    print(
        f"Segments sans chemin relatif : "
        f"{missing_relative_path}"
    )

    display_counter(
        "PROGRAMMES",
        programs,
    )

    display_counter(
        "MATIÈRES",
        subjects,
    )

    display_counter(
        "SEMESTRES",
        semesters,
    )

    print(
        "\n=== VALEURS AVEC UN ENCODAGE SUSPECT ==="
    )

    if suspicious_values:
        for value in sorted(suspicious_values):
            print(value)
    else:
        print(
            "Aucune valeur suspecte détectée."
        )


def display_ingestion_report() -> None:
    """
    Affiche les informations importantes du rapport d'ingestion.
    """

    print(
        "\n=== RAPPORT D'INGESTION ==="
    )

    if not REPORT_PATH.exists():
        print(
            "Le rapport d'ingestion est introuvable."
        )
        return

    with REPORT_PATH.open(
        "r",
        encoding="utf-8",
    ) as report_file:
        report = json.load(report_file)

    print(
        f"Fichiers détectés : "
        f"{report.get('total_files_detected', 0)}"
    )

    print(
        f"Fichiers traités : "
        f"{report.get('processed_files', 0)}"
    )

    print(
        f"Doublons ignorés : "
        f"{report.get('duplicate_files', 0)}"
    )

    print(
        f"Fichiers sans texte : "
        f"{report.get('scanned_or_empty_files', 0)}"
    )

    print(
        f"Fichiers en erreur : "
        f"{report.get('failed_files', 0)}"
    )

    print(
        f"Segments enregistrés : "
        f"{report.get('total_chunks', 0)}"
    )

    scanned_files = report.get(
        "scanned_or_empty",
        [],
    )

    print(
        "\n=== FICHIERS SANS TEXTE ==="
    )

    if not scanned_files:
        print(
            "Aucun fichier sans texte."
        )
    else:
        for file_path in scanned_files:
            print(file_path)


if __name__ == "__main__":
    audit_collection()
    display_ingestion_report()