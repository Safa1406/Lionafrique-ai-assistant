import re
import unicodedata

from services.vector_store_service import (
    search_similar_chunks,
)


MAX_ALLOWED_DISTANCE = 0.60


STOP_WORDS = {
    "avec",
    "aux",
    "comment",
    "dans",
    "des",
    "du",
    "elle",
    "elles",
    "est",
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
    "une",
    "un",
}


QUESTION_INTENT_WORDS = {
    "causes": {
        "cause",
        "causes",
        "origine",
        "origines",
        "raison",
        "raisons",
        "facteur",
        "facteurs",
        "pourquoi",
        "declenchement",
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
    },
    "definition": {
        "definition",
        "definir",
        "signifie",
        "signification",
    },
    "roles": {
        "role",
        "roles",
        "fonction",
        "fonctions",
        "utilite",
    },
}


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
    },
    "definition": {
        "definition",
        "definit",
        "signifie",
        "correspond a",
        "est un",
        "est une",
        "designe",
    },
    "roles": {
        "role",
        "roles",
        "fonction",
        "fonctions",
        "sert a",
        "permet de",
        "a pour role",
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
    },
    "consequences": {
        "cause",
        "causes",
        "origine",
        "origines",
        "declenchement",
    },
}


def normalize_text(text: str) -> str:
    """
    Normalise un texte afin de faciliter
    les comparaisons lexicales.
    """

    if not text:
        return ""

    normalized_text = unicodedata.normalize(
        "NFKD",
        text.lower(),
    )

    normalized_text = "".join(
        character
        for character in normalized_text
        if not unicodedata.combining(
            character
        )
    )

    normalized_text = re.sub(
        r"[^a-z0-9\s-]",
        " ",
        normalized_text,
    )

    normalized_text = re.sub(
        r"\s+",
        " ",
        normalized_text,
    )

    return normalized_text.strip()


def detect_question_intent(
    question: str,
) -> str | None:
    """
    Détecte la relation principale
    demandée dans la question.
    """

    normalized_question = normalize_text(
        question
    )

    definition_patterns = (
        "qu est ce que",
        "qu est ce qu",
        "que signifie",
        "quelle est la definition",
        "comment definir",
    )

    if any(
        pattern in normalized_question
        for pattern in definition_patterns
    ):
        return "definition"

    question_words = set(
        normalized_question.split()
    )

    for (
        intent,
        intent_words,
    ) in QUESTION_INTENT_WORDS.items():
        if question_words.intersection(
            intent_words
        ):
            return intent

    return None


def extract_topic_keywords(
    question: str,
) -> set[str]:
    """
    Extrait les mots décrivant
    le sujet principal de la question.
    """

    excluded_words = set(
        STOP_WORDS
    )

    for intent_words in (
        QUESTION_INTENT_WORDS.values()
    ):
        excluded_words.update(
            intent_words
        )

    normalized_question = normalize_text(
        question
    )

    return {
        word
        for word in normalized_question.split()
        if len(word) >= 4
        and word not in excluded_words
    }


def contains_expression(
    normalized_text: str,
    expressions: set[str],
) -> bool:
    """
    Vérifie si le texte contient
    au moins une expression donnée.
    """

    return any(
        expression in normalized_text
        for expression in expressions
    )


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

    passage_words = set(
        normalized_passage.split()
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
            intent_bonus = 0.35

        if (
            intent == "definition"
            and ":" in passage_text
            and common_keywords
        ):
            intent_bonus = max(
                intent_bonus,
                0.30,
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
            opposite_penalty = 0.25

    return (
        semantic_score
        + lexical_score * 0.80
        + intent_bonus
        - opposite_penalty
    )


def retrieve_relevant_passages(
    question: str,
    number_of_results: int = 3,
    program: str | None = None,
    subject: str | None = None,
    semester: str | None = None,
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

    candidate_count = max(
        12,
        number_of_results * 4,
    )

    initial_results = search_similar_chunks(
        question=cleaned_question,
        number_of_results=candidate_count,
        program=program,
        subject=subject,
        semester=semester,
    )

    if not initial_results:
        return []

    intent = detect_question_intent(
        cleaned_question
    )

    topic_keywords = extract_topic_keywords(
        cleaned_question
    )

    scored_results = []

    for passage in initial_results:
        distance = float(
            passage.get(
                "distance",
                1.0,
            )
        )

        if distance > MAX_ALLOWED_DISTANCE:
            continue

        normalized_passage = normalize_text(
            passage.get(
                "text",
                "",
            )
        )

        passage_words = set(
            normalized_passage.split()
        )

        if topic_keywords:
            common_keywords = (
                topic_keywords.intersection(
                    passage_words
                )
            )

            if not common_keywords:
                continue

        retrieval_score = (
            calculate_passage_score(
                question=cleaned_question,
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

        if chunk_id:
            selected_chunk_ids.add(
                chunk_id
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