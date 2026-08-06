import re


SENTENCE_BOUNDARY_PATTERN = re.compile(
    r"(?<=[.!?؟؛])(?:\s+|(?=[^\s]))"
)


def normalize_text_for_chunking(
    text: str,
) -> str:
    """Normalise le texte avant son découpage en conservant les lignes."""

    if not text:
        return ""

    normalized_text = text.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    )

    normalized_text = re.sub(
        r"[ \t]+",
        " ",
        normalized_text,
    )

    normalized_text = re.sub(
        r" *\n *",
        "\n",
        normalized_text,
    )

    normalized_text = re.sub(
        r"\n{3,}",
        "\n\n",
        normalized_text,
    )

    return normalized_text.strip()


def split_long_unit(
    unit: str,
    chunk_size: int,
) -> list[str]:
    """Découpe une unité trop longue sans couper les mots."""

    words = unit.split()

    if not words:
        return []

    parts = []
    current_words = []
    current_length = 0

    for word in words:
        additional_length = (
            len(word)
            + (
                1
                if current_words
                else 0
            )
        )

        if (
            current_words
            and current_length
            + additional_length
            > chunk_size
        ):
            parts.append(
                " ".join(
                    current_words
                )
            )

            current_words = [
                word
            ]
            current_length = len(
                word
            )
            continue

        current_words.append(
            word
        )
        current_length += (
            additional_length
        )

    if current_words:
        parts.append(
            " ".join(
                current_words
            )
        )

    return parts


def build_text_units(
    text: str,
    chunk_size: int,
) -> list[str]:
    """Construit des unités à partir des lignes et des phrases."""

    normalized_text = normalize_text_for_chunking(
        text
    )

    if not normalized_text:
        return []

    units = []

    for raw_line in normalized_text.split(
        "\n"
    ):
        line = raw_line.strip()

        if not line:
            continue

        sentences = [
            sentence.strip()
            for sentence in SENTENCE_BOUNDARY_PATTERN.split(
                line
            )
            if sentence.strip()
        ]

        if not sentences:
            sentences = [
                line
            ]

        for sentence in sentences:
            if len(sentence) <= chunk_size:
                units.append(
                    sentence
                )
            else:
                units.extend(
                    split_long_unit(
                        unit=sentence,
                        chunk_size=chunk_size,
                    )
                )

    return units


def build_overlap_units(
    previous_units: list[str],
    chunk_overlap: int,
) -> list[str]:
    """Sélectionne les dernières unités nécessaires au chevauchement."""

    if chunk_overlap <= 0:
        return []

    overlap_units = []
    overlap_length = 0

    for unit in reversed(
        previous_units
    ):
        additional_length = (
            len(unit)
            + (
                1
                if overlap_units
                else 0
            )
        )

        if (
            overlap_units
            and overlap_length
            + additional_length
            > chunk_overlap
        ):
            break

        overlap_units.insert(
            0,
            unit,
        )

        overlap_length += (
            additional_length
        )

        if overlap_length >= chunk_overlap:
            break

    return overlap_units


def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[str]:
    """Divise un texte en segments en respectant lignes et phrases."""

    if chunk_size <= 0:
        raise ValueError(
            "La taille du segment doit être supérieure à zéro."
        )

    if (
        chunk_overlap < 0
        or chunk_overlap
        >= chunk_size
    ):
        raise ValueError(
            "Le chevauchement doit être positif et inférieur "
            "à la taille du segment."
        )

    units = build_text_units(
        text=text,
        chunk_size=chunk_size,
    )

    if not units:
        return []

    chunks = []
    current_units = []
    current_length = 0

    for unit in units:
        additional_length = (
            len(unit)
            + (
                1
                if current_units
                else 0
            )
        )

        if (
            current_units
            and current_length
            + additional_length
            > chunk_size
        ):
            chunk = "\n".join(
                current_units
            ).strip()

            if chunk:
                chunks.append(
                    chunk
                )

            overlap_units = build_overlap_units(
                previous_units=current_units,
                chunk_overlap=chunk_overlap,
            )

            current_units = list(
                overlap_units
            )

            current_length = len(
                "\n".join(
                    current_units
                )
            )

        if current_units:
            current_length += 1

        current_units.append(
            unit
        )
        current_length += len(
            unit
        )

    final_chunk = "\n".join(
        current_units
    ).strip()

    if final_chunk:
        chunks.append(
            final_chunk
        )

    unique_chunks = []
    seen_chunks = set()

    for chunk in chunks:
        if chunk in seen_chunks:
            continue

        seen_chunks.add(
            chunk
        )
        unique_chunks.append(
            chunk
        )

    return unique_chunks


def split_pages_into_chunks(
    pages: list[dict],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[dict]:
    """Divise les pages en segments en conservant leurs métadonnées."""

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
                    "chunk_number": (
                        chunk_index
                    ),
                    "text": chunk_text,
                }
            )

    return document_chunks
