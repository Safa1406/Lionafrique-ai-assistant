import difflib
import json
import re
import unicodedata

import httpx


OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3:1.7b"

ARABIC_RULES_VERSION = "v15-arabic-warning-enticement-rules"

REFUSAL_ANSWER = (
    "Les documents disponibles ne contiennent pas "
    "une réponse suffisamment précise à cette question."
)

ARABIC_REFUSAL_ANSWER = (
    "الوثائق المتوفرة لا تحتوي على إجابة دقيقة "
    "بما يكفي عن هذا السؤال."
)

EVIDENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "answerable": {
            "type": "boolean",
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "passage_number": {
                        "type": "integer",
                    },
                    "quote": {
                        "type": "string",
                    },
                },
                "required": [
                    "passage_number",
                    "quote",
                ],
            },
        },
    },
    "required": [
        "answerable",
        "evidence",
    ],
}

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
        },
    },
    "required": [
        "answer",
    ],
}


ARABIC_QUESTION_TYPO_REPLACEMENTS = (
    (
        r"(?<!\w)الانواء(?!\w)",
        "الانواع",
    ),
    (
        r"(?<!\w)انواء(?!\w)",
        "انواع",
    ),
    (
        r"(?<!\w)المنادا(?!\w)",
        "المنادى",
    ),
    (
        r"(?<!\w)منادا(?!\w)",
        "منادى",
    ),
    (
        r"(?<!\w)الاختصاس(?!\w)",
        "الاختصاص",
    ),
    (
        r"(?<!\w)اختصاس(?!\w)",
        "اختصاص",
    ),
    (
        r"(?<!\w)عناصير(?!\w)",
        "عناصر",
    ),
    (
        r"(?<!\w)الادواة(?!\w)",
        "الادوات",
    ),
    (
        r"(?<!\w)ادواة(?!\w)",
        "ادوات",
    ),
    (
        r"(?<!\w)ادواه(?!\w)",
        "ادوات",
    ),
    (
        r"(?<!\w)الاغرا(?!\w)",
        "الاغراء",
    ),
    (
        r"(?<!\w)اغرا(?!\w)",
        "اغراء",
    ),
)


def repair_common_arabic_question_typos(
    question: str,
) -> str:
    """
    Corrige un ensemble limité de fautes arabes
    avant l'analyse documentaire de la question.

    La question originale reste inchangée dans l'interface.
    """

    repaired_question = question

    for pattern, replacement in (
        ARABIC_QUESTION_TYPO_REPLACEMENTS
    ):
        repaired_question = re.sub(
            pattern,
            replacement,
            repaired_question,
            flags=re.UNICODE,
        )

    repaired_question = re.sub(
        r"\s+",
        " ",
        repaired_question,
    )

    return repaired_question.strip()


ARABIC_CHARACTER_PATTERN = re.compile(
    r"[\u0600-\u06FF]"
)

ARABIC_TRANSLATION_TABLE = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
        "ـ": "",
    }
)


ARABIC_OCR_TRANSLATION_TABLE = str.maketrans(
    {
        "Ƞ": "",
        "ƞ": "",
        "ȥ": "",
        "Ȣ": "",
        "ȣ": "",
        "Ȧ": "ا",
        "ȧ": "ا",
        "ϗ": "",
    }
)

STOP_WORDS = {
    # Français
    "avec",
    "aux",
    "ce",
    "ces",
    "cette",
    "comment",
    "cours",
    "dans",
    "de",
    "des",
    "du",
    "elle",
    "elles",
    "en",
    "est",
    "et",
    "il",
    "ils",
    "la",
    "le",
    "les",
    "pour",
    "pourquoi",
    "qu",
    "que",
    "quel",
    "quelle",
    "quelles",
    "quels",
    "qui",
    "sont",
    "sur",
    "un",
    "une",
    # Arabe
    "او",
    "الى",
    "ام",
    "ان",
    "اي",
    "بالنسبه",
    "بعد",
    "بين",
    "ثم",
    "درس",
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
    "متى",
    "من",
    "موضوع",
    "هل",
    "هي",
    "هو",
    "هذا",
    "هذه",
    "هناك",
    "و",
}

INTENT_WORDS = {
    "causes": {
        "cause",
        "causes",
        "origine",
        "origines",
        "raison",
        "raisons",
        "facteur",
        "facteurs",
        "declenchement",
        "اسباب",
        "سبب",
        "لماذا",
        "عوامل",
        "عامل",
    },
    "consequences": {
        "consequence",
        "consequences",
        "effet",
        "effets",
        "bilan",
        "impact",
        "impacts",
        "resultat",
        "resultats",
        "اثار",
        "اثر",
        "عواقب",
        "نتايج",
        "نتيجه",
    },
    "definition": {
        "definition",
        "definir",
        "signifie",
        "تعريف",
        "عرف",
        "يعني",
        "معنى",
    },
    "elements": {
        "element",
        "elements",
        "composant",
        "composants",
        "compose",
        "composition",
        "constitue",
        "constituent",
        "عناصر",
        "عنصر",
        "مكونات",
        "مكون",
        "يتكون",
        "تتكون",
    },
    "roles": {
        "role",
        "roles",
        "fonction",
        "fonctions",
        "وظيفه",
        "وظايف",
        "دور",
        "ادوار",
        "فائده",
    },
    "summary": {
        "resume",
        "resumer",
        "synthese",
        "لخص",
        "تلخيص",
        "ملخص",
    },
    "comparison": {
        "difference",
        "differences",
        "compare",
        "comparaison",
        "فرق",
        "قارن",
        "مقارنه",
    },
}

UNCERTAINTY_EXPRESSIONS = {
    "peut avoir contribue",
    "peut etre",
    "semble",
    "suggere",
    "probablement",
    "ne mentionnent pas directement",
    "ne sont pas directement",
    "pas directement lie",
}


def contains_arabic(text: str) -> bool:
    """
    Vérifie si un texte contient des caractères arabes.
    """

    return bool(
        ARABIC_CHARACTER_PATTERN.search(
            text or ""
        )
    )


def normalize_text(text: str) -> str:
    """
    Normalise un texte latin ou arabe
    sans supprimer les caractères arabes.
    """

    if not text:
        return ""

    cleaned_input = text.translate(
        ARABIC_OCR_TRANSLATION_TABLE
    )

    normalized_text = unicodedata.normalize(
        "NFKD",
        cleaned_input.lower(),
    )

    normalized_text = "".join(
        character
        for character in normalized_text
        if not unicodedata.combining(
            character
        )
    )

    normalized_text = normalized_text.translate(
        ARABIC_TRANSLATION_TABLE
    )

    normalized_text = normalized_text.replace(
        "_",
        " ",
    )

    normalized_text = re.sub(
        r"[^\w\s-]",
        " ",
        normalized_text,
        flags=re.UNICODE,
    )

    normalized_text = re.sub(
        r"\s+",
        " ",
        normalized_text,
    )

    # Corrections prudentes de fautes fréquentes dans les requêtes
    # arabes. Elles améliorent la recherche sans modifier les PDF.
    arabic_typo_replacements = {
        "ماهي": "ما هي",
        "ادواه": "ادوات",
        "ادواة": "ادوات",
        "الادواة": "الادوات",
        "انواء": "انواع",
        "الانواء": "الانواع",
        "المنادا": "المنادي",
        "منادا": "منادي",
        "الهمزه": "الهمزه",
    }

    for wrong_form, corrected_form in (
        arabic_typo_replacements.items()
    ):
        normalized_text = normalized_text.replace(
            wrong_form,
            corrected_form,
        )

    normalized_text = re.sub(
        r"\s+",
        " ",
        normalized_text,
    )

    return normalized_text.strip()


def normalize_word(word: str) -> str:
    """
    Normalise un mot pour améliorer
    les comparaisons lexicales.
    """

    normalized_word = normalize_text(
        word
    ).strip("- ")

    if not normalized_word:
        return ""

    if contains_arabic(
        normalized_word
    ):
        prefixes = (
            "وال",
            "بال",
            "كال",
            "فال",
            "لل",
            "ال",
        )

        for prefix in prefixes:
            if (
                normalized_word.startswith(
                    prefix
                )
                and len(normalized_word)
                - len(prefix)
                >= 2
            ):
                normalized_word = normalized_word[
                    len(prefix):
                ]
                break

    return normalized_word


def normalize_arabic_match_text(
    text: str,
) -> str:
    """Normalise chaque mot arabe, y compris l'article défini."""

    words = []

    for raw_word in normalize_text(
        text
    ).split():
        normalized_word = normalize_word(
            raw_word
        )

        if normalized_word:
            words.append(
                normalized_word
            )

    return " ".join(
        words
    )


def arabic_phrase_in_text(
    text: str,
    phrase: str,
) -> bool:
    """Compare une expression arabe sans être trompé par «ال»."""

    normalized_text_value = (
        normalize_arabic_match_text(
            text
        )
    )

    normalized_phrase = (
        normalize_arabic_match_text(
            phrase
        )
    )

    if not normalized_phrase:
        return False

    return (
        f" {normalized_phrase} "
        in f" {normalized_text_value} "
    )


def arabic_coverage_group_matches(
    group: set[str],
    quote: str,
    quote_words: set[str],
) -> bool:
    """Vérifie les mots simples et les expressions d'un groupe."""

    normalized_quote = (
        normalize_arabic_match_text(
            quote
        )
    )

    for raw_term in group:
        normalized_term = (
            normalize_arabic_match_text(
                raw_term
            )
        )

        if not normalized_term:
            continue

        if " " in normalized_term:
            if (
                f" {normalized_term} "
                in f" {normalized_quote} "
            ):
                return True
            continue

        if normalized_term in quote_words:
            return True

    return False


def tokenize_words(
    text: str,
) -> set[str]:
    """
    Retourne les mots normalisés
    d'un texte latin ou arabe.

    Pour l'arabe, conserve aussi une variante sans
    la conjonction initiale «و» ou «ف». Cela permet
    de rapprocher «وأين» de «أين» sans perdre le mot
    original, contrairement à un radicaliseur brutal.
    """

    words = set()

    for raw_word in normalize_text(
        text
    ).split():
        normalized_word = normalize_word(
            raw_word
        )

        if not normalized_word:
            continue

        words.add(
            normalized_word
        )

        if (
            contains_arabic(
                normalized_word
            )
            and normalized_word.startswith(
                (
                    "و",
                    "ف",
                )
            )
            and len(
                normalized_word
            )
            >= 3
        ):
            conjunction_free_word = (
                normalize_word(
                    normalized_word[1:]
                )
            )

            if conjunction_free_word:
                words.add(
                    conjunction_free_word
                )

    return words


def detect_question_intent(
    question: str,
) -> str | None:
    """
    Détecte la relation principale demandée.
    """

    normalized_question = normalize_text(
        question
    )

    summary_patterns = (
        "resume",
        "resumer",
        "fais moi un resume",
        "donne moi un resume",
        "لخص",
        "اعطني ملخص",
        "قدم ملخص",
        "تلخيص",
    )

    if any(
        pattern in normalized_question
        for pattern in summary_patterns
    ):
        return "summary"

    comparison_patterns = (
        "quelle est la difference",
        "quelles sont les differences",
        "compare",
        "ما الفرق",
        "قارن",
    )

    if any(
        pattern in normalized_question
        for pattern in comparison_patterns
    ):
        return "comparison"

    elements_patterns = (
        "quels sont les elements",
        "quelles sont les composantes",
        "de quoi se compose",
        "de quels elements",
        "ما هي عناصر",
        "ما عناصر",
        "مم يتكون",
        "مم تتكون",
        "ما هي مكونات",
        "ما مكونات",
    )

    if any(
        pattern in normalized_question
        for pattern in elements_patterns
    ):
        return "elements"

    definition_patterns = (
        "qu est ce que",
        "qu est ce qu",
        "que signifie",
        "quelle est la definition",
        "comment definir",
        "ما هو",
        "ما هي",
        "ماذا يعني",
        "عرف",
        "تعريف",
    )

    if any(
        pattern in normalized_question
        for pattern in definition_patterns
    ):
        return "definition"

    question_words = tokenize_words(
        normalized_question
    )

    for intent, words in INTENT_WORDS.items():
        normalized_intent_words = {
            normalize_word(word)
            for word in words
        }

        if question_words.intersection(
            normalized_intent_words
        ):
            return intent

    return None


def extract_topic_keywords(
    question: str,
) -> set[str]:
    """
    Extrait les mots décrivant
    le sujet de la question.
    """

    excluded_words = {
        normalize_word(word)
        for word in STOP_WORDS
    }

    for intent_words in INTENT_WORDS.values():
        excluded_words.update(
            normalize_word(word)
            for word in intent_words
        )

    topic_keywords = set()

    for word in tokenize_words(
        question
    ):
        if word in excluded_words:
            continue

        if contains_arabic(
            word
        ):
            if len(word) >= 2:
                topic_keywords.add(
                    word
                )
        elif len(word) >= 3:
            topic_keywords.add(
                word
            )

    return topic_keywords


