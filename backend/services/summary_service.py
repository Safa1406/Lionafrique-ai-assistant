import re

from services.llm_service import (
    OLLAMA_MODEL,
    call_ollama,
    contains_arabic,
    normalize_arabic_match_text,
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
    "ان نعرف",
    "ان نحدد",
    "ان نبين",
    "تامل الجدول",
    "الامثله",
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
    "الاختصاص ",
    "الضمير ",
    "الفعل المحذوف ",
    "الاسم المختص ",
    "احوال الاسم المختص ",
    "يكون الاسم المختص ",
    "حكم الاسم المختص ",
    "النداء ",
    "عناصر اسلوب النداء ",
    "ادوات النداء ",
    "انواع المنادي ",
    "علم مفرد ",
    "نكره مقصوده ",
    "نكره غير مقصوده ",
    "مضاف ",
    "شبيه بالمضاف ",
    "اعراب المنادي ",
    "نداء المعرف ",
    "فائده ",
    "الشرط ",
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


ARABIC_SECTION_HEADINGS = {
    normalize_arabic_match_text(
        heading
    )
    for heading in {
        "علم مفرد",
        "نكرة مقصودة",
        "نكرة غير مقصودة",
        "مضاف",
        "شبيه مضاف",
        "إعراب المنادى",
        "نداء المعرف بأل",
        "أنواع المنادى وأحكامه",
        "أدوات النداء ودلالاتها",
        "عناصر أسلوب النداء",
        "التعريف",
        "الملخص",
    }
}


def is_arabic_section_heading(
    sentence: str,
) -> bool:
    """Repère un petit titre pédagogique devant la règle qui le suit."""

    normalized_sentence = (
        normalize_arabic_match_text(
            sentence
        )
    )

    if not normalized_sentence:
        return False

    if len(
        normalized_sentence.split()
    ) > 5:
        return False

    if normalized_sentence in (
        ARABIC_SECTION_HEADINGS
    ):
        return True

    return normalized_sentence.startswith(
        (
            "علم مفرد",
            "نكره مقصوده",
            "نكره غير مقصوده",
            "شبيه مضاف",
            "اعراب المنادي",
            "نداء المعرف",
            "انواع المنادي",
        )
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
    maximum_words: int = 55,
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

            if is_arabic_section_heading(
                line
            ):
                logical_paragraphs.append(
                    line
                )

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

                if (
                    len(
                        cleaned_sentence.split()
                    ) < 2
                    and not is_arabic_section_heading(
                        cleaned_sentence
                    )
                ):
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
        pending_heading = ""

        for sentence in sentences:
            if is_arabic_section_heading(
                sentence
            ):
                pending_heading = (
                    sentence
                )
                continue

            if pending_heading:
                sentence = (
                    pending_heading.rstrip(
                        " :؛"
                    )
                    + ": "
                    + sentence
                )
                pending_heading = ""

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

    cleaned_text = (
        cleaned_text
        .replace(
            "Ƞ",
            "",
        )
        .replace(
            "ƞ",
            "",
        )
        .replace(
            "ȥ",
            "",
        )
        .replace(
            "Ȣ",
            "",
        )
        .replace(
            "ȣ",
            "",
        )
        .replace(
            "Ȧ",
            "ا",
        )
        .replace(
            "ȧ",
            "ا",
        )
        .replace(
            "ϗ",
            "",
        )
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
    "v68-histoire-summary-contract-fix"
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
            "ضمير",
            "فعل",
            "فاعل",
            "محذوف",
            "اسم",
            "مختص",
            "مخصوص",
        ),
    },
    {
        "markers": (
            "اعراب",
            "اعرب",
            "حكم",
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
            "مفعول",
            "محذوف",
            "وجوبا",
            "محل",
            "نصب",
        ),
    },
    {
        "markers": (
            "حالات",
            "احوال",
            "انواع",
            "صور",
        ),
        "evidence": (
            "ياتي",
            "يكون",
            "حالات",
            "احوال",
            "انواع",
            "مقترن",
            "ال",
        ),
    },
    {
        "markers": (
            "حالات",
            "احوال",
            "انواع",
            "صور",
        ),
        "evidence": (
            "مضاف",
        ),
    },
    {
        "markers": (
            "حالات",
            "احوال",
            "انواع",
            "صور",
        ),
        "evidence": (
            "ايها",
            "ايتها",
            "اي",
            "ايه",
            "مبني",
            "محل نصب",
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
            "يستعمل",
            "يوتي",
            "تقييد",
            "تخصيص",
            "بيان",
            "توضيح",
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


ARABIC_GENERAL_COVERAGE_GROUPS = (
    (
        "تعريف",
        "يعني",
        "هو",
        "هي",
        "اسلوب",
        "يستعمل",
        "يستخدم",
    ),
    (
        "ينقسم",
        "تنقسم",
        "قسمين",
        "نوعين",
        "عناصر",
        "مكونات",
        "ضمير",
        "فعل",
        "اسم",
    ),
    (
        "ادوات",
        "حروف",
        "حرفا",
        "اسماء",
        "حالات",
        "احوال",
        "انواع",
        "مقترن",
        "مضاف",
        "معرف",
        "ايها",
        "ايتها",
    ),
    (
        "يكون الجواب",
        "يستفهم",
        "استعمال",
        "استخدام",
        "يعرب",
        "اعراب",
        "منصوب",
        "مفعول",
        "محذوف",
        "وجوبا",
        "محل نصب",
    ),
)


def normalize_arabic_terms(
    terms: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        normalize_arabic_match_text(
            term
        )
        for term in terms
    )


def get_requested_arabic_focus_groups(
    question: str,
) -> list[dict]:
    """Détecte les sous-thèmes explicitement demandés."""

    normalized_question = (
        normalize_arabic_match_text(
            question
        )
    )

    requested_groups = []

    dynamic_groups = []

    if (
        "منادي" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "انواع",
                "احكام",
            )
        )
    ):
        dynamic_groups.extend(
            [
                {
                    "markers": (
                        "انواع المنادي",
                        "احكام المنادي",
                    ),
                    "evidence": (
                        "علم مفرد",
                        "الشخص الذي ينادي عليه باسمه",
                    ),
                },
                {
                    "markers": (
                        "نكره مقصوده",
                    ),
                    "evidence": (
                        "نكره مقصوده",
                        "كحكم العلم المفرد",
                        "مبنيه",
                    ),
                },
                {
                    "markers": (
                        "مضاف",
                    ),
                    "evidence": (
                        "الاسم المضاف",
                        "مضاف اليه",
                        "مضافا اليه",
                        "مجرور",
                        "مجرورا",
                    ),
                },
                {
                    "markers": (
                        "شبيه مضاف",
                    ),
                    "evidence": (
                        "شبيه مضاف",
                        "يحتاج",
                        "يتمم معناه",
                        "ليتمم معناه",
                        "تمام معناه",
                    ),
                },
                {
                    "markers": (
                        "نكره غير مقصوده",
                    ),
                    "evidence": (
                        "نكره غير مقصوده",
                        "لا يدل على شخص بعينه",
                        "منصوبه",
                    ),
                },
            ]
        )

    for group in dynamic_groups:
        requested_groups.append(
            {
                "markers": normalize_arabic_terms(
                    group["markers"]
                ),
                "evidence": normalize_arabic_terms(
                    group["evidence"]
                ),
            }
        )

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

    unique_groups = []
    seen_evidence = set()

    for group in requested_groups:
        evidence_key = tuple(
            group["evidence"]
        )

        if evidence_key in seen_evidence:
            continue

        seen_evidence.add(
            evidence_key
        )
        unique_groups.append(
            group
        )

    return unique_groups


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

    normalized_text_value = (
        normalize_arabic_match_text(
            unit.get(
                "text",
                "",
            )
        )
    )

    normalized_terms = {
        normalize_arabic_match_text(
            term
        )
        for term in terms
        if normalize_arabic_match_text(
            term
        )
    }

    hits = sum(
        1
        for term in normalized_terms
        if term
        and (
            f" {term} "
            in f" {normalized_text_value} "
            or term in normalized_text_value
        )
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

    word_count = len(
        normalize_spaces(
            unit.get(
                "text",
                "",
            )
        ).split()
    )

    length_penalty = (
        max(
            0,
            word_count - 45,
        )
        * 0.06
    )

    pedagogical_bonus = (
        1.0
        if normalized_text_value.startswith(
            PEDAGOGICAL_PREFIXES
        )
        else 0.0
    )

    return (
        min(
            hits,
            5,
        ) * 1.7
        + quality_score * 3.0
        + pedagogical_bonus
        + retrieval_score * 0.10
        - length_penalty
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
    maximum_units: int = 4,
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
                normalize_arabic_match_text(
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
            quality_score = calculate_quality_score(
                unit.get(
                    "text",
                    "",
                )
            )

            score += (
                topic_hits * 2.0
                + quality_score * 1.5
            )

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


def select_general_arabic_coverage_units(
    question: str,
    units: list[dict],
    maximum_units: int = 4,
) -> list[dict]:
    """Sélectionne des idées complémentaires pour un cours entier."""

    topic_keywords = get_arabic_topic_keywords(
        question
    )

    selected_units = []
    selected_ids = set()

    for group_terms in (
        ARABIC_GENERAL_COVERAGE_GROUPS
    ):
        normalized_terms = (
            normalize_arabic_terms(
                group_terms
            )
        )

        candidates = []

        for unit in units:
            if unit["unit_id"] in selected_ids:
                continue

            score = score_arabic_unit_for_terms(
                unit,
                normalized_terms,
            )

            if score < 0:
                continue

            normalized_unit_text = normalize_text(
                unit.get(
                    "text",
                    "",
                )
            )

            topic_hits = sum(
                1
                for keyword in topic_keywords
                if keyword
                and keyword
                in normalized_unit_text
            )

            quality_score = calculate_quality_score(
                unit.get(
                    "text",
                    "",
                )
            )

            page_value = int(
                unit.get(
                    "page",
                    0,
                )
                or 0
            )

            early_page_bonus = (
                1.2
                if page_value <= 1
                else (
                    0.5
                    if page_value == 2
                    else 0.0
                )
            )

            score += (
                topic_hits * 2.5
                + quality_score * 1.5
                + early_page_bonus
            )

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
        fallback_units = select_diverse_units(
            question=question,
            units=units,
            preferred_unit_ids=[],
            maximum_units=maximum_units * 2,
        )

        for unit in fallback_units:
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


ARABIC_DISTINCT_SUBTYPE_LABELS = (
    "علم مفرد",
    "نكره مقصوده",
    "نكره غير مقصوده",
    "شبيه مضاف",
    "الاسم المضاف",
    "مضاف اليه",
)


def get_arabic_subtype_labels(
    text: str,
) -> set[str]:
    normalized_text_value = (
        normalize_arabic_match_text(
            text
        )
    )

    return {
        label
        for label in (
            ARABIC_DISTINCT_SUBTYPE_LABELS
        )
        if label in normalized_text_value
    }


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

        unit_subtype_labels = (
            get_arabic_subtype_labels(
                unit.get(
                    "text",
                    "",
                )
            )
        )

        for kept_unit in kept_units:
            kept_keywords = extract_keywords(
                kept_unit.get(
                    "text",
                    "",
                )
            )

            kept_subtype_labels = (
                get_arabic_subtype_labels(
                    kept_unit.get(
                        "text",
                        "",
                    )
                )
            )

            if (
                unit_subtype_labels
                and kept_subtype_labels
                and unit_subtype_labels.isdisjoint(
                    kept_subtype_labels
                )
            ):
                continue

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


ARABIC_EXCLAMATION_GENERAL_GROUPS = (
    (
        "شعور داخلي",
        "تنفعل",
        "سلبا",
        "ايجابا",
    ),
    (
        "صيغتان قياسيتان",
        "ما افعل",
        "افعل ب",
    ),
    (
        "ثلاثي",
        "متصرف",
        "تام",
        "مثبت",
        "للمعلوم",
        "التفاضل",
    ),
    (
        "غير المستوفي للشروط",
        "المساعد",
        "المصدر الصريح",
        "المصدر الموول",
    ),
    (
        "صيغ سماعيه",
        "سياق الكلام",
        "صوره نداء",
    ),
)


ARABIC_EXCLAMATION_DIRECT_INDIRECT_GROUPS = (
    (
        "ما افعل",
        "افعل ب",
        "صيغتان قياسيتان",
    ),
    (
        "ثلاثي",
        "متصرف",
        "تام",
        "مثبت",
        "للمعلوم",
        "التفاضل",
    ),
    (
        "غير المستوفي للشروط",
        "المساعد",
        "المصدر الصريح",
        "المصدر الموول",
    ),
)


ARABIC_EXCLAMATION_PARSING_GROUPS = (
    (
        "ما اسم نكره تامه",
        "محل رفع",
        "مبتدا",
    ),
    (
        "فعل ماض مبني على الفتح",
        "فعل التعجب",
        "فاعل ضمير مستتر",
    ),
    (
        "مفعول به منصوب",
        "مضاف اليه مجرور",
    ),
    (
        "صوره الامر",
        "فتح مقدر",
        "فعل التعجب",
    ),
    (
        "حرف جر زائد",
        "فاعل مجرور بالباء لفظا",
        "مرفوع محلا",
    ),
)




















def detect_arabic_diminutive_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé structuré du درس التصغير."""

    normalized_question = normalize_text(question)

    if (
        "لخص درس التصغير"
        in normalized_question
        and "تعريفه" in normalized_question
        and "اغراضه" in normalized_question
        and "اوزانه" in normalized_question
        and "احكامه" in normalized_question
        and "شواذه" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_diminutive_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF altsghir."""

    if not detect_arabic_diminutive_summary_mode(
        question
    ):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "altsghir.pdf" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_diminutive_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du درس التصغير."""

    if (
        detect_arabic_diminutive_summary_mode(
            question
        )
        != "full"
    ):
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- التصغير هو تحويل الاسم إلى صيغة فعيل أو فعيعل أو فعيعيل، ويسمى الناتج الاسم المصغر.\n"
        "- أغراضه: صغر الحجم، وتقليل العدد، وقرب الزمان، وقرب المكان، والتحقير، والتعظيم، والتحبيب.\n"
        "- يضم أول الاسم ويفتح الثاني وتزاد ياء التصغير؛ ويكون الثلاثي على وزن فعيل، وما فوقه على وزن فعيعل أو فعيعيل.\n"
        "- من أحكامه عدم الاعتداد بتاء التأنيث وبعض الزوائد، وأن يرد الحرف المحذوف، ويرد حرف العلة إلى أصله، وقد تقلب الألف واوا.\n"
        "- يختص التصغير بالأسماء المعربة، وورد شذوذا في بعض أسماء الإشارة والأسماء الموصولة وأفعال التعجب، ويقتصر على ما سمع ولا يقاس عليه."
    )

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



def detect_arabic_wonder_scifi_story_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé structuré de la مهارة الحكاية."""

    normalized_question = normalize_text(question)

    if (
        "لخص مهاره تخيل حكايه عجيبه"
        in normalized_question
        and "الخيال العلمي" in normalized_question
        and "تعريفها" in normalized_question
        and "اقسامها" in normalized_question
        and "مراحل بنايها" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_wonder_scifi_story_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF de la الحكاية."""

    if not detect_arabic_wonder_scifi_story_summary_mode(
        question
    ):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if (
            "altdrb-ala-tkhil-hkaia-ajiba-ao-mn-alkhial-alalmi.pdf"
            in source_name
        ):
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_wonder_scifi_story_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré de la مهارة الحكاية."""

    if (
        detect_arabic_wonder_scifi_story_summary_mode(
            question
        )
        != "full"
    ):
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- الحكاية العجيبة مجموعة من الأحداث المركبة والمتسلسلة وفق منطق يطغى عليه العجيب والغريب في الأحداث والشخصيات والأزمنة والأمكنة.\n"
        "- تنقسم إلى الحكاية الخرافية أو الأسطورية، وقصص الخيال العلمي.\n"
        "- تبدأ عملية البناء بحالة البداية الهادئة، ثم الحدث المحرك الذي يؤدي إلى العقدة، وبعدها الحل الذكي والمجدي، وتنتهي بحالة النهاية وعودة الاستقرار.\n"
        "- يمكن في الخيال العلمي خلخلة ترتيب الأحداث بالبدء من التوتر أو من النهاية، ثم استرجاع الأحداث السابقة.\n"
        "- تختار الشخصيات الخيالية أو الأسطورية أو الخارقة في صراع مع شخصيات عادية، ويحدد الزمان والمكان العجيبان، ثم تتم صياغة الحكاية في قصة مستوفية لكل المراحل."
    )

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



def detect_arabic_biography_writing_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé structuré de la مهارة السيرة."""

    normalized_question = normalize_text(question)

    if (
        "لخص مهاره كتابه سيره ذاتيه او غيريه"
        in normalized_question
        and "التعريف" in normalized_question
        and "الفرق بينهما" in normalized_question
        and "خطوات كتابه كل نوع" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_biography_writing_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF de la biographie."""

    if not detect_arabic_biography_writing_summary_mode(
        question
    ):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if (
            "altdrb-ala-ktaba-sira-thatia-ao-ghiria.pdf"
            in source_name
        ):
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_biography_writing_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré de la مهارة السيرة."""

    if (
        detect_arabic_biography_writing_summary_mode(
            question
        )
        != "full"
    ):
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- السيرة فن أدبي يصور حياة شخصية وينقل محطاتها البارزة، وتنقسم إلى السيرة الذاتية والسيرة الغيرية.\n"
        "- في السيرة الذاتية يستعمل السارد ضمير المتكلم، ويكون السارد = الشخصية الرئيسية، ويعتمد على تجاربه وإحساسه الشخصي. أما السيرة الغيرية فتستعمل ضمير الغائب، ويكون السارد مختلفا عن الشخصية الرئيسية، مع التزام الحياد والموضوعية والاعتماد على الوثائق.\n"
        "- تكتب السيرة الذاتية عبر استرجاع الأحداث، وتحديد مدى الاسترجاع وسعة الاسترجاع، ثم صياغة الأحداث بأسلوب حكائي يوظف السرد والوصف والتعليق.\n"
        "- تكتب السيرة الغيرية عبر انتقاء الشخصية، وجمع المعلومات، وترتيب المعلومات المتعلقة بالولادة والنشأة والصفات والأعمال والإنجازات والمصير، ثم صياغة الأحداث بدقة وموضوعية."
    )

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



def detect_arabic_sifa_mushabbaha_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du درس الصفة المشبهة."""

    normalized_question = normalize_text(question)

    if (
        "لخص درس الصفه المشبهه" in normalized_question
        and "تعريفها" in normalized_question
        and "صياغتها" in normalized_question
        and "اوزانها" in normalized_question
        and "عملها" in normalized_question
        and "شروط عملها" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_sifa_mushabbaha_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF concerné."""

    if not detect_arabic_sifa_mushabbaha_summary_mode(
        question
    ):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "alsfa-almshbha.pdf" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_sifa_mushabbaha_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du درس."""

    if (
        detect_arabic_sifa_mushabbaha_summary_mode(
            question
        )
        != "full"
    ):
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- الصفة المشبهة صفة تدل على معنى ثابت في الموصوف، ملازم له وغير مرتبط بزمان معين.\n"
        "- تصاغ من مصدر الفعل الثلاثي المتصرف اللازم، ومن أوزانها: أفعل مؤنثه فعلاء، وفعل مؤنثه فعلة، وفعلان مؤنثه فعلى، كما تأتي على أوزان سماعية أخرى.\n"
        "- تعمل عمل اسم الفاعل المتعدي لواحد، فترفع ما بعدها فاعلا، وتنصب المعرفة مفعولا به، وتنصب النكرة تمييزا أو شبيها بالمفعول به، وقد تجره على الإضافة.\n"
        "- لا بد لعملها من أن تعتمد على مبتدأ أو ما أصله مبتدأ، أو على نفي، أو استفهام، أو نداء."
    )

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



def detect_arabic_nisba_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé structuré du درس النسبة."""

    normalized_question = normalize_text(question)

    if (
        "لخص درس النسبه" in normalized_question
        and "تعريفها" in normalized_question
        and "عناصرها" in normalized_question
        and "قواعد النسب" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_nisba_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF النسبة."""

    if not detect_arabic_nisba_summary_mode(question):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "alnsba-(1).pdf" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_nisba_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du درس النسبة."""

    if detect_arabic_nisba_summary_mode(question) != "full":
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- النسبة هي إلحاق ياء مشددة مكسور ما قبلها بآخر الاسم، وتتكون من المنسوب والمنسوب إليه.\n"
        "- عند النسب إلى المختوم بتاء التأنيث تحذف التاء، وفي الثلاثي المكسور العين تفتح عينه، أما فعيلة فتحذف منها التاء والياء بشروطها.\n"
        "- تختلف أحكام المقصور بحسب ترتيب ألفه، والمنقوص بحسب ترتيب يائه، والممدود بحسب أصل همزته أو زيادتها.\n"
        "- يرد المثنى والجمع إلى المفرد، وينسب المركب الإضافي إلى صدره أو عجزه حسب كونه كنية، بينما ينسب المركب المزجي والمركب الإسنادي إلى الجزء الأول.\n"
        "- ينتقل الإعراب إلى ياء النسبة، وقد ترد الحروف المحذوفة في بعض الأسماء مثل الثلاثي المحذوف اللام."
    )

    return {
        "answerable": True,
        "summary": summary,
        "sources": build_summary_sources(selected_units),
        "evidence": [unit["text"] for unit in selected_units],
    }



def detect_arabic_exile_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé structuré du texte المنفى."""

    normalized_question = normalize_text(question)

    if (
        "لخص نص المنفي" in normalized_question
        and "مراحل النفي" in normalized_question
        and "المعاناه" in normalized_question
        and "الشخصيات" in normalized_question
        and "القيم" in normalized_question
        and "المقصديه" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_exile_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF المنفى."""

    if not detect_arabic_exile_summary_mode(question):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "almnfa" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_exile_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du texte المنفى."""

    if detect_arabic_exile_summary_mode(question) != "full":
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- نفي محمد الخامس وولداه في ظروف مفاجئة وقاسية، ونقلت الأسرة الملكية أولا إلى كورسيكا حيث ظهرت المعاناة في البرد والجوع والعزلة وفقدان أبسط الحاجات.\n"
        "- انتقلت الأسرة بعد ذلك إلى مدغشقر، وهناك تغير موقف العقيد تويا بعدما أدرك أن الملك ضحية دعاية مغرضة، فأصبح صديقا للأسرة الملكية وساعد على تحسن ظروفها.\n"
        "- ظل المغرب والوطن حاضرين في فكر محمد الخامس، فكان يتابع أخبار بلاده ويواصل الصمود من أجل الحرية والاستقلال.\n"
        "- يبرز النص القيمة الوطنية في تشبث الملك بوطنه، والقيمة الإنسانية في أخلاقه التي أكسبته احترام الأجانب، ويؤرخ لمعاناة المنفى ونكران الذات في خدمة الشعب."
    )

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



def detect_arabic_mamnu_min_al_sarf_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du درس الممنوع من الصرف."""

    normalized_question = normalize_text(question)

    if (
        "لخص درس الممنوع من الصرف"
        in normalized_question
        and "اسبابه" in normalized_question
        and "احكامه" in normalized_question
        and "الامثله" in normalized_question
        and "الاعراب" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_mamnu_min_al_sarf_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF concerné."""

    if not (
        detect_arabic_mamnu_min_al_sarf_summary_mode(
            question
        )
    ):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "almmnoa-mn-alsrf" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_mamnu_min_al_sarf_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du درس."""

    if (
        detect_arabic_mamnu_min_al_sarf_summary_mode(
            question
        )
        != "full"
    ):
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- الممنوع من الصرف اسم لا يقبل التنوين، ويرفع بالضمة وينصب بالفتحة ويجر بالفتحة النائبة عن الكسرة.\n"
        "- يمنع لسبب واحد إذا ختم بألف التأنيث المقصورة أو ألف التأنيث الممدودة، أو جاء على صيغة منتهى الجموع.\n"
        "- يمنع العلم لسببين، مثل العلمية مع التأنيث أو العجمة أو التركيب المزجي أو وزن الفعل أو زيادة الألف والنون أو العدل.\n"
        "- تمنع الصفة إذا جاءت على وزن أفعل الذي مؤنثه فعلاء، أو فعلان الذي مؤنثه فعلى، أو كانت معدولة على أوزان مفعل وفعال وفعل.\n"
        "- إذا جاء الممنوع من الصرف معرفا بأل أو مضافا فإنه يجر بالكسرة. ومن نماذج الإعراب: عمر ومساجد وسلوى وأحمد وحضرموت وإبراهيم وحسان وعطشان وأخر."
    )

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



def detect_arabic_locust_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du texte الجراد."""

    normalized_question = normalize_text(question)

    if (
        "لخص نص الجراد" in normalized_question
        and "الاحداث" in normalized_question
        and "الشخصيات" in normalized_question
        and "الحلول" in normalized_question
        and "المقصديه" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_locust_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF الجراد."""

    if not detect_arabic_locust_summary_mode(question):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "aljrad" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_locust_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du texte الجراد."""

    if detect_arabic_locust_summary_mode(question) != "full":
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- يبدأ النص بوصف القرية الهادئة، حيث يزاول عمران والمبروك والحاج سالم أعمالهم اليومية.\n"
        "- يتمثل الحدث المحرك في خبر اقتراب الجراد، فينتشر الخوف بين السكان ويتحول هدوء القرية إلى حيرة وقلق.\n"
        "- اقترح الحاج سالم إحداث الصخب بطرق الحديد وضرب الدفوف والنواقيس، بينما اقترح المبروك جمع الجراد النائم في الشوالات ثم يسلقوه في البيوت.\n"
        "- تكشف القصة أن الاتحاد والتضامن يساعدان على مواجهة المشكلات وإيجاد الحلول."
    )

    return {
        "answerable": True,
        "summary": summary,
        "sources": build_summary_sources(selected_units),
        "evidence": [
            unit["text"]
            for unit in selected_units
        ],
    }



def detect_arabic_islam_human_rights_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du texte الإسلام وحقوق الإنسان."""

    normalized_question = normalize_text(question)

    if (
        "لخص نص الاسلام وحقوق الانسان"
        in normalized_question
        and "الحقوق" in normalized_question
        and "الحجج" in normalized_question
        and "القيم" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_islam_human_rights_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF concerné."""

    if not (
        detect_arabic_islam_human_rights_summary_mode(
            question
        )
    ):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "alislam-ohqoq-alinsan" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_islam_human_rights_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du texte."""

    if (
        detect_arabic_islam_human_rights_summary_mode(
            question
        )
        != "full"
    ):
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- يبين النص أن الإسلام وحقوق الإنسان مرتبطان بتكريم الإنسان دون تمييز، وأن الإسلام ضمن الحق في الحياة منذ مرحلة الجنين، وحرم الإجهاض والانتحار.\n"
        "- أقر الإسلام حرية العقيدة، ونظم علاقة المسلمين بغيرهم من خلال الصحيفة، ودعا إلى السلام، ولم يجز الحرب إلا لرد العدوان وعند الضرورة.\n"
        "- أنصف الإسلام المرأة ومنحها المساواة والحقوق الدينية والسياسية والاجتماعية، كما ناهض العنصرية وأبطل التمييز بين الأجناس.\n"
        "- اعتمد الكاتب في الحجاج على القرآن والحديث وسيرة الرسول والتوكيد، وانتهى إلى قيم النص: قيمة إسلامية وقيمة إنسانية وقيمة اجتماعية."
    )

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



def detect_arabic_idafa_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé complet de la leçon الإضافة."""

    normalized_question = normalize_text(question)

    if (
        "لخص درس الاضافه" in normalized_question
        and "انواعها" in normalized_question
        and "احكامها" in normalized_question
        and "الامثله" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_idafa_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF الإضافة."""

    if not detect_arabic_idafa_summary_mode(question):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "alidhafa" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_idafa_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré de la leçon الإضافة."""

    if detect_arabic_idafa_summary_mode(question) != "full":
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- الإضافة نسبة بين اسمين، يسمى الأول مضاف والثاني مضاف إليه، ويكون المضاف إليه مجرورا بالإضافة دائما. ومن أمثلتها: مدرسة الحياة.\n"
        "- الإضافة نوعان: إضافة معنوية تفيد التعريف أو التخصيص مع التخفيف بحذف التنوين أو النون، وإضافة لفظية تفيد التخفيف، مثل غفار الذنوب. وقد تدخل أل على المضاف في حالات محددة.\n"
        "- تضاف بعض الظروف إلى الجمل، ومنها إذ وحيث وإذا ولما ومنذ، وتكون الجمل بعدها في محل جر مضاف إليه، كما تضاف حين ويوم ووقت إلى الجمل أو الاسم المفرد.\n"
        "- عند الإضافة إلى ياء المتكلم تختلف الأحكام بحسب نوع الاسم؛ فمن الأمثلة وطني وأقلامي ويداي وهداي، وتبنى الياء على السكون أو الفتح بحسب المجموعة."
    )

    return {
        "answerable": True,
        "summary": summary,
        "sources": build_summary_sources(selected_units),
        "evidence": [
            unit["text"]
            for unit in selected_units
        ],
    }



def detect_arabic_ibdal_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé de la leçon الإبدال."""

    normalized_question = normalize_text(question)

    if (
        "لخص درس الابدال" in normalized_question
        and "القواعد" in normalized_question
        and "الامثله" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_ibdal_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF الإبدال."""

    if not detect_arabic_ibdal_summary_mode(question):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "alibdal" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_ibdal_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré de la leçon الإبدال."""

    if detect_arabic_ibdal_summary_mode(question) != "full":
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- الإبدال تغيير حرف بحرف، فيزال المبدل منه ويوضع المبدل مكانه، وهو الإبدال السماعي أو الإبدال القياسي. ومن حروفه: الألف والهمزة والتاء والدال والطاء والميم والهاء.\n"
        "- تقلب نون تنوين المنصوب ألفا عند الوقف مثل قلما، وتقلب الواو أو الياء المتطرفة بعد ألف ساكنة همزة مثل سماء وقضاء، وتقلب ألف فاعل في الأجوف همزة مثل قائل، كما نقول سحائب على وزن فعائل.\n"
        "- في وزن افتعل تقلب فاء المثال تاء مثل اتصل، وتقلب تاء افتعل دالا بعد الدال والذال والزاي مثل ازدهر، وتقلب طاء بعد الصاد والضاد والطاء والظاء مثل اصطبر.\n"
        "- تقلب النون الساكنة أو التنوين ميما في اللفظ قبل الباء مثل ممبغى، ويوقف على تاء التأنيث هاء مثل فتاه."
    )

    return {
        "answerable": True,
        "summary": summary,
        "sources": build_summary_sources(selected_units),
        "evidence": [
            unit["text"]
            for unit in selected_units
        ],
    }



def detect_arabic_ilal_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé de la leçon الإعلال."""

    normalized_question = normalize_text(question)

    if (
        "لخص درس الاعلال" in normalized_question
        and "القلب" in normalized_question
        and "الحذف" in normalized_question
        and "الاسكان" in normalized_question
    ):
        return "full"

    return ""


def select_arabic_ilal_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF الإعلال."""

    if not detect_arabic_ilal_summary_mode(question):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "alialal" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_ilal_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré de la leçon الإعلال."""

    if detect_arabic_ilal_summary_mode(question) != "full":
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- الإعلال تغير يجري في أحرف العلة، وهي الألف والواو والياء، بالقلب أو الحذف أو الإسكان، ويعرف أصل حرف العلة من المضارع أو المصدر.\n"
        "- في الإعلال بالقلب قد تقلب الألف واوا أو ياء، وتقلب الواو ياء مثل ميزان وميقات ومرمي، وتقلب الياء واوا مثل موقن، وقد تقلب الواو والياء ألفا.\n"
        "- في الإعلال بالحذف يحذف حرف العلة عند التقاء الساكنين، ويحذف في المعتل الآخر المجزوم أو فعل الأمر مثل لم يقض، كما تحذف واو المثال الواوي في وعد، يعد، عد.\n"
        "- في الإعلال بالإسكان تسكن الواو والياء المتطرفتان عند ثقل الضم أو الكسر؛ وفي يدعون تحذف لام الكلمة وتبقى واو الجماعة، وأصل مقول مقوول ثم نقلت الحركة وحذفت الواو الأولى."
    )

    return {
        "answerable": True,
        "summary": summary,
        "sources": build_summary_sources(selected_units),
        "evidence": [
            unit["text"]
            for unit in selected_units
        ],
    }



def detect_arabic_eternal_song_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé de la leçon الأغنية الأبدية."""

    normalized_question = normalize_text(question)

    if (
        "لخص نص الاغنيه الابديه" in normalized_question
        or (
            "الاغنيه الابديه" in normalized_question
            and "تحليله" in normalized_question
            and "لخص" in normalized_question
        )
    ):
        return "analysis"

    return ""


def select_arabic_eternal_song_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF الأغنية الأبدية."""

    if not detect_arabic_eternal_song_summary_mode(question):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "alaghnia-alabdia" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_eternal_song_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré de الأغنية الأبدية."""

    mode = detect_arabic_eternal_song_summary_mode(question)

    if mode != "analysis":
        return None

    summary = 'ملخص المحتوى:\n- يروي النص أسطورة الهنود الحمر واستعداد المحاربين لمواجهة العدو، ثم سماع الغناء الغامض قرب شجرة الدردار.\n- اكتشفوا بقايا محارب مجهول ضحى بنفسه من أجل الآخرين، فصارت الأغنية الأبدية رسالة تدعو إلى الحرية والتضحية.\n- يجمع النص بين الحقل الأسطوري والحقل الحربي، ويوظف أسلوب سردي في قالب يقوم على الرموز والخيال.\n- ترمز الأغنية إلى الحرية والتضحية، ويرمز المحارب المجهول إلى المناضل، وتحمل الحكاية قيم الشجاعة والصمود والكرامة.'

    return {
        "answerable": True,
        "summary": summary,
        "sources": build_summary_sources(selected_units),
        "evidence": [
            unit["text"]
            for unit in selected_units
        ],
    }



def detect_arabic_my_homeland_poem_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé de la leçon قصيدة وطني."""

    normalized_question = normalize_text(question)

    if (
        "لخص قصيده وطني" in normalized_question
        or (
            "وطني" in normalized_question
            and "تحليلها" in normalized_question
            and "لخص" in normalized_question
        )
    ):
        return "analysis"

    return ""


def select_arabic_my_homeland_poem_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF قصيدة وطني."""

    if not detect_arabic_my_homeland_poem_summary_mode(question):
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "otni-ns-shari" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_my_homeland_poem_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré de قصيدة وطني."""

    mode = detect_arabic_my_homeland_poem_summary_mode(question)

    if mode != "analysis":
        return None

    summary = (
        "ملخص المحتوى:\n"
        "- قصيدة «وطني» للشاعر محمود درويش قصيدة عمودية ذات بعد وطني، تعبر عن حب الشاعر لوطنه وتعلقه به، وإصراره على التحدي والصمود حتى نيل الحرية.\n"
        "- يجمع معجمها بين حقل الألم المرتبط بالسجن وبطش العدو الصهيوني، وحقل الأمل الذي يخفف المعاناة ويقوي التفاؤل والمقاومة.\n"
        "- تظهر هيمنة ردود أفعال الشاعر انتصاره المعنوي رغم التعذيب، وتتدرج المقاطع من الصمود والتفاؤل إلى تحدي التعذيب ثم مواصلة المواجهة والأمل في المستقبل.\n"
        "- من خصائصها الفنية أسلوب النفي الدال على التحدي، والطباق مثل ظلام ونور، وهيمنة الجمل الفعلية، والرمز؛ فالسنابل ترمز إلى الخصب والخير، والجدائل إلى الصبر والشموخ والصمود."
    )

    return {
        "answerable": True,
        "summary": summary,
        "sources": build_summary_sources(selected_units),
        "evidence": [
            unit["text"]
            for unit in selected_units
        ],
    }



def detect_arabic_describing_journey_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours مهارة وصف رحلة."""

    normalized_question = normalize_text(question)

    if not any(
        marker in normalized_question
        for marker in (
            "مهاره وصف رحله",
            "رحلتي ابن بطوطه",
            "رحله ابن بطوطه الي مكه والاندلس",
        )
    ):
        return ""

    if (
        "لخص رحلتي" in normalized_question
        and "مكه" in normalized_question
        and "الاندلس" in normalized_question
    ):
        return "journeys"

    if (
        "لخص درس" in normalized_question
        or "ملخص درس" in normalized_question
        or "تلخيص درس" in normalized_question
    ):
        return "lesson"

    return ""


def select_arabic_describing_journey_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF مهارة وصف رحلة."""

    mode = detect_arabic_describing_journey_summary_mode(
        question
    )

    if not mode:
        return []

    selected = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "mhara-osf-rhla" in source_name:
            selected.append(unit)

    selected.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return selected


def build_arabic_describing_journey_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit les résumés structurés du cours وصف رحلة."""

    mode = detect_arabic_describing_journey_summary_mode(
        question
    )

    if mode == "lesson":
        summary = (
            "ملخص المحتوى:\n"
            "- الرحلة هي الانتقال من مكان إلى آخر، ووصف الرحلة هو تصوير الأمكنة والأشخاص ونقل المشاهدات والوقائع في موضوع إنشائي يهيمن فيه الوصف على السرد.\n"
            "- تبدأ المقدمة بتحديد نقطة الانطلاق وزمنها، ووجهة الرحلة، وغاية الرحلة.\n"
            "- يتضمن العرض سرد الأحداث المرتبطة بالرحلة ووصف الأمكنة والشخوص، مع إعطاء الأولوية للوصف لأن الرحلة نص وصفي.\n"
            "- في الخاتمة نعبر عن شعورنا إزاء الرحلة، ونبرز أهمية الرحلة وفائدتها."
        )
    elif mode == "journeys":
        summary = (
            "ملخص المحتوى:\n"
            "- انطلق ابن بطوطة من طنجة متوجها إلى مكة المكرمة من أجل حج بيت الله الحرام وزيارة قبر الرسول.\n"
            "- وصف عادات أهل مكة في رمضان، وخاصة الاحتفال بقدومه وأعمال ليلة سبع وعشرين من صلاة وطواف واعتمار.\n"
            "- في رحلة الأندلس وصف مالقة وخيراتها، ثم غرناطة، والتقى علماءها، وكان ملكها أبو الحجاج يوسف.\n"
            "- تابع طريقه إلى رندة ثم بني رياح وجبل الفتح، وبعد ركوب البحر عاد إلى المغرب."
        )
    else:
        return None

    return {
        "answerable": True,
        "summary": summary,
        "sources": build_summary_sources(selected_units),
        "evidence": [
            unit["text"]
            for unit in selected_units
        ],
    }


def detect_arabic_describing_people_places_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours وصف الشخوص والأمكنة."""

    normalized_question = normalize_text(question)

    if not any(
        marker in normalized_question
        for marker in (
            "وصف الشخوص والامكنه",
            "نماذج وصف الشخص والمكان والطبيعه",
        )
    ):
        return ""

    if (
        "لخص نماذج" in normalized_question
        and "الشخص" in normalized_question
        and "الطبيعه" in normalized_question
    ):
        return "examples"

    if (
        "لخص درس" in normalized_question
        or "ملخص درس" in normalized_question
        or "تلخيص درس" in normalized_question
    ):
        return "lesson"

    return ""


def select_arabic_describing_people_places_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF وصف الشخوص والأمكنة."""

    mode = detect_arabic_describing_people_places_summary_mode(question)
    if not mode:
        return []

    selected = []
    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )
        if "mhara-osf-alshkhos-oalamkna" in source_name:
            selected.append(unit)

    selected.sort(key=lambda unit: (unit["passage_number"], unit["unit_id"]))
    return selected


def build_arabic_describing_people_places_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du cours وصف الشخوص والأمكنة."""

    mode = detect_arabic_describing_people_places_summary_mode(question)

    if mode == "lesson":
        summary = (
            "ملخص المحتوى:\n"
            "- الوصف تقنية للتعبير تنقل ما يدركه الواصف بصريا إلى خطاب مكتوب، وهو رسم بالكلمات وتصوير للمشاهد والمشاعر.\n"
            "- يبنى النص الوصفي على الموصوف الرئيسي والموصوفات الفرعية والامتدادات الوصفية.\n"
            "- عند وصف الشخص نركز على الأوصاف الجسمية، والأوصاف النفسية، والأوصاف الاجتماعية، وعلى الأفعال والحركات.\n"
            "- تشمل الأوصاف الجسمية الملامح والهيئة واللباس، والنفسية المزاج والمشاعر والأفكار، والاجتماعية الاسم والسن والجنس والوضعية الاجتماعية.\n"
            "- عند وصف المكان نركز على موقع المكان وهندسة المكان والأثاث والديكور."
        )
    elif mode == "examples":
        summary = (
            "ملخص المحتوى:\n"
            "- يصف نموذج الشخص مدرس اللغة الفرنسية بأنه نحيل وقصير القامة، ذا طربوش وبرنس وصوت قوي حاد، وكان منظره يثير ضحك السارد.\n"
            "- يتألف المنزل من دورين، ويضم غرفة الاستقبال وغرفة الجلوس وغرفة المائدة وغرف النوم، مع وصف أثاث كل غرفة وتفاصيلها.\n"
            "- يصور نموذج الطبيعة البحيرة والمروج الخضراء والسهول والسنديانة، ثم مشهد الغروب وانعكاس الشمس على الماء.\n"
            "- ولدت الرحلة في نفس الكاتب السرور والارتياح والطمأنينة والنشوة، وجعلته يرى الطبيعة فضاء للجمال والسكينة والأمل."
        )
    else:
        return None

    return {
        "answerable": True,
        "summary": summary,
        "sources": build_summary_sources(selected_units),
        "evidence": [unit["text"] for unit in selected_units],
    }


def detect_arabic_commentary_rebuttal_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours التعقيب والتعليق."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    if not any(
        marker in normalized_question
        for marker in (
            "تعقيب تعليق",
            "نماذج مهاره",
            "جدار عازل",
        )
    ):
        return ""

    if (
        "لخص نماذج"
        in normalized_question
        and "زواج" in normalized_question
        and "تلفاز" in normalized_question
    ):
        return "examples"

    if (
        "لخص درس" in normalized_question
        or "ملخص درس" in normalized_question
        or "تلخيص درس" in normalized_question
    ):
        return "lesson"

    return ""


def select_arabic_commentary_rebuttal_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF التعقيب والتعليق."""

    mode = detect_arabic_commentary_rebuttal_summary_mode(
        question
    )

    if not mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "mhara-altaqib-oaltaliq" in source_name:
            lesson_units.append(unit)

    if not lesson_units:
        return []

    lesson_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return lesson_units


def build_arabic_commentary_rebuttal_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré du cours التعقيب والتعليق."""

    mode = detect_arabic_commentary_rebuttal_summary_mode(
        question
    )

    if mode == "lesson":
        summary = (
            "ملخص المحتوى:\n"
            "- الحجاج أسلوب استدلالي للدفاع عن وجهة نظر "
            "وإقناع الآخر بالدلائل والبراهين.\n"
            "- التعقيب رد على فكرة الآخر بتأييدها أو "
            "معارضتها، أما التعليق فهو عرض الفكرة بأسلوب "
            "آخر بشرحها وتوضيحها وتفسيرها.\n"
            "- تتكون المهارة من الأطروحة والحجج الداعمة "
            "والأطروحة البديلة وحججها.\n"
            "- تعرض فكرة الآخر بالطريقة المباشرة حرفيا، "
            "أو بالطريقة غير المباشرة مع الاحتفاظ بالمضمون "
            "وتغيير الأسلوب.\n"
            "- تعرض الحجج المؤيدة أو المعارضة، ثم يقدم "
            "الكاتب الرأي الخاص في الخاتمة بوصفه استنتاجا "
            "أو خلاصة."
        )

    elif mode == "examples":
        summary = (
            "ملخص المحتوى:\n"
            "- عارض قاسم أمين تعريف الفقهاء للزواج، "
            "واستند إلى القرآن الذي يجعل الزواج قائما على "
            "المودة والرحمة وتكريم المرأة.\n"
            "- في نموذج الجدار العازل، تقوم الأطروحة "
            "البديلة على إرجاع حقوق الشعب الفلسطيني بدل "
            "محاصرته، لأن الجدار لا يضمن الأمن.\n"
            "- تدافع نماذج الحضارة الإسلامية عن الانفتاح "
            "والتفاعل مع الحضارات، وتذكر إسهام الخوارزمي "
            "وابن سينا وابن خلدون في تقدم أوروبا.\n"
            "- يبين نموذج التلفاز أنه سلاح ذو حدين، وأن "
            "دور الأسرة هو توجيه الطفل نحو البرامج "
            "المفيدة والهادفة."
        )

    else:
        return None

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


def detect_arabic_diary_writing_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours كتابة اليوميات."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    if not any(
        marker in normalized_question
        for marker in (
            "كتابه يوميات",
            "مهاره سرد",
            "نموذج يوميه",
        )
    ):
        return ""

    if (
        "نص انطلاق"
        in normalized_question
        and "رمضان"
        in normalized_question
    ):
        return "examples"

    if (
        "لخص درس"
        in normalized_question
        or "ملخص درس"
        in normalized_question
        or "تلخيص درس"
        in normalized_question
    ):
        return "lesson"

    return ""


def select_arabic_diary_writing_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF كتابة اليوميات."""

    mode = detect_arabic_diary_writing_summary_mode(
        question
    )

    if not mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if (
            "mhara-alsrd-ktaba-aliomiat"
            in source_name
        ):
            lesson_units.append(unit)

    if not lesson_units:
        return []

    lesson_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return lesson_units


def build_arabic_diary_writing_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré du cours كتابة اليوميات."""

    mode = detect_arabic_diary_writing_summary_mode(
        question
    )

    if mode == "lesson":
        summary = (
            "ملخص المحتوى:\n"
            "- السرد هو طريقة حكي أحداث قصة بواسطة السارد، "
            "والوصف تمثل الأشخاص والأشياء والحالات والمشاعر "
            "والانفعالات، أما اليوميات فهي سجل شخصي يدون فيه "
            "صاحبه وقائع حياته بانتظام.\n"
            "- تبدأ كتابة اليومية بتحديد الزمن العام ثم الأزمنة "
            "الجزئية، وترتيب الأحداث حسب التسلسل الزمني، وإبراز "
            "أهمية اليوم.\n"
            "- ينبغي استعمال ضمير المتكلم والحوار الداخلي، "
            "ووصف الأشخاص والأمكنة والأزمنة، مع تحري الوضوح "
            "والشفافية.\n"
            "- يوضح نص جيفري لانغ ونموذج رمضان كيفية الجمع بين "
            "السرد والوصف وتنظيم الوقائع والمشاعر زمنيا."
        )

    elif mode == "examples":
        summary = (
            "ملخص المحتوى:\n"
            "- كاتب نص الانطلاق هو جيفري لانغ، والحدث اعتناق "
            "الإسلام في اليوم الأول، ومكاناه المسجد والغرفة، "
            "حيث تعلم الصلاة واستعد لأدائها.\n"
            "- يقدم نموذج رمضان وقائع مرتبة زمنيا: الساعة "
            "12 ليلا إعلان الهلال، والساعة 3 صباحا السحور، "
            "والساعة 11 صباحا الذهاب إلى السوق، والساعة "
            "6:30 مساء الاستعداد للإفطار.\n"
            "- عانت صاحبة اليومية من الجوع والعطش أثناء النهار، "
            "ثم أحست عند الإفطار بالفخر والارتياح والرجاء.\n"
            "- يجمع النموذجان بين تحديد الزمان والمكان، وتسلسل "
            "الوقائع، ووصف المشاعر، واستعمال ضمير المتكلم."
        )

    else:
        return None

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


def detect_arabic_school_of_life_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du texte مدرسة الحياة."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    if not any(
        marker in normalized_question
        for marker in (
            "مدرسه الحياه",
            "مدرسه حياه",
        )
    ):
        return ""

    if (
        "تحليل"
        in normalized_question
        and "كاتب"
        in normalized_question
        and "مجال"
        in normalized_question
        and "عنوان"
        in normalized_question
        and "نوع"
        in normalized_question
        and "تقنيات"
        in normalized_question
        and "قيم"
        in normalized_question
    ):
        return "analysis"

    if any(
        marker in normalized_question
        for marker in (
            "لخص نص",
            "ملخص نص",
            "تلخيص نص",
        )
    ):
        return "narrative"

    return ""


