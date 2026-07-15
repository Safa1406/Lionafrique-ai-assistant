from services.text_cleaner import clean_extracted_text
from pathlib import Path

import fitz


def extract_pdf_pages(pdf_path: str | Path) -> list[dict]:
    """
    Extrait le texte de chaque page d'un fichier PDF.
    """

    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Le fichier PDF est introuvable : {path}"
        )

    if path.suffix.lower() != ".pdf":
        raise ValueError(
            "Le fichier fourni n'est pas un fichier PDF."
        )

    extracted_pages = []

    with fitz.open(path) as document:
        for page_index, page in enumerate(document):
            raw_text = page.get_text("text")
            text = clean_extracted_text(raw_text)

            extracted_pages.append(
                {
                    "source": path.name,
                    "page": page_index + 1,
                    "text": text,
                    "has_text": bool(text),
                }
            )

    return extracted_pages


def get_pdf_summary(pdf_path: str | Path) -> dict:
    """
    Retourne un résumé du fichier PDF analysé.
    """

    pages = extract_pdf_pages(pdf_path)

    pages_with_text = sum(
        1 for page in pages if page["has_text"]
    )

    return {
        "source": Path(pdf_path).name,
        "total_pages": len(pages),
        "pages_with_text": pages_with_text,
        "empty_pages": len(pages) - pages_with_text,
    }