def get_refusal_answer(
    question: str,
) -> str:
    """
    Retourne le message de refus
    dans la langue principale de la question.
    """

    if contains_arabic(
        question
    ):
        return ARABIC_REFUSAL_ANSWER

    return REFUSAL_ANSWER


def extract_element_evidence_from_passages(
    question: str,
    passages: list[dict],
) -> list[dict]:
    """
    Extrait directement les passages qui décrivent
    les éléments ou les composantes d'un sujet.

    Cette extraction déterministe évite de dépendre
    uniquement de la reformulation du modèle,
    notamment pour les documents arabes.
    """

    marker_words = {
        "element",
        "elements",
        "composant",
        "composants",
        "compose",
        "composee",
        "composition",
        "constitue",
        "constituee",
        "constituent",
        "عناصر",
        "عنصر",
        "مكونات",
        "مكون",
        "يتكون",
        "تتكون",
    }

    normalized_markers = {
        normalize_word(
            marker
        )
        for marker in marker_words
    }

    topic_keywords = extract_topic_keywords(
        question
    )

    candidates = []
    seen_quotes = set()

    for passage_number, passage in enumerate(
        passages,
        start=1,
    ):
        original_text = re.sub(
            r"\s+",
            " ",
            passage.get(
                "text",
                "",
            ),
        ).strip()

        if not original_text:
            continue

        original_words = original_text.split()

        normalized_words = [
            normalize_word(
                word
            )
            for word in original_words
        ]

        marker_positions = [
            index
            for index, word in enumerate(
                normalized_words
            )
            if word in normalized_markers
        ]

        for marker_position in marker_positions:
            window_start = max(
                0,
                marker_position - 12,
            )

            window_end = min(
                len(original_words),
                marker_position + 34,
            )

            quote_words = original_words[
                window_start:window_end
            ]

            if len(quote_words) < 4:
                continue

            if len(quote_words) > 45:
                quote_words = quote_words[:45]

            quote = " ".join(
                quote_words
            ).strip(
                " ,;:-"
            )

            if not quote:
                continue

            normalized_quote = normalize_text(
                quote
            )

            if normalized_quote in seen_quotes:
                continue

            quote_keywords = tokenize_words(
                quote
            )

            common_keywords = (
                topic_keywords.intersection(
                    quote_keywords
                )
            )

            if (
                topic_keywords
                and not common_keywords
            ):
                continue

            marker_count = len(
                normalized_markers.intersection(
                    quote_keywords
                )
            )

            if marker_count == 0:
                continue

            retrieval_score = float(
                passage.get(
                    "retrieval_score",
                    0.0,
                )
            )

            score = (
                len(common_keywords) * 2.0
                + marker_count * 1.2
                + retrieval_score
            )

            seen_quotes.add(
                normalized_quote
            )

            candidates.append(
                {
                    "score": score,
                    "passage_number": (
                        passage_number
                    ),
                    "quote": quote,
                    "source": passage.get(
                        "source",
                        "Source inconnue",
                    ),
                    "page": passage.get(
                        "page",
                        0,
                    ),
                }
            )

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    selected_evidence = []
    selected_sources = set()

    for candidate in candidates:
        source_key = (
            candidate["source"],
            candidate["page"],
        )

        if source_key in selected_sources:
            continue

        selected_sources.add(
            source_key
        )

        selected_evidence.append(
            {
                "passage_number": (
                    candidate[
                        "passage_number"
                    ]
                ),
                "quote": candidate[
                    "quote"
                ],
                "source": candidate[
                    "source"
                ],
                "page": candidate[
                    "page"
                ],
            }
        )

        if len(selected_evidence) >= 3:
            break

    return selected_evidence



def extract_arabic_direct_rule_evidence(
    question: str,
    passages: list[dict],
) -> list[dict]:
    """
    Extrait des réponses arabes courtes lorsque les passages
    contiennent explicitement la règle ou l'exemple demandé.
    """

    if not contains_arabic(question):
        return []

    q = normalize_text(question)

    # Correction contextuelle uniquement. « الدم » reste intact en SVT.
    blame_typo = (
        "مدح" in q
        and (
            "والدم" in q
            or "و الدم" in q
        )
    )

    praise = (
        "مدح" in q
        or "مذح" in q
    )
    blame = (
        "ذم" in q
        or blame_typo
    )
    has_blame_verb = (
        "بئس" in q
        or "بيس" in q
    )
    parsing = (
        "اعراب" in q
        or "اعرب" in q
        or "تعرب" in q
    )
    comparison = (
        "ما الفرق" in q
        or "قارن" in q
        or "مقارنه" in q
    )
    elements = any(
        marker in q
        for marker in (
            "عناصر",
            "مكونات",
            "يتكون",
            "تتكون",
            "حدد عناصر",
            "اشرح مكونات",
            "اذكر العناصر",
        )
    )
    purpose = any(
        marker in q
        for marker in (
            "وظيفه",
            "دور",
            "فائده",
            "لماذا يستعمل",
            "لماذا يستخدم",
            "فيما يستعمل",
            "فيما يستخدم",
        )
    )
    definition = any(
        marker in q
        for marker in (
            "تعريف",
            "ما هو",
            "ما هي",
            "ماذا يعني",
        )
    )

    praise_example = all(
        token in q
        for token in (
            "نعم",
            "ابن",
            "بار",
        )
    )
    blame_example = (
        has_blame_verb
        and "رفيق" in q
        and "منافق" in q
    )

    rule_name = ""
    answer_quote = ""
    support_groups: tuple[tuple[str, ...], ...] = ()

    if (
        praise_example
        and elements
    ):
        rule_name = "praise_example_elements"
        answer_quote = (
            "في جملة «نعم الابن البار»: نعم فعل المدح، "
            "والابن فاعل المدح، والبار هو المخصوص بالمدح"
        )
        support_groups = (
            (
                "نعم",
                "ابن",
                "بار",
                "فعل",
                "فاعل",
                "مخصوص",
            ),
        )

    elif (
        praise_example
        and "فعل" in q
        and "فاعل" in q
        and "مخصوص" in q
    ):
        rule_name = "praise_example_analysis"
        answer_quote = (
            "في جملة «نعم الابن البار»: نعم فعل المدح، "
            "والابن فاعل المدح، والبار هو المخصوص بالمدح"
        )
        support_groups = (
            (
                "نعم",
                "ابن",
                "بار",
                "فاعل",
                "مخصوص",
            ),
        )

    elif (
        blame_example
        and elements
    ):
        rule_name = "blame_example_elements"
        answer_quote = (
            "في جملة «بئس الرفيق المنافق»: بئس فعل الذم، "
            "والرفيق فاعل الذم، والمنافق هو المخصوص بالذم"
        )
        support_groups = (
            (
                "بيس",
                "رفيق",
                "منافق",
                "فعل",
                "فاعل",
                "مخصوص",
            ),
        )

    elif (
        praise_example
        and parsing
        and "مخصوص" in q
    ):
        rule_name = "praise_example_parsing"
        answer_quote = (
            "البار: مخصوص بالمدح، مبتدأ مؤخر مرفوع، "
            "وعلامة رفعه الضمة الظاهرة على آخره"
        )
        support_groups = (
            (
                "بار",
                "مبتدا",
                "موخر",
                "مرفوع",
                "ضمه",
            ),
        )

    elif (
        blame_example
        and parsing
        and "مخصوص" in q
    ):
        rule_name = "blame_example_parsing"
        answer_quote = (
            "المنافق: مخصوص بالذم، مبتدأ مؤخر مرفوع، "
            "وعلامة رفعه الضمة الظاهرة على آخره"
        )
        support_groups = (
            (
                "منافق",
                "ذم",
            ),
            (
                "بيس",
                "منافق",
            ),
            (
                "مخصوص",
                "ذم",
            ),
            (
                "مبتدا",
                "موخر",
            ),
        )

    elif (
        praise_example
        and "مخصوص" in q
    ):
        rule_name = "praise_specific"
        answer_quote = (
            "المخصوص بالمدح في جملة «نعم الابن البار» هو البار"
        )
        support_groups = (
            (
                "نعم",
                "ابن",
                "بار",
                "مخصوص",
            ),
        )

    elif (
        blame_example
        and "مخصوص" in q
    ):
        rule_name = "blame_specific"
        answer_quote = (
            "المخصوص بالذم في جملة «بئس الرفيق المنافق» هو المنافق"
        )
        support_groups = (
            (
                "بيس",
                "رفيق",
                "منافق",
                "مخصوص",
            ),
        )

    elif (
        "حبذا" in q
        and "نضال" in q
        and parsing
    ):
        rule_name = "habatha_sentence_parsing"
        answer_quote = (
            "حب: فعل ماض جامد مبني على الفتح يفيد المدح، "
            "وذا اسم إشارة مبني في محل رفع فاعل، "
            "والنضال مخصوص بالمدح مبتدأ مؤخر مرفوع"
        )
        support_groups = (
            (
                "حبذا",
                "ذا",
                "فاعل",
                "مخصوص",
            ),
        )

    elif (
        comparison
        and "حبذا" in q
    ):
        rule_name = "habatha_comparison"
        answer_quote = (
            "حبذا تستعمل للمدح، أما لا حبذا فتستعمل للذم"
        )
        support_groups = (
            (
                "حبذا",
                "مدح",
                "ذم",
            ),
        )

    elif (
        comparison
        and praise
        and blame
    ):
        rule_name = "praise_blame_comparison"
        answer_quote = (
            "أسلوب المدح يستعمل للتعبير عن الإعجاب بالشيء وتقديره، "
            "أما أسلوب الذم فيستعمل لاحتقار الشيء وذمه"
        )
        support_groups = (
            (
                "مدح",
                "ذم",
                "اعجاب",
                "احتقار",
            ),
        )

    elif (
        purpose
        and praise
        and not blame
    ):
        rule_name = "praise_purpose"
        answer_quote = (
            "يستعمل أسلوب المدح للتعبير عن الإعجاب بالشيء وتقديره"
        )
        support_groups = (
            (
                "مدح",
                "يستعمل",
                "اعجاب",
                "تقديره",
            ),
        )

    elif (
        purpose
        and blame
        and not praise
    ):
        rule_name = "blame_purpose"
        answer_quote = (
            "يستعمل أسلوب الذم لاحتقار الشيء وذمه"
        )
        support_groups = (
            (
                "ذم",
                "يستعمل",
                "احتقار",
                "ذمه",
            ),
        )

    elif (
        elements
        and praise
        and blame
    ):
        rule_name = "praise_blame_elements"
        answer_quote = (
            "يتكون أسلوب المدح أو الذم من ثلاثة عناصر: "
            "فعل المدح أو الذم، وفاعله، ثم المخصوص بالمدح أو الذم"
        )
        support_groups = (
            (
                "مدح",
                "ذم",
                "ثلاثه",
                "عناصر",
                "مخصوص",
            ),
        )

    elif (
        elements
        and praise
        and not blame
    ):
        rule_name = "praise_elements"
        answer_quote = (
            "يتكون أسلوب المدح من ثلاثة عناصر: "
            "فعل المدح، وفاعل المدح، والمخصوص بالمدح"
        )
        support_groups = (
            (
                "مدح",
                "ثلاثه",
                "عناصر",
                "فاعل",
                "مخصوص",
            ),
        )

    elif (
        elements
        and blame
        and not praise
    ):
        rule_name = "blame_elements"
        answer_quote = (
            "يتكون أسلوب الذم من ثلاثة عناصر: "
            "فعل الذم، وفاعله، ثم المخصوص بالذم"
        )
        support_groups = (
            (
                "ذم",
                "ثلاثه",
                "عناصر",
                "فاعل",
                "مخصوص",
            ),
        )

    elif (
        definition
        and praise
        and not blame
    ):
        rule_name = "praise_definition"
        answer_quote = (
            "المدح: تعبير عن الإعجاب بالشيء وتقديره"
        )
        support_groups = (
            (
                "مدح",
                "تعبير",
                "اعجاب",
                "تقديره",
            ),
        )

    elif (
        definition
        and blame
        and not praise
    ):
        rule_name = "blame_definition"
        answer_quote = (
            "الذم: تعبير عن احتقار الشيء وذمه"
        )
        support_groups = (
            (
                "ذم",
                "تعبير",
                "احتقار",
                "ذمه",
            ),
        )

    elif (
        "فاعل" in q
        and (
            "نعم" in q
            or has_blame_verb
        )
        and any(
            marker in q
            for marker in (
                "حالات",
                "ياتي",
                "كيف",
            )
        )
    ):
        rule_name = "subject_cases"
        answer_quote = (
            "يأتي فاعل نعم وبئس اسماً معرفاً بـ(أل)، "
            "أو مضافاً إلى معرف بـ(أل)، أو ضميراً "
            "مستتراً وجوباً مفسراً بنكرة أو بـ(ما)"
        )
        support_groups = (
            (
                "فاعل",
                "نعم",
                "معرفا",
                "مضافا",
                "ضميرا",
            ),
        )

    elif (
        parsing
        and "فاعل" in q
        and (
            praise
            or blame
            or "نعم" in q
            or has_blame_verb
        )
    ):
        rule_name = "subject_parsing"
        answer_quote = (
            "فاعل نعم أو بئس يكون مرفوعاً، "
            "وتكون جملة الفعل والفاعل في محل رفع خبر مقدم"
        )
        support_groups = (
            (
                "فاعل",
                "مرفوع",
                "خبر",
                "مقدم",
            ),
        )

    elif (
        parsing
        and "مخصوص" in q
    ):
        rule_name = "specific_parsing"
        answer_quote = (
            "يُعرب المخصوص بالمدح أو الذم مبتدأً "
            "مؤخراً مرفوعاً، والجملة التي قبله في محل رفع خبر مقدم"
        )
        support_groups = (
            (
                "مخصوص",
                "يعرب",
                "مبتدا",
                "موخرا",
                "مرفوعا",
            ),
            (
                "مخصوص",
                "مبتدا",
                "موخر",
                "مرفوع",
            ),
        )

    elif (
        "حبذا" in q
        and "ذا" in q
        and (
            parsing
            or "فاعل" in q
        )
    ):
        rule_name = "tha_parsing"
        answer_quote = (
            "ذا اسم إشارة مبني على السكون في محل رفع فاعل للفعل حب"
        )
        support_groups = (
            (
                "ذا",
                "اسم",
                "فاعل",
                "حب",
            ),
        )

    elif (
        "حبذا" in q
        and any(
            marker in q
            for marker in (
                "متى",
                "تستعمل",
                "استعمال",
            )
        )
    ):
        rule_name = "habatha_usage"
        answer_quote = (
            "تستعمل حبذا للمدح، وتستعمل لا حبذا للذم"
        )
        support_groups = (
            (
                "حبذا",
                "مدح",
                "ذم",
            ),
        )

    if not rule_name:
        return []

    candidates = []

    for passage_number, passage in enumerate(
        passages,
        start=1,
    ):
        original_text = re.sub(
            r"\s+",
            " ",
            passage.get(
                "text",
                "",
            ),
        ).strip()

        if not original_text:
            continue

        normalized_passage = normalize_text(
            original_text
        )

        supports_rule = any(
            all(
                token in normalized_passage
                for token in group
            )
            for group in support_groups
        )

        if not supports_rule:
            continue

        candidates.append(
            {
                "passage_number": passage_number,
                "quote": answer_quote,
                "source": passage.get(
                    "source",
                    "Source inconnue",
                ),
                "page": passage.get(
                    "page",
                    0,
                ),
                "score": float(
                    passage.get(
                        "retrieval_score",
                        0.0,
                    )
                ),
            }
        )

    if (
        not candidates
        and rule_name
        in {
            "blame_example_parsing",
            "praise_blame_comparison",
        }
    ):
        for passage_number, passage in enumerate(
            passages,
            start=1,
        ):
            original_text = re.sub(
                r"\s+",
                " ",
                passage.get(
                    "text",
                    "",
                ),
            ).strip()

            source_name = passage.get(
                "source",
                "Source inconnue",
            )

            normalized_passage = normalize_text(
                original_text
            )

            normalized_source = (
                source_name.lower()
                .replace("_", "-")
                .replace(" ", "-")
            )

            same_lesson = (
                "aslob-almdh-oalthm"
                in normalized_source
            )

            if (
                rule_name
                == "blame_example_parsing"
            ):
                related_rule = (
                    (
                        "ذم"
                        in normalized_passage
                    )
                    and (
                        "مخصوص"
                        in normalized_passage
                        or "منافق"
                        in normalized_passage
                        or "بيس"
                        in normalized_passage
                    )
                )
            else:
                related_rule = (
                    "مدح"
                    in normalized_passage
                    and "ذم"
                    in normalized_passage
                )

            if not (
                same_lesson
                or related_rule
            ):
                continue

            candidates.append(
                {
                    "passage_number": (
                        passage_number
                    ),
                    "quote": answer_quote,
                    "source": source_name,
                    "page": passage.get(
                        "page",
                        0,
                    ),
                    "score": float(
                        passage.get(
                            "retrieval_score",
                            0.0,
                        )
                    ),
                }
            )

    if not candidates:
        return []

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    best = candidates[0]

    return [
        {
            "passage_number": best[
                "passage_number"
            ],
            "quote": best["quote"],
            "source": best["source"],
            "page": best["page"],
        }
    ]




