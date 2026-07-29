import re

from services.llm_service import (
    OLLAMA_MODEL,
    call_ollama,
    contains_arabic,
    normalize_text,
    tokenize_words,
)


FRENCH_SUMMARY_REFUSAL = (
    "Les documents disponibles ne contiennent pas "
    "assez d'informations pour produire un résumé fiable."
)

ARABIC_SUMMARY_REFUSAL = (
    "الوثائق المتوفرة لا تحتوي على معلومات كافية "
    "لإنتاج ملخص موثوق."
)

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "answerable": {
            "type": "boolean",
        },
        "selected_unit_ids": {
            "type": "array",
            "items": {
                "type": "integer",
            },
        },
    },
    "required": [
        "answerable",
        "selected_unit_ids",
    ],
}

STOP_WORDS = {
    # Français
    "alors",
    "avec",
    "avoir",
    "aux",
    "car",
    "ces",
    "cette",
    "comme",
    "dans",
    "des",
    "donc",
    "dont",
    "elle",
    "elles",
    "entre",
    "est",
    "etre",
    "ils",
    "leurs",
    "mais",
    "moins",
    "nous",
    "plus",
    "pour",
    "que",
    "quel",
    "quelle",
    "quelles",
    "quels",
    "qui",
    "sans",
    "sont",
    "sur",
    "tous",
    "tout",
    "toutes",
    "une",
    "vous",
    # Arabe
    "الى",
    "او",
    "ان",
    "اي",
    "بعد",
    "بين",
    "ثم",
    "ذلك",
    "عن",
    "على",
    "في",
    "قبل",
    "كل",
    "كيف",
    "لا",
    "ما",
    "ماذا",
    "من",
    "هل",
    "هي",
    "هو",
    "هذا",
    "هذه",
    "هناك",
}

DEPENDENT_PREFIXES = (
    "il ",
    "ils ",
    "elle ",
    "elles ",
    "cela ",
    "ceci ",
    "ce dernier ",
    "cette derniere ",
    "ces derniers ",
    "ces dernieres ",
    "ceux ci ",
    "celles ci ",
    "وهو ",
    "وهي ",
    "وهذا ",
    "وهذه ",
    "كما ",
)

NOISE_PREFIXES = (
    "objectif",
    "objectifs",
    "competence",
    "competences",
    "professeur",
    "enseignant",
    "niveau",
    "duree",
    "activite",
    "exercice",
    "consigne",
    "الهدف",
    "الاهداف",
    "الكفاية",
    "الكفايات",
    "الاستاذ",
    "المستوى",
    "المدة",
    "النشاط",
    "التمرين",
    "التعليمة",
)

SENTENCE_BOUNDARY_PATTERN = re.compile(
    r"(?<=[.!?؟؛])(?:\s+|(?=[^\s]))"
)

ARABIC_DANGLING_ENDING_PATTERN = re.compile(
    r"(?:\s|^)(?:الذي|التي|الذين|اللاتي|اللذان|اللتان)\s*[.!؟]?$"
)

ARABIC_NEW_SENTENCE_PREFIXES = (
    "المدح ",
    "الذم ",
    "يتكون ",
    "يستعمل ",
    "يستخدم ",
    "ياتي ",
    "يعرب ",
    "المخصوص ",
    "تستعمل ",
    "فاعل ",
    "فعل ",
    "الصنف ",
    "اما ",
    "واما ",
    "كما ",
    "ملحوظه ",
)

PEDAGOGICAL_PREFIXES = (
    "تعريف ",
    "يتكون ",
    "يستعمل ",
    "يستخدم ",
    "ياتي ",
    "يعرب ",
    "المخصوص ",
    "تستعمل ",
    "ينقسم ",
    "تتمثل ",
    "تشمل ",
)


def get_summary_refusal(
    question: str,
) -> str:
    """Retourne le message de refus dans la langue de la demande."""

    if contains_arabic(
        question
    ):
        return ARABIC_SUMMARY_REFUSAL

    return FRENCH_SUMMARY_REFUSAL


def normalize_spaces(
    text: str,
) -> str:
    """Normalise les espaces d'une phrase."""

    return re.sub(
        r"[ \t]+",
        " ",
        text,
    ).strip()