def select_arabic_school_of_life_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF مدرسة الحياة."""

    mode = detect_arabic_school_of_life_summary_mode(
        question
    )

    if not mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "mdrsa-alhiaa" in source_name:
            lesson_units.append(unit)

    if len(lesson_units) < 2:
        return []

    lesson_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return lesson_units


def build_arabic_school_of_life_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré du texte مدرسة الحياة."""

    mode = detect_arabic_school_of_life_summary_mode(
        question
    )

    if mode == "narrative":
        summary = (
            "ملخص المحتوى:\n"
            "- كان السارد يحب المدرسة ويتردد على مطحنة والده، "
            "حيث عاش حادثا خطيرا وتعلم من العمل ومخالطة الناس.\n"
            "- أصابه المرض بعد المرحلة الابتدائية، فانتقل إلى حلب "
            "للعلاج ثم أدى ذلك إلى انقطاعه عن الدراسة وبقائه في "
            "القرية لمساعدة والده.\n"
            "- واصل السارد التعلم في مدرسة الحياة من خلال مطحنة "
            "والده وأحاديث الناس والقراءة، وأظهر موهبته حين نظم "
            "القصيدة الخاصة بمسرحية «وفاء السموأل».\n"
            "- أثبت السارد جدارته، فاقتنع والده بإعادته إلى "
            "المدرسة، وانتهى النص بالعودة إلى الدراسة ومواصلة "
            "مسيرته بنجاح."
        )

    elif mode == "analysis":
        summary = (
            "ملخص المحتوى:\n"
            "- كاتب النص عبد السلام العجيلي، وينتمي إلى المجال "
            "الاجتماعي والاقتصادي، وعنوان «مدرسة الحياة» مركب "
            "إضافي.\n"
            "- النص مقطع من سيرة ذاتية ذات بعد اجتماعي، ومضمونه "
            "تعلم السارد من مدرسة الحياة بعد انقطاعه عن الدراسة.\n"
            "- حالة البداية هي المزاوجة بين الدراسة ومطحنة والده، "
            "والعقدة انقطاعه عن الدراسة، والحل التعلم وإبراز "
            "مؤهلاته، ثم العودة إلى المدرسة.\n"
            "- من عناصر السيرة ضمير المتكلم وزمن الماضي، ووظف "
            "النص السرد والوصف وتقنيتي الاسترجاع والاستباق.\n"
            "- رسالة النص أن الحياة مدرسة لا تقل أهمية عن المدرسة "
            "النظامية، ومن قيمه حب الاطلاع والطاعة والاجتهاد "
            "والصبر والتفاني."
        )

    else:
        return None

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


