from services.vector_store_service import (
    COLLECTION_NAME,
    get_chroma_client,
)


def get_collection_names(
    collections: list,
) -> set[str]:
    """
    Extrait les noms des collections
    selon la version de ChromaDB utilisée.
    """

    collection_names = set()

    for collection in collections:
        if isinstance(collection, str):
            collection_names.add(
                collection
            )
            continue

        collection_name = getattr(
            collection,
            "name",
            None,
        )

        if collection_name:
            collection_names.add(
                collection_name
            )

    return collection_names


def reset_vector_database() -> None:
    """
    Supprime uniquement la collection documentaire
    de ChromaDB.

    Les fichiers PDF ne sont pas supprimés.
    """

    client = get_chroma_client()

    existing_collections = (
        client.list_collections()
    )

    collection_names = get_collection_names(
        existing_collections
    )

    if COLLECTION_NAME not in collection_names:
        print(
            "La collection documentaire "
            "n'existe pas encore."
        )
        return

    client.delete_collection(
        name=COLLECTION_NAME
    )

    print(
        "La collection documentaire "
        "a été supprimée avec succès."
    )


if __name__ == "__main__":
    reset_vector_database()