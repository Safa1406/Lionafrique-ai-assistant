import re

from services.llm_service import (
    contains_arabic,
    detect_question_intent,
    extract_topic_keywords,
    normalize_text,
    tokenize_words,
)
from services.vector_store_service import (
    search_similar_chunks,
)


DEFAULT_MAX_ALLOWED_DISTANCE = 0.64
RELAXED_MAX_ALLOWED_DISTANCE = 0.90


INTENT_MARKERS = {
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
        "provoque par",
        "a cause de",
        "en raison de",
        "سبب",
        "اسباب",
        "بسبب",
        "عوامل",
        "عامل",
    },
    "consequences": {
        "consequence",
        "consequences",
        "bilan",
        "effet",
        "effets",
        "impact",
        "impacts",
        "resultat",
        "resultats",
        "provoque",
        "entraine",
        "a pour consequence",
        "نتيجه",
        "نتايج",
        "اثار",
        "اثر",
        "عواقب",
        "يودي",
        "ينتج",
    },
    "definition": {
        "definition",
        "definit",
        "signifie",
        "correspond a",
        "est un",
        "est une",
        "designe",
        "تعريف",
        "يعني",
        "هو",
        "هي",
        "يقصد",
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
        "sert a",
        "permet de",
        "a pour role",
        "دور",
        "وظيفه",
        "فائده",
        "يساعد",
        "يسمح",
        "يستخدم",
    },
    "summary": {
        "resume",
        "synthese",
        "bilan",
        "ملخص",
        "تلخيص",
        "خلاصه",
    },
    "comparison": {
        "difference",
        "differences",
        "compare",
        "comparaison",
        "فرق",
        "قارن",
        "مقارنه",
        "يختلف",
    },
}


OPPOSITE_MARKERS = {
    "causes": {
        "consequence",
        "consequences",
        "bilan",
        "resultat",
        "resultats",
        "apres guerre",
        "defaite",
        "disparition",
        "victimes",
        "نتيجه",
        "نتايج",
        "اثار",
        "عواقب",
    },
    "consequences": {
        "cause",
        "causes",
        "origine",
        "origines",
        "declenchement",
        "سبب",
        "اسباب",
        "عوامل",
    },
}


SUMMARY_PREFIX_PATTERNS = (
    r"^\s*(?:résume|resume|résumer|resumer)\s+",
    r"^\s*(?:fais-moi|fais moi|donne-moi|donne moi)\s+"
    r"(?:un|une)\s+(?:résumé|resume|synthèse|synthese)\s+",
    r"^\s*(?:summarize|summarise)\s+",
    r"^\s*(?:لخص|لخّص)\s+",
    r"^\s*(?:اعطني|أعطني|قدم|قدّم)\s+"
    r"(?:ملخصا|ملخص|تلخيصا|تلخيص)\s+",
    r"^\s*(?:تلخيص|ملخص)\s+",
)


def prepare_search_query(
    question: str,
) -> str:
    """
    Supprime les mots de commande
    qui ne décrivent pas le sujet recherché.
    """

    cleaned_question = question.strip()

    for pattern in SUMMARY_PREFIX_PATTERNS:
        cleaned_question = re.sub(
            pattern,
            "",
            cleaned_question,
            count=1,
            flags=re.IGNORECASE,
        ).strip()

    cleaned_question = re.sub(
        r"^(?:le|la|les|un|une|du|de la|des)\s+",
        "",
        cleaned_question,
        count=1,
        flags=re.IGNORECASE,
    ).strip()

    cleaned_question = re.sub(
        r"^(?:درس|موضوع)\s+",
        "",
        cleaned_question,
        count=1,
    ).strip()

    return (
        cleaned_question
        if cleaned_question
        else question.strip()
    )


def contains_expression(
    normalized_text: str,
    expressions: set[str],
) -> bool:
    """
    Vérifie si le texte contient
    au moins une expression donnée.
    """

    normalized_expressions = {
        normalize_text(
            expression
        )
        for expression in expressions
    }

    return any(
        expression
        and expression in normalized_text
        for expression in normalized_expressions
    )


def get_max_allowed_distance(
    question: str,
    intent: str | None,
) -> float:
    """
    Retourne un seuil adapté
    à la langue et au type de demande.
    """

    if (
        contains_arabic(
            question
        )
        or intent == "summary"
    ):
        return RELAXED_MAX_ALLOWED_DISTANCE

    return DEFAULT_MAX_ALLOWED_DISTANCE