def clean_sentence(
    sentence: str,
) -> str:
    """Nettoie une unité sans ajouter d'information."""

    cleaned_sentence = normalize_spaces(
        sentence
    )

    cleaned_sentence = cleaned_sentence.strip(
        " \t\r\n-•▪◦"
    )

    return cleaned_sentence


def is_noise_sentence(
    sentence: str,
) -> bool:
    """Détecte les unités administratives sans contenu pédagogique."""

    normalized_sentence = normalize_text(
        sentence
    )

    if not normalized_sentence:
        return True

    if normalized_sentence.startswith(
        NOISE_PREFIXES
    ):
        return True

    if normalized_sentence in {
        "sommaire",
        "page",
        "استنتاج",
        "ملحوظه",
        "الملخص",
    }:
        return True

    if (
        "اللغه العربيه" in normalized_sentence
        and "الدروس اللغويه" in normalized_sentence
    ):
        return True

    return False


def split_long_sentence(
    sentence: str,
    maximum_words: int = 70,
) -> list[str]:
    """Découpe une phrase anormalement longue par groupes de mots."""

    words = sentence.split()

    if len(words) <= maximum_words:
        return [
            sentence
        ]

    parts = []

    for start_index in range(
        0,
        len(words),
        maximum_words,
    ):
        part = " ".join(
            words[
                start_index:
                start_index + maximum_words
            ]
        ).strip()

        if part:
            parts.append(
                part
            )

    return parts


def split_into_sentences(
    text: str,
) -> list[str]:
    """Découpe un passage en phrases françaises ou arabes cohérentes."""

    if not text:
        return []

    normalized_text = text.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    )

    logical_paragraphs = []
    current_lines = []

    def flush_current_lines() -> None:
        if not current_lines:
            return

        paragraph = normalize_spaces(
            " ".join(
                current_lines
            )
        )

        if paragraph:
            logical_paragraphs.append(
                paragraph
            )

        current_lines.clear()

    for raw_line in normalized_text.split(
        "\n"
    ):
        line = clean_sentence(
            raw_line
        )

        if not line:
            flush_current_lines()
            continue

        if is_noise_sentence(
            line
        ):
            flush_current_lines()
            continue

        word_count = len(
            line.split()
        )

        is_short_heading = (
            word_count <= 10
            and line[-1]
            not in ".!?؟؛"
            and ":" not in line
        )

        if is_short_heading:
            flush_current_lines()
            continue

        line_is_arabic = contains_arabic(
            line
        )

        previous_line = (
            current_lines[-1]
            if current_lines
            else ""
        )

        should_continue_previous = (
            bool(current_lines)
            and (
                starts_with_dependent_expression(
                    line
                )
                or previous_line.endswith(
                    (",", "،", ":", ";", "؛", "(")
                )
            )
        )

        normalized_line = normalize_text(
            line
        )

        # Certains PDF arabes perdent le point final mais conservent
        # le début clair de la phrase suivante sur une nouvelle ligne.
        if (
            current_lines
            and line_is_arabic
            and not should_continue_previous
            and normalized_line.startswith(
                ARABIC_NEW_SENTENCE_PREFIXES
            )
        ):
            flush_current_lines()

        current_lines.append(
            line
        )

        if line[-1] in ".!?؟؛":
            flush_current_lines()

    flush_current_lines()

    sentences = []

    for paragraph in logical_paragraphs:
        paragraph_parts = [
            part.strip()
            for part in SENTENCE_BOUNDARY_PATTERN.split(
                paragraph
            )
            if part.strip()
        ]

        if not paragraph_parts:
            paragraph_parts = [
                paragraph
            ]

        for paragraph_part in paragraph_parts:
            for sentence in split_long_sentence(
                paragraph_part
            ):
                cleaned_sentence = clean_sentence(
                    sentence
                )

                if len(
                    cleaned_sentence.split()
                ) < 2:
                    continue

                sentences.append(
                    cleaned_sentence
                )

    return sentences

def starts_with_dependent_expression(
    sentence: str,
) -> bool:
    """Vérifie si une phrase dépend de la précédente."""

    normalized_sentence = normalize_text(
        sentence
    )

    return normalized_sentence.startswith(
        DEPENDENT_PREFIXES
    )


