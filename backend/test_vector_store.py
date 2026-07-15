from pathlib import Path

from services.pdf_service import extract_pdf_pages
from services.text_splitter import split_pages_into_chunks
from services.vector_store_service import (
    search_similar_chunks,
    store_chunks,
)


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

        stored_chunks = store_chunks(chunks)

        print(
            f"{stored_chunks} segments ont été enregistrés "
            "dans ChromaDB."
        )

        question = "Quels sont les rôles des aliments ?"

        print(f"\nQuestion : {question}")

        results = search_similar_chunks(
            question,
            number_of_results=3,
        )

        if not results:
            print("Aucun segment pertinent n'a été trouvé.")
            return

        for position, result in enumerate(results, start=1):
            print(f"\nRésultat {position}")
            print(f"Source : {result['source']}")
            print(f"Page : {result['page']}")
            print(
                f"Numéro du segment : "
                f"{result['chunk_number']}"
            )
            print(f"Distance : {result['distance']:.4f}")
            print(f"Texte :\n{result['text'][:600]}")

    except Exception as error:
        print(
            "Une erreur est survenue pendant le test "
            f"de ChromaDB : {error}"
        )


if __name__ == "__main__":
    main()