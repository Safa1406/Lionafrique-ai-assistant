import re


def normalize_text_for_chunking(text: str) -> str:
    """
    Normalise le texte avant son découpage en segments.
    """

    if not text:
        return ""

    # Remplacer les retours à la ligne par des espaces.
    normalized_text = text.replace("\r\n", "\n")
    normalized_text = normalized_text.replace("\r", "\n")
    normalized_text = normalized_text.replace("\n", " ")

    # Réduire les espaces successifs.
    normalized_text = re.sub(r"[ \t]+", " ", normalized_text)

    return normalized_text.strip()


def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[str]:
    """
    Divise un texte en segments avec un léger chevauchement.
    """

    if chunk_size <= 0:
        raise ValueError(
            "La taille du segment doit être supérieure à zéro."
        )

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError(
            "Le chevauchement doit être positif et inférieur "
            "à la taille du segment."
        )

    normalized_text = normalize_text_for_chunking(text)

    if not normalized_text:
        return []

    chunks = []
    start = 0
    text_length = len(normalized_text)

    while start < text_length:
        end = min(start + chunk_size, text_length)

        if end < text_length:
            last_space = normalized_text.rfind(" ", start, end)

            if last_space > start:
                end = last_space

        chunk = normalized_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = end - chunk_overlap

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def split_pages_into_chunks(
    pages: list[dict],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[dict]:
    """
    Divise les pages en segments tout en conservant leurs métadonnées.
    """

    document_chunks = []

    for page in pages:
        page_chunks = split_text(
            page["text"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for chunk_index, chunk_text in enumerate(
            page_chunks,
            start=1,
        ):
            document_chunks.append(
                {
                    "chunk_id": (
                        f"{page['source']}"
                        f"-page-{page['page']}"
                        f"-segment-{chunk_index}"
                    ),
                    "source": page["source"],
                    "page": page["page"],
                    "chunk_number": chunk_index,
                    "text": chunk_text,
                }
            )

    return document_chunks