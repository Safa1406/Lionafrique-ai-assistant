from pathlib import Path

import chromadb

from services.embedding_service import (
    generate_passage_embeddings,
    generate_query_embedding,
)


BACKEND_ROOT = Path(__file__).resolve().parent.parent
CHROMA_PATH = BACKEND_ROOT / "chroma_db"
COLLECTION_NAME = "lionafrique_documents"


def get_chroma_client() -> chromadb.PersistentClient:
    """
    Retourne le client local persistant de ChromaDB.
    """

    return chromadb.PersistentClient(
        path=str(CHROMA_PATH)
    )


def get_document_collection():
    """
    Retourne ou crée la collection des documents pédagogiques.
    """

    client = get_chroma_client()

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description": (
                "Documents pédagogiques de LionAfrique"
            )
        },
    )


def store_chunks(chunks: list[dict]) -> int:
    """
    Enregistre les segments et leurs embeddings dans ChromaDB.
    """

    if not chunks:
        return 0

    collection = get_document_collection()

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    embeddings = generate_passage_embeddings(texts)

    ids = [
        chunk["chunk_id"]
        for chunk in chunks
    ]

    metadatas = [
        {
            "source": chunk["source"],
            "page": chunk["page"],
            "chunk_number": chunk["chunk_number"],
        }
        for chunk in chunks
    ]

    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return len(chunks)


def search_similar_chunks(
    question: str,
    number_of_results: int = 3,
) -> list[dict]:
    """
    Recherche les segments les plus proches d'une question.
    """

    collection = get_document_collection()

    if collection.count() == 0:
        return []

    query_embedding = generate_query_embedding(question)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=number_of_results,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    matches = []

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    identifiers = results["ids"][0]

    for identifier, document, metadata, distance in zip(
        identifiers,
        documents,
        metadatas,
        distances,
    ):
        matches.append(
            {
                "chunk_id": identifier,
                "text": document,
                "source": metadata["source"],
                "page": metadata["page"],
                "chunk_number": metadata["chunk_number"],
                "distance": distance,
            }
        )

    return matches