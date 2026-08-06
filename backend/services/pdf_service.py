import re
import statistics
import unicodedata
from pathlib import Path

import fitz

from services.text_cleaner import (
    clean_extracted_text,
)


ARABIC_CHARACTER_PATTERN = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF"
    r"\uFB50-\uFDFF\uFE70-\uFEFF]"
)


def contains_arabic(
    text: str,
) -> bool:
    """Vérifie si un texte contient des caractères arabes."""

    return bool(
        ARABIC_CHARACTER_PATTERN.search(
            text or ""
        )
    )


def get_line_direction(
    text: str,
) -> str:
    """Détermine la direction principale d'une ligne."""

    arabic_count = 0
    latin_count = 0

    for character in text:
        direction = unicodedata.bidirectional(
            character
        )

        if direction in {
            "R",
            "AL",
        }:
            arabic_count += 1
        elif direction == "L":
            latin_count += 1

    if arabic_count > latin_count:
        return "rtl"

    return "ltr"


def normalize_fragment(
    text: str,
) -> str:
    """Normalise un fragment de texte sans modifier son ordre."""

    normalized_text = unicodedata.normalize(
        "NFKC",
        text,
    )

    normalized_text = "".join(
        character
        for character in normalized_text
        if unicodedata.category(
            character
        )
        not in {
            "Cc",
            "Cf",
            "Co",
            "Cs",
            "Cn",
        }
    )

    normalized_text = normalized_text.replace(
        "\ufffe",
        "",
    ).replace(
        "\uffff",
        "",
    )

    return normalized_text


def group_rtl_fragments(
    line_words: list[tuple],
) -> list[tuple[str, float, float]]:
    """
    Réunit les fragments graphiques appartenant au même mot arabe.

    Certains PDF découpent un mot arabe en plusieurs pseudo-mots.
    L'ordre d'origine est conservé à l'intérieur du mot, puis les mots
    sont classés de droite à gauche.
    """

    heights = [
        float(word[3]) - float(word[1])
        for word in line_words
    ]

    median_height = (
        statistics.median(
            heights
        )
        if heights
        else 12.0
    )

    gap_threshold = max(
        0.8,
        median_height * 0.08,
    )

    grouped_fragments = []
    current_fragments = []
    current_min_x = 0.0
    current_max_x = 0.0

    for word_data in line_words:
        fragment_text = normalize_fragment(
            str(
                word_data[4]
            )
        )

        if not fragment_text:
            continue

        x0 = float(
            word_data[0]
        )
        x1 = float(
            word_data[2]
        )

        if not current_fragments:
            current_fragments = [
                fragment_text
            ]
            current_min_x = x0
            current_max_x = x1
            continue

        jumps_to_right = (
            x0
            > current_max_x
            + gap_threshold
        )

        leaves_gap_to_left = (
            x1
            < current_min_x
            - gap_threshold
        )

        if (
            jumps_to_right
            or leaves_gap_to_left
        ):
            grouped_fragments.append(
                (
                    "".join(
                        current_fragments
                    ),
                    current_min_x,
                    current_max_x,
                )
            )

            current_fragments = [
                fragment_text
            ]
            current_min_x = x0
            current_max_x = x1
            continue

        current_fragments.append(
            fragment_text
        )

        current_min_x = min(
            current_min_x,
            x0,
        )

        current_max_x = max(
            current_max_x,
            x1,
        )

    if current_fragments:
        grouped_fragments.append(
            (
                "".join(
                    current_fragments
                ),
                current_min_x,
                current_max_x,
            )
        )

    grouped_fragments.sort(
        key=lambda group: group[2],
        reverse=True,
    )

    return grouped_fragments


def build_ltr_tokens(
    line_words: list[tuple],
) -> list[tuple[str, float, float]]:
    """Construit les mots d'une ligne latine de gauche à droite."""

    tokens = []

    for word_data in line_words:
        token_text = normalize_fragment(
            str(
                word_data[4]
            )
        )

        if not token_text:
            continue

        tokens.append(
            (
                token_text,
                float(
                    word_data[0]
                ),
                float(
                    word_data[2]
                ),
            )
        )

    tokens.sort(
        key=lambda token: token[1]
    )

    return tokens


def join_line_tokens(
    tokens: list[tuple[str, float, float]],
) -> str:
    """Réunit les mots d'une ligne et corrige les espaces simples."""

    line = " ".join(
        token[0].strip()
        for token in tokens
        if token[0].strip()
    )

    line = re.sub(
        r"\s+",
        " ",
        line,
    )

    return line.strip()