def build_summary_units(
    passages: list[dict],
) -> list[dict]:
    """Construit des unités pédagogiques cohérentes."""

    units = []
    unit_id = 1

    for passage_number, passage in enumerate(
        passages,
        start=1,
    ):
        sentences = split_into_sentences(
            passage.get(
                "text",
                "",
            )
        )

        passage_units = []

        for sentence in sentences:
            if (
                passage_units
                and starts_with_dependent_expression(
                    sentence
                )
            ):
                passage_units[-1]["text"] = (
                    passage_units[-1]["text"].rstrip()
                    + " "
                    + sentence
                )
                continue

            passage_units.append(
                {
                    "unit_id": unit_id,
                    "passage_number": (
                        passage_number
                    ),
                    "text": sentence,
                    "source": passage.get(
                        "source",
                        "Source inconnue",
                    ),
                    "page": passage.get(
                        "page",
                        0,
                    ),
                    "relative_path": passage.get(
                        "relative_path",
                        "",
                    ),
                    "retrieval_score": float(
                        passage.get(
                            "retrieval_score",
                            0.0,
                        )
                    ),
                }
            )

            unit_id += 1

        units.extend(
            passage_units
        )

    return units


def build_summary_context(
    units: list[dict],
) -> str:
    """Prépare les unités numérotées envoyées au modèle."""

    context_parts = []

    for unit in units:
        context_parts.append(
            (
                f"UNITÉ {unit['unit_id']}\n"
                f"Passage : {unit['passage_number']}\n"
                f"Source : {unit['source']}\n"
                f"Page : {unit['page']}\n"
                f"Texte exact : {unit['text']}"
            )
        )

    return "\n\n".join(
        context_parts
    )


def extract_keywords(
    text: str,
) -> set[str]:
    """Extrait les mots significatifs latins et arabes."""

    normalized_stop_words = {
        normalize_text(
            word
        )
        for word in STOP_WORDS
    }

    keywords = set()

    for word in tokenize_words(
        text
    ):
        if word in normalized_stop_words:
            continue

        if contains_arabic(
            word
        ):
            if len(word) >= 2:
                keywords.add(
                    word
                )
        elif len(word) >= 3:
            keywords.add(
                word
            )

    return keywords


def calculate_relevance_score(
    text: str,
    question: str,
) -> float:
    """Calcule la proximité lexicale entre une unité et le sujet."""

    text_keywords = extract_keywords(
        text
    )
    question_keywords = extract_keywords(
        question
    )

    if not text_keywords or not question_keywords:
        return 0.0

    common_keywords = (
        text_keywords
        & question_keywords
    )

    if not common_keywords:
        return 0.0

    question_coverage = (
        len(common_keywords)
        / len(question_keywords)
    )

    text_coverage = (
        len(common_keywords)
        / len(text_keywords)
    )

    return (
        question_coverage * 0.8
        + text_coverage * 0.2
    )


def calculate_similarity(
    first_text: str,
    second_text: str,
) -> float:
    """Calcule une similarité lexicale de Jaccard."""

    first_keywords = extract_keywords(
        first_text
    )
    second_keywords = extract_keywords(
        second_text
    )

    if not first_keywords or not second_keywords:
        return 0.0

    union = (
        first_keywords
        | second_keywords
    )

    if not union:
        return 0.0

    return (
        len(
            first_keywords
            & second_keywords
        )
        / len(union)
    )


def calculate_quality_score(
    text: str,
) -> float:
    """Évalue la lisibilité d'une unité extraite du PDF."""

    original_text = normalize_spaces(
        text
    )

    if ARABIC_DANGLING_ENDING_PATTERN.search(
        original_text
    ):
        return 0.05

    cleaned_text = original_text

    if contains_arabic(
        cleaned_text
    ):
        cleaned_text = clean_arabic_display_text(
            cleaned_text
        )

    word_count = len(
        cleaned_text.split()
    )

    if word_count < 4:
        return 0.05

    parenthesis_balance = 0
    invalid_parenthesis_order = False

    for character in cleaned_text:
        if character == "(":
            parenthesis_balance += 1
        elif character == ")":
            if parenthesis_balance == 0:
                invalid_parenthesis_order = True
                break

            parenthesis_balance -= 1

    if parenthesis_balance != 0:
        invalid_parenthesis_order = True

    parenthesis_penalty = (
        0.70
        if invalid_parenthesis_order
        else 0.0
    )

    if word_count <= 32:
        base_score = 1.0
    elif word_count <= 45:
        base_score = 0.75
    elif word_count <= 55:
        base_score = 0.35
    else:
        base_score = 0.10

    return max(
        0.0,
        base_score
        - parenthesis_penalty,
    )

