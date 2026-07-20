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


def build_chunk_metadata(chunk: dict) -> dict:
    """
    Prépare les métadonnées autorisées pour ChromaDB.
    """

    metadata_fields = (
        "source",
        "relative_path",
        "document_id",
        "program",
        "subject",
        "semester",
        "page",
        "chunk_number",
    )

    return {
        field: chunk[field]
        for field in metadata_fields
        if field in chunk
        and chunk[field] is not None
        and chunk[field] != ""
    }


def store_chunks(
    chunks: list[dict],
    batch_size: int = 32,
) -> int:
    """
    Enregistre les segments par lots dans ChromaDB.
    """

    if not chunks:
        return 0

    if batch_size <= 0:
        raise ValueError(
            "La taille du lot doit être supérieure à zéro."
        )

    collection = get_document_collection()
    stored_chunks = 0

    for start_index in range(0, len(chunks), batch_size):
        batch = chunks[start_index:start_index + batch_size]

        texts = [
            chunk["text"]
            for chunk in batch
        ]

        embeddings = generate_passage_embeddings(texts)

        ids = [
            chunk["chunk_id"]
            for chunk in batch
        ]

        metadatas = [
            build_chunk_metadata(chunk)
            for chunk in batch
        ]

        collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        stored_chunks += len(batch)

    return stored_chunks


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
        n_results=min(
            number_of_results,
            collection.count(),
        ),
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
                "source": metadata.get(
                    "source",
                    "Source inconnue",
                ),
                "relative_path": metadata.get(
                    "relative_path",
                    "",
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
                "page": metadata.get("page", 0),
                "chunk_number": metadata.get(
                    "chunk_number",
                    0,
                ),
                "distance": float(distance),
            }
        )

    return matches