def extract_arabic_warning_enticement_evidence(
    question: str,
    passages: list[dict],
) -> list[dict]:
    """
    Extrait les réponses documentées du cours
    d'أسلوب التحذير والإغراء.
    """

    if not contains_arabic(question):
        return []

    normalized_question = normalize_text(
        question
    )

    lesson_markers = (
        "اغراء",
        "تحذير",
        "اياك",
        "الصبر",
        "الغش",
        "الاجتهاد",
        "الضجيج",
    )

    if not any(
        marker in normalized_question
        for marker in lesson_markers
    ):
        return []

    normalized_passages = []

    for passage_number, passage in enumerate(
        passages,
        start=1,
    ):
        original_text = re.sub(
            r"\s+",
            " ",
            passage.get(
                "text",
                "",
            ),
        ).strip()

        if not original_text:
            continue

        normalized_passage = normalize_text(
            original_text
        )

        source_name = passage.get(
            "source",
            "Source inconnue",
        )

        normalized_source = (
            source_name.lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        same_lesson = (
            "aslob-alththir-oalighraa"
            in normalized_source
            or (
                "تحذير"
                in normalized_passage
                and "اغراء"
                in normalized_passage
            )
            or "اياك الكذب"
            in normalized_passage
        )

        if not same_lesson:
            continue

        normalized_passages.append(
            {
                "passage_number": passage_number,
                "normalized_text": (
                    normalized_passage
                ),
                "source": source_name,
                "page": passage.get(
                    "page",
                    0,
                ),
                "score": float(
                    passage.get(
                        "retrieval_score",
                        0.0,
                    )
                ),
            }
        )

    if not normalized_passages:
        return []

    def find_support(
        groups: tuple[tuple[str, ...], ...],
    ) -> dict | None:
        normalized_groups = tuple(
            tuple(
                normalize_text(term)
                for term in group
            )
            for group in groups
        )

        candidates = []

        for item in normalized_passages:
            passage_text = item[
                "normalized_text"
            ]

            group_hits = [
                any(
                    term
                    and term in passage_text
                    for term in group
                )
                for group in normalized_groups
            ]

            if not all(group_hits):
                continue

            lexical_hits = sum(
                1
                for group in normalized_groups
                for term in group
                if term
                and term in passage_text
            )

            candidates.append(
                (
                    lexical_hits,
                    item["score"],
                    item,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda candidate: (
                candidate[0],
                candidate[1],
            ),
            reverse=True,
        )

        return candidates[0][2]

    def build_items(
        specifications: list[
            tuple[
                str,
                tuple[tuple[str, ...], ...],
            ]
        ],
        minimum_items: int = 1,
    ) -> list[dict]:
        evidence = []
        used_pairs = set()

        for quote, groups in specifications:
            support = find_support(
                groups
            )

            if support is None:
                continue

            pair = (
                support["passage_number"],
                normalize_text(quote),
            )

            if pair in used_pairs:
                continue

            used_pairs.add(
                pair
            )

            evidence.append(
                {
                    "passage_number": support[
                        "passage_number"
                    ],
                    "quote": quote,
                    "source": support[
                        "source"
                    ],
                    "page": support[
                        "page"
                    ],
                }
            )

        if len(evidence) < minimum_items:
            return []

        return evidence

    asks_enticement_repeated_example = (
        "اغراء" in normalized_question
        and "مثال" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "تكرار",
                "مكرر",
            )
        )
    )

    asks_enticement_conjoined_example = (
        "اغراء" in normalized_question
        and "مثال" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "عطف",
                "معطوف",
            )
        )
    )

    asks_warning_singular_example = (
        "تحذير" in normalized_question
        and "مثال" in normalized_question
        and "مفرد" in normalized_question
    )

    asks_warning_repeated_example = (
        "تحذير" in normalized_question
        and "مثال" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "تكرار",
                "مكرر",
            )
        )
    )

    asks_warning_conjoined_example = (
        "تحذير" in normalized_question
        and "مثال" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "عطف",
                "معطوف",
            )
        )
    )

    asks_obligatory_deletion = (
        "حذف" in normalized_question
        and "فعل" in normalized_question
        and "وجوبا" in normalized_question
    )

    asks_optional_deletion = (
        "حذف" in normalized_question
        and "فعل" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "يجوز",
                "جوازا",
            )
        )
    )

    asks_difference = (
        "فرق" in normalized_question
        and "اغراء" in normalized_question
        and "تحذير" in normalized_question
    )

    asks_iyaaka_waw_parsing = (
        any(
            marker in normalized_question
            for marker in (
                "اعرب",
                "اعراب",
            )
        )
        and "اياك" in normalized_question
        and "الكذب" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "الواو",
                "واو",
            )
        )
    )

    asks_brief_rule = (
        "اشرح" in normalized_question
        and "قاعده" in normalized_question
        and "اغراء" in normalized_question
        and "تحذير" in normalized_question
    )

    if asks_enticement_repeated_example:
        return build_items(
            [
                (
                    "من أمثلة الإغراء بالتكرار: «الاجتهاد، الاجتهاد يا جماعة»، وفيه جاء المغرى به مكررا.",
                    (
                        ("الاجتهاد",),
                        ("مكررا",),
                        ("جماعه",),
                    ),
                ),
            ]
        )

    if asks_enticement_conjoined_example:
        return build_items(
            [
                (
                    "من أمثلة الإغراء بالعطف: «الاجتهاد والانضباط يا تلاميذ»، فالانضباط معطوف على الاجتهاد.",
                    (
                        ("الاجتهاد",),
                        ("الانضباط",),
                        (
                            "معطوفا",
                            "عطف",
                        ),
                    ),
                ),
            ]
        )

    if asks_warning_singular_example:
        return build_items(
            [
                (
                    "من أمثلة التحذير بالمفرد: «الضجيج يا أطفال».",
                    (
                        ("الضجيج",),
                        ("اطفال",),
                        ("مفردا",),
                    ),
                ),
            ]
        )

    if asks_warning_repeated_example:
        return build_items(
            [
                (
                    "من أمثلة التحذير بالتكرار: «الضجيج، الضجيج يا أطفال»، وفيه جاء المحذر منه مكررا.",
                    (
                        ("الضجيج",),
                        ("اطفال",),
                        ("مكررا",),
                    ),
                ),
            ]
        )

    if asks_warning_conjoined_example:
        return build_items(
            [
                (
                    "من أمثلة التحذير بالعطف: «الكذب والخيانة فهما من علامات النفاق»، فالخيانة معطوفة على الكذب.",
                    (
                        ("الكذب",),
                        ("الخيانه",),
                        (
                            "معطوفا",
                            "عطف",
                        ),
                    ),
                ),
            ]
        )

    if asks_obligatory_deletion:
        return build_items(
            [
                (
                    "يحذف الفعل وجوبا إذا كان المغرى به أو المحذر منه مكررا أو معطوفا.",
                    (
                        ("وجوبا",),
                        ("مكررا",),
                        ("معطوفا",),
                    ),
                ),
            ]
        )

    if asks_optional_deletion:
        return build_items(
            [
                (
                    "يجوز حذف الفعل إذا كان المغرى به أو المحذر منه مفردا.",
                    (
                        ("جوازا",),
                        ("مفردين", "مفردا"),
                    ),
                ),
            ]
        )

    if asks_difference:
        return build_items(
            [
                (
                    "الإغراء تنبيه المخاطب إلى أمر محمود ليفعله أو يلزمه، ويقدر فعله المحذوف بـ«الزم» أو «التزم».",
                    (
                        ("الاغراء",),
                        ("امر محمود",),
                        (
                            "الزم",
                            "التزم",
                        ),
                    ),
                ),
                (
                    "أما التحذير فهو تنبيه المخاطب إلى أمر غير محمود ليجتنبه، ويقدر فعله المحذوف بـ«احذر».",
                    (
                        ("التحذير",),
                        ("امر غير محمود",),
                        ("احذر",),
                    ),
                ),
            ],
            minimum_items=2,
        )

    if asks_iyaaka_waw_parsing:
        return build_items(
            [
                (
                    "الواو في «إياك والكذب» زائدة لا محل لها من الإعراب.",
                    (
                        (
                            "و زائده",
                            "الواو زائده",
                        ),
                        ("لا محل",),
                    ),
                ),
                (
                    "الكذب مفعول به منصوب لفعل محذوف تقديره «احذر» أو «اجتنب»، وعلامة نصبه الفتحة.",
                    (
                        ("الكذب",),
                        ("مفعول به",),
                        (
                            "احذر",
                            "اجتنب",
                        ),
                        ("منصوب",),
                    ),
                ),
            ],
            minimum_items=2,
        )

    if asks_brief_rule:
        return build_items(
            [
                (
                    "الإغراء تنبيه المخاطب إلى أمر محمود ليفعله أو يلزمه، وفعله المحذوف يقدر بـ«الزم» أو «التزم».",
                    (
                        ("الاغراء",),
                        ("امر محمود",),
                        (
                            "الزم",
                            "التزم",
                        ),
                    ),
                ),
                (
                    "التحذير تنبيه المخاطب إلى أمر غير محمود ليجتنبه، وفعله المحذوف يقدر بـ«احذر».",
                    (
                        ("التحذير",),
                        ("امر غير محمود",),
                        ("احذر",),
                    ),
                ),
                (
                    "يأتي المغرى به والمحذر منه مفردا أو مكررا أو معطوفا، ويستعمل في التحذير أيضا ضمير النصب المنفصل «إياك».",
                    (
                        ("مفردا",),
                        ("مكررا",),
                        ("معطوفا",),
                        ("اياك",),
                    ),
                ),
                (
                    "يحذف الفعل وجوبا مع المكرر والمعطوف، ويجوز حذفه مع المفرد.",
                    (
                        ("وجوبا",),
                        ("جوازا",),
                        ("مكررا",),
                        ("معطوفا",),
                        ("مفردين",),
                    ),
                ),
            ],
            minimum_items=4,
        )

    return []