def calculate_passage_score(
    question: str,
    passage: dict,
    intent: str | None,
) -> float:
    """
    Calcule un score combinant
    la proximité sémantique,
    les mots du sujet et l'intention.
    """

    passage_text = passage.get(
        "text",
        "",
    )

    normalized_passage = normalize_text(
        passage_text
    )

    passage_words = tokenize_words(
        passage_text
    )

    topic_keywords = extract_topic_keywords(
        question
    )

    common_keywords = (
        topic_keywords.intersection(
            passage_words
        )
    )

    lexical_score = (
        len(common_keywords)
        / max(
            len(topic_keywords),
            1,
        )
    )

    distance = float(
        passage.get(
            "distance",
            1.0,
        )
    )

    semantic_score = max(
        0.0,
        1.0 - distance,
    )

    intent_bonus = 0.0
    opposite_penalty = 0.0

    if intent:
        intent_markers = INTENT_MARKERS.get(
            intent,
            set(),
        )

        if contains_expression(
            normalized_passage,
            intent_markers,
        ):
            intent_bonus = 0.30

        if (
            intent == "definition"
            and ":" in passage_text
            and common_keywords
        ):
            intent_bonus = max(
                intent_bonus,
                0.28,
            )

        if (
            intent == "summary"
            and len(common_keywords) >= 1
        ):
            intent_bonus = max(
                intent_bonus,
                0.20,
            )

        opposite_markers = (
            OPPOSITE_MARKERS.get(
                intent,
                set(),
            )
        )

        if contains_expression(
            normalized_passage,
            opposite_markers,
        ):
            opposite_penalty = 0.22

    return (
        semantic_score
        + lexical_score * 0.85
        + intent_bonus
        - opposite_penalty
    )


def should_keep_without_lexical_overlap(
    distance: float,
    intent: str | None,
    question_is_arabic: bool,
) -> bool:
    """
    Autorise un résultat sémantiquement fort
    même si les formes lexicales diffèrent.
    """

    if question_is_arabic:
        return distance <= 0.56

    if intent == "summary":
        return distance <= 0.58

    return distance <= 0.48


def retrieve_relevant_passages(
    question: str,
    number_of_results: int = 3,
    program: str | None = None,
    subject: str | None = None,
    semester: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """
    Recherche et reclasse les passages
    en appliquant les filtres pédagogiques.
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

    search_question = prepare_search_query(
        cleaned_question
    )

    intent = detect_question_intent(
        cleaned_question
    )

    question_is_arabic = contains_arabic(
        cleaned_question
    )

    if question_is_arabic:
        # Les embeddings arabes peuvent classer le passage exact
        # plus bas que prévu, surtout pour les courtes questions
        # de définition ou de grammaire. On élargit donc le vivier
        # avant le reclassement lexical et documentaire.
        candidate_count = max(
            60,
            number_of_results * 12,
        )
    elif intent == "summary":
        candidate_count = max(
            30,
            number_of_results * 8,
        )
    else:
        candidate_count = max(
            14,
            number_of_results * 4,
        )

    initial_results = search_similar_chunks(
        question=search_question,
        number_of_results=candidate_count,
        program=program,
        subject=subject,
        semester=semester,
        source=source,
    )

    if not initial_results:
        return []

    if source:
        cleaned_source = source.strip()

        initial_results = [
            passage
            for passage in initial_results
            if passage.get(
                "source",
                "",
            )
            == cleaned_source
        ]

        if not initial_results:
            return []

    topic_keywords = extract_topic_keywords(
        search_question
    )

    max_allowed_distance = (
        get_max_allowed_distance(
            question=cleaned_question,
            intent=intent,
        )
    )

    scored_results = []

    for passage in initial_results:
        distance = float(
            passage.get(
                "distance",
                1.0,
            )
        )

        passage_words = tokenize_words(
            passage.get(
                "text",
                "",
            )
        )

        common_keywords = (
            topic_keywords.intersection(
                passage_words
            )
        )

        strong_arabic_lexical_match = (
            question_is_arabic
            and len(common_keywords) >= 2
            and distance <= 0.96
        )

        # Pour l'arabe, un passage qui contient clairement plusieurs
        # mots du sujet ne doit pas être éliminé uniquement à cause
        # d'une distance vectorielle imparfaite. La validation des
        # preuves effectuée ensuite empêche les réponses inventées.
        if (
            distance > max_allowed_distance
            and not strong_arabic_lexical_match
        ):
            continue

        if (
            topic_keywords
            and not common_keywords
            and not should_keep_without_lexical_overlap(
                distance=distance,
                intent=intent,
                question_is_arabic=(
                    question_is_arabic
                ),
            )
        ):
            continue

        retrieval_score = (
            calculate_passage_score(
                question=search_question,
                passage=passage,
                intent=intent,
            )
        )

        enriched_passage = {
            **passage,
            "retrieval_score": round(
                retrieval_score,
                6,
            ),
        }

        scored_results.append(
            enriched_passage
        )

    scored_results.sort(
        key=lambda passage: (
            passage["retrieval_score"]
        ),
        reverse=True,
    )

    selected_passages = []
    selected_chunk_ids = set()
    source_page_counts = {}

    for passage in scored_results:
        chunk_id = passage.get(
            "chunk_id",
            "",
        )

        if (
            chunk_id
            and chunk_id
            in selected_chunk_ids
        ):
            continue

        source_page_key = (
            passage.get(
                "source",
                "",
            ),
            passage.get(
                "page",
                0,
            ),
        )

        source_page_count = (
            source_page_counts.get(
                source_page_key,
                0,
            )
        )

        if (
            intent == "summary"
            and source_page_count >= 2
        ):
            continue

        if chunk_id:
            selected_chunk_ids.add(
                chunk_id
            )

        source_page_counts[
            source_page_key
        ] = (
            source_page_count + 1
        )

        selected_passages.append(
            passage
        )

        if (
            len(selected_passages)
            >= number_of_results
        ):
            break

    return selected_passages