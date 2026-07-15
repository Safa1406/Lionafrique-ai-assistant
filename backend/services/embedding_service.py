from sentence_transformers import SentenceTransformer


MODEL_NAME = "intfloat/multilingual-e5-small"

_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """
    Charge le modèle d'embeddings une seule fois.
    """

    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(MODEL_NAME)

    return _embedding_model


def generate_passage_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Génère les embeddings des segments de documents.
    """

    if not texts:
        return []

    model = get_embedding_model()

    prepared_texts = [
        f"passage: {text}"
        for text in texts
    ]

    embeddings = model.encode(
        prepared_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return embeddings.tolist()


def generate_query_embedding(question: str) -> list[float]:
    """
    Génère l'embedding d'une question utilisateur.
    """

    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError(
            "La question ne peut pas être vide."
        )

    model = get_embedding_model()

    embedding = model.encode(
        f"query: {cleaned_question}",
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return embedding.tolist()