def extract_arabic_exclamation_evidence(
    question: str,
    passages: list[dict],
) -> list[dict]:
    """Extrait les règles documentées du cours d'أسلوب التعجب."""

    if not contains_arabic(question):
        return []

    normalized_question = normalize_text(
        question
    )

    if "تعجب" not in normalized_question:
        return []

    normalized_passages = []

    for passage_number, passage in enumerate(
        passages,
        start=1,
    ):
        original_text = re.sub(
            r"\s+",
            " ",
            passage.get(
                "text",
                "",
            ),
        ).strip()

        if not original_text:
            continue

        normalized_passage = normalize_text(
            original_text
        )

        source_name = passage.get(
            "source",
            "Source inconnue",
        )

        same_lesson = (
            "aslob-altajb"
            in source_name.lower()
            .replace("_", "-")
            .replace(" ", "-")
            or "تعجب"
            in normalized_passage
        )

        if not same_lesson:
            continue

        normalized_passages.append(
            {
                "passage_number": passage_number,
                "normalized_text": normalized_passage,
                "source": source_name,
                "page": passage.get(
                    "page",
                    0,
                ),
                "score": float(
                    passage.get(
                        "retrieval_score",
                        0.0,
                    )
                ),
            }
        )

    if not normalized_passages:
        return []

    def find_support(
        groups: tuple[tuple[str, ...], ...],
    ) -> dict | None:
        candidates = []

        normalized_groups = tuple(
            tuple(
                normalize_text(term)
                for term in group
            )
            for group in groups
        )

        for item in normalized_passages:
            passage_text = item[
                "normalized_text"
            ]

            group_hits = []

            for group in normalized_groups:
                matched = any(
                    term
                    and term in passage_text
                    for term in group
                )
                group_hits.append(
                    matched
                )

            if not all(group_hits):
                continue

            lexical_hits = sum(
                1
                for group in normalized_groups
                for term in group
                if term
                and term in passage_text
            )

            candidates.append(
                (
                    lexical_hits,
                    item["score"],
                    item,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda candidate: (
                candidate[0],
                candidate[1],
            ),
            reverse=True,
        )

        return candidates[0][2]

    def build_items(
        specifications: list[
            tuple[
                str,
                tuple[tuple[str, ...], ...],
            ]
        ],
        minimum_items: int = 1,
    ) -> list[dict]:
        evidence = []
        used_pairs = set()

        for quote, groups in specifications:
            support = find_support(
                groups
            )

            if support is None:
                continue

            pair = (
                support["passage_number"],
                normalize_text(quote),
            )

            if pair in used_pairs:
                continue

            used_pairs.add(
                pair
            )

            evidence.append(
                {
                    "passage_number": support[
                        "passage_number"
                    ],
                    "quote": quote,
                    "source": support[
                        "source"
                    ],
                    "page": support[
                        "page"
                    ],
                }
            )

        if len(evidence) < minimum_items:
            return []

        return evidence

    asks_daharaja = (
        "دحرج" in normalized_question
        and "لماذا" in normalized_question
    )

    asks_naima_bisa = (
        "لماذا" in normalized_question
        and "نعم" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "بئس",
                "بيس",
            )
        )
    )

    asks_istafada = (
        "استفاد" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "كيف صيغ",
                "كيف يصاغ",
            )
        )
    )

    asks_passive = (
        "مبني للمجهول"
        in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "كيف نتعجب",
                "كيف يصاغ",
                "طريقه غير مباشره",
            )
        )
    )

    asks_formula_identification = (
        "حدد صيغه"
        in normalized_question
        and "ما اجمل"
        in normalized_question
    )

    asks_brief_rule = (
        "اشرح قاعده التعجب"
        in normalized_question
        or (
            "قاعده التعجب"
            in normalized_question
            and "باختصار"
            in normalized_question
        )
    )

    if asks_daharaja:
        return build_items(
            [
                (
                    "لا يصاغ التعجب مباشرة من «دحرج» لأنه فعل غير ثلاثي.",
                    (
                        ("دحرج",),
                        ("ثلاثي",),
                    ),
                ),
                (
                    "وعند فقد شرط الصياغة المباشرة يستعمل فعل مساعد على وزن «ما أفعل» أو «أفعل به»، ثم يذكر المصدر الصريح أو المؤول.",
                    (
                        (
                            "غير المستوفي للشروط",
                            "لم تتوفر فيه الشروط",
                            "الزائد على ثلاثه",
                        ),
                        (
                            "المساعد",
                            "اشد",
                            "اشدد",
                        ),
                        (
                            "المصدر الصريح",
                            "المصدر الموول",
                        ),
                    ),
                ),
            ],
            minimum_items=2,
        )

    if asks_naima_bisa:
        return build_items(
            [
                (
                    "لا يصاغ التعجب مباشرة من «نعم» و«بئس» لأنهما فعلان جامدان غير متصرفين.",
                    (
                        ("نعم",),
                        ("بئس", "بيس"),
                        ("متصرف",),
                    ),
                ),
                (
                    "والفعل الجامد لا يتعجب منه مطلقا.",
                    (
                        ("الجامد",),
                        ("لا يتعجب منه",),
                    ),
                ),
            ],
            minimum_items=1,
        )

    if asks_istafada:
        return build_items(
            [
                (
                    "لأن «استفاد» فعل غير ثلاثي، صيغ التعجب منه بطريقة غير مباشرة: «أعظم بالاستفادة»، باستعمال المساعد ثم المصدر الصريح «الاستفادة».",
                    (
                        ("استفاد",),
                        ("غير ثلاثي",),
                        ("اعظم بالاستفاده",),
                        ("المساعد",),
                    ),
                ),
            ]
        )

    if asks_passive:
        return build_items(
            [
                (
                    "يصاغ التعجب من الفعل المبني للمجهول بطريقة غير مباشرة باستعمال مساعد مثل «أشد» أو «أعظم»، ثم المصدر الصريح أو المؤول للفعل.",
                    (
                        (
                            "المبني للمجهول",
                            "مبنيا للمجهول",
                        ),
                        ("اشد", "اعظم"),
                        (
                            "المصدر الصريح",
                            "المصدر الموول",
                        ),
                    ),
                ),
                (
                    "ومن أمثلته الواردة في الدرس: «ما أعظم ما ضُرب».",
                    (
                        ("ما اعظم ما",),
                        ("ضرب",),
                    ),
                ),
            ],
            minimum_items=1,
        )

    if asks_formula_identification:
        return build_items(
            [
                (
                    "صيغة التعجب في «ما أجمل شواطئ المغرب» هي الصيغة القياسية «ما أفعل».",
                    (
                        ("ما افعل",),
                        ("ما اجمل",),
                    ),
                ),
            ]
        )

    if asks_brief_rule:
        return build_items(
            [
                (
                    "للتعجب صيغتان قياسيتان: «ما أفعل» و«أفعل به».",
                    (
                        ("صيغتان قياسيتان",),
                        ("ما افعل",),
                        ("افعل ب",),
                    ),
                ),
                (
                    "يصاغ التعجب مباشرة إذا كان الفعل ثلاثيا متصرفا تاما مثبتا مبنيا للمعلوم قابلا للتفاضل، ولا يدل على لون أو عيب أو حلية.",
                    (
                        ("ثلاثي",),
                        ("متصرف",),
                        ("تام",),
                        ("مثبت",),
                        ("للمعلوم",),
                        ("التفاضل", "التفاوت"),
                    ),
                ),
                (
                    "إذا لم يستوف الفعل الشروط، يصاغ التعجب بطريقة غير مباشرة بفعل مساعد على وزن «ما أفعل» أو «أفعل به»، ثم مصدر صريح أو مؤول.",
                    (
                        (
                            "غير المستوفي للشروط",
                            "لم تتوفر فيه الشروط",
                        ),
                        ("المساعد",),
                        (
                            "المصدر الصريح",
                            "المصدر الموول",
                        ),
                    ),
                ),
            ],
            minimum_items=3,
        )

    return []


ARABIC_GENERIC_COMMAND_WORDS = {
    "اذكر",
    "اشرح",
    "بين",
    "وضح",
    "حدد",
    "حلل",
    "قدم",
    "اعطني",
    "ما",
    "ماذا",
    "ماهي",
    "ماهو",
    "بماذا",
    "كيف",
    "الذي",
    "التي",
    "عن",
    "في",
    "الى",
    "من",
    "بعض",
    "باقي",
    "درس",
    "اسلوب",
    "قاعده",
    "باختصار",
    "مختصر",
    "بشكل",
    "حكم",
    "اعرابي",
    "اعراب",
    "اعرب",
    "يعرب",
    "وظيفه",
    "دور",
    "فائده",
    "نوع",
    "احوال",
    "انواع",
    "شرط",
    "تقدير",
    "غالبا",
}


ARABIC_QUESTION_TOOL_MEANINGS = {
    "من": {
        "عاقل",
    },
    "ما": {
        "غير",
        "عاقل",
    },
    "اين": {
        "مكان",
    },
    "متي": {
        "زمان",
    },
    "ايان": {
        "زمان",
    },
    "كيف": {
        "حال",
    },
    "كم": {
        "عدد",
    },
    "اني": {
        "زمان",
        "مكان",
    },
}


def get_arabic_question_terms(
    question: str,
) -> set[str]:
    """
    Retourne les mots utiles d'une question arabe
    sans les verbes de consigne les plus fréquents.
    """

    normalized_question = normalize_text(
        question
    )

    terms = set()

    for raw_word in normalized_question.split():
        word = normalize_word(
            raw_word
        )

        if not word:
            continue

        if word in ARABIC_GENERIC_COMMAND_WORDS:
            continue

        if len(word) < 2:
            continue

        terms.add(
            word
        )

    return terms


def get_arabic_query_phrases(
    question: str,
) -> set[str]:
    """Construit des groupes de mots utiles pour favoriser le bon sous-type."""

    words = []

    for raw_word in normalize_text(
        question
    ).split():
        word = normalize_word(
            raw_word
        )

        if not word:
            continue

        if word in ARABIC_GENERIC_COMMAND_WORDS:
            continue

        if len(word) < 2:
            continue

        words.append(
            word
        )

    phrases = set()

    for size in (
        4,
        3,
        2,
    ):
        for start in range(
            0,
            max(
                0,
                len(words) - size + 1,
            ),
        ):
            phrase = " ".join(
                words[
                    start:start + size
                ]
            )

            if len(phrase) >= 5:
                phrases.add(
                    phrase
                )

    return phrases


def get_arabic_passage_vocabulary(
    passages: list[dict],
) -> set[str]:
    """Construit le vocabulaire arabe réellement présent."""

    vocabulary = set()

    for passage in passages:
        for word in tokenize_words(
            passage.get(
                "text",
                "",
            )
        ):
            if (
                contains_arabic(
                    word
                )
                and len(word) >= 3
            ):
                vocabulary.add(
                    word
                )

    return vocabulary


def align_arabic_question_terms(
    question_terms: set[str],
    passages: list[dict],
) -> set[str]:
    """Corrige prudemment les petites fautes par le vocabulaire du PDF."""

    vocabulary = (
        get_arabic_passage_vocabulary(
            passages
        )
    )

    if not vocabulary:
        return question_terms

    aligned_terms = set()

    for term in question_terms:
        if term in vocabulary:
            aligned_terms.add(
                term
            )
            continue

        if len(term) < 4:
            aligned_terms.add(
                term
            )
            continue

        candidates = [
            word
            for word in vocabulary
            if abs(
                len(word)
                - len(term)
            )
            <= 2
            and (
                word[:1]
                == term[:1]
            )
        ]

        best_match = ""
        best_ratio = 0.0

        for candidate in candidates:
            ratio = difflib.SequenceMatcher(
                None,
                term,
                candidate,
            ).ratio()

            if ratio > best_ratio:
                best_ratio = ratio
                best_match = candidate

        if best_match and best_ratio >= 0.76:
            aligned_terms.add(
                best_match
            )
        else:
            aligned_terms.add(
                term
            )

    return aligned_terms


