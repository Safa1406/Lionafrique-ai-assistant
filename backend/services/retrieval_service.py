import re
import unicodedata

from services.vector_store_service import search_similar_chunks


MAX_ALLOWED_DISTANCE = 0.55

STOP_WORDS = {
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    "du",
    "de",
    "dans",
    "sur",
    "avec",
    "pour",
    "par",
    "et",
    "ou",
    "est",
    "sont",
    "quelles",
    "quels",
    "quelle",
    "quel",
    "comment",
    "pourquoi",
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
        "declenche",
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
    },
    "definition": {
        "definition",
        "definit",
        "signifie",
        "correspond a",
        "est un",
        "est une",
    },
    "roles": {
        "role",
        "roles",
        "fonction",
        "fonctions",
        "sert a",
        "permet de",
    },
}

QUESTION_INTENT_WORDS = {
    "causes": {
        "cause",
        "causes",
        "origine",
        "origines",
        "raison",
        "raisons",
        "pourquoi",
    },
    "consequences": {
        "consequence",
        "consequences",
        "bilan",
        "effet",
        "effets",
        "impact",
        "impacts",
    },
    "definition": {
        "definition",
        "definir",
        "signifie",
    },
    "roles": {
        "role",
        "roles",
        "fonction",
        "fonctions",
    },
}


def normalize_text(text: str) -> str:
    """
    Normalise le texte pour faciliter les comparaisons.
    """

    normalized_text = unicodedata.normalize(
        "NFKD",
        text.lower(),
    )

    normalized_text = "".join(
        character
        for character in normalized_text
        if not unicodedata.combining(character)
    )

    normalized_text = re.sub(
        r"[^a-z0-9\s-]",
        " ",
        normalized_text,
    )

    return re.sub(
        r"\s+",
        " ",
        normalized_text,
    ).strip()


def detect_question_intent(
    question: str,
) -> str | None:
    """
    Détecte l'intention principale de la question.
    """

    normalized_question = normalize_text(question)
    question_words = set(normalized_question.split())

    for intent, words in QUESTION_INTENT_WORDS.items():
        if question_words.intersection(words):
            return intent

    return None


def extract_topic_keywords(
    question: str,
) -> set[str]:
    """
    Extrait les mots décrivant le sujet de la question.
    """

    normalized_question = normalize_text(question)

    excluded_words = set(STOP_WORDS)

    for intent_words in QUESTION_INTENT_WORDS.values():
        excluded_words.update(intent_words)

    return {
        word
        for word in normalized_question.split()
        if len(word) >= 4
        and word not in excluded_words
    }


def passage_contains_marker(
    passage_text: str,
    markers: set[str],
) -> bool:
    """
    Vérifie la présence d'un marqueur explicite.
    """

    return any(
        marker in passage_text
        for marker in markers
    )


def has_required_topic(
    question: str,
    passage_text: str,
) -> bool:
    """
    Vérifie que le passage traite réellement du sujet demandé.
    """

    topic_keywords = extract_topic_keywords(question)

    if not topic_keywords:
        return True

    passage_words = set(passage_text.split())
    common_keywords = topic_keywords.intersection(
        passage_words
    )

    required_count = min(
        2,
        len(topic_keywords),
    )

    return len(common_keywords) >= required_count


def retrieve_relevant_passages(
    question: str,
    number_of_results: int = 3,
) -> list[dict]:
    """
    Recherche uniquement les passages contenant
    des preuves directes pour répondre à la question.
    """

    initial_results = search_similar_chunks(
        question=question,
        number_of_results=12,
    )

    intent = detect_question_intent(question)
    accepted_results = []

    for passage in initial_results:
        distance = float(
            passage.get("distance", 1.0)
        )

        if distance > MAX_ALLOWED_DISTANCE:
            continue

        normalized_passage = normalize_text(
            passage.get("text", "")
        )

        if not has_required_topic(
            question,
            normalized_passage,
        ):
            continue

        if intent:
            markers = INTENT_MARKERS[intent]

            if not passage_contains_marker(
                normalized_passage,
                markers,
            ):
                continue

        topic_keywords = extract_topic_keywords(question)
        passage_words = set(normalized_passage.split())

        overlap_count = len(
            topic_keywords.intersection(passage_words)
        )

        passage["retrieval_score"] = (
            1.0 - distance
        ) + overlap_count * 0.15

        accepted_results.append(passage)

    accepted_results.sort(
        key=lambda passage: passage["retrieval_score"],
        reverse=True,
    )

    return accepted_results[:number_of_results]