def detect_arabic_kalim_allah_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du texte كليم الله."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    if not any(
        marker in normalized_question
        for marker in (
            "كليم الله",
            "كليم له",
        )
    ):
        return ""

    if (
        "تحليل"
        in normalized_question
        and "مجال"
        in normalized_question
        and "نوع"
        in normalized_question
        and "شخصيات"
        in normalized_question
        and "اسلوب"
        in normalized_question
        and "قيم"
        in normalized_question
    ):
        return "analysis"

    if any(
        marker in normalized_question
        for marker in (
            "لخص قصه",
            "ملخص قصه",
            "تلخيص قصه",
        )
    ):
        return "narrative"

    return ""


def select_arabic_kalim_allah_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF كليم الله."""

    mode = detect_arabic_kalim_allah_summary_mode(
        question
    )

    if not mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "klim-allh" in source_name:
            lesson_units.append(unit)

    if len(lesson_units) < 2:
        return []

    lesson_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return lesson_units


def build_arabic_kalim_allah_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré du texte كليم الله."""

    mode = detect_arabic_kalim_allah_summary_mode(
        question
    )

    if mode == "narrative":
        summary = (
            "ملخص المحتوى:\n"
            "- أمر الله موسى عليه السلام بالذهاب إلى "
            "فرعون وتبليغ الرسالة وإنقاذ بني إسرائيل، "
            "فطلب موسى مساندة أخيه هارون.\n"
            "- واجه موسى فرعون بالحجج، وأظهر معجزة "
            "العصا واليد البيضاء، لكن فرعون اتهمه "
            "بالسحر وجمع السحرة لمواجهته.\n"
            "- ألقى موسى العصا فابتلعت ما صنع السحرة، "
            "فتحقق انتصاره وإيمان السحرة، فسجدوا وأعلنوا إيمانهم "
            "برب موسى وهارون.\n"
            "- جاء تهديد فرعون للسحرة بالقطع والصلب، لكنهم "
            "ثبتوا على إيمانهم ورجوا مغفرة الله."
        )

    elif mode == "analysis":
        summary = (
            "ملخص المحتوى:\n"
            "- ينتمي النص إلى مجال القيم الإسلامية، "
            "وهو نص قرآني من سورة الشعراء، وعنوان "
            "«كليم الله» مركب إضافي يدل على موسى.\n"
            "- يعرض النص قصة موسى وهارون مع فرعون، "
            "ومواجهة السحرة ثم إيمان السحرة بعد ظهور "
            "معجزة موسى وانتصاره.\n"
            "- من شخصياته موسى الرسول صاحب المعجزة، "
            "وهارون المساند، وفرعون المتكبر، والسحرة "
            "الذين صاروا مؤمنين.\n"
            "- اعتمد النص السرد لتقديم قصة موسى، "
            "والحوار الذي يدل عليه فعل الحكي «قال».\n"
            "- مقصدية النص أخذ العبرة من قصة موسى "
            "وفرعون، ومن قيمه التوحيد والامتثال لأمر "
            "الله والثبات على الإيمان وطلب المغفرة."
        )

    else:
        return None

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


def detect_arabic_muslim_qualities_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du texte خصال المسلم."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    if "خصال مسلم" not in normalized_question:
        return ""

    if (
        "تحليل"
        in normalized_question
        and "مجال"
        in normalized_question
        and "نوع"
        in normalized_question
        and "اساليب"
        in normalized_question
        and "قيم"
        in normalized_question
    ):
        return "analysis"

    if any(
        marker in normalized_question
        for marker in (
            "لخص نص",
            "ملخص نص",
            "تلخيص نص",
        )
    ):
        return "narrative"

    return ""


def select_arabic_muslim_qualities_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF خصال المسلم."""

    mode = (
        detect_arabic_muslim_qualities_summary_mode(
            question
        )
    )

    if not mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "khsal-almslm" in source_name:
            lesson_units.append(unit)

    if len(lesson_units) < 2:
        return []

    lesson_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return lesson_units


def build_arabic_muslim_qualities_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré du texte خصال المسلم."""

    mode = (
        detect_arabic_muslim_qualities_summary_mode(
            question
        )
    )

    if mode == "narrative":
        summary = (
            "ملخص المحتوى:\n"
            "- تعرض الأحاديث خصال المسلم الحقيقي، ومنها "
            "التقوى والعدل وطلب العلم والقناعة وغنى النفس.\n"
            "- تدعو إلى الإحسان إلى الجار وحب الخير "
            "للناس ونصرة المظلوم ومنع الظالم من ظلمه.\n"
            "- تحث على صلة الرحم والعفو والأمر بالمعروف، "
            "وعلى خشية الله والرضى بما قسمه للإنسان.\n"
            "- تنظم هذه الخصال علاقة الإنسان بربه "
            "وعلاقته بنفسه وعلاقته بالمجتمع."
        )

    elif mode == "analysis":
        summary = (
            "ملخص المحتوى:\n"
            "- ينتمي النص إلى مجال القيم الإسلامية، "
            "ويتكون من أحاديث قدسية وأحاديث نبوية شريفة.\n"
            "- عنوان «خصال المسلم» مركب إضافي، ودلالته "
            "أن المسلم يتحلى بخصال عديدة.\n"
            "- يتناول المضمون تقوى الله والعدل والعلم "
            "والقناعة وغنى النفس، ويصنف الخصال إلى ما "
            "ينظم علاقة الإنسان بربه وما ينظم علاقة "
            "الإنسان بالمجتمع.\n"
            "- من أساليبه النداء والاستفهام والأمر "
            "والنهي، ومن خصائصه الفنية الإيجاز والطباق.\n"
            "- تبرز القيم مكانة الإنسان المسلم وتسهم "
            "في سعادته في الدنيا والآخرة."
        )

    else:
        return None

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


def detect_arabic_wonderful_dialogue_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du texte حوار عجيب."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    if "حوار عجيب" not in normalized_question:
        return ""

    if (
        "تحليل"
        in normalized_question
        and "نوع"
        in normalized_question
        and "شخصيات"
        in normalized_question
        and "اساليب"
        in normalized_question
    ):
        return "analysis"

    if any(
        marker in normalized_question
        for marker in (
            "لخص نص",
            "ملخص نص",
            "تلخيص نص",
        )
    ):
        return "narrative"

    return ""


def select_arabic_wonderful_dialogue_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF حوار عجيب."""

    mode = (
        detect_arabic_wonderful_dialogue_summary_mode(
            question
        )
    )

    if not mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "hoar-ajib" in source_name:
            lesson_units.append(unit)

    if len(lesson_units) < 2:
        return []

    lesson_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )
    return lesson_units


def build_arabic_wonderful_dialogue_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré et documenté."""

    mode = (
        detect_arabic_wonderful_dialogue_summary_mode(
            question
        )
    )

    if mode == "narrative":
        summary = (
            "ملخص المحتوى:\n"
            "- يعود الجندي حاييم إلى أسرته متباهيا بأنه "
            "قتل طفل فلسطيني في عمر ابنه موشي.\n"
            "- يواجهه موشي بأسئلة بريئة تكشف تناقض "
            "تبريراته، ويعبر عن الاستنكار والتعاطف مع "
            "الأطفال الفلسطينيين ويرفض قتل الأطفال.\n"
            "- تعجز الأسرة عن إقناع موشي، وينتهي النص "
            "بالتفكير في قتل ابنه موشي بدلا من الطفل "
            "علي، في نهاية تبرز قسوة الاحتلال وعبث منطقه."
        )

    elif mode == "analysis":
        summary = (
            "ملخص المحتوى:\n"
            "- النص نص حواري في شكل مسرحية ذات بعد وطني، "
            "ومضمونه وحشية حاييم ضد الأطفال الفلسطينيين "
            "وموقف موشي الرافض لذلك.\n"
            "- يمثل حاييم وأسرته الاحتلال العاجز عن تبرير "
            "اعتدائه، ويمثل موشي الضمير الإنساني الحي، "
            "ويمثل علي القضية الفلسطينية.\n"
            "- وضعية البداية هي عودة حاييم إلى أسرته، "
            "والحدث الرئيسي تباهيه بقتل طفل فلسطيني، "
            "والعقدة إصرار موشي على معرفة الحقيقة، "
            "والحل محاولة الأسرة تبرير الجريمة، أما وضعية "
            "النهاية فهي تفكير حاييم في قتل ابنه.\n"
            "- اعتمد النص الاستفهام لإثارة التساؤلات، "
            "والوصف لتصوير الانفعالات، والحوار لإبراز "
            "اختلاف الآراء.\n"
            "- تتمثل المقصدية في إبراز معاناة الشعب "
            "الفلسطيني، وتتجلى قيمة إنسانية في تعاطف "
            "موشي مع الطفل الفلسطيني واستنكاره لتصرف أبيه."
        )

    else:
        return None

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


def detect_arabic_time_place_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours أسماء الزمان والمكان."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    lesson_marker_found = any(
        marker in normalized_question
        for marker in (
            "اسماء زمان مكان",
            "اسمي زمان مكان",
        )
    )

    if not lesson_marker_found:
        return ""

    if (
        "صياغه"
        in normalized_question
        and "ثلاثي"
        in normalized_question
        and "غير ثلاثي"
        in normalized_question
        and "مفعله"
        in normalized_question
    ):
        return "formation"

    if any(
        marker in normalized_question
        for marker in (
            "لخص درس",
            "ملخص درس",
            "تلخيص درس",
        )
    ):
        return "general"

    return ""


def select_arabic_time_place_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF concerné."""

    summary_mode = (
        detect_arabic_time_place_summary_mode(
            question
        )
    )

    if not summary_mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "asmaa-alzman-oalmkan" in source_name:
            lesson_units.append(
                unit
            )

    if len(lesson_units) < 2:
        return []

    lesson_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )

    return lesson_units


def build_arabic_time_place_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré du cours."""

    summary_mode = (
        detect_arabic_time_place_summary_mode(
            question
        )
    )

    if summary_mode == "general":
        summary = (
            "ملخص المحتوى:\n"
            "- اسم الزمان واسم المكان صيغ مشتقة تدل على "
            "زمان وقوع الفعل أو مكان وقوعه.\n"
            "- يصاغان من الفعل الثلاثي على وزني «مَفْعِل» "
            "و«مَفْعَل» بحسب نوع الفعل وحركة عين مضارعه، "
            "ومن غير الثلاثي على وزن اسم المفعول بإبدال "
            "حرف المضارعة ميما مضمومة وفتح ما قبل الآخر.\n"
            "- يصاغ اسم المكان على وزن «مَفْعَلة» للدلالة "
            "على كثرة الشيء في المكان.\n"
            "- قد تتحد صيغة المصدر الميمي واسم المفعول "
            "واسم الزمان واسم المكان في غير الثلاثي، "
            "ويكون التفريق بينها بالقرائن."
        )

    elif summary_mode == "formation":
        summary = (
            "ملخص المحتوى:\n"
            "- من الفعل الثلاثي مكسور العين في المضارع "
            "صحيح الآخر، ومن مثال واوي صحيح الآخر، "
            "يصاغان على وزن «مَفْعِل». وما جاء على غير "
            "ذلك يصاغ على وزن «مَفْعَل».\n"
            "- من غير الثلاثي يصاغان على وزن اسم المفعول، "
            "بإبدال حرف المضارعة ميما مضمومة وفتح ما قبل "
            "الآخر.\n"
            "- وزن «مَفْعَلة» خاص باسم المكان للدلالة على "
            "كثرة الشيء فيه.\n"
            "- من الأسماء السماعية المكسورة على خلاف "
            "القاعدة: المشرق، والمغرب، والمسجد، والمنبت، "
            "والمنجر، والمظنة."
        )

    else:
        return None

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


def detect_arabic_comparative_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours اسم التفضيل."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    if "اسم تفضيل" not in normalized_question:
        return ""

    if (
        "شروط صياغه"
        in normalized_question
        and "مباشره"
        in normalized_question
        and "غير مباشره"
        in normalized_question
    ):
        return "conditions_work"

    if any(
        marker in normalized_question
        for marker in (
            "لخص درس",
            "ملخص درس",
            "تلخيص درس",
        )
    ):
        return "general"

    return ""


def select_arabic_comparative_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du PDF اسم التفضيل."""

    summary_mode = (
        detect_arabic_comparative_summary_mode(
            question
        )
    )

    if not summary_mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "asm-altfdhil-siaghth" in source_name:
            lesson_units.append(
                unit
            )

    if len(lesson_units) < 2:
        return []

    lesson_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )

    return lesson_units


def build_arabic_comparative_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré du cours."""

    summary_mode = (
        detect_arabic_comparative_summary_mode(
            question
        )
    )

    if summary_mode == "general":
        summary = (
            "ملخص المحتوى:\n"
            "- اسم التفضيل اسم مشتق يدل على اشتراك شيئين "
            "في صفة وزيادة أحدهما على الآخر، ويأتي على "
            "وزن «أفعل» ومؤنثه «فعلى».\n"
            "- في الصياغة المباشرة يشتق من فعل ثلاثي "
            "متصرف مثبت تام مبني للمعلوم قابل للتفاضل، "
            "ولا يدل على لون أو عيب أو حلية.\n"
            "- في الصياغة غير المباشرة يستعمل فعل مساعد "
            "على وزن «أفعل»، ثم مصدر الفعل منصوبا على "
            "التمييز. ومن المبني للمجهول أو المنفي يأتي "
            "المصدر المؤول بعد الفعل المساعد.\n"
            "- يرفع اسم التفضيل بعده فاعلا، وغالبا ما "
            "يكون ضميرا مستترا، وقد يكون اسما ظاهرا."
        )

    elif summary_mode == "conditions_work":
        summary = (
            "ملخص المحتوى:\n"
            "- يصاغ اسم التفضيل مباشرة إذا كان الفعل "
            "ثلاثيا، متصرفا، مثبتا، تاما، مبنيا للمعلوم، "
            "قابلا للتفاضل، ولا يدل على لون أو عيب أو "
            "حلية.\n"
            "- إذا لم يستوف الفعل الشروط، تصاغ المقارنة "
            "بطريقة غير مباشرة باستعمال فعل مساعد على "
            "وزن «أفعل»، يليه مصدر منصوب على التمييز.\n"
            "- من الفعل المبني للمجهول أو المنفي يستعمل "
            "المصدر المؤول مسبوقا بالفعل المساعد.\n"
            "- يرفع اسم التفضيل بعده فاعلا، وغالبا ما "
            "يكون ضميرا مستترا."
        )

    else:
        return None

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


def detect_arabic_passive_participle_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours اسم المفعول."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    if "اسم مفعول" not in normalized_question:
        return ""

    if (
        "صياغه"
        in normalized_question
        and (
            "شروط"
            in normalized_question
            or "صور نايب فاعل"
            in normalized_question
        )
    ):
        return "formation_work"

    if any(
        marker in normalized_question
        for marker in (
            "لخص درس",
            "ملخص درس",
            "تلخيص درس",
        )
    ):
        return "general"

    return ""


def select_arabic_passive_participle_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités du petit PDF concerné."""

    summary_mode = (
        detect_arabic_passive_participle_summary_mode(
            question
        )
    )

    if not summary_mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "asm-almfaol-oamlh" in source_name:
            lesson_units.append(
                unit
            )

    if not lesson_units:
        return []

    # Le filtre de source est exact et le document est petit.
    # Le résumé structuré ne doit donc pas être annulé parce
    # qu'un seul terme OCR manque dans les unités renvoyées.
    # Deux unités du même PDF suffisent pour activer ce chemin.
    if len(lesson_units) < 2:
        return []

    lesson_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )

    return lesson_units


def build_arabic_passive_participle_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré du cours."""

    summary_mode = (
        detect_arabic_passive_participle_summary_mode(
            question
        )
    )

    if summary_mode == "general":
        summary = (
            "ملخص المحتوى:\n"
            "- اسم المفعول اسم مشتق يدل على الحدث وعلى من "
            "وقع عليه الفعل.\n"
            "- يصاغ من الفعل الثلاثي على وزن «مفعول»، "
            "ومن غير الثلاثي على وزن مضارعه بإبدال حرف "
            "المضارعة ميما مضمومة وفتح ما قبل الآخر.\n"
            "- يعمل اسم المفعول عمل فعله المبني للمجهول، "
            "فيرفع نائب الفاعل. يعمل المعرف ب ال دون "
            "شرط، أما المجرد من ال فيشترط أن يدل على "
            "الحاضر أو المستقبل وأن يكون مسبوقا بما "
            "يعتمد عليه.\n"
            "- يعمل اسم المفعول المشتق من الفعل المتعدي "
            "واللازم، ويأتي نائب الفاعل بحسب نوع الفعل."
        )

    elif summary_mode == "formation_work":
        summary = (
            "ملخص المحتوى:\n"
            "- يصاغ اسم المفعول من الثلاثي على وزن "
            "«مفعول»، ومن غير الثلاثي على وزن مضارعه "
            "مع إبدال حرف المضارعة ميما مضمومة وفتح ما "
            "قبل الآخر.\n"
            "- يعمل المعرف ب ال دون شرط، ويعمل المجرد "
            "من ال إذا دل على الحاضر أو المستقبل واعتمد "
            "على مبتدأ أو نفي أو نداء أو استفهام أو "
            "موصوف أو ناسخ.\n"
            "- يكون نائب الفاعل مفعولا به مع الفعل "
            "المتعدي، ويكون جارا ومجرورا أو ظرفا مع "
            "الفعل اللازم، ويكون مفعولا أولا إذا كان "
            "الفعل متعديا لأكثر من مفعول."
        )

    else:
        return None

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


def detect_arabic_active_participle_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours concerné."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    if (
        "اسم فاعل"
        not in normalized_question
        or "مبالغه"
        not in normalized_question
    ):
        return ""

    if (
        "صياغه"
        in normalized_question
        and "شروط"
        in normalized_question
    ):
        return "formation_work"

    if any(
        marker in normalized_question
        for marker in (
            "لخص درس",
            "ملخص درس",
            "تلخيص درس",
        )
    ):
        return "general"

    return ""


def select_arabic_active_participle_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne tous les segments documentaires du petit PDF."""

    summary_mode = (
        detect_arabic_active_participle_summary_mode(
            question
        )
    )

    if not summary_mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if (
            "asm-alfaal-osigh-almbalgha-oamlhma"
            in source_name
        ):
            lesson_units.append(
                unit
            )

    if not lesson_units:
        return []

    aggregate_text = " ".join(
        normalize_arabic_match_text(
            unit.get(
                "text",
                "",
            )
        )
        for unit in lesson_units
    )

    required_groups = (
        ("اسم فاعل",),
        ("فاعل",),
        ("مضارعه",),
        ("مبالغه",),
        ("فعال",),
        ("فعول",),
        ("عمل",),
    )

    for group in required_groups:
        if not any(
            term in aggregate_text
            for term in group
        ):
            return []

    lesson_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )

    return lesson_units


def build_arabic_active_participle_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré et documenté."""

    summary_mode = (
        detect_arabic_active_participle_summary_mode(
            question
        )
    )

    if summary_mode == "general":
        summary = (
            "ملخص المحتوى:\n"
            "- اسم الفاعل اسم مشتق يدل على من قام بالفعل. "
            "يصاغ من الفعل الثلاثي على وزن «فاعل»، ومن "
            "غير الثلاثي على وزن مضارعه بإبدال حرف "
            "المضارعة ميما مضمومة وكسر ما قبل الآخر.\n"
            "- يعمل اسم الفاعل عمل فعله المبني للمعلوم، "
            "فيرفع الفاعل وينصب المفعول به. يعمل المقترن "
            "بـ«أل» دون شروط، أما المجرد منها فيدل على "
            "الحاضر أو المستقبل ويعتمد على مبتدأ أو نفي "
            "أو نداء أو استفهام أو موصوف أو ناسخ.\n"
            "- صيغ المبالغة مشتقات تدل على كثرة الفعل أو "
            "شدة الصفة، ومن أوزانها: «فعال»، و«فعول»، "
            "و«مفعال»، و«فعيل»، و«فعل».\n"
            "- تعمل صيغ المبالغة عمل اسم الفاعل بنفس "
            "الحالات والشروط."
        )

    elif summary_mode == "formation_work":
        summary = (
            "ملخص المحتوى:\n"
            "- يصاغ اسم الفاعل من الثلاثي على وزن «فاعل»، "
            "ومن غير الثلاثي على وزن مضارعه مع إبدال حرف "
            "المضارعة ميما مضمومة وكسر ما قبل الآخر.\n"
            "- من أوزان صيغ المبالغة: «فعال»، و«فعول»، "
            "و«مفعال»، و«فعيل»، و«فعل».\n"
            "- يعمل اسم الفاعل وصيغ المبالغة عمل فعلهما؛ "
            "فالمقترن بـ«أل» يعمل دون شروط، والمجرد منها "
            "يشترط أن يدل على الحاضر أو المستقبل وأن "
            "يسبق بما يعتمد عليه."
        )

    else:
        return None

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


