from pathlib import Path

from services.pdf_service import extract_pdf_pages, get_pdf_summary


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PDF_PATH = (
    PROJECT_ROOT
    / "data"
    / "sample"
    / "les_aliments_partie_2.pdf"
)


def main() -> None:
    try:
        summary = get_pdf_summary(PDF_PATH)
        pages = extract_pdf_pages(PDF_PATH)

        print("Analyse du fichier PDF terminée avec succès.")
        print(f"Fichier : {summary['source']}")
        print(f"Nombre total de pages : {summary['total_pages']}")
        print(
            f"Pages contenant du texte : "
            f"{summary['pages_with_text']}"
        )
        print(f"Pages vides : {summary['empty_pages']}")

        if pages:
            preview = pages[0]["text"][:500]

            print("\nAperçu de la première page :")
            print(preview or "Aucun texte détecté sur cette page.")

    except (FileNotFoundError, ValueError) as error:
        print(f"Erreur : {error}")

    except Exception as error:
        print(
            "Une erreur inattendue est survenue pendant "
            f"l'analyse du PDF : {error}"
        )


if __name__ == "__main__":
    main()