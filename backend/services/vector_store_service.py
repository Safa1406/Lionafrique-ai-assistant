from pathlib import Path

import chromadb

from services.embedding_service import (
    generate_passage_embeddings,
    generate_query_embedding,
)


BACKEND_ROOT = Path(__file__).resolve().parent.parent
CHROMA_PATH = BACKEND_ROOT / "chroma_db"
COLLECTION_NAME = "lionafrique_documents"


def get_chroma_client():
    """
    Retourne le client local persistant de ChromaDB.
    """

    return chromadb.PersistentClient(
        path=str(CHROMA_PATH)
    )


def get_document_collection():
    """
    Retourne ou crée la collection
    des documents pédagogiques.
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


def build_chunk_metadata(
    chunk: dict,
) -> dict:
    """
    Prépare les métadonnées autorisées
    pour un segment ChromaDB.
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
    Enregistre les segments par lots
    dans ChromaDB.
    """

    if not chunks:
        return 0

    if batch_size <= 0:
        raise ValueError(
            "La taille du lot doit être supérieure à zéro."
        )

    collection = get_document_collection()
    stored_chunks = 0

    for start_index in range(
        0,
        len(chunks),
        batch_size,
    ):
        batch = chunks[
            start_index:start_index + batch_size
        ]

        texts = [
            chunk["text"]
            for chunk in batch
        ]

        embeddings = generate_passage_embeddings(
            texts
        )

        identifiers = [
            chunk["chunk_id"]
            for chunk in batch
        ]

        metadatas = [
            build_chunk_metadata(chunk)
            for chunk in batch
        ]

        collection.upsert(
            ids=identifiers,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        stored_chunks += len(batch)

    return stored_chunks


def clean_filter_value(
    value: str | None,
) -> str | None:
    """
    Nettoie une valeur de filtre facultative.
    """

    if value is None:
        return None

    cleaned_value = value.strip()

    if not cleaned_value:
        return None

    if cleaned_value.lower() in {
        "tous",
        "toutes",
        "all",
    }:
        return None

    return cleaned_value


def build_metadata_filter(
    program: str | None = None,
    subject: str | None = None,
    semester: str | None = None,
    source: str | None = None,
) -> dict | None:
    """
    Construit le filtre ChromaDB
    à partir des métadonnées sélectionnées.
    """

    cleaned_program = clean_filter_value(
        program
    )

    cleaned_subject = clean_filter_value(
        subject
    )

    cleaned_semester = clean_filter_value(
        semester
    )

    cleaned_source = clean_filter_value(
        source
    )

    conditions = []

    if cleaned_program:
        conditions.append(
            {
                "program": {
                    "$eq": cleaned_program
                }
            }
        )

    if cleaned_subject:
        conditions.append(
            {
                "subject": {
                    "$eq": cleaned_subject
                }
            }
        )

    if cleaned_semester:
        conditions.append(
            {
                "semester": {
                    "$eq": cleaned_semester
                }
            }
        )

    if cleaned_source:
        conditions.append(
            {
                "source": {
                    "$eq": cleaned_source
                }
            }
        )

    if not conditions:
        return None

    if len(conditions) == 1:
        return conditions[0]

    return {
        "$and": conditions
    }


def search_similar_chunks(
    question: str,
    number_of_results: int = 3,
    program: str | None = None,
    subject: str | None = None,
    semester: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """
    Recherche les segments les plus proches
    avec des filtres de métadonnées facultatifs.
    """

    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError(
            "La question ne peut pas être vide."
        )

    if number_of_results <= 0:
        raise ValueError(
            "Le nombre de résultats doit être supérieur à zéro."
        )

    collection = get_document_collection()
    collection_size = collection.count()

    if collection_size == 0:
        return []

    query_embedding = generate_query_embedding(
        cleaned_question
    )

    metadata_filter = build_metadata_filter(
        program=program,
        subject=subject,
        semester=semester,
        source=source,
    )

    query_arguments = {
        "query_embeddings": [
            query_embedding
        ],
        "n_results": min(
            number_of_results,
            collection_size,
        ),
        "include": [
            "documents",
            "metadatas",
            "distances",
        ],
    }

    if metadata_filter is not None:
        query_arguments["where"] = (
            metadata_filter
        )

    results = collection.query(
        **query_arguments
    )

    documents_groups = (
        results.get("documents")
        or [[]]
    )

    metadata_groups = (
        results.get("metadatas")
        or [[]]
    )

    distance_groups = (
        results.get("distances")
        or [[]]
    )

    identifier_groups = (
        results.get("ids")
        or [[]]
    )

    documents = documents_groups[0]
    metadatas = metadata_groups[0]
    distances = distance_groups[0]
    identifiers = identifier_groups[0]

    matches = []

    for (
        identifier,
        document,
        metadata,
        distance,
    ) in zip(
        identifiers,
        documents,
        metadatas,
        distances,
    ):
        metadata = metadata or {}

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
                "document_id": metadata.get(
                    "document_id",
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
                "page": metadata.get(
                    "page",
                    0,
                ),
                "chunk_number": metadata.get(
                    "chunk_number",
                    0,
                ),
                "distance": float(
                    distance
                ),
            }
        )

    return matches


def get_metadata_options() -> list[dict]:
    """
    Retourne les combinaisons disponibles
    de programme, matière et semestre.
    """

    collection = get_document_collection()

    if collection.count() == 0:
        return []

    results = collection.get(
        include=[
            "metadatas"
        ],
    )

    metadatas = results.get(
        "metadatas",
        [],
    )

    # METADATA_SOURCES_BY_SEMESTER_V2
    grouped_options: dict[
        tuple[str, str],
        dict[str, set[str]],
    ] = {}

    for metadata in metadatas:
        if not metadata:
            continue

        program = metadata.get(
            "program",
            "Non d?fini",
        )

        subject = metadata.get(
            "subject",
            "Non d?finie",
        )

        semester = metadata.get(
            "semester",
            "Non d?fini",
        )

        source = str(
            metadata.get(
                "source",
                "",
            )
            or ""
        ).strip()

        option_key = (
            program,
            subject,
        )

        if option_key not in grouped_options:
            grouped_options[
                option_key
            ] = {}

        if (
            semester
            not in grouped_options[
                option_key
            ]
        ):
            grouped_options[
                option_key
            ][semester] = set()

        if source:
            grouped_options[
                option_key
            ][semester].add(
                source
            )

    options = []

    for (
        program,
        subject,
    ), semester_sources in grouped_options.items():

        semesters = sorted(
            semester_sources.keys()
        )

        sources_by_semester = {
            semester: sorted(
                semester_sources[
                    semester
                ]
            )
            for semester
            in semesters
        }

        options.append(
            {
                "program": program,
                "subject": subject,
                "semesters": semesters,
                "sources_by_semester":
                    sources_by_semester,
            }
        )

    options.sort(
        key=lambda option: (
            option["program"].lower(),
            option["subject"].lower(),
        )
    )

    return options