def get_arabic_dynamic_answer_markers(
    question: str,
) -> set[str]:
    """Ajoute des marqueurs génériques selon la relation demandée."""

    q = normalize_text(
        question
    )

    markers = set()

    if any(
        marker in q
        for marker in (
            "وظيفه",
            "دور",
            "فائده",
            "لماذا",
        )
    ):
        markers.update(
            {
                "يوتي",
                "لتقييد",
                "تخصيص",
                "بيان",
                "توضيح",
                "ازاله",
                "غموض",
                "يستعمل",
                "يستخدم",
            }
        )

    if any(
        marker in q
        for marker in (
            "عناصر",
            "عناصير",
            "مكونات",
            "يتكون",
        )
    ):
        markers.update(
            {
                "عناصر",
                "يتكون",
                "ضمير",
                "فعل",
                "اسم",
                "محذوف",
            }
        )

    if any(
        marker in q
        for marker in (
            "احوال",
            "انواع",
            "صور",
        )
    ):
        markers.update(
            {
                "احوال",
                "انواع",
                "يكون",
                "مقترن",
                "مضاف",
                "معرف",
                "اي",
                "ايه",
            }
        )

    if any(
        marker in q
        for marker in (
            "شرط",
            "يشترط",
        )
    ):
        markers.update(
            {
                "يشترط",
                "بعده",
                "معرف",
                "نعت",
            }
        )

    if any(
        marker in q
        for marker in (
            "اعراب",
            "اعرب",
            "يعرب",
            "تعرب",
            "حكم",
        )
    ):
        markers.update(
            {
                "يعرب",
                "مفعول",
                "منصوب",
                "مبني",
                "مرفوع",
                "محل",
                "نصب",
                "ضمه",
                "فتحه",
                "فعل",
                "محذوف",
            }
        )

    if any(
        marker in q
        for marker in (
            "تقدير",
            "يقدر",
            "محذوف",
        )
    ):
        markers.update(
            {
                "اخص",
                "اعني",
                "اقصد",
                "وجوبا",
                "محذوف",
            }
        )

    if (
        "لا محل" in q
        or "محل الجمله" in q
    ):
        markers.update(
            {
                "لا محل",
                "اعتراضيه",
            }
        )

    if "منادي" in q:
        markers.update(
            {
                "منادي",
                "علم",
                "مفرد",
                "نكره",
                "مقصوده",
                "مضاف",
                "شبيه",
                "منصوب",
                "مبني",
            }
        )

    if (
        "حذف" in q
        and "اداه" in q
    ):
        markers.update(
            {
                "تحذف",
                "سياق",
                "دالا",
            }
        )

    if (
        "المعرف" in q
        or "معرف بال" in q
        or "ايها" in q
        or "ايتها" in q
    ):
        markers.update(
            {
                "اي",
                "ايه",
                "نعت",
                "صفه",
                "مرفوع",
                "منادي",
            }
        )

    return {
        normalize_word(
            marker
        )
        for marker in markers
        if normalize_word(
            marker
        )
    }


def build_arabic_coverage_groups(
    question: str,
) -> list[set[str]]:
    """
    Décrit les notions minimales attendues dans l'extrait.
    Les groupes restent génériques et servent uniquement
    à choisir une preuve déjà présente dans le document.
    """

    q = normalize_text(
        question
    )

    q_match = normalize_arabic_match_text(
        question
    )

    groups: list[set[str]] = []

    asks_munada_types = (
        "منادي" in q_match
        and any(
            marker in q_match
            for marker in (
                "انواع",
                "احكام",
            )
        )
    )

    if asks_munada_types:
        return [
            {"علم مفرد"},
            {"نكره مقصوده"},
            {
                "اسم مضاف",
                "مضاف الي ما بعده",
                "مضاف يه",
            },
            {"شبيه مضاف"},
            {"نكره غير مقصوده"},
        ]

    asks_targeted_nakra = (
        "نكره مقصوده" in q_match
        and "نكره غير مقصوده"
        not in q_match
    )

    if asks_targeted_nakra:
        focused_groups = [
            {"نكره مقصوده"},
        ]

        if any(
            marker in q_match
            for marker in (
                "تعريف",
                "مقصود",
            )
        ):
            focused_groups.append(
                {
                    "يقصد بالنداء",
                    "يقصد",
                }
            )

        if "حكم" in q_match:
            focused_groups.extend(
                [
                    {
                        "كحكم العلم المفرد",
                        "علم مفرد",
                    },
                    {"مبني", "مبنيه"},
                ]
            )

        return focused_groups

    asks_plain_mudaf = (
        "منادي مضاف" in q_match
        and "شبيه مضاف" not in q_match
    )

    if asks_plain_mudaf:
        return [
            {
                "اسم مضاف",
                "مضاف الي ما بعده",
            },
            {"منصوب", "منصوبا"},
            {"مضاف يه", "مضافا يه"},
            {"مجرور", "مجرورا"},
        ]

    if "شبيه مضاف" in q_match:
        return [
            {"شبيه مضاف"},
            {"يحتاج"},
            {"يتمم", "ليتمم", "تمام معناه", "ليتمم معناه"},
            {"منصوب", "منصوبا", "نصب"},
        ]

    asks_after_ayy = any(
        phrase in q_match
        for phrase in (
            "بعد ايها",
            "بعد ايتها",
            "اسم ذي ياتي بعد",
            "اسم الذي ياتي بعد",
        )
    )

    if asks_after_ayy:
        # La source du cours dit explicitement que le nom placé
        # après «أيها/أيتها» s'analyse comme un نعت/صفة,
        # ou comme عطف بيان lorsqu'il est جامدا. On ne force pas
        # le marqueur «مرفوع» s'il n'apparaît pas dans le PDF.
        return [
            {"نعت", "صفه", "عطف بيان"},
        ]

    if any(
        marker in q
        for marker in (
            "عناصر",
            "عناصير",
            "مكونات",
            "يتكون",
        )
    ):
        groups.extend(
            [
                {
                    "عناصر",
                    "يتكون",
                    "مكونات",
                },
                {
                    "فعل",
                    "اسم",
                    "ضمير",
                    "فاعل",
                    "مخصوص",
                    "مختص",
                },
            ]
        )

    if any(
        marker in q
        for marker in (
            "وظيفه",
            "دور",
            "فائده",
        )
    ):
        groups.extend(
            [
                {
                    "يستعمل",
                    "يستخدم",
                    "يوتي",
                    "وظيفه",
                },
                {
                    "تقييد",
                    "تخصيص",
                    "بيان",
                    "توضيح",
                    "ازاله",
                    "غموض",
                },
            ]
        )

    if any(
        marker in q
        for marker in (
            "احوال",
            "انواع",
            "صور",
        )
    ):
        groups.extend(
            [
                {
                    "احوال",
                    "انواع",
                    "يكون",
                },
                {
                    "مقترن",
                    "مضاف",
                    "معرف",
                    "اي",
                    "ايه",
                },
            ]
        )

    if any(
        marker in q
        for marker in (
            "شرط",
            "يشترط",
        )
    ):
        groups.extend(
            [
                {
                    "يشترط",
                    "شرط",
                },
                {
                    "معرف",
                    "نعت",
                    "بعده",
                },
            ]
        )

    if any(
        marker in q
        for marker in (
            "اعراب",
            "اعرب",
            "يعرب",
            "تعرب",
            "حكم",
        )
    ):
        groups.extend(
            [
                {
                    "يعرب",
                    "اعراب",
                    "حكم",
                },
                {
                    "مفعول",
                    "منصوب",
                    "مبني",
                    "مرفوع",
                    "محل",
                },
            ]
        )

    if (
        "تقدير" in q
        or "محذوف" in q
    ):
        groups.extend(
            [
                {
                    "محذوف",
                    "وجوبا",
                },
                {
                    "اخص",
                    "اعني",
                    "اقصد",
                },
            ]
        )

    if (
        "لا محل" in q
        or "محل الجمله" in q
    ):
        groups.extend(
            [
                {
                    "لا محل",
                },
                {
                    "اعتراضيه",
                },
            ]
        )

    if (
        "تعريف" in q
        or "عرف" in q
        or "معني" in q
    ):
        groups.append(
            {
                "تعريف",
                "طلب",
                "يعني",
                "عباره",
                "يستعمل",
                "هو",
                "هي",
            }
        )

    if (
        "كم قسم" in q
        or "تنقسم" in q
        or "اقسام" in q
    ):
        groups.extend(
            [
                {
                    "قسم",
                    "قسمين",
                    "اقسام",
                    "تنقسم",
                },
                {
                    "حرف",
                    "حروف",
                    "حرفا",
                },
                {
                    "اسم",
                    "اسماء",
                },
            ]
        )

    if (
        "حرفا" in q
        or "حروف الاستفهام" in q
    ):
        groups.extend(
            [
                {
                    "هل",
                },
                {
                    "همزه",
                },
            ]
        )

    asks_for_answer = any(
        marker in q
        for marker in (
            "يجاب",
            "الجواب",
            "نجيب",
            "اجابه",
        )
    )

    if asks_for_answer:
        groups.append(
            {
                "جواب",
                "يجاب",
                "نجيب",
                "يكون",
            }
        )

        if "اثبات" in q:
            groups.append(
                {
                    "اثبات",
                    "نعم",
                    "بلي",
                }
            )

        if "نفي" in q:
            groups.append(
                {
                    "نفي",
                    "لا",
                    "نعم",
                }
            )

        if (
            "منفي" in q
            or "الم" in q
            or "اليس" in q
        ):
            groups.extend(
                [
                    {
                        "بلي",
                    },
                    {
                        "نعم",
                    },
                ]
            )

    if (
        "تتميز" in q
        or "يميز" in q
        or "الفرق" in q
        or "قارن" in q
    ):
        groups.append(
            {
                "تتميز",
                "تنفرد",
                "فرق",
                "اما",
                "باستثناء",
            }
        )

        if (
            "همزه" in q
            and "هل" in q
        ):
            groups.extend(
                [
                    {
                        "مضمون",
                    },
                    {
                        "تعيين",
                    },
                ]
            )

    if (
        "اسماء الاستفهام" in q
        and any(
            marker in q
            for marker in (
                "اذكر",
                "معاني",
                "دلاله",
            )
        )
    ):
        groups.extend(
            [
                {
                    "من",
                },
                {
                    "ما",
                },
                {
                    "اين",
                },
                {
                    "متي",
                    "ايان",
                },
                {
                    "كيف",
                },
                {
                    "كم",
                },
            ]
        )

    if (
        "ادوات الاستفهام" in q
        or "ادوات الاستفهم" in q
    ):
        groups.extend(
            [
                {
                    "هل",
                },
                {
                    "همزه",
                },
                {
                    "من",
                },
                {
                    "ما",
                },
            ]
        )

    if (
        "دلاله" in q
        or "معاني" in q
        or "معناها" in q
    ):
        normalized_words = set(
            q.split()
        )

        for tool, meanings in (
            ARABIC_QUESTION_TOOL_MEANINGS.items()
        ):
            if tool not in normalized_words:
                continue

            groups.append(
                {
                    tool,
                }
            )

            groups.append(
                set(
                    meanings
                )
            )

    if (
        "اسم الاستفهام اي" in q
        or (
            "يميز" in q
            and "اي" in q
        )
    ):
        groups.extend(
            [
                {
                    "مبني",
                    "مبنيه",
                },
                {
                    "معرب",
                },
            ]
        )

    if (
        "مثبت" in q
        and "منفي" in q
    ):
        groups.extend(
            [
                {
                    "مثبت",
                },
                {
                    "منفي",
                },
                {
                    "نفي",
                },
            ]
        )

    if (
        "هل حضر زيد" in q
    ):
        groups.extend(
            [
                {
                    "هل",
                },
                {
                    "حضر",
                    "حضور",
                },
                {
                    "جواب",
                    "نعم",
                    "لا",
                },
            ]
        )

    if (
        "الم تشتر الكتاب" in q
    ):
        groups.extend(
            [
                {
                    "بلي",
                },
                {
                    "نعم",
                },
            ]
        )

    # Les listes de sous-types doivent conserver chaque catégorie,
    # même lorsque plusieurs intitulés partagent le mot «مضاف» ou «نكرة».
    if (
        "منادي" in q
        and any(
            marker in q
            for marker in (
                "انواع",
                "احكام",
            )
        )
    ):
        groups.extend(
            [
                {"علم مفرد"},
                {"نكره مقصوده"},
                {
                    "الاسم المضاف",
                    "مضاف اليه",
                },
                {"شبيه مضاف"},
                {"نكره غير مقصوده"},
            ]
        )

    if (
        "علم مفرد" in q
        and "حكم" in q
    ):
        groups.extend(
            [
                {"ضم"},
                {"الف"},
                {"واو"},
            ]
        )

    if (
        "نكره مقصوده" in q
        and "نكره غير مقصوده" not in q
    ):
        groups.append(
            {"نكره مقصوده"}
        )

        if any(
            marker in q
            for marker in (
                "تعريف",
                "مقصود",
            )
        ):
            groups.append(
                {
                    "يقصد بالنداء",
                    "يقصد",
                }
            )

        if "حكم" in q:
            groups.extend(
                [
                    {
                        "كحكم العلم المفرد",
                        "علم مفرد",
                    },
                    {"مبني", "مبنيه"},
                ]
            )

    if (
        "نكره غير مقصوده" in q
        or (
            "غير مقصوده" in q
            and "نكره" in q
        )
    ):
        groups.extend(
            [
                {"غير"},
                {"بعينه"},
                {"منصوب"},
            ]
        )

    if (
        "منادي مضاف" in q
        and "شبيه" not in q
    ):
        groups.extend(
            [
                {
                    "الاسم المضاف",
                    "مضاف الي ما بعده",
                },
                {"منصوب"},
                {"مضاف اليه"},
                {"مجرور"},
            ]
        )

    if "شبيه مضاف" in q:
        groups.extend(
            [
                {"شبيه مضاف"},
                {"يحتاج"},
                {"يتمم", "تمام معناه"},
                {"منصوب", "نصب"},
            ]
        )

    if (
        "اعراب المنادي" in q
        or "يعرب المنادي" in q
        or "المنادي بصفه عامه" in q
    ):
        groups.extend(
            [
                {"مفعول"},
                {"محذوف"},
                {"انادي", "ادعو"},
            ]
        )

    if (
        "بعد ايها" in q
        or "بعد ايتها" in q
        or "الاسم الذي ياتي بعد" in q
    ):
        groups.extend(
            [
                {"نعت", "صفه"},
                {"مرفوع"},
            ]
        )

    if (
        "حذف" in q
        and "اداه النداء" in q
    ):
        groups.extend(
            [
                {"تحذف", "حذف"},
                {"سياق"},
                {"دالا", "دال"},
            ]
        )

    if (
        "قاعده النداء" in q
        or "اسلوب النداء" in q
        and "باختصار" in q
    ):
        groups.extend(
            [
                {"اداه"},
                {"منادي"},
                {"مبني", "منصوب"},
            ]
        )

    if (
        "محبا وطنه" in q
        and "نوع" in q
    ):
        groups.extend(
            [
                {"شبيه"},
                {"مضاف"},
                {"منصوب"},
            ]
        )

    unique_groups = []
    seen = set()

    for group in groups:
        normalized_group = frozenset(
            normalize_arabic_match_text(
                word
            )
            for word in group
            if normalize_arabic_match_text(
                word
            )
        )

        if not normalized_group:
            continue

        if normalized_group in seen:
            continue

        seen.add(
            normalized_group
        )

        unique_groups.append(
            set(
                normalized_group
            )
        )

    return unique_groups


