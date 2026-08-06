import re
import unicodedata


ZERO_WIDTH_CHARACTERS = (
    "\u200b",
    "\u200c",
    "\u200d",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\ufeff",
)

ARABIC_DIACRITICS_PATTERN = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
)

ARABIC_CHARACTER_PATTERN = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF"
    r"\uFB50-\uFDFF\uFE70-\uFEFF]"
)

# Quelques caractères parasites observés dans certains PDF scolaires.
PDF_ARTIFACT_CHARACTERS = {
    "\u0229",  # ȩ
    "\u022a",  # Ȫ
    "\u022b",  # ȫ
    "\ufffe",
    "\uffff",
}


def contains_arabic(
    text: str,
) -> bool:
    """Vérifie si un texte contient des caractères arabes."""

    return bool(
        ARABIC_CHARACTER_PATTERN.search(
            text or ""
        )
    )


def remove_unsupported_characters(
    text: str,
) -> str:
    """
    Supprime les caractères de contrôle, les icônes privées
    et les marqueurs non Unicode qui polluent certains PDF.
    """

    cleaned_characters = []

    for character in text:
        if character in {
            "\n",
            "\t",
        }:
            cleaned_characters.append(
                character
            )
            continue

        if character in PDF_ARTIFACT_CHARACTERS:
            continue

        category = unicodedata.category(
            character
        )

        if category in {
            "Cc",
            "Cf",
            "Co",
            "Cs",
            "Cn",
        }:
            continue

        cleaned_characters.append(
            character
        )

    return "".join(
        cleaned_characters
    )


def remove_arabic_diacritics(
    text: str,
) -> str:
    """
    Retire les signes vocaliques arabes.

    Cette étape rend les textes extraits plus stables pour
    les embeddings et évite les lettres séparées par des harakats.
    """

    return ARABIC_DIACRITICS_PATTERN.sub(
        "",
        text,
    ).replace(
        "ـ",
        "",
    )


def clean_punctuation_spacing(
    text: str,
) -> str:
    """Corrige les espaces autour de la ponctuation latine et arabe."""

    cleaned_text = re.sub(
        r"[ \t]+([،؛؟!?.,:;%)\]»}])",
        r"\1",
        text,
    )

    cleaned_text = re.sub(
        r"([({\[«])[ \t]+",
        r"\1",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"([،؛,:;!?؟])(?=\S)",
        r"\1 ",
        cleaned_text,
    )

    return cleaned_text


def fix_reversed_parentheses(
    text: str,
) -> str:
    """
    Corrige une forme fréquente produite par les PDF RTL :
    ``نعم) .(`` devient ``(نعم).``.
    """

    return re.sub(
        (
            r"(?P<inside>[\w\u0600-\u06FF\u0750-\u077F"
            r"\u08A0-\u08FF]+)"
            r"\)\s*"
            r"(?P<ending>[.!؟])?"
            r"\s*\("
        ),
        lambda match: (
            f"({match.group('inside')})"
            f"{match.group('ending') or ''}"
        ),
        text,
    )


def fix_common_pdf_artifacts(
    text: str,
) -> str:
    """
    Corrige uniquement des erreurs d'extraction répétitives,
    sans ajouter de contenu absent du document.
    """

    cleaned_text = text

    replacements = {
        "1'énergie": "l'énergie",
        "1es": "les",
        "lls": "Ils",
        "Lesaliments": "Les aliments",
        "lesaliments": "les aliments",
        "richesen": "riches en",
        "فسنجددها": "فسنجدها",
        "أسلوبا المدح": "أسلوب المدح",
        "أسلوبا الذم": "أسلوب الذم",
        "نعمنعم": "نعم",
        "بئسبئس": "بئس",
    }

    for old_value, new_value in replacements.items():
        cleaned_text = cleaned_text.replace(
            old_value,
            new_value,
        )

    cleaned_text = fix_reversed_parentheses(
        cleaned_text
    )

    cleaned_text = re.sub(
        r"\b(نعم|بئس)\)\s+([^()\n]{2,50})\s+\(",
        r"(\1 \2) ",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\b(ثلاثة|أربعة|خمسة)\s*:\s*(عناصر)\b",
        r"\1 \2:",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"(المخصوص|ثم المخصوص)\s*\.\s*(بالمدح|بالذم)",
        r"\1 \2.",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"فاعل\s*،\s*(المدح|الذم)",
        r"فاعل \1،",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"المخصوص\s*:\s*(بالمدح|بالذم)",
        r"المخصوص \1:",
        cleaned_text,
    )

    return cleaned_text


def remove_symbol_only_lines(
    text: str,
) -> str:
    """Supprime les lignes qui ne contiennent que des icônes ou symboles."""

    useful_lines = []

    for line in text.split(
        "\n"
    ):
        stripped_line = line.strip()

        if not stripped_line:
            useful_lines.append(
                ""
            )
            continue

        if not any(
            character.isalnum()
            or contains_arabic(
                character
            )
            for character in stripped_line
        ):
            continue

        useful_lines.append(
            line
        )

    return "\n".join(
        useful_lines
    )


def clean_extracted_text(
    text: str,
) -> str:
    """Nettoie et normalise le texte extrait d'un fichier PDF."""

    if not text:
        return ""

    cleaned_text = unicodedata.normalize(
        "NFKC",
        text,
    )

    cleaned_text = remove_unsupported_characters(
        cleaned_text
    )

    for character in ZERO_WIDTH_CHARACTERS:
        cleaned_text = cleaned_text.replace(
            character,
            "",
        )

    cleaned_text = cleaned_text.replace(
        "\u00a0",
        " ",
    )

    cleaned_text = cleaned_text.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    )

    if contains_arabic(
        cleaned_text
    ):
        cleaned_text = remove_arabic_diacritics(
            cleaned_text
        )

    cleaned_text = re.sub(
        (
            r"([A-Za-zÀ-ÖØ-öø-ÿ])"
            r"-\n"
            r"([A-Za-zÀ-ÖØ-öø-ÿ])"
        ),
        r"\1\2",
        cleaned_text,
    )

    cleaned_text = fix_common_pdf_artifacts(
        cleaned_text
    )

    cleaned_text = clean_punctuation_spacing(
        cleaned_text
    )

    cleaned_text = re.sub(
        r"[ \t]+",
        " ",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r" *\n *",
        "\n",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned_text,
    )

    cleaned_text = remove_symbol_only_lines(
        cleaned_text
    )

    return cleaned_text.strip()


def normalize_arabic_for_search(
    text: str,
) -> str:
    """
    Produit une forme arabe stable pour la recherche lexicale.
    Le texte d'affichage original ne doit pas être remplacé par cette forme.
    """

    if not text:
        return ""

    normalized_text = clean_extracted_text(
        text
    )

    normalized_text = normalized_text.translate(
        str.maketrans(
            {
                "أ": "ا",
                "إ": "ا",
                "آ": "ا",
                "ٱ": "ا",
                "ى": "ي",
            }
        )
    )

    normalized_text = re.sub(
        r"\s+",
        " ",
        normalized_text,
    )

    return normalized_text.strip()