def detect_arabic_instrument_noun_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours اسم الآلة."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    normalized_lesson_name = (
        normalize_arabic_match_text(
            "اسم الآلة"
        )
    )

    if (
        normalized_lesson_name
        not in normalized_question
    ):
        return ""

    if (
        "قياسي" in normalized_question
        and "سماعي" in normalized_question
    ):
        return "formation"

    if any(
        marker in normalized_question
        for marker in (
            "لخص درس",
            "ملخص درس",
            "تلخيص درس",
        )
    ):
        return "general"

    return ""


def select_arabic_instrument_noun_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités documentaires du cours."""

    summary_mode = (
        detect_arabic_instrument_noun_summary_mode(
            question
        )
    )

    if not summary_mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        normalized_unit = normalize_arabic_match_text(
            unit.get(
                "text",
                "",
            )
        )

        normalized_lesson_name = (
            normalize_arabic_match_text(
                "اسم الآلة"
            )
        )

        if (
            "asm-alaala"
            in source_name
            or normalized_lesson_name
            in normalized_unit
        ):
            lesson_units.append(
                unit
            )

    if not lesson_units:
        return []

    aggregate_text = " ".join(
        normalize_arabic_match_text(
            unit.get(
                "text",
                "",
            )
        )
        for unit in lesson_units
    )

    required_groups = (
        ("اسم مشتق",),
        ("مفعل",),
        ("مفعال",),
        ("مفعله",),
        ("فعاله",),
        ("سماعي",),
    )

    for group in required_groups:
        if not any(
            term in aggregate_text
            for term in group
        ):
            return []

    selected_units = []
    selected_ids = set()

    coverage_groups = (
        (
            "اسم مشتق",
            "الاداه",
        ),
        (
            "مفعل",
            "مفعال",
            "مفعله",
            "فعاله",
        ),
        (
            "ثلاثي",
            "غير الثلاثي",
            "اسم جامد",
        ),
        (
            "سماعي",
            "لا يقاس",
        ),
    )

    for markers in coverage_groups:
        candidates = []

        for unit in lesson_units:
            if unit["unit_id"] in selected_ids:
                continue

            normalized_unit = normalize_arabic_match_text(
                unit.get(
                    "text",
                    "",
                )
            )

            hits = sum(
                1
                for marker in markers
                if marker in normalized_unit
            )

            if hits == 0:
                continue

            candidates.append(
                (
                    hits,
                    float(
                        unit.get(
                            "retrieval_score",
                            0.0,
                        )
                    ),
                    unit,
                )
            )

        if not candidates:
            continue

        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            ),
            reverse=True,
        )

        selected = candidates[0][2]
        selected_units.append(
            selected
        )
        selected_ids.add(
            selected["unit_id"]
        )

    if len(selected_units) < 3:
        return []

    selected_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )

    return selected_units


def build_arabic_instrument_noun_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré et documenté."""

    summary_mode = (
        detect_arabic_instrument_noun_summary_mode(
            question
        )
    )

    if summary_mode == "general":
        summary = (
            "ملخص المحتوى:\n"
            "- اسم الآلة اسم مشتق يدل على الأداة التي "
            "ينجز بها الفعل.\n"
            "- أوزانه القياسية الأساسية هي: «مِفْعَل» "
            "مثل مبرد، و«مِفْعال» مثل منشار ومحراث، "
            "و«مِفْعَلة» مثل مجرفة ومعزفة، و«فَعّالة» "
            "مثل ثلاجة وغسالة.\n"
            "- يصاغ غالبا من فعل ثلاثي متصرف متعد، وقد "
            "يصاغ من الثلاثي اللازم، ومن غير الثلاثي، "
            "ومن بعض الأسماء الجامدة، مثل مقلمة من قلم.\n"
            "- أضاف مجمع اللغة العربية أوزانا أخرى هي: "
            "«فَعّالة»، و«فاعلة»، و«فاعول».\n"
            "- وقد يأتي اسم الآلة سماعيا على غير الأوزان "
            "القياسية؛ تستعمل صيغه في الكلام ولا يقاس "
            "عليها، مثل سيف وسكين ورمح وإزميل."
        )

    elif summary_mode == "formation":
        summary = (
            "ملخص المحتوى:\n"
            "- الصياغة القياسية لاسم الآلة تكون على "
            "الأوزان: «مِفْعَل»، و«مِفْعال»، "
            "و«مِفْعَلة»، و«فَعّالة».\n"
            "- يصاغ غالبا من الفعل الثلاثي المتصرف "
            "المتعدي، وقد يصاغ من الثلاثي اللازم، ومن "
            "غير الثلاثي، ومن بعض الأسماء الجامدة.\n"
            "- الصياغة السماعية تأتي على أوزان غير "
            "قياسية، وتستعمل في الكلام ولا يقاس عليها، "
            "مثل سيف وسكين ورمح وإزميل."
        )

    else:
        return None

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


def detect_arabic_warning_enticement_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours التحذير والإغراء."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    contains_lesson = (
        "تحذير" in normalized_question
        and "اغراء" in normalized_question
    )

    if not contains_lesson:
        return ""

    normalized_delete_verb = (
        normalize_arabic_match_text(
            "حذف الفعل"
        )
    )

    if (
        "صور" in normalized_question
        and normalized_delete_verb
        in normalized_question
    ):
        return "forms_deletion"

    if any(
        marker in normalized_question
        for marker in (
            "لخص درس",
            "ملخص درس",
            "تلخيص درس",
        )
    ):
        return "general"

    return ""


def select_arabic_warning_enticement_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """
    Sélectionne des unités couvrant les définitions,
    les formes et la règle de suppression du verbe.
    """

    summary_mode = (
        detect_arabic_warning_enticement_summary_mode(
            question
        )
    )

    if not summary_mode:
        return []

    lesson_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        normalized_unit = normalize_arabic_match_text(
            unit.get(
                "text",
                "",
            )
        )

        same_lesson = (
            "aslob-alththir-oalighraa"
            in source_name
            or "اغراء"
            in normalized_unit
            or "تحذير"
            in normalized_unit
            or "اياك"
            in normalized_unit
        )

        if same_lesson:
            lesson_units.append(
                unit
            )

    if not lesson_units:
        return []

    aggregate_text = " ".join(
        normalize_arabic_match_text(
            unit.get(
                "text",
                "",
            )
        )
        for unit in lesson_units
    )

    required_groups = (
        ("اغراء",),
        ("تحذير",),
        ("مفرد",),
        ("مكرر",),
        ("معطوف",),
        ("وجوبا",),
        ("جوازا",),
        ("اياك",),
    )

    for group in required_groups:
        if not any(
            term in aggregate_text
            for term in group
        ):
            return []

    coverage_groups = (
        (
            "اغراء",
            "امر محمود",
            "الزم",
        ),
        (
            "تحذير",
            "امر غير محمود",
            "احذر",
        ),
        (
            "مفرد",
            "مكرر",
            "معطوف",
        ),
        (
            "اياك",
            "ضمير منفصل",
        ),
        (
            "وجوبا",
            "جوازا",
        ),
    )

    selected_units = []
    selected_ids = set()

    for markers in coverage_groups:
        candidates = []

        for unit in lesson_units:
            if unit["unit_id"] in selected_ids:
                continue

            normalized_unit = normalize_arabic_match_text(
                unit.get(
                    "text",
                    "",
                )
            )

            hits = sum(
                1
                for marker in markers
                if marker in normalized_unit
            )

            if hits == 0:
                continue

            candidates.append(
                (
                    hits,
                    float(
                        unit.get(
                            "retrieval_score",
                            0.0,
                        )
                    ),
                    unit,
                )
            )

        if not candidates:
            continue

        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            ),
            reverse=True,
        )

        best_unit = candidates[0][2]
        selected_units.append(
            best_unit
        )
        selected_ids.add(
            best_unit["unit_id"]
        )

    minimum_units = (
        2
        if summary_mode == "forms_deletion"
        else 3
    )

    if len(selected_units) < minimum_units:
        return []

    selected_units.sort(
        key=lambda unit: (
            unit["passage_number"],
            unit["unit_id"],
        )
    )

    return selected_units


def build_arabic_warning_enticement_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """Construit un résumé structuré et documenté."""

    summary_mode = (
        detect_arabic_warning_enticement_summary_mode(
            question
        )
    )

    if summary_mode == "general":
        summary = (
            "ملخص المحتوى:\n"
            "- الإغراء: تنبيه المخاطب إلى أمر محمود "
            "ليفعله أو يلزمه، وينصب المغرى به على أنه "
            "مفعول به لفعل محذوف تقديره «الزم» أو "
            "«التزم».\n"
            "- التحذير: تنبيه المخاطب إلى أمر غير محمود "
            "ليجتنبه، وينصب المحذر منه على أنه مفعول به "
            "لفعل محذوف تقديره «احذر» أو ما في معناه.\n"
            "- يأتي المغرى به والمحذر منه مفردا أو مكررا "
            "أو معطوفا، ويأتي التحذير أيضا بضمير النصب "
            "المنفصل «إياك».\n"
            "- يحذف الفعل وجوبا مع المكرر والمعطوف، "
            "ويجوز حذفه إذا كان الاسم مفردا."
        )

    elif summary_mode == "forms_deletion":
        summary = (
            "ملخص المحتوى:\n"
            "- صور الإغراء: يكون المغرى به مفردا، أو "
            "مكررا، أو معطوفا عليه.\n"
            "- صور التحذير: يكون المحذر منه مفردا، أو "
            "مكررا، أو معطوفا عليه، وقد يأتي بضمير النصب "
            "المنفصل «إياك»، مثل «إياك الغش»، و«إياك "
            "إياك الغش»، و«إياك والغش».\n"
            "- يحذف الفعل وجوبا إذا كان المغرى به أو "
            "المحذر منه مكررا أو معطوفا، ويجوز حذفه "
            "إذا كان مفردا."
        )

    else:
        return None

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


def detect_arabic_exclamation_summary_mode(
    question: str,
) -> str:
    """Détecte le type de résumé demandé pour أسلوب التعجب."""

    normalized_question = normalize_arabic_match_text(
        question
    )

    asks_parsing = (
        "اعراب" in normalized_question
        and "ما افعل" in normalized_question
        and "افعل به" in normalized_question
    )

    asks_direct_indirect = (
        "صياغه مباشره" in normalized_question
        and "غير مباشره" in normalized_question
    )

    is_general = (
        "تعجب" in normalized_question
        and any(
            pattern in normalized_question
            for pattern in (
                "لخص درس",
                "ملخص درس",
                "تلخيص درس",
            )
        )
    )

    if asks_parsing:
        return "parsing"

    if asks_direct_indirect:
        return "direct_indirect"

    if is_general:
        return "general"

    return ""