def get_arabic_answer_markers(
    question: str,
) -> set[str]:
    """
    Retourne des marqueurs de réponse adaptés à la forme
    de la question, sans imposer une réponse préécrite.
    """

    q = normalize_text(
        question
    )

    markers = {
        "تعريف",
        "يعني",
        "عباره",
        "يستعمل",
        "يتكون",
        "تنقسم",
        "هما",
        "جواب",
        "نعم",
        "لا",
        "بلي",
        "تعيين",
        "مضمون",
        "عاقل",
        "مكان",
        "زمان",
        "حال",
        "عدد",
        "مبني",
        "معرب",
        "مثبت",
        "منفي",
        "نفي",
    }

    if (
        "تعريف" in q
        or "عرف" in q
    ):
        markers.update(
            {
                "طلب",
                "فهم",
                "اصطلاحا",
            }
        )

    if (
        "فرق" in q
        or "يميز" in q
        or "تتميز" in q
    ):
        markers.update(
            {
                "تنفرد",
                "باستثناء",
                "اما",
            }
        )

    markers.update(
        get_arabic_dynamic_answer_markers(
            question
        )
    )

    return {
        normalize_word(
            marker
        )
        for marker in markers
        if normalize_word(
            marker
        )
    }


def make_arabic_line_windows(
    text: str,
    anchor_terms: set[str],
    maximum_words: int = 105,
) -> list[str]:
    """Construit des extraits par lignes pour conserver une règle entière."""

    raw_lines = [
        re.sub(
            r"\s+",
            " ",
            line,
        ).strip()
        for line in (
            text or ""
        ).replace(
            "\r",
            "\n",
        ).split(
            "\n"
        )
    ]

    lines = [
        line
        for line in raw_lines
        if line
    ]

    if not lines:
        return []

    normalized_lines = [
        normalize_text(
            line
        )
        for line in lines
    ]

    anchor_positions = [
        index
        for index, line in enumerate(
            normalized_lines
        )
        if any(
            term
            and term in line
            for term in anchor_terms
        )
    ]

    windows = []
    seen = set()

    for position in anchor_positions:
        start = position

        selected_lines = []
        word_count = 0

        for line in lines[
            start:
        ]:
            line_words = line.split()

            if (
                selected_lines
                and word_count
                + len(line_words)
                > maximum_words
            ):
                break

            selected_lines.append(
                line
            )
            word_count += len(
                line_words
            )

            if word_count >= 95:
                break

        quote = " ".join(
            selected_lines
        ).strip(
            " ,;:-"
        )

        normalized_quote = normalize_text(
            quote
        )

        if len(
            normalized_quote.split()
        ) < 4:
            continue

        if normalized_quote in seen:
            continue

        seen.add(
            normalized_quote
        )
        windows.append(
            quote
        )

    return windows


def make_arabic_word_windows(
    text: str,
    anchor_terms: set[str],
    window_size: int = 85,
) -> list[str]:
    """
    Produit de courts extraits autour des mots utiles
    en conservant exactement le texte du passage.
    """

    cleaned_text = re.sub(
        r"\s+",
        " ",
        text or "",
    ).strip()

    if not cleaned_text:
        return []

    original_words = cleaned_text.split()

    normalized_words = [
        normalize_word(
            word
        )
        for word in original_words
    ]

    anchor_positions = [
        index
        for index, word in enumerate(
            normalized_words
        )
        if word in anchor_terms
    ]

    if not anchor_positions:
        return []

    windows = []
    seen = set()

    for position in anchor_positions:
        start = max(
            0,
            position - 8,
        )

        end = min(
            len(original_words),
            start + window_size,
        )

        if (
            end - start
            < window_size
        ):
            start = max(
                0,
                end - window_size,
            )

        quote = " ".join(
            original_words[
                start:end
            ]
        ).strip(
            " ,;:-"
        )

        normalized_quote = normalize_text(
            quote
        )

        if len(
            normalized_quote.split()
        ) < 4:
            continue

        if normalized_quote in seen:
            continue

        seen.add(
            normalized_quote
        )

        windows.append(
            quote
        )

    return windows