def normalize_selected_ids(
    selected_ids: list,
) -> list[int]:
    """Nettoie les identifiants retournés par le modèle."""

    normalized_ids = []

    for raw_id in selected_ids:
        if isinstance(
            raw_id,
            int,
        ):
            unit_id = raw_id
        elif (
            isinstance(
                raw_id,
                str,
            )
            and raw_id.isdigit()
        ):
            unit_id = int(
                raw_id
            )
        else:
            continue

        if unit_id not in normalized_ids:
            normalized_ids.append(
                unit_id
            )

    return normalized_ids


def select_diverse_units(
    question: str,
    units: list[dict],
    preferred_unit_ids: list[int],
    maximum_units: int = 5,
) -> list[dict]:
    """Sélectionne des unités pertinentes, variées et lisibles."""

    preferred_positions = {
        unit_id: position
        for position, unit_id in enumerate(
            preferred_unit_ids
        )
    }

    scored_units = []

    for unit in units:
        relevance_score = calculate_relevance_score(
            text=unit["text"],
            question=question,
        )

        quality_score = calculate_quality_score(
            unit["text"]
        )

        retrieval_score = max(
            0.0,
            min(
                1.0,
                unit.get(
                    "retrieval_score",
                    0.0,
                )
                / 2.0,
            ),
        )

        preferred_bonus = 0.0

        if unit["unit_id"] in preferred_positions:
            preferred_bonus = (
                0.35
                / (
                    preferred_positions[
                        unit["unit_id"]
                    ]
                    + 1
                )
            )

        normalized_unit_text = normalize_text(
            unit["text"]
        )

        pedagogical_bonus = (
            0.45
            if normalized_unit_text.startswith(
                PEDAGOGICAL_PREFIXES
            )
            else 0.0
        )

        base_score = (
            relevance_score * 0.50
            + retrieval_score * 0.15
            + quality_score * 0.15
            + preferred_bonus
            + pedagogical_bonus
        )

        if quality_score < 0.10:
            continue

        scored_units.append(
            {
                "unit": unit,
                "base_score": base_score,
                "relevance_score": (
                    relevance_score
                ),
                "quality_score": (
                    quality_score
                ),
            }
        )

    strong_units_count = sum(
        1
        for item in scored_units
        if item["quality_score"] >= 0.80
    )

    if strong_units_count >= 3:
        scored_units = [
            item
            for item in scored_units
            if item["quality_score"] >= 0.80
        ]

    selected_units = []
    remaining_units = sorted(
        scored_units,
        key=lambda item: item[
            "base_score"
        ],
        reverse=True,
    )

    while (
        remaining_units
        and len(selected_units)
        < maximum_units
    ):
        best_item = None
        best_final_score = -1.0

        for item in remaining_units:
            unit = item["unit"]

            if selected_units:
                maximum_similarity = max(
                    calculate_similarity(
                        unit["text"],
                        selected_unit["text"],
                    )
                    for selected_unit in selected_units
                )
            else:
                maximum_similarity = 0.0

            if maximum_similarity >= 0.88:
                continue

            novelty_score = (
                1.0
                - maximum_similarity
            )

            final_score = (
                item["base_score"]
                + novelty_score * 0.15
            )

            if final_score > best_final_score:
                best_final_score = final_score
                best_item = item

        if best_item is None:
            break

        if (
            selected_units
            and best_final_score < 0.28
        ):
            break

        selected_units.append(
            best_item["unit"]
        )
        remaining_units.remove(
            best_item
        )

    selected_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )

    return selected_units