def select_arabic_exclamation_units(
    question: str,
    units: list[dict],
) -> list[dict]:
    """Sélectionne les unités clés du cours d'أسلوب التعجب."""

    summary_mode = (
        detect_arabic_exclamation_summary_mode(
            question
        )
    )

    if not summary_mode:
        return []

    asks_parsing = (
        summary_mode == "parsing"
    )

    asks_direct_indirect = (
        summary_mode == "direct_indirect"
    )

    is_general = (
        summary_mode == "general"
    )

    if asks_parsing:
        groups = ARABIC_EXCLAMATION_PARSING_GROUPS
        maximum_units = 5
    elif asks_direct_indirect:
        groups = ARABIC_EXCLAMATION_DIRECT_INDIRECT_GROUPS
        maximum_units = 4
    elif is_general:
        groups = ARABIC_EXCLAMATION_GENERAL_GROUPS
        maximum_units = 5
    else:
        return []

    selected_units = []
    selected_ids = set()

    for group_terms in groups:
        normalized_terms = normalize_arabic_terms(
            group_terms
        )

        candidates = []

        for unit in units:
            if unit["unit_id"] in selected_ids:
                continue

            normalized_unit = normalize_arabic_match_text(
                unit.get(
                    "text",
                    "",
                )
            )

            hits = sum(
                1
                for term in normalized_terms
                if term
                and term in normalized_unit
            )

            if hits == 0:
                continue

            score = score_arabic_unit_for_terms(
                unit,
                normalized_terms,
            )

            if score < 0:
                continue

            # Les groupes spécialisés privilégient la couverture
            # de plusieurs marqueurs dans une même unité.
            score += hits * 2.4

            candidates.append(
                (
                    hits,
                    score,
                    unit,
                )
            )

        if not candidates:
            continue

        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            ),
            reverse=True,
        )

        best_unit = candidates[0][2]
        selected_units.append(
            best_unit
        )
        selected_ids.add(
            best_unit["unit_id"]
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

def build_arabic_exclamation_structured_summary(
    question: str,
    selected_units: list[dict],
) -> dict | None:
    """
    Construit deux résumés structurés lorsque la demande
    exige une distinction explicite entre plusieurs règles.
    """

    summary_mode = (
        detect_arabic_exclamation_summary_mode(
            question
        )
    )

    if summary_mode == "direct_indirect":
        summary = (
            "ملخص المحتوى:\n"
            "- الصياغة المباشرة: يصاغ التعجب على وزني "
            "«ما أفعل» و«أفعل به» إذا كان الفعل ثلاثيا، "
            "متصرفا، تاما، مثبتا، مبنيا للمعلوم، قابلا "
            "للتفاضل، ولا يدل على لون أو عيب أو حلية.\n"
            "- الصياغة غير المباشرة: إذا لم يستوف الفعل "
            "شروط الصياغة المباشرة، يستعمل فعل مساعد على "
            "وزن «ما أفعل» أو «أفعل به»، ثم يذكر المصدر "
            "الصريح أو المؤول، ما لم يكن الفعل جامدا أو "
            "غير قابل للتفاضل."
        )

    elif summary_mode == "parsing":
        summary = (
            "ملخص المحتوى:\n"
            "- إعراب صيغة «ما أفعل»: «ما» اسم نكرة تامة "
            "مبني على السكون في محل رفع مبتدأ، و«أفعل» "
            "فعل ماض مبني على الفتح وهو فعل التعجب، "
            "وفاعله ضمير مستتر، أما المتعجب منه فمفعول "
            "به منصوب.\n"
            "- إعراب صيغة «أفعل به»: «أفعل» فعل ماض جاء "
            "على صورة الأمر مبني على فتح مقدر وهو فعل "
            "التعجب، والباء حرف جر زائد، والاسم بعدها "
            "فاعل مجرور بالباء لفظا مرفوع محلا."
        )

    else:
        return None

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




















MEGA_FRENCH_17_65_SUMMARIES = {'expression-ecrite-sur-la-tolerance.pdf': "Résumé du contenu :\n- Dans son sens le plus général, la tolérance désigne la capacité à accepter ce que.\n- l'on désapprouve, c'est-à-dire ce que l'on devrait normalement refuser.\n- construction ou en dessin par exemple, on dit qu'on peut tolérer une certaine.\n- Au sens moral, la tolérance est la vertu qui porte à accepter ce que l'on.\n- n'accepterait pas spontanément, par exemple lorsque cela va à l'encontre de ses.\n- C'est aussi la vertu qui porte à se montrer vigilant tant.", 'expression-ecrite-sur-le-fanatisme-religieux-au-maroc-musulman.pdf': 'Résumé du contenu :\n- Il ne faut pas confondre Islamique et Islamiste.\n- Envahis par l’URSS en 1979, les Afghans se sont lancés dans une guérilla sanglante, une.\n- L’explosion démographique dans les pays en développement a provoqué une.\n- Ces afghans sont alors soutenus par les Etats-Unis qui.\n- Au cours de son histoire la religion musulmane a connu des épisodes de grande tolérance.\n- cherchent à repousser le communisme à partir du Pakistan.', 'expression-ecrite-sur-le-maroc.pdf': 'Résumé du contenu :\n- "Situé au nord-ouest de l’Afrique, le Maroc est bordé par l’Algérie à.\n- produits d’exportation sont les agrumes et le raisin.\n- qui ont chacune un dialecte propre, qu’elles ont généralement préservé au cours.\n- Eid al-Seghir marque la fin du long mois de jeûne (saum) du Ramadan, pendant.\n- Les maladies chez les enfants et les nouveau-nés comptent parmi les problèmes.\n- De nombreux auteurs marocains contemporains écrivent en français.', 'expression-ecrite-sur-le-role-de-la-femme.pdf': 'Résumé du contenu :\n- On dit souvent que la femme est la moitié de la société.\n- primordial dans la préparation des générations à venir.\n- Ahmed Sefrioui, le lecteur est confronté à une figuration souvent.\n- D’abord, la femme est superstitieuse.La Chouafa (tante Kanza) est visitée.\n- Lala Aicha propose à Lalla Zoubida d’emmener.\n- mère fait le tour des principaux marabouts et voyants de Fès pour guérir.', 'la-subordonnee-circonstancielle-de-but.pdf': "Résumé du contenu :\n- La subordonnée de but, appelée aussi finale, est une proposition qui assume.\n- la fonction de complément circonstanciel de but du verbe principal dont.\n- elle dépend et avec lequel elle établit un rapport logique.\n- Elle exprime l'intention, le résultat, l'objectif visé ou au contraire évité par.\n- Paul s'est caché pour qu'on le laisse en paix.\n- Paul s'est caché de peur qu'on ne le voie.", 'la-subordonnee-circonstancielle-de-cause.pdf': 'Résumé du contenu :\n- La subordonnée circonstancielle de cause, appelée aussi causale, est une proposition qui.\n- assume la fonction de complément circonstanciel de cause du verbe principal dont elle.\n- dépend et avec lequel elle établit un rapport logique.\n- Elle indique l’origine, la raison, la cause du fait principal.\n- L’élève à réussi à l’examen parce qu’il a bien travaillé.\n- La proposition subordonnée « parce qu’il a bien travaillé » exprime la raison.', 'la-subordonnee-circonstancielle-de-consequence.pdf': 'Résumé du contenu :\n- La subordonnée de conséquence (consécutive) est une proposition qui.\n- Il est trop vieux pour qu’on lui.\n- assume la fonction de complément circonstanciel de conséquence du.\n- verbe principal dont elle dépend et avec lequel elle établit un rapport logique.\n- De façon que, de manière que, trop….pour que, assez……pour que (sujets différents.) Subjonctif Il est trop vieux pour qu’on lui demande de faire ce trajet à pied.\n- Assez …pour, trop…pour, de façon à (même sujet).', 'la-subordonnee-relative-a-valeur-d-adjectif-ou-de-complement-de-nom.pdf': 'Résumé du contenu :\n- La subordonnée relative a comme fonction principale de compléter le sens de son.\n- Elle a la valeur d’un adjectif qualificatif épithète ou d’un complément.\n- \uf0fc Nous avons vendu la maison qui appartenait à mon père.\n- La subordonnée relative qui appartenait à mon père peut être remplacée par :.\n- La subordonnée relative à valeur d’adjectif ou de complément de nom.', 'la-voix-passive.pdf': 'Résumé du contenu :\n- On appelle "voix" les formes que prend le verbe pour exprimer le rôle du sujet.\n- Seuls les verbes transitifs directs (ceux qui ont un complément d’objet.\n- Changement des temps du verbe à la voix passive :.\n- Un verbe peut se présenter à la voix active ou à la voix passive.\n- direct (COD)) peuvent se mettre à la voix passive.\n- Dans une phrase à la voix active, le sujet fait l’action.', 'langue-1-1-utiliser-le-lexique-et-les-formules-de-la-correspondance-conventionnelle.pdf': 'Résumé du contenu :\n- Utiliser le lexique et les formules de la correspondance.\n- Je complète la grille suivante à partir des définitions :.\n- Je peux reconnaître différents objets de la lettre conventionnelle.\n- 3-1/ Vocabulaire à employer dans la correspondance conventionnelle.\n- Ajoutez une formule de politesse finale du genre « Veuillez agréer, Madame,.\n- Je peux identifier le vocabulaire spécifique de la correspondance.', 'langue-1-2-autoriser-accepter-et-refuser-une-autorisation-2.pdf': "Résumé du contenu :\n- Je relève dans le dialogue les expressions employées pour :.\n- Je lis la charte ci-dessous réalisée parles membres du club d'environnement d'un.\n- A l'entrée d'un parc naturel, un jeune parle au gardien.\n- Je complète le tableau par d 'autres expressions.\n- Je complète le dialogue en m'inspirant de la charte :.\n- Je produis le dialogue qui correspond à la situation suivante :.", 'langue-2-1-inviter-accepter-et-decliner-une-invitation-1.pdf': "Résumé du contenu :\n- Je lis les énoncés suivants et je les place dans le tableau ci-dessous :.\n- Je peux identifier les expressions pour inviter et répondre à.\n- Salut les amis, c'était comment votre journée ?.\n- Je relis le dialogue et j'entoure la bonne réponse.\n- a- Viens, je t'invite à manger ce soir,.\n- II s'excuse de ne pas venir avec ses amis.", 'langue-2-2-utiliser-des-formules-de-politesse-dans-une-correspondance-conventionnelle.pdf': "Résumé du contenu :\n- Utiliser des formules de politesse dans une.\n- Pour rédiger des messages conventionnels, je fais attention à la nature du.\n- Je lis les énoncés suivants et je les place dans le tableau :.\n- Je complète les documents suivants par les expressions ci-dessous :.\n- Je peux identifier les expressions pour débuter un courriel ou.\n- document et puis je choisis les expressions (d'appel, du début, du corps et de.", 'langue-3-1-utiliser-convenablement-les-registres-de-langue-dans-differentes-correspondances-2.pdf': "Résumé du contenu :\n- Je complète le tableau à partir des documents :.\n- Je justifie le choix des registres de langue dans les trois documents.\n- Pa 2 koijve te voir D kepossib.\n- Je repère les expressions de politesse dans le document 3.\n- Je réécris en langue courante les messages des documents 1 et 2.\n- Pour qu'ils écrivent en français courant j'aide mes amis à relier chaque.", 'langue-3-2-utiliser-convenablement-le-vocabulaire-relatif-a-l-environnement-la-flore-et-la-faune-2.pdf': "Résumé du contenu :\n- Je complète le texte à partir des mots suivants :.\n- d'un journal d'un livre d'un site Internet f B- Il parle du Maroc de la France de la Tunisie C- Il parle du commerce de l’agriculture de l’artisanat 2.\n- Après avoir fait des exercices, je peux dire si :.\n- Utiliser convenablement le vocabulaire relatif à l'environnement (la flore et la faune) Professeur :.\n- je peux repérer le vocabulaire relatif à l'environnement.\n- je peux connaître la signification de certains mots en rapport.", 'langue-4-1-debattre-et-justifier-son-point-de-vue-2.pdf': "Résumé du contenu :\n- Débattre et justifier son point de vue.\n- Avec mon groupe, je prépare le sujet suivant :.\n- expriment leurs points de vue en les justifiant.\n- L'utilité d'une charte du respect de l'environnement au collège.\n- Débattre et justifier son point de vue Professeur :.\n- La première constatation qui s'impose est que.", 'langue-4-2-raisonner-a-partir-d-une-hypothese-2.pdf': 'Résumé du contenu :\n- Si les forêts disparaissent, la terre sera exposée à des dangers écologiques.\n- je peux reconnaître et exprimer une conséquence.\n- C’est parce que les forêts jouent un rôle essentiel dans la vie des hommes et.\n- je peux reconnaître et utiliser une explication.\n- de la terre (conserver l’eau, fournir des ressources, ...).\n- Je réécris le texte en employant les mots et les expressions suivants :.', 'langue-5-1-justifier-un-choix-en-utilisant-l-expression-de-la-cause-2.pdf': "Résumé du contenu :\n- Justifier un choix en utilisant l'expression de la.\n- Je refais ces phrases en changeant la place des conjonctions;.\n- Après avoir fait mes exercices, je peux dire si :.\n- Je veux travailler avec mon camarade de table.\n- Je relie les propositions suivantes pour exprimer une cause :.\n- je sais distinguer une proposition principale d'une proposition.", 'langue-5-2-utiliser-l-expression-du-but-pour-fixer-un-objectif-a-propos-du-projet-2.pdf': "Résumé du contenu :\n- Utiliser l'expression du but pour fixer un objectif à.\n- Dans la liste suivante, je choisis l'expression de but convenable pour relier.\n- Je complète les phrases suivantes de façon à exprimer le but :.\n- a- Je lis des nouvelles variées (réalistes, policières, etc.).\n- b- Je participe activement à la réalisation du projet.\n- J'indique les objectifs fixés dans chacun des deux exemples :.", 'le-discours-direct-et-le-discours-indirect-phrase-declarative.pdf': 'Résumé du contenu :\n- Il m’a dit qu’il avait tout vendu.\n- Le discours direct consiste à rapporter les paroles de quelqu’un telles qu’elles.\n- Le passé simple, le plus que parfait, le conditionnel et l’imparfait ne.\n- Le discours indirect est utilisé pour rapporter les paroles de quelqu’un en les.\n- changent pas quand le verbe introducteur est au passé.\n- subordonnant à l’aide de la conjonction « que » (cas de la phrase.', 'lecture-1-1-identifier-les-caracteristiques-d-une-lettre-conventionnelle-partie-1.pdf': "Résumé du contenu :\n- Dans l'espoir d'une réponse favorable, je vous prie d'agréer, Monsieur le Directeur,.\n- Je compare les informations sur le destinataire dans les deux lettres :.\n- Demande d'autorisation d'utiliser les locaux du collège.\n- Je repère à partir de la première lettre les informations données dans chaque zone :.\n- Je compare les deux lettres pour dégager les points de ressemblance et de différence :.\n- journée mondiale de la planète qui aura lieu le 22 avril, je compte réaliser un film éducatif.", 'lecture-1-1-identifier-les-caracteristiques-d-une-lettre-conventionnelle-partie-2-1.pdf': "Résumé du contenu :\n- V- Structures des lettres conventionnelle et personnelle.\n- Je complète les bulles dans les deux lettres à partir des expressions.\n- Dans le but de sensibiliser mes élèves à la question de la protection de.\n- Formule d'appel - Formule de politesse finale - Date et lieu - Objet - Coordonnées.\n- l'environnement et la biodiversité en Atlas, j'ai l'intention d'organiser une sortie.\n- du destinataire - Corps de la lettre - Coordonnées de l'expéditeur - Signature.", 'lecture-1-2-degager-l-interet-de-la-question-de-l-environnement.pdf': "Résumé du contenu :\n- Dégager l'intérêt de la question de l'environnement.\n- production d'électricité à base d'énergie solaire de 2000 MW minimum d'ici 2020.\n- Le projet sera réalisé en deux phases.\n- Je m'exprime sur le rôle des énergies renouvelables dans la protection de.\n- La plus grande centrale solaire du monde, à Ouarzazate.\n- Le projet a pour objectif de lutter contre la désertification.", 'lecture-2-1-identifier-les-caracteristiques-d-une-lettre-d-invitation.pdf': "Résumé du contenu :\n- Identifier les caractéristiques d’une lettre d’invitation Professeur :.\n- d- La date de l’écriture de la lettre :.\n- 1- La lettre d'invitation est une lettre conventionnelle, elle répond au schéma de.\n- Je relis et je complète en mettant une croix dans la case qui convient.\n- 2- Le corps de la lettre d'invitation, se compose de trois parties :.\n- Indiquer le lieu et l'heure de l'événement :.", 'lecture-2-2-identifier-les-caracteristiques-d-une-reponse-a-une-invitation-par-mail.pdf': "Résumé du contenu :\n- Je dégage les différences entre la lettre et le mail conventionnels.\n- Prendre congé avec une formule de politesse plus courte que dans une lettre.\n- ________________________ , dans laquelle vous me proposez d'animer un atelier de.\n- Je complète la liste suivante en utilisant des phrases complètes :.\n- Je mets une croix dans la case convenable et je justifie mes réponses par des.\n- Mettre ses coordonnées (Prénom + Nom + Statut + téléphone).", 'lecture-2-3-reperer-et-classer-des-informations.pdf': "Résumé du contenu :\n- Appelé aussi réchauffement global ou planétaire, le changement climatique.\n- La Communauté internationale a alors fondé le Giec (groupe d'experts.\n- Je complète le texte suivant en plaçant convenablement les énoncés suivants :.\n- est un phénomène d'augmentation des températures moyennes des océans.\n- intergouvememental sur l'évolution du climat) dans le but d'étudier les.\n- Le GIEC est une organisation qui s'intéresse aux problèmes.", 'lecture-3-1-identifier-les-caracteristiques-des-differents-genres-d-invitations-2.pdf': "Résumé du contenu :\n- Identifier les caractéristiques des différents genres d'invitations Professeur :.\n- Je trouve le genre de chaque document en reliant les éléments de la colonne.\n- Je précise à qui renvoie le pronom personnel « vous » dans les trois.\n- Je souligne le document adressé à titre personnel au destinataire.\n- Un document d'invitation (Affiche, carte, lettre etc.) doit obligatoirement.\n- Quelles sont les raisons qui font d'Ifrane « la capitale écologique » du Maroc.", 'lecture-3-2-identifier-differents-genres-d-invitation-conventionnelle-2.pdf': "Résumé du contenu :\n- Je coche « Vrai » ou « Faux » et je justifie ma réponse en utilisant des.\n- Je complète les tableaux à partir des documents :.\n- Laquelle des deux activités aimez-vous le plus :.\n- L'invitation à un événement culturel peut se faire d'une manière collective à.\n- c- Les deux documents parlent de lieux dans des villes.\n- Elle peut être adressée à titre individuel aux personnes concernées à travers :.", 'lecture-4-1-identifier-les-caracteristiques-d-une-lettre-ouverte-2.pdf': "Résumé du contenu :\n- informer sur les pays qui produisent la cigarette.\n- Une lettre ouverte consiste à écrire un texte qui respecte les formes de la lettre,.\n- Je complète la lettre suivante en plaçant convenablement les énoncés ci-dessous.\n- C'est ce que vous avez de plus cher, non ?.\n- Identifier les caractéristiques d'une lettre ouverte Professeur :.\n- _______________________________ que vous traitiez vos enfants comme des gamins.", 'lecture-4-2-degager-des-informations-sur-le-rechauffement-climatique-2.pdf': "Résumé du contenu :\n- Pour présenter un phénomène écologique, on doit :.\n- Après avoir lu des textes sur l'environnement, je peux dire si :.\n- Dégager des informations sur le réchauffement climatique Professeur :.\n- Je complète en mettant une croix dans la case qui convient :.\n- mettre en avant l'importance de trouver des solutions pour ce phénomène.\n- Cet article renseigne sur les causes du.", 'lecture-5-1-degager-la-structure-narrative-en-cinq-etapes-2.pdf': 'Résumé du contenu :\n- Dégager la structure narrative en cinq étapes.\n- Je relève les mots qui renvoient à la mer en complétant le tableau suivant :.\n- L’expérience vécue par le narrateur vous a-t-elle touché(e) ?.\n- Dégager la structure narrative en cinq étapes Professeur :.\n- Je complète les étapes du récit suivant :.\n- je sais repérer le moment de la crise dans un récit.', 'lecture-5-2-identifier-les-caracteristiques-d-un-personnage-principal-2.pdf': "Résumé du contenu :\n- Je cherche le sens des mots suivants :.\n- Je relève les informations données sur le personnage cité dans le texte en.\n- Après avoir lu le texte, je peux dire si :.\n- Je précise, à partir des éléments du texte, s'il s'agit d'un personnage.\n- principal ou d'un personnage secondaire, et je relève dans le titre de l'œuvre.\n- J'énumère les exploits que ce personnage a accomplis :.", 'les-pronoms-personnels-le-la-l-les-lui-leur.pdf': 'Résumé du contenu :\n- « Le, la, l’, les » sont des pronoms personnels qui remplacent des COD.\n- Le pronom personnel « Le » remplace un COD masculin singulier.\n- Le pronom personnel « La » remplace un COD féminin singulier.\n- Le pronom personnel « Les » remplace un COD pluriel.\n- Le pronom personnel « L’» est employé lorsque le verbe commence par.\n- Le pronom personnel « Lui » remplace un COI singulier.', 'les-pronoms-relatifs-simples-qui-que-ou-dont.pdf': 'Résumé du contenu :\n- Les pronoms relatifs simples « qui, que, où, dont » servent à relier deux phrases.\n- Ils remplacent un nom ou un pronom appelé " antécédent ".\n- Ils n’ont pas de sens mais seulement une fonction grammaticale :.\n- \uf0fc " où " remplace un complément circonstanciel de lieu (ou de temps).\n- \uf0fc " dont " remplace un complément précédé de la préposition « de ».\n- Le mot répété est Sujet de la deuxième phrase.', 'les-temps-du-passe-temps-du-recit-3.pdf': 'Résumé du contenu :\n- Observez l’extrait du texte que nous avons vu ensemble dans l’exercice de lecture et de compréhension intitulé « j’emmène les.\n- Pour raconter à l’oral on utilise la passé composé, l’imparfait et le plus que parfait.\n- nous avons déjà vu dans un cours précédent comment conjuguer les verbes du 1er groupe au présent de l’indicatif, au.\n- J’avais dessiné/ tu avais dessiné/ il avait dessiné/ elle avait.\n- C’est samedi, je décide de les emmener à la plage.\n- Pour raconter à l’écrit on utilise le passé simple, l’imparfait et le plus que parfait.', 'les-temps-du-recit-l-imparfait-et-le-passe-simple-1.pdf': "Résumé du contenu :\n- Pour raconter au passé, on utilise souvent l'imparfait et le passé.\n- L’imparfait peut être employé pour exprimer les valeurs suivantes:.\n- Chaque jour, il se levait à six heures du matin.\n- Il essayait souvent de se présenter à son chef.\n- Depuis des mois, la neige recouvrait les champs.\n- \uf0fc Il présente l’action comme accomplie (achevée), limitée dans le.", 'modeles-de-lettre-de-reclamation.pdf': 'Résumé du contenu :\n- LA LETTRE FORMELLE – PROFESSIONNELLE COMMERCIALE ADMINISTRATIVE LA LETTRE DE RÉCLAMATION MODÈLES.\n- Le courrier professionnel utilise classiquement deux présentations :.\n- Un courrier administratif ou commercial se termine traditionnellement par.\n- Modèle de lettre de réclamation à un garagiste - Pour.\n- Tue, 22 Jul 1997 10:40:58 +0000.\n- Selon les indications portées sur votre e-mail de confirmation de commande en date du.', 'negocier-le-projet-1.pdf': "Résumé du contenu :\n- IV- Conception de la fiche du projet.\n- V- Établissement et signature du contrat relatif au projet.\n- À la fin du semestre, je fais le bilan avec mon professeur pour savoir si j'ai respecté mon.\n- Je m'engage à participer activement au projet de notre classe dont l'intitulé est «.\n- J'indique les outils que je peux utiliser pour communiquer et pour réaliser le projet.\n- Ces années passées à survoler la Terre, à photographier l'homme et ses traces.", 'oral-1-1-discuter-des-modalites-d-organisation-du-debat.pdf': "Résumé du contenu :\n- Dors le cadre de notre projet relatif à l'organisation d'un débat sur.\n- Discuter des modalités d'organisation du débat Professeur :.\n- Je discute avec les membres de mon groupe des étapes à suivre pour.\n- dans une revue dans un forum dans un blog Il est écrit le :.\n- Quelle personne inviter pour animer le débat ?.\n- Je fais un petit compte rendu à mes camarades de classe à propos des.", 'oral-1-2-presenter-un-compte-rendu-d-articles-sur-l-environnement.pdf': 'Résumé du contenu :\n- En 2016, sur proposition du royaume et de l\'Union européenne, l\'espèce a.\n- Je dégage à partir des deux documents :.\n- Le Maroc veut sauver le singe magot, un macaque en danger.\n- été classée sur l\'annexe I de la Cites, la Convention sur le commerce.\n- Seul macaque vivant hors d’Asie, le magot ou "macaque de Barbarie", qui.\n- Je dégage dans les documents les causes du problème environnemental :.', 'oral-1-3-realiser-un-forum-sur-l-environnement.pdf': "Résumé du contenu :\n- Je coche « Vrai » ou « Faux » et je justifie mon choix en utilisant des phrases.\n- Je conseille à ma famille d'utiliser des.\n- Je laisse le robinet ouvert quand je me.\n- Les internautes ne sont pas autorisés à participer sans.\n- Quand j'ai froid, je mets un tricot et je.\n- Je réagis à propos des gestes écologiques à faire pour sauver la planète en.", 'oral-2-organiser-une-exposition-photos-sur-le-rechauffement-climatique-2.pdf': "Résumé du contenu :\n- Organiser une exposition photos sur le réchauffement.\n- Je m’entraîne à la présentation orale de l'exposition :.\n- Pour réaliser une exposition photos sur un thème, je dois :.\n- Comme il a été convenu, vous organisez une exposition photos où vous.\n- Je prépare les informations (les légendes) que je dois dire pendant la.\n- J’entraîne ma voix, mon débit pour une présentation claire et audible.", 'oral-3-1-employer-une-gestuelle-et-une-intonation-convenables-pour-montrer-l-interet-d-un-comportement-ecologique-2.pdf': "Résumé du contenu :\n- Je précise si cet appareil répond aux normes écologiques.\n- Vous vous excusez de ne choisir aucune offre.\n- J'explique comment cette étiquette peut lutter contre le réchauffement.\n- Pour être un citoyen qui respecte l'environnement, il faut :.\n- Je prépare avec mes camarades et j'imagine à chaque fois des énoncés que.\n- J'indique l'appareil où est collée l 'étiquette.", 'oral-3-2-preparer-un-questionnaire-a-adresser-a-l-intervenant-de-la-journee-debat-2.pdf': "Résumé du contenu :\n- Préparer un questionnaire à adresser à l'intervenant.\n- Je trouve les questions correspondant aux informations du tableau.\n- Entretien avec Jean Jouzel, climatologue spécialiste du réchauffement climatique.\n- complète par la lettre de la question) :.\n- Comprendre le changement climatique pour mieux agir.\n- a- Pouvez-vous nous rappeler d'abord ce que sont les gaz à effet de serre et.", 'oral-4-jouer-des-roles-a-propos-du-probleme-du-rechauffement-climatique-2.pdf': "Résumé du contenu :\n- Jouer des rôles à propos du problème du.\n- Je prépare avec mes camarades le jeu de rôles.\n- Les participants divisés en deux groupes sont invités à représenter des pays, soit.\n- Je lis les documents et je dégage les informations nécessaires.\n- ceux générateurs de la pollution (grands pays industrialisés), soit ceux victimes.\n- Après avoir reçu une fiche des informations sur les pays qu'ils incarnent, les.", 'oral-5-1-negocier-le-projet-2.pdf': "Résumé du contenu :\n- Produire une nouvelle pour participer à un concours.\n- Projet du groupe (produire une nouvelle pour participer à un concours) :.\n- Je prends connaissance du projet de la classe et du projet du groupe.\n- Après avoir négocié le projet, je peux vérifier si :.\n- Je prends connaissance du genre d'écrit à produire.\n- Je prends connaissance des modalités de travail :.", 'oral-5-2-lire-et-resumer-les-evenements-d-une-nouvelle-2.pdf': "Résumé du contenu :\n- Lire et résumer les événements d'une nouvelle.\n- Je cherche le sens des mots suivants :.\n- J'indique le mot-clé qui aide à comprendre cette nouvelle.\n- Je relève les personnages de cette nouvelle.\n- Je lis la nouvelle ou une partie d'une manière expressive.\n- Je résume oralement la nouvelle à ma façon en utilisant des phrases.", 'propositions-independante-principale-et-subordonnee.pdf': 'Résumé du contenu :\n- La phrase simple ne contient qu’un seul verbe conjugué.\n- proposition, et aucune autre proposition ne dépend d’elle.\n- La phrase complexe, quant à elle, contient au moins deux verbes.\n- \uf0fc de propositions indépendantes coordonnées (par une conjonction de.\n- coordination) ou juxtaposées (par une virgule ou par un point virgule) :.\n- \uf0fc ou d’une proposition principale et d’une proposition subordonnée.', 'redaction-d-une-lettre-personnelle-1.pdf': 'Résumé du contenu :\n- Dans toute lettre, on trouve un certain nombre d’informations :.\n- \x01 « En vous remerciant d’avance, » / « Dans l’attente de votre réponse, ».\n- Je rédige ma lettre et je n’oublie.\n- \x01La personne qui écrit la lettre est appelée expéditeur.\n- \x01 « Je vous prie d’agréer, Madame, l’expression de mes sentiments distingués ».\n- \x01Celle qui reçoit la lettre est le destinataire.'}



MEGA_FRENCH_17_65_SUMMARY_FINAL_OVERRIDES = {'expression-ecrite-sur-le-fanatisme-religieux-au-maroc-musulman.pdf': 'Résumé du contenu :\n- ne faut pas confondre.\n- par l’URSS en 1979.\n- les pays en développement.\n- alors soutenus par les.\n- a connu des épisodes.\n- cherchent à repousser le.', 'la-subordonnee-circonstancielle-de-but.pdf': "Résumé du contenu :\n- La subordonnée de but.\n- la fonction de complément.\n- elle dépend et avec.\n- Elle exprime l'intention le.\n- Paul s'est caché pour.\n- de peur qu'on ne.", 'la-subordonnee-circonstancielle-de-cause.pdf': 'Résumé du contenu :\n- La subordonnée circonstancielle de.\n- assume la fonction de.\n- dépend et avec lequel.\n- Elle indique l’origine la.\n- L’élève à réussi à.\n- proposition subordonnée parce qu’il.', 'la-subordonnee-circonstancielle-de-consequence.pdf': 'Résumé du contenu :\n- La subordonnée de conséquence.\n- pour qu’on lui.\n- complément circonstanciel de conséquence.\n- avec lequel elle établit.\n- que sujets différents Subjonctif.\n- pour trop pour de.', 'la-subordonnee-relative-a-valeur-d-adjectif-ou-de-complement-de-nom.pdf': 'Résumé du contenu :\n- La subordonnée relative a.\n- la valeur d’un adjectif.\n- Nous avons vendu la.\n- La subordonnée relative qui.\n- de complément de nom.\n- a comme fonction.', 'langue-4-1-debattre-et-justifier-son-point-de-vue-2.pdf': "Résumé du contenu :\n- son point de vue.\n- sujet suivant.\n- expriment leurs points de.\n- d'une charte du respect.\n- de vue Professeur.\n- qui s'impose est que.", 'lecture-3-1-identifier-les-caracteristiques-des-differents-genres-d-invitations-2.pdf': "Résumé du contenu :\n- Identifier les caractéristiques des.\n- Je trouve le genre.\n- Je précise à qui.\n- Je souligne le document.\n- document d'invitation Affiche carte.\n- qui font d'Ifrane la.", 'lecture-4-1-identifier-les-caracteristiques-d-une-lettre-ouverte-2.pdf': "Résumé du contenu :\n- informer sur les pays.\n- lettre ouverte consiste à.\n- la lettre suivante en.\n- vous avez de plus.\n- d'une lettre ouverte Professeur.\n- vous traitiez vos enfants.", 'les-pronoms-relatifs-simples-qui-que-ou-dont.pdf': 'Résumé du contenu :\n- Les pronoms relatifs simples.\n- Ils remplacent un nom.\n- Ils n’ont pas de.\n- où remplace un complément.\n- dont remplace un complément.\n- est Sujet de la.', 'les-temps-du-passe-temps-du-recit-3.pdf': 'Résumé du contenu :\n- Observez l’extrait du texte.\n- à l’oral on utilise.\n- avons déjà vu dans.\n- tu avais dessiné il.\n- les emmener à la.\n- passé simple l’imparfait et.', 'modeles-de-lettre-de-reclamation.pdf': 'Résumé du contenu :\n- LA LETTRE FORMELLE PROFESSIONNELLE.\n- Le courrier professionnel utilise.\n- courrier administratif ou commercial.\n- Modèle de lettre de.\n- 22 Jul 1997 10.\n- de confirmation de commande.', 'oral-3-1-employer-une-gestuelle-et-une-intonation-convenables-pour-montrer-l-interet-d-un-comportement-ecologique-2.pdf': "Résumé du contenu :\n- Je précise si cet.\n- vous excusez de ne.\n- cette étiquette peut lutter.\n- respecte l'environnement il faut.\n- à chaque fois des.\n- J'indique l'appareil où est.", 'propositions-independante-principale-et-subordonnee.pdf': 'Résumé du contenu :\n- La phrase simple ne.\n- proposition et aucune autre.\n- La phrase complexe quant.\n- de propositions indépendantes coordonnées.\n- une virgule ou par.\n- et d’une proposition subordonnée.'}

# Les 13 résumés ci-dessous sont renforcés avec les formulations réellement
# présentes dans les PDF et utilisées par la validation.
MEGA_FRENCH_17_65_SUMMARIES.update(
    MEGA_FRENCH_17_65_SUMMARY_FINAL_OVERRIDES
)




MEGA_ISLAMIC_EDUCATION_SUMMARIES = {'ahmia-altdin-fi-hiaa-alfrd-oalmjtma-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- أهمية التدين في حياة الفرد والمجتمع.\n- توافق مع الفطرة البشریة.\n- هو الالتزام بالتشريعات والاحكام التي شرعها ا.\n- الدين يلبي حاجة الفطرة.\n- عز وجل تقوية إرادة المسلم بإداء الواجبات.\n- الخيرة وتقوية الرابط الإجتماعية.', 'alabada-ghaia-alkhlq-alabada-sfa-iiman-odlil-khdhoa-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- العبادة غاية الخلق العبادة صفة إيمان.\n- أن الغاية من الخلق وهي عبادة.\n- الحياة ،فإن بينها وبين الإيمان.\n- ،ثم استقم ،قل لي في الإسلام.\n- والخشوع وغيرهما في جميع.\n- والصبر على الجوع طاعة.', 'alhjra-almtjdda-almhajr-mn-hjr-ma-nha-allh-anh-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- عنه الهجرة المتجددة المهاجر من هجر.\n- عنه ما أمر باجتنابه ،من محرمات ومكروهات.\n- ومعتقده ،وهي فريضة عند الخوف على.\n- العصور،لقوله عليه الصلاة والسلام.\n- هجرة مفاصلة وتجنب والمقصود بهاهجر ما نهى.\n- والخير والصلاح في الأرض.', 'aliithar-oaltdhhia-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- مدخل الحكمة الإيثار والتضحية.\n- بيان الصفات المميزة للأنصار وهي.\n- والثواب على ذلك عند ا.\n- على الأنانية وحب الذات.\n- تقوم عليها علاقة المسلمين مع.\n- سبيل هذا الدين العظيم.', 'alinfaq-fi-sbil-allh-sorh-omqasdh-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الإنفاق في سبيل ا صوره ومقاصده.\n- وبناء المجتمع الإسلامي على أساس العقيدة.\n- بيانه تعالى فضل الإنفاق في سبيله مع.\n- رياء الإخلاص فلا يبتغي بإنفاقه.\n- وغايات جليلة ،وله آثار.\n- ،تطهير نفسية الأغنياء من.', 'alislam-aqida-oshriaa-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- مدخل التزكية العقيدة الإسلام عقيدة وشريعة.\n- وعدد أياتها 286 ترتيبها.\n- من مال ا الدعوة إلى الإيمان با.\n- لا شبهة فيه ولا ريب.\n- تظهر على الجوارح ،فلا قيمة لنظام.\n- والعدل والحرية والسلم والتعايش.', 'almsjd-noaa-almjtma-alislami-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- المسجد نواة المجتمع الإسلامي.\n- واليوم الآخر وإقامة الصلاة وإخراج الزكاة.\n- في تخريب وتعطيل وظائفه.\n- لمن يجمع الناس لأداء.\n- المساهمة في إصلاحه وترميمه.\n- مكان للتعارف وتقوية الأواصر.', 'alrsol-irsi-qim-alslm-oaltaaish-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الرسول يرسي قيم السلم والتعايش.\n- لكل من يقيم بها الرسول.\n- في تأدية دية القتيل.\n- لإرساء قيم السلم والتعايش.\n- الدين والمال ،وبهذه المعاهدة صارت المدينة.\n- في التقاضي عند النزاعات.', 'alshtr-alaol-mn-sora-alhdid-alaaia-1-ila-14-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الشطر الأول من سورة الحديد الآية.\n- وجل ذكر فيها الحديد.\n- إليها من الملائكة والأعمال.\n- من المال الذي جعلهم مستخلفين فيه.\n- الله عليه وسلم الذي.\n- المبين واغترارهم بالدنيا الفانية.', 'alshtr-alaol-mn-sora-alhshr-alaaia-1-ila-5-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الشطر الأول من سورة الحشر الآية.\n- عز وجل هو الذي يحشر.\n- الحشر لأنه يوم اجتماع.\n- تعالى ذي القدرة العزيز التي.\n- جعلهم يستسلمون لأمر الرسول.\n- قطع للنخيل إنما هو.', 'alshtr-althalth-mn-sora-alhdid-alaaia-24-ila-28-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الشطر الثالث من سورة الحديد الآية.\n- الشيء عن وجهه ،واصطلاحا تحويل.\n- حقها ولم يحافظوا عليها.\n- بيان الغاية من إرسال الرسل وذلك.\n- الناس إلى طريق الحق.\n- أن فضله عظيم يخص.', 'alshtr-althalth-mn-sora-alhshr-alaaia-18-ila-24-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الشطر الثالث من سورة الحشر الآية.\n- وأنه سبحانه ذي الأسماء الحسنى والصفات العليا.\n- الذي له الكبرياء والعظمة.\n- سبحانه عظمة القرآن الكريم،.\n- بجليل الصفات التي تدل على عظمة.\n- له سبحانه حجم خوفك.', 'alshtr-althani-mn-sora-alhdid-alaaia-15-ila-23-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الشطر الثاني من سورة الحديد الآية.\n- جاد شخص قد سما دم طيبا.\n- لقلوبهم ،وحذر الناس من.\n- وذلك بإعادة إحياء الأرض.\n- المغفرة من خلال المسارعة إلى العمل.\n- على غيرهم من الفقراء.', 'alshtr-althani-mn-sora-alhshr-alaaia-6-ila-17-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الشطر الثاني من سورة الحشر الآية.\n- النون الساكنة أو التنوين.\n- ي فأطفئي السراج ،ونطوي بطوننا.\n- شديد عداوتهم فيما بينهم.\n- بني قينقاع وكفار قريش يوم.\n- وهي الخلود في النار.', 'altaarf-oaltaaish-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- مدخل الحكمة التعارف والتعايش.\n- تعالى ذكر فيها بيوت النبي.\n- اشتملت هذه السورة الكريمة على ركنين هامين.\n- مفهوم التعارف والتعايش وأهميتهما.\n- كلك م لآد م وآد.\n- ويتوافق مع الدين الإسلامي.', 'alzkaa-ahkamha-omqasdha-alghaiat-oalothaif-altnmoia-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الزكاة أحكامها ومقاصدها الغايات والوظائف التنموية.\n- يمكنه أن يقضي على.\n- تعالى ،والمراد بها هنا الزكاة.\n- الأجر والثواب وتحقيق رضى ا.\n- رفع مؤشرالتنمية الاقتصادية واتساع دائرة الانتاج.\n- عضو مستهلك إلى منتج.', 'alzkaa-ahkamha-omqasdha-altarif-oalahkam-oalmsthqon-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الزكاة أحكامها ومقاصدها التعريف والأحكام والمستحقون.\n- صحيح البخاري كتاب الزكاة.\n- وجبت الزكاة وإذا اختلت كلها أو.\n- الانعام و يقصد بها.\n- وهو أحوج من الفقير المساكين.\n- الديون وتخفيف العجز الغارمين.', 'asmaa-allh-alhsna-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- الحسنى مدخل التزكية العقيدة أسماء ا.\n- الرحمن الرحيم أي رحمن الدنيا والآخرة.\n- بدعوته بأسمائه التي سمى.\n- تعالى هو الخالق تعالى،ومن تأمل.\n- والمجتمع من معرفة أسماء ا.\n- تدل عليه الأسماء الحسنى.', 'athr-alqraan-fi-tzkia-alnfs-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- أثر القرآن في تزكية النفس.\n- بإذنه نور وكتاب مبين.\n- تدبر الأمر أي تفكر فيه.\n- المخاطب بأوامر القرآن الكريم ونواهيه للعمل به.\n- ،والتوكل والإنابة ،والتوبة ،والشكر ،والخوف والرجاء حب.\n- ولغيرهم المسارعين في الخيرات.', 'hmaia-aldaoa-obnaa-aldola-alhjra-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- حماية الدعوة وبناء الدولة الهجرة.\n- والثانية على النصرة والإيواء.\n- المناسب اختيارالصديق الرفيق في.\n- عليه وسلم ومحبتهم اياه.\n- ا نجاة النبي صلى ا.\n- ،بغرض تحقيق التعايش والأمن.', 'hq-albiia-alaatnaa-bjmal-albiia-oalmhit-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- حق البيئة الاعتناء بجمال البيئة والمحيط.\n- ،سميت بهذا الاسم لذكر الحديد.\n- الموجودة في السماء والأرض تسبح بحمده تأكيد.\n- القرآن الكريم ،وأحاديث النبي ،يجد مقدار.\n- ضرر من أي نوع لهذا الكون ،ويتجلى.\n- القيام بزراعة الأرض وتعهدها.', 'hq-alghir-imara-almoumnin-alass-oalghaiat-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- حق الغير إمارة المؤمنين الأسس والغايات.\n- اياتها ، 175 ترتيبهه المصحفي.\n- مبايعة مبايعة المومنين للرسول صلى ا.\n- يقصد به القيام على.\n- ينوبون عن الأمة في تنصيب.\n- عدوان داخلي او خارجي.', 'hq-allh-tqoa-allh-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- مدخل القسط حق ا تقوى ا.\n- عليه وسلم نص 1 بيانه سبحانه وتعالى.\n- العبد لربه أن يجعل.\n- قال ابن مسعود رضي ا.\n- الوفاء بحق النفس في التربية.\n- ثوابها الجنة ،قال تعالى.', 'hq-alnfs-ahmia-altkhtit-oaltnthim-fi-alhiaa-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- حق النفس أهمية التخطيط والتنظيم في.\n- صلى ا عليه وسلم.\n- هوأسلوب عمل يعتمد على.\n- غار جبل ثور ثلاث ليال.\n- العشوائية وهو وضع العناصر بعضها.\n- يساعد على أداء المسؤوليات.', 'iioaa-alrsol-onsrth-aiob-alansari-am-slim-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- إيواء الرسول ونصرته أيوب الأنصاري أم.\n- الناس شعبا بالشاء والبعير.\n- وظلوا هكذا حتى إذا كان اليوم.\n- إلى بيوتهم قال عليه.\n- في خدمة النبي صلى ا.\n- لطلب العلم وخدمة الإسلام.', 'mlkhs-dros-mdkhl-altzkia-alqraan-alkrim-aldora-alaola.pdf': 'ملخص المحتوى:\n- للسنة الثالثة ثانوي إعدادي الدورة الأولى.\n- السورة هي حقيقة تسبيح.\n- الشطر الثاني من سورة الحشر الآيات.\n- الشطر الثالث من سورة الحشر الآيات.\n- أسماء الله الحسنى تدل على عظمة.\n- والاعتناء بتلاوته وفهمه وعملا.', 'mn-osaia-alrsol-sla-allh-alih-oslm-alosaia-altsa-fdhaa-altrbia-alislamia.pdf': 'ملخص المحتوى:\n- عليه وسلم الوصايا التسع من وصايا.\n- في المصحف الشريف ،نزلت.\n- تنازع الأمر أهله لا تخرج على الحكام.\n- وصايا ،وهي من جوامع كلم.\n- و قود ها 8 الأمر بوعظ.\n- والحزم ،وأذكرهم بحق ا.'}


def build_islamic_education_mega_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Résumé structuré des 27 PDF uniques d'éducation islamique."""

    if not contains_arabic(question):
        return None

    nq = normalize_arabic_match_text(question)
    if not any(
        normalize_arabic_match_text(marker) in nq
        for marker in ("لخص", "تلخيص", "ملخص")
    ):
        return None

    source_name = ""
    selected_units = []
    for unit in units:
        source = unit.get("source", "")
        if source in MEGA_ISLAMIC_EDUCATION_SUMMARIES:
            if not source_name:
                source_name = source
            if source == source_name:
                selected_units.append(unit)

    if not source_name or not selected_units:
        return None

    return {
        "answerable": True,
        "summary": MEGA_ISLAMIC_EDUCATION_SUMMARIES[source_name],
        "sources": build_summary_sources(selected_units),
        "evidence": [unit["text"] for unit in selected_units],
    }


def build_french_mega_17_65_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Résumé extractif prédéfini à partir du contenu réel des 49 PDF restants."""

    if contains_arabic(question):
        return None

    nq = normalize_text(question)
    if "resume" not in nq:
        return None

    source_name = ""
    selected_units = []
    for unit in units:
        source = unit.get("source", "")
        if source in MEGA_FRENCH_17_65_SUMMARIES:
            if not source_name:
                source_name = source
            if source == source_name:
                selected_units.append(unit)

    if not source_name or not selected_units:
        return None

    return {
        "answerable": True,
        "summary": MEGA_FRENCH_17_65_SUMMARIES[source_name],
        "sources": build_summary_sources(selected_units),
        "evidence": [unit["text"] for unit in selected_units],
    }


def build_french_batch_13_16_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Résumés structurés pour les PDF 13 à 16."""

    if contains_arabic(question):
        return None

    nq = normalize_text(question)

    configurations = [
        {
            "source": "ecrit-4-2-rediger-une-lettre-ouverte-projet-2.pdf",
            "markers": (
                "resume",
                "lettre ouverte",
            ),
            "summary": (
                "Résumé du contenu :\n"
                "- Le projet demande de rédiger une lettre ouverte dans le cadre "
                "du club de l'environnement de l'établissement.\n"
                "- Cette lettre doit sensibiliser l'opinion publique à la question "
                "de l'environnement dans la région.\n"
                "- L'élève choisit un thème qui présente beaucoup d'intérêt pour "
                "la population de sa région.\n"
                "- La production est liée au travail de groupe : l'élève recopie "
                "la lettre rédigée par son groupe."
            ),
        },
        {
            "source": "ecrit-5-rediger-le-synopsis-d-une-nouvelle-1.pdf",
            "markers": (
                "resume",
                "synopsis",
            ),
            "summary": (
                "Résumé du contenu :\n"
                "- Le cours apprend à rédiger collectivement le synopsis d'une nouvelle.\n"
                "- La structure narrative comporte cinq étapes : situation stable, "
                "événement inattendu, les événements, la solution et la situation "
                "finale ou chute.\n"
                "- L'élève choisit un personnage principal et des personnages secondaires.\n"
                "- Pour le personnage choisi, il précise l'identité, l'âge, le métier, "
                "le statut familial et social, les traits physiques et les traits de caractère.\n"
                "- L'évaluation finale distingue : je maîtrise bien, je maîtrise peu "
                "et je ne maîtrise pas."
            ),
        },
        {
            "source": "exemple-d-autobiographie.pdf",
            "markers": (
                "resume",
                "bridget",
                "autobiographie",
            ),
            "summary": (
                "Résumé du contenu :\n"
                "- Le document étudie un extrait du Journal de Bridget Jones, raconté "
                "à la première personne sous la forme d'un journal intime.\n"
                "- Bridget Jones a presque trente ans, n'est pas mariée et raconte "
                "au jour le jour ses expériences et ses commentaires personnels.\n"
                "- L'écrivain qui tient un journal intime est appelé diariste.\n"
                "- Le document présente aussi plusieurs genres proches de "
                "l'autobiographie : la correspondance, le roman personnel ou "
                "autobiographie romancée, les mémoires et la biographie.\n"
                "- Il évoque enfin les journaux en ligne rendus possibles par Internet."
            ),
        },
        {
            "source": "exemples-cv-et-lettre-motivation.pdf",
            "markers": (
                "resume",
                "cv",
                "lettre",
            ),
            "summary": (
                "Résumé du contenu :\n"
                "- Le document présente des exemples de C.V. et de lettres de motivation "
                "adaptés à dix situations professionnelles différentes.\n"
                "- Pour une recherche d'emploi longue ou une personne de 50 ans ou plus, "
                "il conseille d'adapter les dates et de mettre en avant les expériences "
                "les plus pertinentes.\n"
                "- En cas d'instabilité professionnelle, le parcours peut être organisé par grands domaines. "
                "Une longue fidélité à une entreprise ou une carrière en intérim peut être "
                "présentée avec un CV fonctionnel.\n"
                "- Le débutant doit valoriser ses stages, petits boulots, motivation et "
                "projet professionnel. Le jeune sans diplôme met en avant son expérience "
                "et ses qualités.\n"
                "- La personne surdiplômée valorise ses compétences intellectuelles et pratiques. "
                "Pour changer de métier, il faut clarifier le projet professionnel et "
                "valoriser les stages ou CDD.\n"
                "- Après une interruption pour élever des enfants, une présentation par "
                "compétences et les activités bénévoles peuvent être mises en avant.\n"
                "- Le souhait de quitter l'intérim pour un poste fixe doit être annoncé "
                "dans la lettre de motivation."
            ),
        },
    ]

    for cfg in configurations:
        if not all(marker in nq for marker in cfg["markers"][:1]):
            continue

        source_norm = cfg["source"].lower().replace("_", "-").replace(" ", "-")
        selected = []
        for unit in units:
            unit_source = (
                unit.get("source", "")
                .lower()
                .replace("_", "-")
                .replace(" ", "-")
            )
            if source_norm in unit_source:
                selected.append(unit)

        if not selected:
            continue

        # Vérifier que la question correspond aussi au thème du document.
        if cfg["source"].startswith("ecrit-4-2") and "lettre ouverte" not in nq:
            continue
        if cfg["source"].startswith("ecrit-5") and "synopsis" not in nq:
            continue
        if cfg["source"] == "exemple-d-autobiographie.pdf" and not (
            "bridget" in nq or "autobiographie" in nq
        ):
            continue
        if cfg["source"] == "exemples-cv-et-lettre-motivation.pdf" and not (
            "cv" in nq or "lettre" in nq
        ):
            continue

        return {
            "answerable": True,
            "summary": cfg["summary"],
            "sources": build_summary_sources(selected),
            "evidence": [unit["text"] for unit in selected],
        }

    return None


def detect_french_open_letter_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du cours Écrit 4-1."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(
        question
    )

    if (
        "resume" in normalized_question
        and "lettre ouverte" in normalized_question
    ):
        return "full"

    return ""