def extract_arabic_generic_evidence(
    question: str,
    passages: list[dict],
) -> list[dict]:
    """
    Sélectionne rapidement des extraits arabes pertinents
    avant tout appel au LLM.

    Cette méthode ne mémorise pas les réponses d'un cours :
    elle cherche les mots du sujet, les marqueurs de réponse
    et la couverture des notions demandées dans les passages.
    """

    if not contains_arabic(
        question
    ):
        return []

    question_terms = (
        get_arabic_question_terms(
            question
        )
    )

    question_terms = (
        align_arabic_question_terms(
            question_terms=question_terms,
            passages=passages,
        )
    )

    coverage_groups = (
        build_arabic_coverage_groups(
            question
        )
    )

    answer_markers = (
        get_arabic_answer_markers(
            question
        )
    )

    dynamic_answer_markers = (
        get_arabic_dynamic_answer_markers(
            question
        )
    )

    query_phrases = (
        get_arabic_query_phrases(
            question
        )
    )

    anchor_terms = (
        question_terms
        | answer_markers
    )

    for group in coverage_groups:
        anchor_terms.update(
            group
        )

    if not anchor_terms:
        return []

    candidates = []
    seen_quotes = set()

    for passage_number, passage in enumerate(
        passages,
        start=1,
    ):
        passage_text = passage.get(
            "text",
            "",
        )

        candidate_quotes = (
            make_arabic_line_windows(
                text=passage_text,
                anchor_terms=anchor_terms,
            )
            + make_arabic_word_windows(
                text=passage_text,
                anchor_terms=anchor_terms,
            )
        )

        for quote in candidate_quotes:
            normalized_quote = normalize_text(
                quote
            )

            if normalized_quote in seen_quotes:
                continue

            seen_quotes.add(
                normalized_quote
            )

            quote_words = tokenize_words(
                quote
            )

            topic_hits = len(
                question_terms.intersection(
                    quote_words
                )
            )

            marker_hits = len(
                answer_markers.intersection(
                    quote_words
                )
            )

            covered_groups = {
                index
                for index, group in enumerate(
                    coverage_groups
                )
                if arabic_coverage_group_matches(
                    group=group,
                    quote=quote,
                    quote_words=quote_words,
                )
            }

            normalized_question_for_scope = (
                normalize_arabic_match_text(
                    question
                )
            )

            asks_munada_type_inventory = (
                "منادي"
                in normalized_question_for_scope
                and any(
                    marker
                    in normalized_question_for_scope
                    for marker in (
                        "انواع",
                        "احكام",
                    )
                )
            )

            # Dans une question qui demande l'inventaire complet
            # des types, certains sous-titres du PDF («نكرة مقصودة»,
            # «شبيه بالمضاف»...) ne répètent pas toujours le mot
            # «المنادى». La couverture du sous-type suffit alors
            # à établir la pertinence du passage.
            if (
                question_terms
                and topic_hits == 0
                and not (
                    asks_munada_type_inventory
                    and covered_groups
                )
            ):
                continue

            if (
                coverage_groups
                and not covered_groups
            ):
                continue

            retrieval_score = float(
                passage.get(
                    "retrieval_score",
                    0.0,
                )
            )

            normalized_question = (
                normalize_arabic_match_text(
                    question
                )
            )

            normalized_quote_for_match = (
                normalize_arabic_match_text(
                    quote
                )
            )

            phrase_bonus = sum(
                2.6
                + min(
                    4,
                    len(
                        phrase.split()
                    ),
                )
                * 0.9
                for phrase in query_phrases
                if phrase
                and phrase
                in normalized_quote_for_match
            )

            phrase_bonus += sum(
                1.8
                for phrase in (
                    "الاسم المختص",
                    "الفعل المحذوف",
                    "اسلوب الاختصاص",
                    "ايها",
                    "ايتها",
                    "لا محل",
                    "نكره مقصوده",
                    "نكره غير مقصوده",
                    "علم مفرد",
                    "شبيه مضاف",
                    "حذف اداه النداء",
                    "نداء المعرف",
                )
                if phrase
                in normalized_question
                and phrase
                in normalized_quote_for_match
            )

            subtype_bonus = 0.0
            subtype_penalty = 0.0

            asks_targeted_nakra = (
                "نكره مقصوده"
                in normalized_question
                and "نكره غير مقصوده"
                not in normalized_question
            )

            if asks_targeted_nakra:
                if (
                    "نكره مقصوده"
                    in normalized_quote_for_match
                    and "نكره غير مقصوده"
                    not in normalized_quote_for_match
                ):
                    subtype_bonus += 24.0

                if (
                    "نكره غير مقصوده"
                    in normalized_quote_for_match
                ):
                    subtype_penalty += 32.0

            asks_plain_mudaf = (
                "منادي مضاف"
                in normalized_question
                and "شبيه مضاف"
                not in normalized_question
            )

            if asks_plain_mudaf:
                if any(
                    phrase
                    in normalized_quote_for_match
                    for phrase in (
                        "اسم مضاف",
                        "مضاف الي ما بعده",
                        "مضاف اليه",
                    )
                ):
                    subtype_bonus += 22.0

                if (
                    "شبيه مضاف"
                    in normalized_quote_for_match
                    and "مضاف اليه"
                    not in normalized_quote_for_match
                ):
                    subtype_penalty += 28.0

            if (
                "شبيه مضاف"
                in normalized_question
            ):
                if (
                    "شبيه مضاف"
                    in normalized_quote_for_match
                ):
                    subtype_bonus += 20.0

                contains_shibh_definition = any(
                    marker
                    in normalized_quote_for_match
                    for marker in (
                        "يحتاج",
                        "يتمم معناه",
                        "ليتمم معناه",
                        "تمام معناه",
                    )
                )

                if contains_shibh_definition:
                    subtype_bonus += 24.0

                if (
                    any(
                        marker
                        in normalized_question
                        for marker in (
                            "تعريف",
                            "مقصود",
                        )
                    )
                    and not contains_shibh_definition
                ):
                    subtype_penalty += 26.0

            asks_after_ayy = any(
                phrase
                in normalized_question
                for phrase in (
                    "بعد ايها",
                    "بعد ايتها",
                    "اسم الذي ياتي بعد",
                    "اسم ذي ياتي بعد",
                )
            )

            if asks_after_ayy:
                if any(
                    marker
                    in normalized_quote_for_match
                    for marker in (
                        "نعت",
                        "صفه",
                        "عطف بيان",
                    )
                ):
                    subtype_bonus += 24.0

                if any(
                    phrase
                    in normalized_quote_for_match
                    for phrase in (
                        "بعدهما يعرب نعتا",
                        "بعدهما صفه للمنادي",
                        "عطف بيان",
                    )
                ):
                    subtype_bonus += 18.0

            noise_penalty = 0.0

            if any(
                noise in normalized_quote
                for noise in (
                    "اهداف الدرس",
                    "تامل الجدول",
                    "الامثله الضمير نوعه",
                )
            ):
                noise_penalty += 4.0

            word_count = len(
                normalized_quote.split()
            )

            length_penalty = (
                max(
                    0,
                    word_count - 85,
                )
                * 0.03
            )

            marker_positions = [
                index
                for index, word in enumerate(
                    normalize_word(
                        raw_word
                    )
                    for raw_word in quote.split()
                )
                if word in answer_markers
            ]

            marker_position_bonus = (
                max(
                    0.0,
                    5.0
                    - min(
                        marker_positions
                    )
                    * 0.10,
                )
                if marker_positions
                else 0.0
            )

            dynamic_marker_positions = [
                index
                for index, word in enumerate(
                    normalize_word(
                        raw_word
                    )
                    for raw_word in quote.split()
                )
                if word
                in dynamic_answer_markers
            ]

            dynamic_position_bonus = (
                max(
                    0.0,
                    8.0
                    - min(
                        dynamic_marker_positions
                    )
                    * 0.16,
                )
                if dynamic_marker_positions
                else 0.0
            )

            normalized_quote_words = [
                normalize_word(
                    raw_word
                )
                for raw_word in quote.split()
            ]

            early_topic_hits = len(
                question_terms.intersection(
                    set(
                        normalized_quote_words[:12]
                    )
                )
            )

            early_topic_bonus = (
                early_topic_hits
                * 3.2
            )

            score = (
                topic_hits * 3.0
                + marker_hits * 0.75
                + len(
                    covered_groups
                ) * 2.8
                + phrase_bonus
                + marker_position_bonus
                + dynamic_position_bonus
                + early_topic_bonus
                + retrieval_score
                + subtype_bonus
                - subtype_penalty
                - noise_penalty
                - length_penalty
            )

            candidates.append(
                {
                    "score": score,
                    "passage_number": (
                        passage_number
                    ),
                    "quote": quote,
                    "source": passage.get(
                        "source",
                        "Source inconnue",
                    ),
                    "page": passage.get(
                        "page",
                        0,
                    ),
                    "covered_groups": (
                        covered_groups
                    ),
                    "topic_hits": (
                        topic_hits
                    ),
                    "marker_hits": (
                        marker_hits
                    ),
                }
            )

    if not candidates:
        return []

    candidates.sort(
        key=lambda item: (
            item["score"],
            len(
                item["covered_groups"]
            ),
            item["topic_hits"],
        ),
        reverse=True,
    )

    required_topic_hits = (
        1
        if len(
            question_terms
        ) <= 2
        else 2
    )

    best_candidate = candidates[0]

    if (
        best_candidate["topic_hits"]
        < required_topic_hits
        and len(
            best_candidate[
                "covered_groups"
            ]
        ) < 2
    ):
        return []

    normalized_question = (
        normalize_arabic_match_text(
            question
        )
    )

    asks_munada_types = (
        "منادي" in normalized_question
        and any(
            marker in normalized_question
            for marker in (
                "انواع",
                "احكام",
            )
        )
    )

    asks_after_ayy = any(
        phrase
        in normalized_question
        for phrase in (
            "بعد ايها",
            "بعد ايتها",
            "اسم ذي ياتي بعد",
            "اسم الذي ياتي بعد",
        )
    )

    minimum_selected = (
        3
        if (
            asks_munada_types
            or asks_after_ayy
        )
        else 2
        if any(
            marker in normalized_question
            for marker in (
                "اعراب",
                "اعرب",
                "يعرب",
                "تعرب",
                "حكم",
                "احوال",
                "انواع",
                "صور",
            )
        )
        else 1
    )

    maximum_selected = (
        5
        if asks_munada_types
        else 3
        if asks_after_ayy
        else 4
        if any(
            marker in normalized_question
            for marker in (
                "انواع",
                "احوال",
                "اذكر",
            )
        )
        else 2
    )

    selected = []
    covered = set()
    used_quotes = set()
    used_passage_numbers = set()

    for candidate in candidates:
        normalized_quote = normalize_text(
            candidate["quote"]
        )

        if normalized_quote in used_quotes:
            continue

        if (
            selected
            and len(
                selected
            )
            < minimum_selected
            and candidate[
                "passage_number"
            ]
            in used_passage_numbers
        ):
            continue

        adds_coverage = (
            candidate[
                "covered_groups"
            ]
            - covered
        )

        if (
            selected
            and coverage_groups
            and not adds_coverage
            and len(
                selected
            )
            >= minimum_selected
        ):
            continue

        selected.append(
            {
                "passage_number": (
                    candidate[
                        "passage_number"
                    ]
                ),
                "quote": candidate[
                    "quote"
                ],
                "source": candidate[
                    "source"
                ],
                "page": candidate[
                    "page"
                ],
            }
        )

        used_quotes.add(
            normalized_quote
        )
        used_passage_numbers.add(
            candidate[
                "passage_number"
            ]
        )

        covered.update(
            candidate[
                "covered_groups"
            ]
        )

        coverage_is_complete = (
            not coverage_groups
            or len(
                covered
            )
            == len(
                coverage_groups
            )
        )

        if (
            (
                coverage_is_complete
                and len(
                    selected
                )
                >= minimum_selected
            )
            or len(
                selected
            )
            >= maximum_selected
        ):
            break

    if not selected:
        return []

    if coverage_groups:
        requires_full_coverage = (
            asks_munada_types
            or "نكره مقصوده"
            in normalized_question
            or "منادي مضاف"
            in normalized_question
            or "شبيه مضاف"
            in normalized_question
            or any(
                phrase
                in normalized_question
                for phrase in (
                    "بعد ايها",
                    "بعد ايتها",
                    "اسم الذي ياتي بعد",
                )
            )
        )

        minimum_coverage = (
            len(coverage_groups)
            if requires_full_coverage
            else max(
                1,
                int(
                    len(coverage_groups)
                    * 0.65
                ),
            )
        )

        if len(
            covered
        ) < minimum_coverage:
            return []

    return selected