def clean_arabic_display_text(
    text: str,
) -> str:
    """Corrige les artefacts RTL courants sans changer le sens."""

    cleaned_text = normalize_spaces(
        text
    )

    # Artefact RTL fréquent : « أو) الذم (» devient « أو الذم ».
    cleaned_text = re.sub(
        r"\bأو\)\s*([^()]{1,30}?)\s*\(",
        r"أو \1",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\bأو\)\s*([^()،؛.!؟]{1,30})(?=[،؛.!؟]|$)",
        r"أو \1",
        cleaned_text,
    )

    # Artefacts RTL fréquents autour de deux termes coordonnés.
    cleaned_text = re.sub(
        r"\(([^()]+)\)\s*([^()]+)\)و\s*\(",
        r"\1 و\2 ",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\(\(([^()]+)\)([^()]+)\)و",
        r"\1 و\2",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\bب\s+\(([^()]+)\)",
        r"بـ(\1)",
        cleaned_text,
    )

    # Supprime les virgules placées par erreur après une préposition.
    cleaned_text = re.sub(
        r"\b(من|إلى|على|في|عن|مع|لا|ولا|ثم|أو)\s*،\s*",
        r"\1 ",
        cleaned_text,
    )

    cleaned_text = cleaned_text.replace(
        "وفاعله ثم",
        "وفاعله، ثم",
    )

    common_merged_forms = {
        "وفاعله،ثم": "وفاعله، ثم",
        "ضميرامستترا": "ضميرا مستترا",
        "ضميرمستتر": "ضمير مستتر",
    }

    for merged_form, corrected_form in (
        common_merged_forms.items()
    ):
        cleaned_text = cleaned_text.replace(
            merged_form,
            corrected_form,
        )

    cleaned_text = re.sub(
        r"\s+([،؛؟.!,:;])",
        r"\1",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"([،؛,:;])(?=\S)",
        r"\1 ",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\(\s+",
        "(",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\s+\)",
        ")",
        cleaned_text,
    )

    # Si l'extraction a laissé un pronom relatif sans complément,
    # on retire uniquement ce fragment final incomplet.
    cleaned_text = ARABIC_DANGLING_ENDING_PATTERN.sub(
        "",
        cleaned_text,
    ).rstrip(
        " ،؛,:;-"
    )

    return normalize_spaces(
        cleaned_text
    )


def prepare_display_text(
    text: str,
) -> str:
    """Améliore uniquement la présentation de l'unité sélectionnée."""

    display_text = normalize_spaces(
        text
    )

    display_text = display_text.replace(
        "bâtiseurs",
        "bâtisseurs",
    ).replace(
        "Bâtiseurs",
        "Bâtisseurs",
    )

    if contains_arabic(
        display_text
    ):
        display_text = clean_arabic_display_text(
            display_text
        )
    elif (
        display_text
        and display_text[0].isalpha()
    ):
        display_text = (
            display_text[0].upper()
            + display_text[1:]
        )

    if (
        display_text
        and display_text[-1]
        not in ".!?؟"
    ):
        display_text += "."

    return display_text

def format_summary(
    selected_units: list[dict],
    question: str,
) -> str:
    """Transforme les unités sélectionnées en résumé lisible."""

    formatted_points = []

    for unit in selected_units:
        display_text = prepare_display_text(
            unit.get(
                "text",
                "",
            )
        )

        if display_text:
            formatted_points.append(
                f"- {display_text}"
            )

    if not formatted_points:
        return get_summary_refusal(
            question
        )

    title = (
        "ملخص المحتوى:"
        if contains_arabic(
            question
        )
        else "Résumé du contenu :"
    )

    return (
        title
        + "\n"
        + "\n".join(
            formatted_points
        )
    )


def build_summary_sources(
    selected_units: list[dict],
) -> list[dict]:
    """Construit la liste unique des sources utilisées."""

    sources = []

    for unit in selected_units:
        source = {
            "file": unit.get(
                "source",
                "Source inconnue",
            ),
            "page": unit.get(
                "page",
                0,
            ),
            "relative_path": unit.get(
                "relative_path",
                "",
            ),
        }

        if source not in sources:
            sources.append(
                source
            )

    return sources


def build_summary_response(
    selected_units: list[dict],
    question: str,
) -> dict:
    """Construit la réponse finale du résumé."""

    summary = format_summary(
        selected_units,
        question,
    )

    refusal = get_summary_refusal(
        question
    )

    if summary == refusal:
        return {
            "answerable": False,
            "summary": refusal,
            "sources": [],
            "evidence": [],
        }

    return {
        "answerable": True,
        "summary": summary,
        "sources": build_summary_sources(
            selected_units
        ),
        "evidence": [
            unit["text"]
            for unit in selected_units
        ],
    }


SUMMARY_SERVICE_VERSION = (
    "v4-arabic-topic-linked-coverage"
)