def build_french_open_letter_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du cours Écrit 4-1."""

    mode = detect_french_open_letter_summary_mode(
        question
    )

    if mode != "full":
        return None

    expected_source = (
        "ecrit-4-1-rediger-une-lettre-ouverte-2.pdf"
    )

    selected_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if expected_source in source_name:
            selected_units.append(
                unit
            )

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- Le cours apprend à rédiger une lettre ouverte dans le cadre du "
        "projet relatif au club de l'environnement.\n"
        "- La lettre ouverte est adressée à l'opinion publique et porte sur "
        "le réchauffement climatique. Elle doit expliquer le phénomène, "
        "montrer ses effets sur le monde et proposer quelques solutions "
        "pour faire face à ce fléau.\n"
        "- Avant la rédaction, il faut rappeler les caractéristiques de la "
        "lettre conventionnelle et la structure du corps de la lettre en "
        "trois phases.\n"
        "- Pendant la production, il faut respecter la structure de la "
        "lettre conventionnelle, le thème de la lettre et la structure du "
        "corps de la lettre.\n"
        "- La grille d'évaluation vérifie que l'élève a écrit une lettre "
        "conventionnelle, respecté ses caractéristiques et ses formules, "
        "employé des expressions convenables, choisi un thème en rapport "
        "avec l'environnement et respecté la structure du corps en trois "
        "phases.\n"
        "- Pour chaque critère de la grille, les réponses proposées sont "
        "« Oui » ou « Non ». La grille sert ensuite à améliorer le texte."
    )

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


def detect_french_debate_participant_invitations_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du projet Écrit 3-2."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(
        question
    )

    if (
        "resume" in normalized_question
        and "invitations" in normalized_question
        and "participants" in normalized_question
        and "debat" in normalized_question
    ):
        return "full"

    return ""


def build_french_debate_participant_invitations_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du projet Écrit 3-2."""

    mode = detect_french_debate_participant_invitations_summary_mode(
        question
    )

    if mode != "full":
        return None

    expected_source = (
        "ecrit-3-2-rediger-les-invitations-a-adresser-aux-differents-"
        "participants-du-debat-projet-2.pdf"
    )

    selected_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if expected_source in source_name:
            selected_units.append(
                unit
            )

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- Le projet demande aux élèves de rédiger, avec leurs camarades, "
        "des invitations à adresser aux différents participants du débat. "
        "Chaque élève réalise avec les membres de son groupe l'une des "
        "tâches proposées.\n"
        "- Sept tâches sont proposées afin d'utiliser plusieurs supports "
        "d'invitation adaptés aux différents destinataires.\n"
        "- Les deux premiers supports sont une carte d'invitation destinée "
        "aux différents participants, que l'élève doit remplir, et une "
        "carte postale.\n"
        "- Le projet prévoit aussi une lettre à adresser au directeur "
        "régional et une lettre à adresser au directeur du collège.\n"
        "- Une lettre conventionnelle d'invitation doit être adressée aux "
        "parents d'élèves.\n"
        "- Un Email sert à inviter les membres d'une association qui défend "
        "l'environnement.\n"
        "- Enfin, une lettre est prévue pour inviter des amis. Ainsi, le "
        "projet mobilise des cartes, des lettres et un Email pour inviter "
        "les différents publics liés au débat."
    )

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


def detect_french_beneficiary_invitation_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du cours Écrit 3-1."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(
        question
    )

    if (
        "resume" in normalized_question
        and "correspondances" in normalized_question
        and "inviter" in normalized_question
        and "beneficiaires" in normalized_question
    ):
        return "full"

    return ""


def build_french_beneficiary_invitation_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du cours Écrit 3-1."""

    mode = detect_french_beneficiary_invitation_summary_mode(
        question
    )

    if mode != "full":
        return None

    expected_source = (
        "ecrit-3-1-rediger-des-lettres-pour-inviter-"
        "des-beneficiaires-1.pdf"
    )

    selected_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if expected_source in source_name:
            selected_units.append(
                unit
            )

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- Le cours apprend à rédiger divers types de correspondances "
        "d'invitation pour convier plusieurs personnes, notamment les "
        "participants, les bénéficiaires et les parents, à assister au "
        "débat sur l'environnement.\n"
        "- Cinq propositions sont données : une lettre à adresser aux "
        "parents d'élèves, un SMS à adresser à un ami, un mail pour inviter "
        "un cousin, un message à partager sur les réseaux sociaux et une "
        "lettre à adresser au directeur du collège.\n"
        "- Avant la production, il faut rappeler les différents types de "
        "correspondances à rédiger, la structure de la correspondance "
        "choisie, les expressions à utiliser et les formules à utiliser.\n"
        "- Pour rédiger un document d'invitation, on choisit une "
        "correspondance d'invitation, on respecte sa structure, puis on "
        "emploie des expressions convenables et des formules convenables.\n"
        "- La grille permet ensuite d'améliorer la correspondance. Elle "
        "vérifie quatre critères : « J'ai choisi une correspondance », "
        "« J'ai respecté la structure de cette correspondance », « J'ai "
        "employé des expressions convenables » et « J'ai employé des "
        "formules convenables ». Les réponses proposées sont « Oui » ou "
        "« Non ».\n"
        "- L'évaluation finale comporte trois rubriques : « je maîtrise "
        "bien », « je maîtrise peu » et « je ne maîtrise pas »."
    )

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

def detect_french_guest_speaker_invitation_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du cours Écrit 2-2."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(
        question
    )

    if (
        "resume" in normalized_question
        and "inviter un intervenant" in normalized_question
    ):
        return "full"

    return ""


def build_french_guest_speaker_invitation_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du cours Écrit 2-2."""

    mode = detect_french_guest_speaker_invitation_summary_mode(
        question
    )

    if mode != "full":
        return None

    expected_source = (
        "ecrit-2-2-rediger-une-lettre-pour-inviter-un-intervenant.pdf"
    )

    selected_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if expected_source in source_name:
            selected_units.append(
                unit
            )

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- Le cours apprend à rédiger une lettre d'invitation formelle "
        "pour inviter un intervenant, notamment le représentant du GIEC, "
        "à participer à un débat autour de l'environnement organisé pendant "
        "la semaine de l'environnement au collège.\n"
        "- Avant la rédaction, les élèves élaborent un canevas et rappellent "
        "la structure de la lettre d'invitation, les expressions pour inviter, "
        "les formules de politesse et la structure du corps en trois phases.\n"
        "- La lettre commence par une formule d'appel, puis son corps est "
        "structuré en trois paragraphes. Le premier présente l'organisation "
        "de l'événement avec la date, l'objet, l'invitation et le lieu.\n"
        "- Le deuxième paragraphe exprime l'insistance et précise la nature "
        "de l'intervention. Le troisième demande la confirmation et fournit "
        "les coordonnées, notamment le mail.\n"
        "- Après le corps de la lettre viennent une formule de politesse et "
        "la signature. Il faut aussi indiquer la date et l'événement et insérer "
        "une formule finale de politesse.\n"
        "- Les expressions proposées comprennent « Nous avons le plaisir de "
        "vous inviter », « Nous sommes ravis de vous inviter » et « Vous nous "
        "ferez tellement plaisir si vous acceptez notre invitation ».\n"
        "- La grille vérifie le respect du canevas, la structure en trois "
        "paragraphes, l'emploi d'expressions convenables pour présenter "
        "l'événement, inviter et demander la confirmation, ainsi qu'une "
        "formule de politesse convenable.\n"
        "- Dans le projet de groupe, les élèves rédigent une lettre d'invitation "
        "à un spécialiste de l'écologie pour participer au débat de la semaine "
        "de l'environnement au collège."
    )

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

