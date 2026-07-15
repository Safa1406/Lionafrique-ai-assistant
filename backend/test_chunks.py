from pathlib import Path

from services.pdf_service import extract_pdf_pages
from services.text_splitter import split_pages_into_chunks


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PDF_PATH = (
    PROJECT_ROOT
    / "data"
    / "sample"
    / "les_aliments_partie_2.pdf"
)


def main() -> None:
    try:
        pages = extract_pdf_pages(PDF_PATH)

        chunks = split_pages_into_chunks(
            pages,
            chunk_size=800,
            chunk_overlap=120,
        )

        print("Découpage du document terminé avec succès.")
        print(f"Nombre de pages : {len(pages)}")
        print(f"Nombre de segments : {len(chunks)}")

        if chunks:
            first_chunk = chunks[0]

            print("\nPremier segment :")
            print(f"Identifiant : {first_chunk['chunk_id']}")
            print(f"Source : {first_chunk['source']}")
            print(f"Page : {first_chunk['page']}")
            print(f"Numéro du segment : {first_chunk['chunk_number']}")
            print(f"Texte :\n{first_chunk['text']}")

    except Exception as error:
        print(
            "Une erreur est survenue pendant le découpage "
            f"du document : {error}"
        )


if __name__ == "__main__":
    main()