ARABIC_SUMMARY_REQUEST_WORDS = {
    normalize_text(word)
    for word in {
        "لخص",
        "تلخيص",
        "ملخص",
        "ملخصا",
        "ملخصاً",
        "قدم",
        "اعطني",
        "أعطني",
        "اكتب",
        "اشرح",
        "المحتوى",
        "الموضوع",
        "الدرس",
        "درس",
        "عن",
    }
}


ARABIC_NARROW_SUMMARY_MARKERS = {
    normalize_text(marker)
    for marker in {
        "تعريف",
        "عناصر",
        "مكونات",
        "حالات",
        "أنواع",
        "انواع",
        "أسباب",
        "اسباب",
        "نتائج",
        "مراحل",
        "دور",
        "وظيفة",
        "استعمال",
        "استخدام",
        "إعراب",
        "اعراب",
        "مقارنة",
        "الفرق",
    }
}


ARABIC_FOCUS_GROUPS = (
    {
        "markers": (
            "تعريف",
            "معنى",
            "ما هو",
        ),
        "evidence": (
            "تعريف",
            "يعني",
            "هو",
            "تعبير",
        ),
    },
    {
        "markers": (
            "عناصر",
            "مكونات",
            "يتكون",
        ),
        "evidence": (
            "عناصر",
            "يتكون",
            "مكونات",
            "فعل",
            "فاعل",
            "مخصوص",
        ),
    },
    {
        "markers": (
            "اعراب",
            "اعرب",
        ),
        "evidence": (
            "يعرب",
            "اعراب",
            "مبتدا",
            "موخر",
            "مرفوع",
            "منصوب",
            "مجرور",
            "خبر",
            "فاعل",
            "محل",
        ),
    },
    {
        "markers": (
            "حالات",
            "انواع",
            "صور",
        ),
        "evidence": (
            "ياتي",
            "حالات",
            "انواع",
            "معرف",
            "مضاف",
            "ضمير",
            "مستتر",
        ),
    },
    {
        "markers": (
            "استعمال",
            "استخدام",
            "متى",
        ),
        "evidence": (
            "يستعمل",
            "تستعمل",
            "استخدام",
            "استعمال",
            "مدح",
            "ذم",
        ),
    },
    {
        "markers": (
            "اسباب",
            "سبب",
            "لماذا",
        ),
        "evidence": (
            "سبب",
            "اسباب",
            "ينتج",
            "بسبب",
            "لان",
        ),
    },
    {
        "markers": (
            "نتائج",
            "اثار",
            "عواقب",
        ),
        "evidence": (
            "نتائج",
            "اثار",
            "عواقب",
            "ينتج",
            "يودي",
        ),
    },
    {
        "markers": (
            "مراحل",
            "خطوات",
        ),
        "evidence": (
            "مراحل",
            "مرحله",
            "خطوات",
            "اولا",
            "ثانيا",
            "اخيرا",
        ),
    },
    {
        "markers": (
            "دور",
            "وظيفه",
            "اهميه",
        ),
        "evidence": (
            "دور",
            "وظيفه",
            "اهميه",
            "يساهم",
            "يساعد",
        ),
    },
    {
        "markers": (
            "مقارنه",
            "الفرق",
            "قارن",
        ),
        "evidence": (
            "اما",
            "بينما",
            "الفرق",
            "يختلف",
            "مقارنه",
        ),
    },
)


def normalize_arabic_terms(
    terms: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        normalize_text(term)
        for term in terms
    )


def get_requested_arabic_focus_groups(
    question: str,
) -> list[dict]:
    """Détecte les sous-thèmes explicitement demandés."""

    normalized_question = normalize_text(
        question
    )

    requested_groups = []

    for group in ARABIC_FOCUS_GROUPS:
        markers = normalize_arabic_terms(
            group["markers"]
        )

        if any(
            marker in normalized_question
            for marker in markers
        ):
            requested_groups.append(
                {
                    "markers": markers,
                    "evidence": normalize_arabic_terms(
                        group["evidence"]
                    ),
                }
            )

    return requested_groups


def get_arabic_summary_focus_keywords(
    question: str,
) -> set[str]:
    """Extrait le sujet réel et ajoute ses variantes pédagogiques."""

    focus_keywords = {
        keyword
        for keyword in extract_keywords(
            question
        )
        if keyword
        not in ARABIC_SUMMARY_REQUEST_WORDS
    }

    for group in get_requested_arabic_focus_groups(
        question
    ):
        focus_keywords.update(
            group["evidence"]
        )

    return focus_keywords