def extract_page_text_with_layout(
    page: fitz.Page,
) -> str:
    """
    Reconstruit le texte en tenant compte du sens RTL.

    La méthode évite d'insérer des espaces entre les fragments
    d'un même mot arabe, problème présent dans plusieurs PDF scolaires.
    """

    words = page.get_text(
        "words",
        sort=False,
    )

    if not words:
        return page.get_text(
            "text"
        )

    grouped_lines: dict[
        tuple[int, int],
        list[tuple],
    ] = {}

    for word_data in words:
        if len(word_data) < 8:
            continue

        block_number = int(
            word_data[5]
        )
        line_number = int(
            word_data[6]
        )

        grouped_lines.setdefault(
            (
                block_number,
                line_number,
            ),
            [],
        ).append(
            word_data
        )

    line_records = []

    for line_words in grouped_lines.values():
        raw_line_text = "".join(
            str(
                word[4]
            )
            for word in line_words
        )

        direction = get_line_direction(
            raw_line_text
        )

        if direction == "rtl":
            tokens = group_rtl_fragments(
                line_words
            )
        else:
            tokens = build_ltr_tokens(
                line_words
            )

        line_text = join_line_tokens(
            tokens
        )

        if not line_text:
            continue

        minimum_y = min(
            float(
                word[1]
            )
            for word in line_words
        )

        minimum_x = min(
            float(
                word[0]
            )
            for word in line_words
        )

        maximum_x = max(
            float(
                word[2]
            )
            for word in line_words
        )

        horizontal_order = (
            -maximum_x
            if direction == "rtl"
            else minimum_x
        )

        line_records.append(
            {
                "y": minimum_y,
                "horizontal_order": (
                    horizontal_order
                ),
                "text": line_text,
            }
        )

    line_records.sort(
        key=lambda line: (
            round(
                line["y"],
                1,
            ),
            line[
                "horizontal_order"
            ],
        )
    )

    return "\n".join(
        line["text"]
        for line in line_records
    )


def extraction_quality_score(
    text: str,
) -> float:
    """Évalue sommairement si le texte reconstruit est exploitable."""

    if not text.strip():
        return 0.0

    words = re.findall(
        r"\w+",
        text,
        flags=re.UNICODE,
    )

    if not words:
        return 0.0

    useful_words = sum(
        1
        for word in words
        if len(word) >= 2
    )

    isolated_arabic_letters = sum(
        1
        for word in words
        if (
            len(word) == 1
            and contains_arabic(
                word
            )
        )
    )

    return max(
        0.0,
        (
            useful_words
            - isolated_arabic_letters * 0.5
        )
        / len(words),
    )


def extract_page_text(
    page: fitz.Page,
) -> str:
    """Extrait le texte d'une page avec une stratégie adaptée à sa langue."""

    standard_text = page.get_text(
        "text"
    )

    if not contains_arabic(
        standard_text
    ):
        return standard_text

    reconstructed_text = (
        extract_page_text_with_layout(
            page
        )
    )

    if (
        reconstructed_text.strip()
        and extraction_quality_score(
            reconstructed_text
        )
        >= 0.45
    ):
        return reconstructed_text

    return standard_text


def extract_pdf_pages(
    pdf_path: str | Path,
) -> list[dict]:
    """Extrait et nettoie le texte de chaque page d'un fichier PDF."""

    path = Path(
        pdf_path
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Le fichier PDF est introuvable : {path}"
        )

    if path.suffix.lower() != ".pdf":
        raise ValueError(
            "Le fichier fourni n'est pas un fichier PDF."
        )

    extracted_pages = []

    with fitz.open(
        path
    ) as document:
        for page_index, page in enumerate(
            document
        ):
            raw_text = extract_page_text(
                page
            )

            text = clean_extracted_text(
                raw_text
            )

            extracted_pages.append(
                {
                    "source": path.name,
                    "page": page_index + 1,
                    "text": text,
                    "has_text": bool(
                        text
                    ),
                }
            )

    return extracted_pages


def get_pdf_summary(
    pdf_path: str | Path,
) -> dict:
    """Retourne un résumé technique du fichier PDF analysé."""

    pages = extract_pdf_pages(
        pdf_path
    )

    pages_with_text = sum(
        1
        for page in pages
        if page["has_text"]
    )

    return {
        "source": Path(
            pdf_path
        ).name,
        "total_pages": len(
            pages
        ),
        "pages_with_text": (
            pages_with_text
        ),
        "empty_pages": (
            len(pages)
            - pages_with_text
        ),
    }