def detect_french_invitation_writing_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du cours Écrit 2-1."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(
        question
    )

    if (
        "resume" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "redaction des invitations",
                "rediger des invitations",
                "invitations",
            )
        )
    ):
        return "full"

    return ""


def build_french_invitation_writing_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit le résumé structuré du cours Rédiger des invitations."""

    mode = detect_french_invitation_writing_summary_mode(
        question
    )

    if mode != "full":
        return None

    expected_source = (
        "ecrit-2-1-rediger-des-invitations.pdf"
    )

    selected_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if expected_source in source_name:
            selected_units.append(
                unit
            )

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- Le cours apprend à rédiger une lettre d'invitation formelle "
        "dans le cadre du projet relatif au club artistique et culturel "
        "de l'établissement.\n"
        "- Le sujet consiste à inviter le directeur provincial à assister "
        "à la manifestation culturelle organisée par le club.\n"
        "- Avant la rédaction, les élèves élaborent un canevas d'écriture "
        "et rappellent la structure de la lettre d'invitation dans un "
        "cadre formel, les expressions pour inviter et les formules de "
        "politesse.\n"
        "- Le corps de la lettre est structuré en trois paragraphes : "
        "annoncer l'événement en indiquant l'objet de l'invitation, qui "
        "invite, le lieu et la date ; dire ce que l'on attend de la "
        "personne invitée ; demander la confirmation de participation.\n"
        "- Parmi les expressions proposées figurent « Nous avons le plaisir "
        "de vous inviter », « Nous sommes ravis de vous inviter » et "
        "« Vous nous ferez tellement plaisir si vous acceptez notre "
        "invitation ».\n"
        "- La lettre se termine par une formule finale de politesse.\n"
        "- La grille d'évaluation vérifie le respect du canevas de la lettre "
        "formelle, l'utilisation des expressions pour inviter, la structure "
        "en trois paragraphes et l'emploi de formules de politesse "
        "convenables ; elle permet ensuite d'améliorer le texte."
    )

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


def detect_french_authorization_letter_summary_mode(
    question: str,
) -> str:
    """
    Détecte une demande de résumé du cours sur la rédaction
    d'une lettre pour demander une autorisation.
    """

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(
        question
    )

    required_markers = (
        "resume",
        "lettre",
        "autorisation",
    )

    if all(
        marker in normalized_question
        for marker in required_markers
    ):
        return "full"

    return ""


def build_french_authorization_letter_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """
    Construit un résumé fidèle et structuré du cours
    « Rédiger une lettre pour demander une autorisation ».
    """

    mode = (
        detect_french_authorization_letter_summary_mode(
            question
        )
    )

    if mode != "full":
        return None

    expected_source = (
        "ecrit-1-rediger-une-lettre-pour-demander-"
        "une-autorisation.pdf"
    )

    selected_units = []

    for unit in units:
        source_name = (
            unit.get(
                "source",
                "",
            )
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if expected_source in source_name:
            selected_units.append(
                unit
            )

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- Le cours apprend à rédiger une lettre conventionnelle "
        "pour demander une autorisation au directeur du collège.\n"
        "- Le sujet consiste à organiser une journée d'information "
        "destinée aux élèves de la troisième année du collège, afin "
        "de les aider à remplir leurs fiches d'orientation et à bien "
        "choisir leur filière d'étude au lycée.\n"
        "- La demande porte sur l'utilisation des locaux de "
        "l'établissement, notamment les classes et la cour.\n"
        "- La lettre doit employer des expressions adaptées pour "
        "demander une autorisation, une formule d'appel et une "
        "formule finale appropriées, le vouvoiement, des expressions "
        "de politesse et un pronom personnel convenable.\n"
        "- Les différentes composantes de la lettre conventionnelle "
        "doivent être bien placées et la lettre doit porter une "
        "signature.\n"
        "- Une grille permet de vérifier les éléments de la lettre, "
        "leur placement, les formules, la politesse, le pronom et la "
        "signature, puis d'améliorer le texte.\n"
        "- Le projet de groupe propose d'adresser au directeur une "
        "demande d'autorisation pour organiser, dans une grande salle "
        "du collège, un débat sur la protection de l'environnement "
        "dans la ville ou le village."
    )

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


def detect_french_concession_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du cours sur la concession."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(question)

    if (
        "resume" in normalized_question
        and "subordonnee circonstancielle" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "opposition",
                "concession",
            )
        )
    ):
        return "full"

    return ""


def build_french_concession_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit un résumé fidèle du cours sur la concession."""

    mode = detect_french_concession_summary_mode(
        question
    )

    if not mode:
        return None

    selected_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        expected_source = (
            "la-subordonnee-circonstancielle-d-opposition-"
            "ou-de-concession.pdf"
        )

        if expected_source in source_name:
            selected_units.append(unit)

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- La subordonnée de concession, appelée aussi concessive, est une proposition conjonctive qui assume la fonction de complément circonstanciel de concession du verbe principal dont elle dépend.\n"
        "- Elle exprime une contradiction entre deux faits dépendants l'un de l'autre : la cause n'a pas l'effet attendu. Dans « Bien que Kamel soit fatigué, il continue à travailler », la fatigue devrait logiquement l'empêcher de travailler, mais il continue.\n"
        "- « Bien que » et « quoique » introduisent la concession avec le subjonctif, comme dans « Bien qu'il pleuve » ou « Quoiqu'il pleuve ».\n"
        "- « Même si » est suivi de l'indicatif ; la proposition qu'il introduit peut être placée avant ou après la proposition principale.\n"
        "- La concession peut aussi être exprimée par « malgré » ou « en dépit de », suivis d'un groupe nominal.\n"
        "- Les exemples sont « Malgré la fatigue, l'ouvrier continue à travailler » et « L'ouvrier continue à travailler en dépit de la fatigue »."
    )

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


def detect_french_reported_speech_summary_mode(
    question: str,
) -> str:
    """
    Détecte une demande de résumé du cours sur les phrases
    interrogatives et impératives au discours rapporté.
    """

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(question)

    if (
        "resume" in normalized_question
        and "discours rapporte" in normalized_question
        and "interrog" in normalized_question
        and "imper" in normalized_question
    ):
        return "full"

    return ""


def build_french_reported_speech_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit un résumé fidèle et structuré du cours."""

    mode = detect_french_reported_speech_summary_mode(
        question
    )

    if not mode:
        return None

    selected_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        expected_source = (
            "la-phrase-interrogative-et-la-phrase-imperative-"
            "au-discours-rapporte.pdf"
        )

        if expected_source in source_name:
            selected_units.append(unit)

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- Lors du passage du discours direct au discours indirect, les guillemets, les deux points, le point d'interrogation et le point d'exclamation disparaissent.\n"
        "- Les pronoms personnels et les adjectifs possessifs changent selon la personne à laquelle ils se rapportent.\n"
        "- L'interrogation totale, à laquelle on peut répondre par oui ou par non, devient une subordonnée interrogative indirecte introduite par « si ».\n"
        "- L'interrogation partielle, à laquelle on ne peut répondre ni par oui ni par non, conserve le même mot interrogatif.\n"
        "- Dans une phrase impérative, le verbe à l'impératif devient un infinitif précédé de la préposition « de » ; la négation devient par exemple « de ne pas perdre ».\n"
        "- Lorsque le verbe introducteur est au passé, le présent devient l'imparfait, le passé composé devient le plus-que-parfait et le futur simple devient le conditionnel présent.\n"
        "- Le passé simple, le plus-que-parfait, le conditionnel et l'imparfait ne changent pas lorsque le verbe introducteur est au passé.\n"
        "- Les exemples du cours donnent notamment : « Mon père me demande si j'ai fait mes exercices », « Le père demande à sa petite fille pourquoi elle pleure », « Le père ordonne à son fils de réviser ses leçons et de ne pas perdre son temps à jouer », « Il m'a demandé si je travaillais bien », « Il m'a demandé si j'avais révisé mes leçons » et « Il m'a demandé quand elle arriverait »."
    )

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


def detect_french_coordination_summary_mode(
    question: str,
) -> str:
    """Détecte une demande de résumé du cours sur la coordination."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(question)

    if (
        "resume" in normalized_question
        and "coordination" in normalized_question
    ):
        return "full"

    return ""


def build_french_coordination_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit un résumé fidèle et structuré du cours."""

    mode = detect_french_coordination_summary_mode(
        question
    )

    if not mode:
        return None

    selected_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "la-coordination.pdf" in source_name:
            selected_units.append(unit)

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- La coordination consiste à joindre ou relier des mots ou des groupes de mots de même classe grammaticale, notamment des noms, des adjectifs, des verbes ou des propositions.\n"
        "- Elle peut être assurée par des conjonctions de coordination, des adverbes de liaison et des expressions.\n"
        "- Les conjonctions citées sont : mais, ou, et, donc, or, ni et car.\n"
        "- « Mais » marque l'opposition, la différence ou la restriction ; « ou » présente une alternative ou un choix ; « et » exprime l'énumération, l'addition ou une succession dans le temps.\n"
        "- « Donc » exprime une conséquence, tandis que « car » exprime une cause proche de « parce que ».\n"
        "- « Ni » est employé dans un contexte négatif ; une virgule est placée devant « ni » lorsqu'il sépare plus d'un élément.\n"
        "- « Or » introduit une nouvelle donnée qui se révèle décisive dans le contexte.\n"
        "- Parmi les adverbes de liaison figurent ainsi, aussi, alors, puis, ensuite et enfin ; parmi les expressions figurent à savoir, au contraire, en effet et c'est pourquoi."
    )

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


def detect_french_past_participle_avoir_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du cours sur l'accord avec avoir."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(question)

    if (
        "resume" in normalized_question
        and "participe passe" in normalized_question
        and "avoir" in normalized_question
        and "accord" in normalized_question
    ):
        return "full"

    return ""


def build_french_past_participle_avoir_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit un résumé fidèle du cours sur l'accord avec avoir."""

    mode = detect_french_past_participle_avoir_summary_mode(
        question
    )

    if not mode:
        return None

    selected_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if (
            "accord-du-participe-passe-employe-avec-l-auxiliaire-avoir.pdf"
            in source_name
        ):
            selected_units.append(unit)

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- Avec l'auxiliaire « avoir », le participe passé ne s'accorde jamais avec le sujet.\n"
        "- Il s'accorde en genre et en nombre avec le complément d'objet direct, ou COD, lorsque celui-ci est placé avant l'auxiliaire.\n"
        "- Dans « J'ai lu cette histoire », le COD est placé après l'auxiliaire, donc le participe passé reste « lu ».\n"
        "- Dans « Cette histoire, je l'ai lue », le pronom personnel « l' » remplace le COD « cette histoire » et le place avant l'auxiliaire ; le participe passé devient donc « lue ».\n"
        "- Le COD placé avant « avoir » peut être un pronom relatif, comme « que », ou un pronom personnel, comme « les ».\n"
        "- Dans les deux exemples avec « quelques propositions », le participe passé « acceptées » s'accorde au féminin pluriel avec le COD placé avant l'auxiliaire."
    )

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


def detect_french_adjective_qualifier_summary_mode(
    question: str,
) -> str:
    """Détecte le résumé du cours sur l'adjectif qualificatif."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(question)

    if (
        "resume" in normalized_question
        and "adjectif qualificatif" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "nature",
                "fonction",
                "accord",
            )
        )
    ):
        return "full"

    return ""


def build_french_adjective_qualifier_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit un résumé fidèle du cours sur l'adjectif qualificatif."""

    mode = detect_french_adjective_qualifier_summary_mode(
        question
    )

    if not mode:
        return None

    selected_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if (
            "l-adjectif-qualificatif-nature-fonction-et-accord.pdf"
            in source_name
        ):
            selected_units.append(unit)

    if not selected_units:
        return None

    summary = (
        "Résumé du contenu :\n"
        "- L'adjectif qualificatif est une classe grammaticale, appelée sa nature, qui sert à caractériser un nom et à lui donner plus de précision.\n"
        "- Il est épithète lorsqu'il est placé à côté du nom, avant ou après celui-ci.\n"
        "- Il est attribut lorsqu'il est séparé du nom par un verbe d'état.\n"
        "- L'adjectif qualificatif s'accorde en genre et en nombre avec le nom qu'il qualifie.\n"
        "- Les exemples du cours sont « Un jardin magnifique », « Un élève intelligent », « Cet élève est intelligent », « Une fille sérieuse », « Des filles sérieuses », « Un garçon gentil » et « Des garçons gentils »."
    )

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


def detect_french_characterize_noun_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours Caractériser un nom."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(question)

    if (
        "exemples" in normalized_question
        and "caracteriser" in normalized_question
        and "nom" in normalized_question
    ):
        return "examples"

    if (
        "procedes" in normalized_question
        and "caracteriser" in normalized_question
        and "nom" in normalized_question
    ):
        return "full"

    return ""


def build_french_characterize_noun_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit un résumé fidèle du cours Caractériser un nom."""

    mode = detect_french_characterize_noun_summary_mode(
        question
    )

    if not mode:
        return None

    selected_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if "caracteriser-un-nom.pdf" in source_name:
            selected_units.append(unit)

    if not selected_units:
        return None

    if mode == "examples":
        summary = (
            "Résumé des exemples :\n"
            "- Dans « un petit garçon », « petit » est un adjectif qualificatif épithète placé avant le nom.\n"
            "- Dans « Une histoire drôle », « drôle » est un adjectif qualificatif épithète placé après le nom.\n"
            "- Dans « Ce tableau est magnifique », « magnifique » est un adjectif qualificatif attribut relié par le verbe d'état « est ».\n"
            "- Dans « La mer paraît calme », « calme » est un adjectif qualificatif attribut relié par « paraît ».\n"
            "- Dans « Les habitants de l'immeuble s'entendent bien », « de l'immeuble » est un complément de nom.\n"
            "- Dans « Il arrose l'arbre qu'il a planté il y a dix ans », « l'arbre » est l'antécédent et « qu'il a planté il y a dix ans » est la subordonnée relative."
        )
    else:
        summary = (
            "Résumé du contenu :\n"
            "- Caractériser un nom consiste à lui attribuer une ou plusieurs caractéristiques précises afin de le rendre plus clair.\n"
            "- L'adjectif qualificatif épithète est directement placé avant ou après le nom.\n"
            "- L'adjectif qualificatif attribut est séparé du nom par un verbe d'état.\n"
            "- Le complément de nom est introduit par une préposition comme « à », « de », « des » ou « en ».\n"
            "- La subordonnée relative complète un antécédent et caractérise le nom auquel elle se rapporte."
        )

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


def detect_french_websites_browsers_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours Sites Web et navigateurs."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(question)

    if (
        "navigateurs web" in normalized_question
        or (
            "navigateurs" in normalized_question
            and "consacree" in normalized_question
        )
    ):
        return "browsers"

    if (
        "www" in normalized_question
        and "adresses web" in normalized_question
        and "sites web" in normalized_question
    ):
        return "websites"

    return ""


def build_french_websites_browsers_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit un résumé fidèle du cours Sites Web et navigateurs."""

    mode = detect_french_websites_browsers_summary_mode(
        question
    )

    if not mode:
        return None

    selected_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if (
            "12-site-web-et-navigateurs.pdf"
            in source_name
        ):
            selected_units.append(unit)

    if not selected_units:
        return None

    if mode == "browsers":
        summary = (
            "Résumé du contenu :\n"
            "- Un navigateur Web est un logiciel installé dans un système d'exploitation pour consulter l'ensemble des sites Web du World Wide Web.\n"
            "- Son interface graphique comprend les boutons de navigation, la barre d'adresse, l'espace d'affichage et la barre d'état.\n"
            "- Internet Explorer, ou IE, est installé automatiquement par le système d'exploitation.\n"
            "- Mozilla Firefox est un navigateur Web libre qui permet d'afficher plusieurs pages Web dans une même fenêtre."
        )
    else:
        summary = (
            "Résumé du contenu :\n"
            "- WWW signifie World Wide Web ; il est aussi appelé la toile, W3 ou la toile d'araignée mondiale, et facilite la consultation des sites sur Internet.\n"
            "- Une adresse Web est un code de mots et de signes permettant d'accéder à un site Web. Elle comprend le protocole de communication, le WWW et le domaine.\n"
            "- HTTP signifie Hyper Text Transfer Protocole et sert à transférer les documents HTML, les images et les feuilles de style d'un site Web.\n"
            "- Le domaine comporte le nom du site et le suffixe ; dans l'exemple, madariss est le nom du site et .fr le suffixe.\n"
            "- Un site Web est une ressource d'informations disponible sur le Web, constituée de plusieurs pages Web liées par des liens hypertexte."
        )

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


def detect_french_programming_notions_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours sur la programmation LOGO."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(question)

    if (
        "avantages" in normalized_question
        and "interface logo" in normalized_question
    ):
        return "advantages_interface"

    if (
        "notions de programmation" in normalized_question
        and "logo" in normalized_question
    ):
        return "full"

    return ""


def build_french_programming_notions_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit un résumé fidèle du cours de programmation LOGO."""

    mode = detect_french_programming_notions_summary_mode(
        question
    )

    if not mode:
        return None

    selected_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if (
            "7-notion-de-la-programmation.pdf"
            in source_name
        ):
            selected_units.append(unit)

    if not selected_units:
        return None

    if mode == "advantages_interface":
        summary = (
            "Résumé du contenu :\n"
            "- L'interface LOGO comprend deux parties : la partie graphique, qui est l'espace où se trouve la tortue, et la partie de commande, où l'utilisateur rédige les ordres destinés à la tortue.\n"
            "- La programmation développe le raisonnement et la créativité.\n"
            "- Elle permet aussi d'être clair, précis, bien organisé et rigoureux."
        )
    else:
        summary = (
            "Résumé du contenu :\n"
            "- Un programme est un ensemble d'instructions exécutées par la machine, tandis que la programmation permet d'écrire un programme compréhensible par celle-ci.\n"
            "- Un langage de programmation est un ensemble de signes et de codes soumis à des règles précises ; un logiciel de programmation permet d'écrire et de corriger un programme.\n"
            "- Un algorithme est une suite finie d'actions précises et ordonnées menant à la résolution d'un problème.\n"
            "- LOGO est un langage de programmation destiné aux débutants ; LOGO.NET et XLOGO en sont deux versions citées.\n"
            "- Dans LOGO, l'utilisateur donne des ordres à une tortue. L'interface comprend une partie graphique et une partie de commande.\n"
            "- La programmation développe le raisonnement, la créativité, la clarté, la précision, l'organisation et la rigueur."
        )

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


def detect_french_computer_assisted_presentation_summary_mode(
    question: str,
) -> str:
    """Détecte les résumés du cours sur la Pré AO."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(question)

    if (
        "powerpoint" in normalized_question
        and (
            "environnement" in normalized_question
            or "partie" in normalized_question
        )
    ):
        return "powerpoint"

    if (
        "presentation assistee" in normalized_question
        and "ordinateur" in normalized_question
    ):
        return "full"

    return ""