def is_general_arabic_summary_request(
    question: str,
) -> bool:
    """Distingue le résumé du cours entier d'un résumé ciblé."""

    normalized_question = normalize_text(
        question
    )

    has_narrow_marker = bool(
        get_requested_arabic_focus_groups(
            question
        )
    )

    general_patterns = (
        "لخص درس",
        "ملخص درس",
        "تلخيص درس",
        "لخص المحتوى",
        "ملخص المحتوى",
        "لخص الموضوع",
    )

    return (
        any(
            normalize_text(pattern)
            in normalized_question
            for pattern in general_patterns
        )
        and not has_narrow_marker
    )


def score_arabic_unit_for_terms(
    unit: dict,
    terms: tuple[str, ...] | set[str],
) -> float:
    """Classe une unité avec des racines arabes simples et robustes."""

    normalized_text_value = normalize_text(
        unit.get(
            "text",
            "",
        )
    )

    hits = sum(
        1
        for term in terms
        if term
        and term in normalized_text_value
    )

    if hits == 0:
        return -1.0

    quality_score = calculate_quality_score(
        unit.get(
            "text",
            "",
        )
    )

    retrieval_score = float(
        unit.get(
            "retrieval_score",
            0.0,
        )
    )

    return (
        hits * 2.0
        + quality_score
        + retrieval_score * 0.10
    )


def rank_arabic_focused_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Classe les unités liées au sous-sujet demandé."""

    focus_keywords = (
        get_arabic_summary_focus_keywords(
            question
        )
    )

    if not focus_keywords:
        return units

    ranked_units = []

    for unit in units:
        score = score_arabic_unit_for_terms(
            unit,
            focus_keywords,
        )

        if score < 0:
            continue

        ranked_units.append(
            (
                score,
                unit,
            )
        )

    ranked_units.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        unit
        for _, unit in ranked_units
    ]


def get_arabic_topic_keywords(
    question: str,
) -> set[str]:
    """Extrait le thème demandé sans les mots de commande."""

    question_keywords = extract_keywords(
        question
    )

    normalized_markers = {
        marker
        for group in ARABIC_FOCUS_GROUPS
        for marker in normalize_arabic_terms(
            group["markers"]
        )
    }

    topic_keywords = set()

    for keyword in question_keywords:
        if keyword in ARABIC_SUMMARY_REQUEST_WORDS:
            continue

        is_focus_marker = any(
            marker in keyword
            or keyword in marker
            for marker in normalized_markers
        )

        if is_focus_marker:
            continue

        topic_keywords.add(
            keyword
        )

    return topic_keywords


def select_arabic_focused_units(
    question: str,
    units: list[dict],
    maximum_units: int = 2,
) -> list[dict]:
    """Couvre chaque sous-thème demandé avec une unité distincte."""

    requested_groups = (
        get_requested_arabic_focus_groups(
            question
        )
    )

    topic_keywords = (
        get_arabic_topic_keywords(
            question
        )
    )

    selected_units = []
    selected_ids = set()

    for group in requested_groups:
        candidates = []

        for unit in units:
            if unit["unit_id"] in selected_ids:
                continue

            score = score_arabic_unit_for_terms(
                unit,
                group["evidence"],
            )

            if score < 0:
                continue

            normalized_unit_text = (
                normalize_text(
                    unit.get(
                        "text",
                        "",
                    )
                )
            )

            topic_hits = sum(
                1
                for keyword in topic_keywords
                if keyword
                and keyword
                in normalized_unit_text
            )

            # Une unité doit couvrir le type demandé
            # tout en restant liée au thème de la question.
            score += topic_hits * 3.5

            candidates.append(
                (
                    score,
                    unit,
                )
            )

        if not candidates:
            continue

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        best_unit = candidates[0][1]
        selected_units.append(
            best_unit
        )
        selected_ids.add(
            best_unit["unit_id"]
        )

        if len(selected_units) >= maximum_units:
            break

    if len(selected_units) < maximum_units:
        for unit in rank_arabic_focused_units(
            question,
            units,
        ):
            if unit["unit_id"] in selected_ids:
                continue

            selected_units.append(
                unit
            )
            selected_ids.add(
                unit["unit_id"]
            )

            if len(selected_units) >= maximum_units:
                break

    selected_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )

    return selected_units


def remove_redundant_summary_units(
    units: list[dict],
) -> list[dict]:
    """Élimine les points qui répètent presque la même idée."""

    kept_units = []

    for unit in units:
        unit_keywords = extract_keywords(
            unit.get(
                "text",
                "",
            )
        )

        if not unit_keywords:
            continue

        is_redundant = False

        for kept_unit in kept_units:
            kept_keywords = extract_keywords(
                kept_unit.get(
                    "text",
                    "",
                )
            )

            smaller_count = min(
                len(unit_keywords),
                len(kept_keywords),
            )

            if smaller_count == 0:
                continue

            overlap = (
                len(
                    unit_keywords
                    & kept_keywords
                )
                / smaller_count
            )

            if overlap >= 0.72:
                is_redundant = True
                break

        if not is_redundant:
            kept_units.append(
                unit
            )

    return kept_units

def generate_summary(
    question: str,
    passages: list[dict],
) -> dict:
    """Produit un résumé extractif fiable en français ou en arabe."""

    cleaned_question = question.strip()
    refusal = get_summary_refusal(
        cleaned_question
    )

    if not cleaned_question:
        raise ValueError(
            "Le sujet du résumé ne peut pas être vide."
        )

    if not passages:
        return {
            "answerable": False,
            "summary": refusal,
            "sources": [],
            "evidence": [],
        }

    units = build_summary_units(
        passages
    )

    if not units:
        return {
            "answerable": False,
            "summary": refusal,
            "sources": [],
            "evidence": [],
        }

    if contains_arabic(
        cleaned_question
    ):
        is_general_request = (
            is_general_arabic_summary_request(
                cleaned_question
            )
        )

        if is_general_request:
            selected_units = (
                select_diverse_units(
                    question=cleaned_question,
                    units=units,
                    preferred_unit_ids=[],
                    maximum_units=5,
                )
            )

            selected_units = (
                remove_redundant_summary_units(
                    selected_units
                )[:4]
            )
        else:
            selected_units = (
                select_arabic_focused_units(
                    question=cleaned_question,
                    units=units,
                    maximum_units=2,
                )
            )

            selected_units = (
                remove_redundant_summary_units(
                    selected_units
                )
            )

        if not selected_units:
            return {
                "answerable": False,
                "summary": refusal,
                "sources": [],
                "evidence": [],
            }

        return build_summary_response(
            selected_units,
            cleaned_question,
        )

    context = build_summary_context(
        units
    )

    system_prompt = """