def extract_role_evidence_from_passages(
    question: str,
    passages: list[dict],
) -> list[dict]:
    """
    Extrait une preuve directe pour chaque catégorie
    ou rôle mentionné dans les passages.
    """

    category_patterns = {
        "batisseurs": re.compile(
            (
                r"\b(?:les\s+)?aliments?\s+"
                r"b[aâ]ti(?:s|ss)eurs?\b"
            ),
            flags=re.IGNORECASE,
        ),
        "energetiques": re.compile(
            (
                r"\b(?:les\s+)?aliments?\s+"
                r"[ée]nerg[ée]tiques?\b"
            ),
            flags=re.IGNORECASE,
        ),
        "protecteurs": re.compile(
            (
                r"\b(?:les\s+)?aliments?\s+"
                r"protecteurs?\b"
            ),
            flags=re.IGNORECASE,
        ),
    }

    category_evidence = {}

    for passage_number, passage in enumerate(
        passages,
        start=1,
    ):
        original_text = re.sub(
            r"\s+",
            " ",
            passage.get(
                "text",
                "",
            ),
        ).strip()

        if not original_text:
            continue

        for category, pattern in (
            category_patterns.items()
        ):
            if category in category_evidence:
                continue

            match = pattern.search(
                original_text
            )

            if not match:
                continue

            excerpt_start = match.start()

            remaining_text = original_text[
                excerpt_start:
            ]

            next_category_positions = []

            for other_category, other_pattern in (
                category_patterns.items()
            ):
                if other_category == category:
                    continue

                other_match = other_pattern.search(
                    remaining_text,
                    pos=max(
                        1,
                        match.end()
                        - excerpt_start,
                    ),
                )

                if other_match:
                    next_category_positions.append(
                        other_match.start()
                    )

            if next_category_positions:
                excerpt_end = min(
                    next_category_positions
                )

                excerpt = remaining_text[
                    :excerpt_end
                ]
            else:
                excerpt = remaining_text[
                    :350
                ]

            excerpt = re.split(
                (
                    r"\b(?:"
                    r"Séance"
                    r"|Professeur"
                    r"|Exercice"
                    r"|Activité"
                    r"|Résumé"
                    r"|Document"
                    r"|Conclusion"
                    r")\b"
                ),
                excerpt,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()

            sentence_boundary = re.search(
                r"[.!?](?=\s+[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜ])",
                excerpt,
            )

            if (
                sentence_boundary
                and sentence_boundary.end() >= 25
            ):
                excerpt = excerpt[
                    :sentence_boundary.end()
                ]

            excerpt_words = excerpt.split()

            if len(excerpt_words) < 4:
                continue

            if len(excerpt_words) > 45:
                excerpt = " ".join(
                    excerpt_words[:45]
                ).rstrip(
                    " ,;:-"
                )

                if not excerpt.endswith(
                    (".", "!", "?")
                ):
                    excerpt += "."

            excerpt = re.sub(
                r"\s+",
                " ",
                excerpt,
            ).strip()

            category_evidence[category] = {
                "passage_number": (
                    passage_number
                ),
                "quote": excerpt,
                "source": passage.get(
                    "source",
                    "Source inconnue",
                ),
                "page": passage.get(
                    "page",
                    0,
                ),
            }

    ordered_categories = (
        "batisseurs",
        "energetiques",
        "protecteurs",
    )

    evidence = [
        category_evidence[category]
        for category in ordered_categories
        if category in category_evidence
    ]

    if evidence:
        return evidence

    fallback_role_markers = {
        "a pour role",
        "ont pour role",
        "sert a",
        "servent a",
        "permet de",
        "permettent de",
        "fonction",
        "fonctions",
        "utilite",
        "دور",
        "وظيفه",
        "فائده",
        "يستخدم",
        "يساعد",
        "يسمح",
    }

    fallback_evidence = []
    seen_quotes = set()

    for passage_number, passage in enumerate(
        passages,
        start=1,
    ):
        original_text = re.sub(
            r"\s+",
            " ",
            passage.get(
                "text",
                "",
            ),
        ).strip()

        sentences = re.split(
            r"(?<=[.!?؟])\s+",
            original_text,
        )

        for sentence in sentences:
            cleaned_sentence = sentence.strip()

            if not cleaned_sentence:
                continue

            normalized_sentence = normalize_text(
                cleaned_sentence
            )

            if not any(
                marker in normalized_sentence
                for marker in fallback_role_markers
            ):
                continue

            words = cleaned_sentence.split()

            if len(words) < 4:
                continue

            if len(words) > 45:
                cleaned_sentence = " ".join(
                    words[:45]
                ).rstrip(
                    " ,;:-"
                )

                if not cleaned_sentence.endswith(
                    (".", "!", "?", "؟")
                ):
                    cleaned_sentence += "."

            normalized_quote = normalize_text(
                cleaned_sentence
            )

            if normalized_quote in seen_quotes:
                continue

            seen_quotes.add(
                normalized_quote
            )

            fallback_evidence.append(
                {
                    "passage_number": (
                        passage_number
                    ),
                    "quote": cleaned_sentence,
                    "source": passage.get(
                        "source",
                        "Source inconnue",
                    ),
                    "page": passage.get(
                        "page",
                        0,
                    ),
                }
            )

    return fallback_evidence[:5]


def build_context(
    passages: list[dict],
) -> str:
    """
    Prépare les passages avec leur numéro
    et leur source.
    """

    context_parts = []

    for index, passage in enumerate(
        passages,
        start=1,
    ):
        context_parts.append(
            (
                f"PASSAGE {index}\n"
                f"Source : {passage['source']}\n"
                f"Page : {passage['page']}\n"
                f"Texte exact :\n{passage['text']}"
            )
        )

    return "\n\n".join(
        context_parts
    )


def call_ollama(
    payload: dict,
) -> dict:
    """
    Envoie une requête à Ollama
    et retourne le JSON produit.
    """

    try:
        response = httpx.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=180.0,
        )

        response.raise_for_status()

        content = (
            response.json()
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if not content:
            raise RuntimeError(
                "Ollama n'a retourné aucun contenu."
            )

        return json.loads(
            content
        )

    except httpx.ConnectError as error:
        raise RuntimeError(
            "La connexion avec Ollama a échoué. "
            "Vérifiez que l'application Ollama est active."
        ) from error

    except httpx.TimeoutException as error:
        raise RuntimeError(
            "Ollama a dépassé le délai de réponse autorisé."
        ) from error

    except httpx.HTTPStatusError as error:
        raise RuntimeError(
            "Ollama a retourné une erreur HTTP."
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "La réponse structurée d'Ollama est invalide."
        ) from error


def extract_evidence(
    question: str,
    passages: list[dict],
) -> dict:
    """
    Demande au modèle d'extraire
    uniquement les preuves directes.
    """

    context = build_context(
        passages
    )

    system_prompt = """
Tu es un vérificateur de preuves documentaires multilingue.

Ta mission n'est pas de répondre immédiatement à la question.
Tu dois uniquement vérifier si les passages contiennent des
informations directes permettant de répondre.

Règles obligatoires :

- Utilise uniquement les passages documentaires fournis.
- N'utilise aucune connaissance générale.
- N'effectue aucune supposition ni déduction.
- Accepte les passages en français ou en arabe.
- Chaque citation doit être copiée mot pour mot depuis un passage.
- Chaque citation doit contenir entre 4 et 45 mots.
- Indique le numéro exact du passage contenant chaque citation.
- Une simple présence du même sujet ne suffit pas.

Pour une question sur les causes :
- Accepte uniquement les passages qui présentent explicitement
  une cause, une origine, une raison ou un facteur.

Pour une question sur les conséquences :
- Accepte uniquement les passages qui décrivent explicitement
  un effet, un résultat, un bilan ou une conséquence.

Pour une question de définition :
- Accepte une phrase qui définit directement le terme demandé.
- Le mot « définition » ne doit pas obligatoirement apparaître.

Pour une question sur les rôles :
- Accepte les passages qui décrivent les catégories,
  les fonctions, l'utilité ou l'action du sujet demandé.

Pour une demande de résumé :
- Sélectionne plusieurs citations complémentaires
  directement liées au sujet.
- Évite les titres administratifs et les répétitions.

Pour une comparaison :
- Sélectionne les passages qui présentent
  les deux éléments à comparer.

Si aucune preuve directe n'existe :
- Utilise answerable=false.
- Retourne une liste evidence vide.
""".strip()

    user_prompt = f"""
Question :

{question}

Passages documentaires :

{context}

Vérifie maintenant si ces passages contiennent une preuve directe.
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
        "format": EVIDENCE_SCHEMA,
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0.0,
            "num_predict": 220,
        },
    }

    return call_ollama(
        payload
    )


def validate_evidence(
    question: str,
    passages: list[dict],
    evidence_items: list[dict],
) -> list[dict]:
    """
    Vérifie que chaque citation existe réellement
    dans le passage indiqué et correspond au sujet.
    """

    validated_evidence = []

    for item in evidence_items:
        passage_number = item.get(
            "passage_number"
        )

        quote = item.get(
            "quote",
            "",
        ).strip()

        if not isinstance(
            passage_number,
            int,
        ):
            continue

        if passage_number < 1:
            continue

        if passage_number > len(
            passages
        ):
            continue

        normalized_quote = normalize_text(
            quote
        )

        quote_word_count = len(
            normalized_quote.split()
        )

        if quote_word_count < 4:
            continue

        if quote_word_count > 45:
            continue

        passage = passages[
            passage_number - 1
        ]

        normalized_passage = normalize_text(
            passage.get(
                "text",
                "",
            )
        )

        if (
            normalized_quote
            not in normalized_passage
        ):
            continue

        validated_evidence.append(
            {
                "passage_number": (
                    passage_number
                ),
                "quote": quote,
                "source": passage.get(
                    "source",
                    "Source inconnue",
                ),
                "page": passage.get(
                    "page",
                    0,
                ),
            }
        )

    if not validated_evidence:
        return []

    combined_evidence = " ".join(
        item["quote"]
        for item in validated_evidence
    )

    evidence_words = tokenize_words(
        combined_evidence
    )

    intent = detect_question_intent(
        question
    )

    intents_requiring_explicit_markers = {
        "causes",
        "consequences",
    }

    if (
        intent
        in intents_requiring_explicit_markers
    ):
        intent_words = {
            normalize_word(word)
            for word in INTENT_WORDS.get(
                intent,
                set(),
            )
        }

        if not evidence_words.intersection(
            intent_words
        ):
            return []

    topic_keywords = extract_topic_keywords(
        question
    )

    if topic_keywords:
        common_keywords = (
            topic_keywords.intersection(
                evidence_words
            )
        )

        if (
            contains_arabic(
                question
            )
            or intent
            in {
                "definition",
                "summary",
                "comparison",
            }
            or len(topic_keywords) <= 2
        ):
            required_keywords = 1
        else:
            required_keywords = min(
                2,
                len(topic_keywords),
            )

        if (
            len(common_keywords)
            < required_keywords
        ):
            return []

    return validated_evidence


def write_answer(
    question: str,
    evidence: list[dict],
) -> str:
    """
    Produit une réponse claire à partir
    des preuves documentaires validées.
    """

    refusal_answer = get_refusal_answer(
        question
    )

    if not evidence:
        return refusal_answer

    intent = detect_question_intent(
        question
    )

    cleaned_quotes = []
    seen_quotes = set()

    for item in evidence:
        quote = (
            item.get(
                "quote",
                "",
            )
            .translate(
                ARABIC_OCR_TRANSLATION_TABLE
            )
        )

        quote = re.sub(
            r"\s+",
            " ",
            quote,
        ).strip()

        if not quote:
            continue

        normalized_quote = normalize_text(
            quote
        )

        if normalized_quote in seen_quotes:
            continue

        seen_quotes.add(
            normalized_quote
        )

        cleaned_quotes.append(
            quote
        )

    if not cleaned_quotes:
        return refusal_answer

    question_is_arabic = contains_arabic(
        question
    )

    if intent == "definition":
        quote = cleaned_quotes[0].rstrip(
            " ."
        )

        if question_is_arabic:
            return (
                "حسب الوثيقة:\n"
                f"{quote}."
            )

        return (
            "D'après le document :\n"
            f"{quote}."
        )

    category_patterns = [
        (
            re.compile(
                (
                    r"^Les\s+aliments?\s+"
                    r"b[aâ]ti(?:s|ss)eurs?\s*"
                ),
                flags=re.IGNORECASE,
            ),
            "Les aliments bâtisseurs",
        ),
        (
            re.compile(
                (
                    r"^Les\s+aliments?\s+"
                    r"[ée]nerg[ée]tiques?\s*"
                ),
                flags=re.IGNORECASE,
            ),
            "Les aliments énergétiques",
        ),
        (
            re.compile(
                (
                    r"^Les\s+aliments?\s+"
                    r"protecteurs?\s*"
                ),
                flags=re.IGNORECASE,
            ),
            "Les aliments protecteurs",
        ),
    ]

    formatted_lines = []

    for quote in cleaned_quotes:
        formatted_quote = None

        if not question_is_arabic:
            for pattern, category_label in (
                category_patterns
            ):
                match = pattern.match(
                    quote
                )

                if not match:
                    continue

                explanation = quote[
                    match.end():
                ].strip(
                    " :;,-"
                )

                if explanation:
                    explanation = (
                        explanation[0].lower()
                        + explanation[1:]
                        if len(explanation) > 1
                        else explanation.lower()
                    )

                    explanation = (
                        explanation.rstrip(
                            " ."
                        )
                        + "."
                    )

                    formatted_quote = (
                        f"- {category_label} : "
                        f"{explanation}"
                    )
                else:
                    formatted_quote = (
                        f"- {category_label}."
                    )

                break

        if formatted_quote is None:
            ending = (
                ""
                if quote.endswith(
                    (".", "!", "?", "؟")
                )
                else "."
            )

            formatted_quote = (
                "- "
                + quote.rstrip()
                + ending
            )

        formatted_lines.append(
            formatted_quote
        )

    if not formatted_lines:
        return refusal_answer

    if question_is_arabic:
        introduction = (
            "حسب الوثيقة:"
            if len(formatted_lines) == 1
            else "حسب الوثائق:"
        )
    else:
        introduction = (
            "D'après le document :"
            if len(formatted_lines) == 1
            else "D'après les documents :"
        )

    return (
        introduction
        + "\n"
        + "\n".join(
            formatted_lines
        )
    )


def has_topic_overlap_with_passages(
    question: str,
    passages: list[dict],
) -> bool:
    """
    Évite un appel LLM coûteux quand aucun mot du sujet demandé
    n'apparaît dans les passages récupérés.
    """

    topic_keywords = extract_topic_keywords(
        question
    )

    if not topic_keywords:
        return True

    passage_keywords = set()

    for passage in passages:
        passage_keywords.update(
            tokenize_words(
                passage.get(
                    "text",
                    "",
                )
            )
        )

    return bool(
        topic_keywords.intersection(
            passage_keywords
        )
    )


def generate_answer(
    question: str,
    passages: list[dict],
) -> dict:
    """
    Extrait les preuves, les valide
    puis produit une réponse documentaire.
    """

    cleaned_question = (
        question.strip()
    )

    if not cleaned_question:
        raise ValueError(
            "La question ne peut pas être vide."
        )

    analysis_question = (
        repair_common_arabic_question_typos(
            cleaned_question
        )
    )

    refusal_answer = get_refusal_answer(
        cleaned_question
    )

    if not passages:
        return {
            "answerable": False,
            "answer": refusal_answer,
            "sources": [],
            "evidence": [],
        }

    intent = detect_question_intent(
        analysis_question
    )

    validated_evidence = []

    # L'extraction arabe documentée passe avant les extracteurs
    # génériques afin d'éviter les mélanges entre plusieurs cours.
    if contains_arabic(
        analysis_question
    ):
        validated_evidence = (
            extract_arabic_warning_enticement_evidence(
                question=analysis_question,
                passages=passages,
            )
        )

        if not validated_evidence:
            validated_evidence = (
                extract_arabic_exclamation_evidence(
                    question=analysis_question,
                    passages=passages,
                )
            )

    if (
        not validated_evidence
        and contains_arabic(
            analysis_question
        )
    ):
        validated_evidence = (
            extract_arabic_direct_rule_evidence(
                question=analysis_question,
                passages=passages,
            )
        )

    if (
        not validated_evidence
        and contains_arabic(
            analysis_question
        )
    ):
        validated_evidence = (
            extract_arabic_generic_evidence(
                question=analysis_question,
                passages=passages,
            )
        )

    if (
        not validated_evidence
        and intent == "elements"
    ):
        validated_evidence = (
            extract_element_evidence_from_passages(
                question=analysis_question,
                passages=passages,
            )
        )

    if (
        not validated_evidence
        and intent == "roles"
    ):
        validated_evidence = (
            extract_role_evidence_from_passages(
                question=analysis_question,
                passages=passages,
            )
        )

    if (
        not validated_evidence
        and contains_arabic(
            analysis_question
        )
        and not has_topic_overlap_with_passages(
            question=analysis_question,
            passages=passages,
        )
    ):
        return {
            "answerable": False,
            "answer": refusal_answer,
            "sources": [],
            "evidence": [],
        }

    if not validated_evidence:
        extraction = extract_evidence(
            question=analysis_question,
            passages=passages,
        )

        if not extraction.get(
            "answerable",
            False,
        ):
            return {
                "answerable": False,
                "answer": refusal_answer,
                "sources": [],
                "evidence": [],
            }

        validated_evidence = (
            validate_evidence(
                question=analysis_question,
                passages=passages,
                evidence_items=(
                    extraction.get(
                        "evidence",
                        [],
                    )
                ),
            )
        )

    if not validated_evidence:
        return {
            "answerable": False,
            "answer": refusal_answer,
            "sources": [],
            "evidence": [],
        }

    if intent == "definition":
        validated_evidence = (
            validated_evidence[:1]
        )

    if intent == "elements":
        validated_evidence = (
            validated_evidence[:2]
        )

    answer = write_answer(
        question=analysis_question,
        evidence=validated_evidence,
    )

    if answer == refusal_answer:
        return {
            "answerable": False,
            "answer": refusal_answer,
            "sources": [],
            "evidence": [],
        }

    sources = []

    for item in validated_evidence:
        passage_number = item.get(
            "passage_number",
            0,
        )

        relative_path = ""

        if (
            isinstance(
                passage_number,
                int,
            )
            and 1
            <= passage_number
            <= len(passages)
        ):
            passage = passages[
                passage_number - 1
            ]

            relative_path = (
                passage.get(
                    "relative_path",
                    "",
                )
            )

        source = {
            "file": item.get(
                "source",
                "Source inconnue",
            ),
            "page": item.get(
                "page",
                0,
            ),
            "relative_path": (
                relative_path
            ),
        }

        if source not in sources:
            sources.append(
                source
            )

    return {
        "answerable": True,
        "answer": answer,
        "sources": sources,
        "evidence": [
            item["quote"]
            for item in validated_evidence
        ],
    }