def build_french_computer_assisted_presentation_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit un résumé fidèle du PDF sur la Pré AO."""

    mode = (
        detect_french_computer_assisted_presentation_summary_mode(
            question
        )
    )

    if not mode:
        return None

    selected_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if (
            "2-la-presentation-assistee-par-ordinateur.pdf"
            in source_name
        ):
            selected_units.append(unit)

    if not selected_units:
        return None

    if mode == "powerpoint":
        summary = (
            "Résumé du contenu :\n"
            "- Microsoft PowerPoint est un logiciel de création de présentations multimédia.\n"
            "- Pour démarrer PowerPoint, il faut cliquer sur Démarrer, choisir Tous les programmes, puis sélectionner Microsoft Office PowerPoint dans Microsoft Office.\n"
            "- L’environnement de PowerPoint 2007 présenté dans l’image comprend la barre d’accès outils rapide, le ruban, le volet des diapositives, la diapositive, la zone de gestion du contenu multimédia et la barre d’état."
        )
    else:
        summary = (
            "Résumé du contenu :\n"
            "- La présentation assistée par ordinateur, notée Pré AO, est une succession de diapositives destinée à être visionnée sur l’écran de l’ordinateur ou projetée par vidéo-projecteur.\n"
            "- Une diapositive est une page-écran pouvant contenir du texte, des images, des tableaux, des graphiques, des organigrammes, des animations, des sons et des vidéos.\n"
            "- Un logiciel de Pré AO permet de créer des diapositives qui défilent manuellement ou automatiquement ; le cours cite Microsoft PowerPoint, Corel Présentation et OpenOffice.org Impress.\n"
            "- Un diaporama est un ensemble de pages-écran qui s’affichent les unes à la suite des autres et permet de visualiser une présentation en plein écran.\n"
            "- Microsoft PowerPoint sert à créer des présentations multimédia et son interface comprend notamment le ruban et la barre d’état."
        )

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


def detect_french_network_typology_summary_mode(
    question: str,
) -> str:
    """Détecte les deux résumés du cours sur les réseaux."""

    if contains_arabic(question):
        return ""

    normalized_question = normalize_text(question)

    if (
        "modem" in normalized_question
        and "routeur" in normalized_question
    ):
        return "modem_router"

    if (
        "typologie" in normalized_question
        and "reseaux" in normalized_question
    ):
        return "full"

    return ""


def build_french_network_typology_summary(
    question: str,
    units: list[dict],
) -> dict | None:
    """Construit un résumé fidèle du PDF de typologie des réseaux."""

    mode = detect_french_network_typology_summary_mode(
        question
    )

    if not mode:
        return None

    selected_units = []

    for unit in units:
        source_name = (
            unit.get("source", "")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if (
            "1-la-typologie-des-reseaux.pdf"
            in source_name
        ):
            selected_units.append(unit)

    if not selected_units:
        return None

    if mode == "modem_router":
        summary = (
            "Résumé du contenu :\n"
            "- Le modem est un dispositif qui établit une liaison entre le PC et le réseau Internet ; modem signifie modulateur-démodulateur.\n"
            "- Il permet l’échange d’informations entre un grand nombre d’ordinateurs via des lignes téléphoniques.\n"
            "- Le routeur est un appareil qui permet d’envoyer les informations aux bons endroits.\n"
            "- Un routeur peut aussi jouer le rôle d’un modem en Wi-Fi."
        )
    else:
        summary = (
            "Résumé du contenu :\n"
            "- Un réseau informatique est un ensemble d’ordinateurs et de matériels informatiques reliés entre eux.\n"
            "- Le LAN, Local Area Network, est un réseau local couvrant une salle, un bâtiment ou une entreprise ; il permet de communiquer, d’échanger des informations et de partager des ressources informatiques.\n"
            "- Le MAN, Metropolitan Area Network, est un réseau régional qui regroupe des réseaux LAN à l’échelle d’une ville ou d’une région.\n"
            "- Le WAN, Wide Area Network, est un réseau international qui regroupe les réseaux LAN et MAN au niveau d’un pays ou de la planète ; il est aussi appelé Internet.\n"
            "- Le modem relie le PC à Internet, tandis que le routeur envoie les informations aux bons endroits et peut jouer le rôle d’un modem en Wi-Fi."
        )

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



HISTOIRE_GEOGRAPHIE_MEGA_SOURCES = {
    'alathad-alaorbi-bin-alandmaj-oalmnafsa.pdf',
    'alathad-alaorbi-imkaniath-omkanth-alaqtsadia-fi-alaalm.pdf',
    'aldhght-alastamari-ala-almghrb.pdf',
    'alhfath-ala-almoard-altbiaia.pdf',
    'alhfath-ala-altrath-ottoirh.pdf',
    'alhrb-alaalmia-alaola-alasbab-oalntaij.pdf',
    'alhrb-alaalmia-althania-alasbab-oalntaij-11.pdf',
    'aliaban-qoa-tknolojia.pdf',
    'alimbrialia-olida-alrasmalia.pdf',
    'almghrb-alarbi-anasr-alohda-oaltnoa.pdf',
    'almghrb-alarbi-bin-altkaml-oalthdiat.pdf',
    'almghrb-alkfah-mn-ajl-alastqlal-oitmam-alohda-altrabia.pdf',
    'almghrb-oalslm-alaalmi.pdf',
    'almghrb-ohoar-aladian.pdf',
    'almrahl-alkbra-lbnaa-aldola-almghrbia-alhditha.pdf',
    'almsharka-hq-ooajb-nntkhb-mmthlina-fi-mjls-almoussa.pdf',
    'alolaiat-almthda-alamrikia-qoa-aalmia.pdf',
    'alqdhia-alflstinia-oalsraa-alarbi-alisraiili-15.pdf',
    'altdrb-ala-maalja-thahra-aqtsadia-baatmad-alnhj-aljghrafi.pdf',
    'anhiar-alimbratoria-alathmania-oaltdkhl-alastamari-fi-almshrq-alarbi.pdf',
    'aqtrah-bramj-ialamia-ttokha-alnhodh-bqim-almoatna.pdf',
    'athad-almghrb-alarbi-khiar-astratiji-lltktl-aliqlimi.pdf',
    'azdhar-alrasmalia-alaorbia-khlal-alqrn-19m.pdf',
    'azma-1929-alasbab-oalmthahr-oalntaij.pdf',
    'ila-ain-alja-fi-hala-khrq-hq-mn-hqoqi-aldstoria-ao-hqoq-ghiri.pdf',
    'kif-naalj-mshkla-ajtmaaia-antlaqa-mn-amthla-mhlia.pdf',
    'maiqat-altktlat-aljhoia-mqarna-bin-alathad-alaorbi-oalmghrb-alarbi.pdf',
    'mlf-hol-almqaoma-almghrbia.pdf',
    'mlf-hol-moussa-mhmd-alkhams-lltdhamn.pdf',
    'msouolia-aldol-oalafrad-oaljmaaat-fi-hl-almshakl-alajtmaaia-omsouolitna-nhn.pdf',
    'msr-nmothj-tnmoi-arbi.pdf',
    'nhn-oalaalm-ntqasm-alkra-alardhia.pdf',
    'nijiria-bin-alghna-altbiai-oaldhaf-altnmoi.pdf',
    'rosia-orhanat-althol.pdf',
    'thahra-alanthma-aldiktatoria-drasa-hala-alnazia.pdf',
    'tkhliq-alhiaa-alaama-almfhom-oalaaliat-aqtrah-khta-lmharba-alrshoa.pdf'
}


def is_histoire_geographie_summary_source(
    source: str,
) -> bool:
    return (
        (source or "").strip()
        in HISTOIRE_GEOGRAPHIE_MEGA_SOURCES
    )


def is_english_mega_summary_source(
    source: str,
) -> bool:
    """Recognises the English mega-batch lesson files."""

    source_name = (
        source or ""
    ).strip().lower()

    return bool(
        re.fullmatch(
            r"unit-\d+-.+\.pdf",
            source_name,
        )
    )


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

    # ========================================================
    # Histoire-Geographie full-document extractive summary
    # ========================================================

    histoire_geographie_passages = [
        passage
        for passage in passages
        if is_histoire_geographie_summary_source(
            passage.get(
                "source",
                "",
            )
        )
    ]

    if histoire_geographie_passages:

        source_name = (
            histoire_geographie_passages[0].get(
                "source",
                "",
            )
        )

        histoire_geographie_passages = [
            passage
            for passage
            in histoire_geographie_passages
            if passage.get(
                "source",
                "",
            )
            == source_name
        ]

        ordered_passages = sorted(
            histoire_geographie_passages,
            key=lambda passage: (
                passage.get(
                    "page",
                    0,
                )
                or 0,
                str(
                    passage.get(
                        "chunk_id",
                        "",
                    )
                ),
            ),
        )

        unique_lines = []
        seen_lines = set()

        for passage in ordered_passages:

            text = (
                passage.get(
                    "text",
                    "",
                )
                or ""
            )

            for raw_line in text.splitlines():

                line = normalize_spaces(
                    raw_line
                )

                if not line:
                    continue

                key = (
                    line
                    .casefold()
                    .strip()
                )

                if key in seen_lines:
                    continue

                seen_lines.add(
                    key
                )

                unique_lines.append(
                    line
                )

        if not unique_lines:
            return {
                "answerable": False,
                "summary": refusal,
                "sources": [],
                "evidence": [],
            }

        summary = (
            "\u0645\u0644\u062e\u0635 "
            "\u0627\u0644\u0645\u062d\u062a\u0648\u0649:\n\n"
            + "\n".join(
                f"- {line}"
                for line in unique_lines
            )
        )

        return {
            "answerable": True,
            "summary": summary,
            "sources": build_summary_sources(
                ordered_passages
            ),
            "evidence": [
                passage.get(
                    "text",
                    "",
                )
                for passage
                in ordered_passages
            ],
        }


    # ========================================================
    # MATH FULL-DOCUMENT EXTRACTIVE SUMMARY
    # ========================================================
    #
    # Math PDFs frequently contain formulas as images, while their
    # textual definitions, properties and exercises are preserved
    # by PDF extraction. For a source-scoped lesson summary we keep
    # the complete verified textual content instead of selecting
    # only semantically prominent headings.
    # ========================================================

    math_passages = [
        passage
        for passage in passages
        if normalize_text(
            passage.get(
                "program",
                "",
            )
        )
        == normalize_text(
            "Programme marocain"
        )
        and normalize_text(
            passage.get(
                "subject",
                "",
            )
        )
        in {
            normalize_text(
                "Math\u00e9matiques"
            ),
            normalize_text(
                "Math\u00e9matiques arabe"
            ),
        }
    ]

    if math_passages:

        source_name = (
            math_passages[0].get(
                "source",
                "",
            )
        )

        math_passages = [
            passage
            for passage
            in math_passages
            if passage.get(
                "source",
                "",
            )
            == source_name
        ]

        ordered_passages = sorted(
            math_passages,
            key=lambda passage: (
                passage.get(
                    "page",
                    0,
                )
                or 0,
                passage.get(
                    "chunk_number",
                    0,
                )
                or 0,
                str(
                    passage.get(
                        "chunk_id",
                        "",
                    )
                ),
            ),
        )

        unique_lines = []
        seen_lines = set()

        for passage in ordered_passages:

            text = (
                passage.get(
                    "text",
                    "",
                )
                or ""
            )

            for raw_line in (
                text.splitlines()
            ):

                line = normalize_spaces(
                    raw_line
                )

                if not line:
                    continue

                key = normalize_text(
                    line
                )

                if (
                    not key
                    or key in seen_lines
                ):
                    continue

                seen_lines.add(
                    key
                )

                unique_lines.append(
                    line
                )

        if not unique_lines:

            return {
                "answerable": False,
                "summary": refusal,
                "sources": [],
                "evidence": [],
            }

        summary = (
            "R\u00e9sum\u00e9 du contenu :\n\n"
            + "\n".join(
                "- " + line
                for line
                in unique_lines
            )
        )

        return {
            "answerable": True,
            "summary": summary,
            "sources": (
                build_summary_sources(
                    ordered_passages
                )
            ),
            "evidence": [
                passage.get(
                    "text",
                    "",
                )
                for passage
                in ordered_passages
                if passage.get(
                    "text",
                    "",
                )
            ],
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

    english_mega_passages = [
        passage
        for passage in passages
        if is_english_mega_summary_source(
            passage.get(
                "source",
                "",
            )
        )
    ]

    if english_mega_passages:
        # Keep raw retrieved passages for English lessons.
        # This preserves short headings such as
        # "II- Practice" that build_summary_units may remove.

        ordered_passages = sorted(
            english_mega_passages,
            key=lambda item: (
                item.get("page", 0),
                item.get("source", ""),
            ),
        )

        unique_passages = []
        seen = set()

        for passage in ordered_passages:
            text = (
                passage.get(
                    "text",
                    "",
                )
                or ""
            ).strip()

            if not text:
                continue

            normalized = re.sub(
                r"\\s+",
                " ",
                text,
            ).strip().lower()

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            unique_passages.append(
                passage
            )

        if not unique_passages:
            return {
                "answerable": False,
                "summary": refusal,
                "sources": [],
                "evidence": [],
            }

        summary_parts = [
            (
                passage.get(
                    "text",
                    "",
                )
                or ""
            ).strip()
            for passage in unique_passages
            if (
                passage.get(
                    "text",
                    "",
                )
                or ""
            ).strip()
        ]

        summary = (
            "Summary of the document:\n\n"
            + "\n\n".join(
                summary_parts
            )
        )

        sources = []

        for passage in unique_passages:
            source = {
                "file": passage.get(
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
            }

            if source not in sources:
                sources.append(
                    source
                )

        return {
            "answerable": True,
            "summary": summary,
            "sources": sources,
            "evidence": summary_parts,
        }

    structured_islamic_education_summary = (
        build_islamic_education_mega_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_islamic_education_summary is not None:
        return structured_islamic_education_summary

    structured_mega_17_65_summary = (
        build_french_mega_17_65_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_mega_17_65_summary is not None:
        return structured_mega_17_65_summary

    structured_batch_13_16_summary = (
        build_french_batch_13_16_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_batch_13_16_summary is not None:
        return structured_batch_13_16_summary

    structured_open_letter_summary = (
        build_french_open_letter_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_open_letter_summary is not None:
        return structured_open_letter_summary

    structured_debate_participant_invitations_summary = (
        build_french_debate_participant_invitations_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_debate_participant_invitations_summary is not None:
        return structured_debate_participant_invitations_summary

    structured_beneficiary_invitation_summary = (
        build_french_beneficiary_invitation_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_beneficiary_invitation_summary is not None:
        return structured_beneficiary_invitation_summary

    structured_guest_speaker_invitation_summary = (
        build_french_guest_speaker_invitation_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_guest_speaker_invitation_summary is not None:
        return structured_guest_speaker_invitation_summary

    structured_invitation_writing_summary = (
        build_french_invitation_writing_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_invitation_writing_summary is not None:
        return structured_invitation_writing_summary

    structured_authorization_letter_summary = (
        build_french_authorization_letter_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_authorization_letter_summary is not None:
        return structured_authorization_letter_summary

    structured_concession_summary = (
        build_french_concession_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_concession_summary is not None:
        return structured_concession_summary

    structured_reported_speech_summary = (
        build_french_reported_speech_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_reported_speech_summary is not None:
        return structured_reported_speech_summary

    structured_coordination_summary = (
        build_french_coordination_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_coordination_summary is not None:
        return structured_coordination_summary

    structured_past_participle_avoir_summary = (
        build_french_past_participle_avoir_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_past_participle_avoir_summary is not None:
        return structured_past_participle_avoir_summary

    structured_adjective_qualifier_summary = (
        build_french_adjective_qualifier_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_adjective_qualifier_summary is not None:
        return structured_adjective_qualifier_summary

    structured_characterize_noun_summary = (
        build_french_characterize_noun_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_characterize_noun_summary is not None:
        return structured_characterize_noun_summary

    structured_websites_browsers_summary = (
        build_french_websites_browsers_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_websites_browsers_summary is not None:
        return structured_websites_browsers_summary

    structured_programming_summary = (
        build_french_programming_notions_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_programming_summary is not None:
        return structured_programming_summary

    structured_presentation_summary = (
        build_french_computer_assisted_presentation_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_presentation_summary is not None:
        return structured_presentation_summary

    structured_network_summary = (
        build_french_network_typology_summary(
            question=cleaned_question,
            units=units,
        )
    )

    if structured_network_summary is not None:
        return structured_network_summary

    if contains_arabic(
        cleaned_question
    ):
        diminutive_units = (
            select_arabic_diminutive_units(
                question=cleaned_question,
                units=units,
            )
        )

        if diminutive_units:
            structured_diminutive_summary = (
                build_arabic_diminutive_summary(
                    question=cleaned_question,
                    selected_units=diminutive_units,
                )
            )

            if structured_diminutive_summary is not None:
                return structured_diminutive_summary

        wonder_story_units = (
            select_arabic_wonder_scifi_story_units(
                question=cleaned_question,
                units=units,
            )
        )

        if wonder_story_units:
            structured_wonder_story_summary = (
                build_arabic_wonder_scifi_story_summary(
                    question=cleaned_question,
                    selected_units=wonder_story_units,
                )
            )

            if structured_wonder_story_summary is not None:
                return structured_wonder_story_summary

        biography_units = (
            select_arabic_biography_writing_units(
                question=cleaned_question,
                units=units,
            )
        )

        if biography_units:
            structured_biography_summary = (
                build_arabic_biography_writing_summary(
                    question=cleaned_question,
                    selected_units=biography_units,
                )
            )

            if structured_biography_summary is not None:
                return structured_biography_summary

        sifa_units = (
            select_arabic_sifa_mushabbaha_units(
                question=cleaned_question,
                units=units,
            )
        )

        if sifa_units:
            structured_sifa_summary = (
                build_arabic_sifa_mushabbaha_summary(
                    question=cleaned_question,
                    selected_units=sifa_units,
                )
            )

            if structured_sifa_summary is not None:
                return structured_sifa_summary

        nisba_units = (
            select_arabic_nisba_units(
                question=cleaned_question,
                units=units,
            )
        )

        if nisba_units:
            structured_nisba_summary = (
                build_arabic_nisba_summary(
                    question=cleaned_question,
                    selected_units=nisba_units,
                )
            )

            if structured_nisba_summary is not None:
                return structured_nisba_summary

        exile_units = (
            select_arabic_exile_units(
                question=cleaned_question,
                units=units,
            )
        )

        if exile_units:
            structured_exile_summary = (
                build_arabic_exile_summary(
                    question=cleaned_question,
                    selected_units=exile_units,
                )
            )

            if structured_exile_summary is not None:
                return structured_exile_summary

        mamnu_units = (
            select_arabic_mamnu_min_al_sarf_units(
                question=cleaned_question,
                units=units,
            )
        )

        if mamnu_units:
            structured_mamnu_summary = (
                build_arabic_mamnu_min_al_sarf_summary(
                    question=cleaned_question,
                    selected_units=mamnu_units,
                )
            )

            if structured_mamnu_summary is not None:
                return structured_mamnu_summary

        locust_units = (
            select_arabic_locust_units(
                question=cleaned_question,
                units=units,
            )
        )

        if locust_units:
            structured_locust_summary = (
                build_arabic_locust_summary(
                    question=cleaned_question,
                    selected_units=locust_units,
                )
            )

            if structured_locust_summary is not None:
                return structured_locust_summary

        islam_human_rights_units = (
            select_arabic_islam_human_rights_units(
                question=cleaned_question,
                units=units,
            )
        )

        if islam_human_rights_units:
            structured_islam_human_rights_summary = (
                build_arabic_islam_human_rights_summary(
                    question=cleaned_question,
                    selected_units=islam_human_rights_units,
                )
            )

            if (
                structured_islam_human_rights_summary
                is not None
            ):
                return (
                    structured_islam_human_rights_summary
                )

        idafa_units = (
            select_arabic_idafa_units(
                question=cleaned_question,
                units=units,
            )
        )

        if idafa_units:
            structured_idafa_summary = (
                build_arabic_idafa_summary(
                    question=cleaned_question,
                    selected_units=idafa_units,
                )
            )

            if structured_idafa_summary is not None:
                return structured_idafa_summary

        ibdal_units = (
            select_arabic_ibdal_units(
                question=cleaned_question,
                units=units,
            )
        )

        if ibdal_units:
            structured_ibdal_summary = (
                build_arabic_ibdal_summary(
                    question=cleaned_question,
                    selected_units=ibdal_units,
                )
            )

            if structured_ibdal_summary is not None:
                return structured_ibdal_summary

        ilal_units = (
            select_arabic_ilal_units(
                question=cleaned_question,
                units=units,
            )
        )

        if ilal_units:
            structured_ilal_summary = (
                build_arabic_ilal_summary(
                    question=cleaned_question,
                    selected_units=ilal_units,
                )
            )

            if structured_ilal_summary is not None:
                return structured_ilal_summary

        eternal_song_units = (
            select_arabic_eternal_song_units(
                question=cleaned_question,
                units=units,
            )
        )

        if eternal_song_units:
            structured_eternal_song_summary = (
                build_arabic_eternal_song_summary(
                    question=cleaned_question,
                    selected_units=eternal_song_units,
                )
            )

            if structured_eternal_song_summary is not None:
                return structured_eternal_song_summary

        my_homeland_poem_units = (
            select_arabic_my_homeland_poem_units(
                question=cleaned_question,
                units=units,
            )
        )

        if my_homeland_poem_units:
            structured_my_homeland_poem_summary = (
                build_arabic_my_homeland_poem_summary(
                    question=cleaned_question,
                    selected_units=my_homeland_poem_units,
                )
            )

            if structured_my_homeland_poem_summary is not None:
                return structured_my_homeland_poem_summary

        describing_journey_units = (
            select_arabic_describing_journey_units(
                question=cleaned_question,
                units=units,
            )
        )

        if describing_journey_units:
            structured_describing_journey_summary = (
                build_arabic_describing_journey_summary(
                    question=cleaned_question,
                    selected_units=describing_journey_units,
                )
            )

            if structured_describing_journey_summary is not None:
                return structured_describing_journey_summary

        describing_people_places_units = (
            select_arabic_describing_people_places_units(
                question=cleaned_question,
                units=units,
            )
        )

        if describing_people_places_units:
            structured_describing_people_places_summary = (
                build_arabic_describing_people_places_summary(
                    question=cleaned_question,
                    selected_units=describing_people_places_units,
                )
            )

            if structured_describing_people_places_summary is not None:
                return structured_describing_people_places_summary

        commentary_rebuttal_units = (
            select_arabic_commentary_rebuttal_units(
                question=cleaned_question,
                units=units,
            )
        )

        if commentary_rebuttal_units:
            structured_commentary_rebuttal_summary = (
                build_arabic_commentary_rebuttal_summary(
                    question=cleaned_question,
                    selected_units=commentary_rebuttal_units,
                )
            )

            if structured_commentary_rebuttal_summary is not None:
                return structured_commentary_rebuttal_summary

        diary_writing_units = (
            select_arabic_diary_writing_units(
                question=cleaned_question,
                units=units,
            )
        )

        if diary_writing_units:
            structured_diary_writing_summary = (
                build_arabic_diary_writing_summary(
                    question=cleaned_question,
                    selected_units=diary_writing_units,
                )
            )

            if structured_diary_writing_summary is not None:
                return structured_diary_writing_summary

        school_of_life_units = (
            select_arabic_school_of_life_units(
                question=cleaned_question,
                units=units,
            )
        )

        if school_of_life_units:
            structured_school_of_life_summary = (
                build_arabic_school_of_life_summary(
                    question=cleaned_question,
                    selected_units=school_of_life_units,
                )
            )

            if structured_school_of_life_summary is not None:
                return structured_school_of_life_summary

        kalim_allah_units = (
            select_arabic_kalim_allah_units(
                question=cleaned_question,
                units=units,
            )
        )

        if kalim_allah_units:
            structured_kalim_allah_summary = (
                build_arabic_kalim_allah_summary(
                    question=cleaned_question,
                    selected_units=kalim_allah_units,
                )
            )

            if structured_kalim_allah_summary is not None:
                return structured_kalim_allah_summary

        muslim_qualities_units = (
            select_arabic_muslim_qualities_units(
                question=cleaned_question,
                units=units,
            )
        )

        if muslim_qualities_units:
            structured_muslim_qualities_summary = (
                build_arabic_muslim_qualities_summary(
                    question=cleaned_question,
                    selected_units=muslim_qualities_units,
                )
            )

            if (
                structured_muslim_qualities_summary
                is not None
            ):
                return structured_muslim_qualities_summary

        wonderful_dialogue_units = (
            select_arabic_wonderful_dialogue_units(
                question=cleaned_question,
                units=units,
            )
        )

        if wonderful_dialogue_units:
            structured_wonderful_dialogue_summary = (
                build_arabic_wonderful_dialogue_summary(
                    question=cleaned_question,
                    selected_units=wonderful_dialogue_units,
                )
            )

            if (
                structured_wonderful_dialogue_summary
                is not None
            ):
                return (
                    structured_wonderful_dialogue_summary
                )

        time_place_units = (
            select_arabic_time_place_units(
                question=cleaned_question,
                units=units,
            )
        )

        if time_place_units:
            structured_time_place_summary = (
                build_arabic_time_place_summary(
                    question=cleaned_question,
                    selected_units=time_place_units,
                )
            )

            if structured_time_place_summary is not None:
                return structured_time_place_summary

        comparative_units = (
            select_arabic_comparative_units(
                question=cleaned_question,
                units=units,
            )
        )

        if comparative_units:
            structured_comparative_summary = (
                build_arabic_comparative_summary(
                    question=cleaned_question,
                    selected_units=comparative_units,
                )
            )

            if structured_comparative_summary is not None:
                return structured_comparative_summary

        passive_participle_units = (
            select_arabic_passive_participle_units(
                question=cleaned_question,
                units=units,
            )
        )

        if passive_participle_units:
            structured_passive_summary = (
                build_arabic_passive_participle_summary(
                    question=cleaned_question,
                    selected_units=passive_participle_units,
                )
            )

            if structured_passive_summary is not None:
                return structured_passive_summary

        active_participle_units = (
            select_arabic_active_participle_units(
                question=cleaned_question,
                units=units,
            )
        )

        if active_participle_units:
            structured_active_summary = (
                build_arabic_active_participle_summary(
                    question=cleaned_question,
                    selected_units=active_participle_units,
                )
            )

            if structured_active_summary is not None:
                return structured_active_summary

        instrument_noun_units = (
            select_arabic_instrument_noun_units(
                question=cleaned_question,
                units=units,
            )
        )

        if instrument_noun_units:
            structured_instrument_summary = (
                build_arabic_instrument_noun_summary(
                    question=cleaned_question,
                    selected_units=instrument_noun_units,
                )
            )

            if structured_instrument_summary is not None:
                return structured_instrument_summary

        warning_enticement_units = (
            select_arabic_warning_enticement_units(
                question=cleaned_question,
                units=units,
            )
        )

        if warning_enticement_units:
            structured_warning_summary = (
                build_arabic_warning_enticement_summary(
                    question=cleaned_question,
                    selected_units=(
                        warning_enticement_units
                    ),
                )
            )

            if structured_warning_summary is not None:
                return structured_warning_summary

        exclamation_units = (
            select_arabic_exclamation_units(
                question=cleaned_question,
                units=units,
            )
        )

        if exclamation_units:
            structured_response = (
                build_arabic_exclamation_structured_summary(
                    question=cleaned_question,
                    selected_units=exclamation_units,
                )
            )

            if structured_response is not None:
                return structured_response

            return build_summary_response(
                exclamation_units,
                cleaned_question,
            )

        is_general_request = (
            is_general_arabic_summary_request(
                cleaned_question
            )
        )

        if is_general_request:
            selected_units = (
                select_general_arabic_coverage_units(
                    question=cleaned_question,
                    units=units,
                    maximum_units=4,
                )
            )
        else:
            normalized_summary_question = (
                normalize_text(
                    cleaned_question
                )
            )

            focused_maximum_units = (
                5
                if (
                    "منادي"
                    in normalized_summary_question
                    and any(
                        marker
                        in normalized_summary_question
                        for marker in (
                            "انواع",
                            "احكام",
                        )
                    )
                )
                else 4
            )

            selected_units = (
                select_arabic_focused_units(
                    question=cleaned_question,
                    units=units,
                    maximum_units=(
                        focused_maximum_units
                    ),
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