Tu sélectionnes les unités documentaires les plus importantes
pour produire un résumé pédagogique en français.

Règles obligatoires :

- Retourne uniquement les identifiants des unités fournies.
- Ne rédige aucune nouvelle phrase.
- Ne reformule aucune information.
- Sélectionne entre trois et six unités lorsque le contenu le permet.
- Sélectionne des idées complémentaires et directement liées au sujet.
- Évite les titres seuls, les répétitions et les éléments administratifs.
- N'invente jamais un identifiant.
- Si aucune unité ne correspond au sujet, utilise answerable=false.
""".strip()

    user_prompt = f"""
Sujet à résumer :

{cleaned_question}

Unités documentaires :

{context}

Sélectionne les unités les plus importantes et complémentaires.
""".strip()

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "format": SUMMARY_SCHEMA,
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0.0,
            "num_predict": 250,
        },
    }

    preferred_unit_ids = []

    try:
        result = call_ollama(
            payload
        )

        if result.get(
            "answerable",
            False,
        ):
            preferred_unit_ids = (
                normalize_selected_ids(
                    result.get(
                        "selected_unit_ids",
                        [],
                    )
                )
            )

    except Exception as error:
        print(
            "La sélection des unités a échoué, "
            "le classement déterministe sera utilisé : "
            f"{error}"
        )

    selected_units = select_diverse_units(
        question=cleaned_question,
        units=units,
        preferred_unit_ids=(
            preferred_unit_ids
        ),
        maximum_units=5,
    )

    if not selected_units:
        return {
            "answerable": False,
            "summary": refusal,
            "sources": [],
            "evidence": [],
        }

    return build_summary_response(
        selected_units,
        cleaned_question,
    )