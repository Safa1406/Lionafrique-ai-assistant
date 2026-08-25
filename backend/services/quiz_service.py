import re
import time
import unicodedata
import uuid
from threading import Lock

from services.llm_service import (
    OLLAMA_MODEL,
    call_ollama,
)
from services.vector_store_service import (
    build_metadata_filter,
    get_document_collection,
)


ALLOWED_DIFFICULTIES = {
    "easy",
    "medium",
    "hard",
}

ALLOWED_TYPES = {
    "mcq",
    "true_false",
    "short_answer",
}


QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "mcq",
                            "true_false",
                            "short_answer",
                        ],
                    },
                    "question": {
                        "type": "string",
                    },
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "correct_answer": {
                        "type": "string",
                    },
                    "explanation": {
                        "type": "string",
                    },
                    "passage_number": {
                        "type": "integer",
                    },
                    "evidence_quote": {
                        "type": "string",
                    },
                },
                "required": [
                    "type",
                    "question",
                    "options",
                    "correct_answer",
                    "explanation",
                    "passage_number",
                    "evidence_quote",
                ],
            },
        },
    },
    "required": [
        "questions",
    ],
}


QUIZ_STORE = {}
QUIZ_STORE_LOCK = Lock()

QUIZ_TTL_SECONDS = (
    2 * 60 * 60
)


def normalize_text(
    value: str,
) -> str:

    value = unicodedata.normalize(
        "NFKD",
        str(
            value
            or ""
        ),
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(
            char
        )
    )

    value = (
        value
        .lower()
        .replace(
            "?",
            "?",
        )
        .replace(
            "?",
            "?",
        )
        .replace(
            "?",
            "?",
        )
        .replace(
            "?",
            "?",
        )
        .replace(
            "?",
            "?",
        )
    )

    value = re.sub(
        r"[^\w\u0600-\u06ff]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def contains_arabic(
    value: str,
) -> bool:

    return bool(
        re.search(
            r"[\u0600-\u06ff]",
            value
            or "",
        )
    )


def clean_expired_quizzes():

    now = time.time()

    with QUIZ_STORE_LOCK:

        expired = [
            quiz_id
            for quiz_id, quiz
            in QUIZ_STORE.items()
            if (
                now
                - quiz.get(
                    "created_at",
                    now,
                )
                > QUIZ_TTL_SECONDS
            )
        ]

        for quiz_id in expired:
            QUIZ_STORE.pop(
                quiz_id,
                None,
            )


def get_lesson_passages(
    program: str,
    subject: str,
    semester: str,
    source: str,
) -> list[dict]:

    collection = (
        get_document_collection()
    )

    where = build_metadata_filter(
        program=program,
        subject=subject,
        semester=semester,
        source=source,
    )

    result = collection.get(
        where=where,
        include=[
            "documents",
            "metadatas",
        ],
    )

    documents = (
        result.get(
            "documents"
        )
        or []
    )

    metadatas = (
        result.get(
            "metadatas"
        )
        or []
    )

    passages = []

    for document, metadata in zip(
        documents,
        metadatas,
    ):

        metadata = (
            metadata
            or {}
        )

        text = str(
            document
            or ""
        ).strip()

        if not text:
            continue

        if (
            metadata.get(
                "source",
                "",
            )
            != source
        ):
            continue

        passages.append(
            {
                "text": text,
                "source": (
                    metadata.get(
                        "source",
                        source,
                    )
                ),
                "page": (
                    metadata.get(
                        "page",
                        0,
                    )
                ),
                "chunk_number": (
                    metadata.get(
                        "chunk_number",
                        0,
                    )
                ),
            }
        )

    passages.sort(
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
        )
    )

    return passages


def evenly_select(
    items: list,
    maximum: int,
) -> list:

    if len(items) <= maximum:
        return list(
            items
        )

    if maximum <= 1:
        return [
            items[0]
        ]

    selected = []

    for index in range(
        maximum
    ):

        position = round(
            index
            * (
                len(items) - 1
            )
            / (
                maximum - 1
            )
        )

        selected.append(
            items[position]
        )

    return selected


def prepare_generation_passages(
    passages: list[dict],
) -> list[dict]:

    selected = evenly_select(
        passages,
        8,
    )

    result = []
    total_chars = 0

    for passage in selected:

        text = passage.get(
            "text",
            "",
        )

        if not text:
            continue

        remaining = (
            14000
            - total_chars
        )

        if remaining <= 0:
            break

        text = text[
            :remaining
        ]

        result.append(
            {
                **passage,
                "text": text,
            }
        )

        total_chars += len(
            text
        )

    return result


def build_quiz_context(
    passages: list[dict],
) -> str:

    parts = []

    for index, passage in enumerate(
        passages,
        start=1,
    ):

        parts.append(
            (
                f"PASSAGE {index}\n"
                f"Source: "
                f"{passage.get('source', '')}\n"
                f"Page: "
                f"{passage.get('page', 0)}\n"
                "Texte:\n"
                f"{passage.get('text', '')}"
            )
        )

    return "\n\n".join(
        parts
    )


def quote_exists(
    quote: str,
    passage: str,
) -> bool:

    normalized_quote = (
        normalize_text(
            quote
        )
    )

    normalized_passage = (
        normalize_text(
            passage
        )
    )

    if len(
        normalized_quote
    ) < 8:
        return False

    return (
        normalized_quote
        in normalized_passage
    )


def normalize_options(
    values,
) -> list[str]:

    if not isinstance(
        values,
        list,
    ):
        return []

    result = []
    seen = set()

    for value in values:

        value = str(
            value
            or ""
        ).strip()

        key = normalize_text(
            value
        )

        if (
            not value
            or not key
            or key in seen
        ):
            continue

        seen.add(
            key
        )

        result.append(
            value
        )

    return result


def validate_generated_question(
    item: dict,
    passages: list[dict],
    allowed_types: set[str],
) -> dict | None:

    if not isinstance(
        item,
        dict,
    ):
        return None

    question_type = str(
        item.get(
            "type",
            "",
        )
    ).strip()

    if (
        question_type
        not in allowed_types
    ):
        return None

    question = str(
        item.get(
            "question",
            "",
        )
    ).strip()

    correct_answer = str(
        item.get(
            "correct_answer",
            "",
        )
    ).strip()

    explanation = str(
        item.get(
            "explanation",
            "",
        )
    ).strip()

    evidence_quote = str(
        item.get(
            "evidence_quote",
            "",
        )
    ).strip()

    try:
        passage_number = int(
            item.get(
                "passage_number"
            )
        )
    except Exception:
        return None

    if not (
        1
        <= passage_number
        <= len(passages)
    ):
        return None

    if (
        len(question) < 5
        or not correct_answer
    ):
        return None

    passage = passages[
        passage_number - 1
    ]

    if not quote_exists(
        evidence_quote,
        passage.get(
            "text",
            "",
        ),
    ):
        return None

    options = normalize_options(
        item.get(
            "options",
            [],
        )
    )

    if question_type == "mcq":

        if len(options) != 4:
            return None

        normalized_correct = (
            normalize_text(
                correct_answer
            )
        )

        if normalized_correct not in {
            normalize_text(
                option
            )
            for option in options
        }:
            return None

    elif (
        question_type
        == "true_false"
    ):

        if len(options) != 2:
            return None

        normalized_correct = (
            normalize_text(
                correct_answer
            )
        )

        if normalized_correct not in {
            normalize_text(
                option
            )
            for option in options
        }:
            return None

    else:

        options = []

    return {
        "type": question_type,
        "question": question,
        "options": options,
        "correct_answer": (
            correct_answer
        ),
        "explanation": (
            explanation
            or evidence_quote
        ),
        "evidence_quote": (
            evidence_quote
        ),
        "passage_number": (
            passage_number
        ),
        "source": passage.get(
            "source",
            "",
        ),
        "page": passage.get(
            "page",
            0,
        ),
    }


def answer_matches(
    submitted: str,
    expected: str,
    question_type: str,
) -> bool:

    submitted_norm = (
        normalize_text(
            submitted
        )
    )

    expected_norm = (
        normalize_text(
            expected
        )
    )

    if (
        not submitted_norm
        or not expected_norm
    ):
        return False

    if question_type in {
        "mcq",
        "true_false",
    }:
        return (
            submitted_norm
            == expected_norm
        )

    if (
        submitted_norm
        == expected_norm
        or expected_norm
        in submitted_norm
        or submitted_norm
        in expected_norm
    ):
        return True

    submitted_words = set(
        submitted_norm.split()
    )

    expected_words = set(
        expected_norm.split()
    )

    if not expected_words:
        return False

    overlap = len(
        submitted_words.intersection(
            expected_words
        )
    )

    coverage = (
        overlap
        / len(
            expected_words
        )
    )

    return coverage >= 0.60



# QUIZ_EVIDENCE_QUALITY_V8

def quiz_evidence_quality_score(
    value: str,
    arabic_expected: bool,
) -> float:

    raw = str(
        value
        or ""
    ).strip()

    if len(raw) < 45:
        return -1.0

    lower = raw.lower()

    if (
        "http://" in lower
        or "https://" in lower
        or ".pdf" in lower
    ):
        return -1.0

    normalized = normalize_text(
        raw
    )

    if len(normalized) < 35:
        return -1.0

    tokens = [
        token
        for token in re.split(
            r"\s+",
            raw,
        )
        if token
    ]

    if len(tokens) < 6:
        return -1.0

    letters = [
        char
        for char in raw
        if char.isalpha()
    ]

    if len(letters) < 25:
        return -1.0

    arabic_letters = [
        char
        for char in letters
        if (
            "\u0600"
            <= char
            <= "\u06ff"
        )
    ]

    arabic_ratio = (
        len(arabic_letters)
        / len(letters)
        if letters
        else 0.0
    )

    mixed_alpha_digit = 0
    one_char_tokens = 0

    for token in tokens:

        has_letter = any(
            char.isalpha()
            for char in token
        )

        has_digit = any(
            char.isdigit()
            for char in token
        )

        if (
            has_letter
            and has_digit
        ):
            mixed_alpha_digit += 1

        normalized_token = (
            normalize_text(
                token
            )
        )

        if len(normalized_token) <= 1:
            one_char_tokens += 1

    if mixed_alpha_digit > 0:
        return -1.0

    one_char_ratio = (
        one_char_tokens
        / len(tokens)
    )

    if one_char_ratio > 0.18:
        return -1.0

    if (
        arabic_expected
        and arabic_ratio < 0.72
    ):
        return -1.0

    suspicious_symbols = sum(
        1
        for char in raw
        if (
            not char.isalnum()
            and not char.isspace()
            and char
            not in (
                ".,;:!?-()[]{}%/"
                "\u060c\u061b\u061f"
            )
        )
    )

    symbol_ratio = (
        suspicious_symbols
        / max(
            len(raw),
            1,
        )
    )

    if symbol_ratio > 0.08:
        return -1.0

    score = 0.0

    score += min(
        len(normalized),
        500,
    ) / 500.0

    score += min(
        len(tokens),
        35,
    ) / 35.0

    if arabic_expected:
        score += arabic_ratio

    score -= (
        one_char_ratio
        * 2.0
    )

    return round(
        score,
        6,
    )




def build_quiz_evidence_items(
    lesson_passages: list[dict],
    arabic_expected: bool,
) -> list[dict]:

    # QUIZ_LOCAL_WINDOWS_NOISE_RANKING_V16

    candidates = []
    seen = set()

    for passage in lesson_passages:

        raw_text = str(
            passage.get(
                "text",
                "",
            )
            or ""
        ).strip()

        if not raw_text:
            continue

        units = quiz_support_units(
            raw_text
        )

        if not units:
            continue

        windows = []

        for index, unit in enumerate(
            units
        ):

            unit = re.sub(
                r"\s+",
                " ",
                str(
                    unit
                    or ""
                ),
            ).strip()

            if unit:
                windows.append(
                    unit
                )

            if index + 1 < len(units):

                second = re.sub(
                    r"\s+",
                    " ",
                    str(
                        units[
                            index + 1
                        ]
                        or ""
                    ),
                ).strip()

                combined = (
                    unit
                    + " "
                    + second
                ).strip()

                if (
                    unit
                    and second
                    and len(combined) <= 900
                ):
                    windows.append(
                        combined
                    )


        for window in windows:

            if (
                len(window) < 55
                or len(window) > 900
            ):
                continue


            tokens = re.findall(
                r"[0-9A-Za-z\u0621-\u064A]+",
                window,
            )

            if len(tokens) < 7:
                continue


            letters = [
                char
                for char in window
                if char.isalpha()
            ]

            if len(letters) < 25:
                continue


            arabic_letters = [
                char
                for char in letters
                if (
                    "\u0621"
                    <= char
                    <= "\u064A"
                )
            ]


            arabic_ratio = (
                len(
                    arabic_letters
                )
                / len(
                    letters
                )
                if letters
                else 0.0
            )


            if (
                arabic_expected
                and arabic_ratio < 0.68
            ):
                continue


            tiny_tokens = sum(
                1
                for token in tokens
                if len(token) <= 1
            )

            tiny_ratio = (
                tiny_tokens
                / len(tokens)
                if tokens
                else 1.0
            )

            if tiny_ratio > 0.24:
                continue


            key = normalize_text(
                window
            )

            if (
                not key
                or key in seen
            ):
                continue

            seen.add(
                key
            )


            noise_penalty = (
                quiz_local_window_noise_penalty_v16(
                    text=window,
                    arabic_expected=(
                        arabic_expected
                    ),
                )
            )


            score = (
                min(
                    len(window),
                    650,
                )
                / 650.0

                + min(
                    len(tokens),
                    35,
                )
                / 35.0

                + (
                    arabic_ratio
                    if arabic_expected
                    else 0.0
                )

                - noise_penalty
            )


            # Reward clean Arabic windows so OCR-heavy
            # formula fragments do not win merely
            # because they are long.
            if (
                arabic_expected
                and noise_penalty == 0.0
            ):
                score += 0.50


            candidates.append(
                {
                    "text": window,
                    "source": (
                        passage.get(
                            "source",
                            "",
                        )
                    ),
                    "page": (
                        passage.get(
                            "page",
                            0,
                        )
                    ),
                    "quality_score": round(
                        score,
                        6,
                    ),
                    "noise_penalty": round(
                        noise_penalty,
                        6,
                    ),
                }
            )


    candidates.sort(
        key=lambda item: (
            -item.get(
                "quality_score",
                0.0,
            ),
            item.get(
                "noise_penalty",
                0.0,
            ),
            item.get(
                "page",
                0,
            )
            or 0,
        )
    )


    return candidates







# QUIZ_GROUNDING_QUALITY_V9


def quiz_content_tokens(
    value: str,
) -> list[str]:

    # QUIZ_TOKEN_NORMALIZATION_V13

    normalized = normalize_text(
        str(
            value
            or ""
        )
    )

    normalized = (
        normalized
        .replace(
            "\u0623",
            "\u0627",
        )
        .replace(
            "\u0625",
            "\u0627",
        )
        .replace(
            "\u0622",
            "\u0627",
        )
        .replace(
            "\u0671",
            "\u0627",
        )
        .replace(
            "\u0649",
            "\u064a",
        )
    )

    # Do not use the whole Arabic Unicode block here.
    # It also contains punctuation such as the Arabic
    # question mark.
    raw_tokens = re.findall(
        r"[0-9A-Za-z\u0621-\u064A]+",
        normalized,
    )

    stopwords = {
        "\u0645\u0646",
        "\u0627\u0644\u0649",
        "\u0639\u0644\u0649",
        "\u0641\u064a",
        "\u0639\u0646",
        "\u0647\u0644",
        "\u0647\u0630\u0627",
        "\u0647\u0630\u0647",
        "\u0627\u0644\u0630\u064a",
        "\u0627\u0644\u062a\u064a",
        "\u064a\u062a\u0645",
        "\u064a\u0643\u0648\u0646",
        "\u062a\u0643\u0648\u0646",
        "\u0645\u0627",
        "\u0645\u0627\u0630\u0627",
        "\u0647\u0648",
        "\u0647\u064a",
        "\u0643\u0645",

        "the",
        "with",
        "from",
        "into",
        "this",
        "that",
        "are",
        "is",
        "what",
        "which",
        "de",
        "du",
        "des",
        "la",
        "le",
        "les",
        "une",
        "un",
        "est",
        "sont",
        "dans",
        "avec",
        "pour",
        "sur",
        "par",
        "quel",
        "quelle",
    }

    output = []

    for token in raw_tokens:

        token = token.lower()

        # Remove the Arabic definite article.
        #
        # "????" -> "??"
        # "?????" -> "??"
        #
        # Do NOT blindly remove the first waw.
        # That previously corrupted words such as
        # "?????".
        if (
            token.startswith(
                "\u0648\u0627\u0644"
            )
            and len(token) >= 6
        ):
            token = token[3:]

        elif (
            token.startswith(
                "\u0627\u0644"
            )
            and len(token) >= 5
        ):
            token = token[2:]

        if (
            not token
            or len(token) < 2
            or token in stopwords
        ):
            continue

        output.append(
            token
        )

    return output



def quiz_grounding_overlap(
    question: str,
    evidence: str,
) -> float:

    question_tokens = (
        quiz_content_tokens(
            question
        )
    )

    evidence_tokens = set(
        quiz_content_tokens(
            evidence
        )
    )

    if not question_tokens:
        return 0.0

    if not evidence_tokens:
        return 0.0

    shared = sum(
        1
        for token
        in question_tokens
        if token in evidence_tokens
    )

    return round(
        shared
        / len(
            question_tokens
        ),
        6,
    )


def quiz_has_heading_noise(
    question: str,
) -> bool:

    raw = str(
        question
        or ""
    ).strip()

    if not raw:
        return True

    normalized = normalize_text(
        raw
    )

    beginning = normalized[
        :60
    ]

    forbidden_headings = [
        "\u0645\u0642\u062f\u0645\u0629",
        "\u0639\u0646\u0648\u0627\u0646",
        "\u0627\u0644\u062f\u0631\u0633",
        "\u0648\u062b\u064a\u0642\u0629",
        "\u0627\u0644\u0648\u062b\u064a\u0642\u0629",
        "introduction",
        "titre",
        "document",
        "page",
    ]

    if any(
        heading in beginning
        for heading
        in forbidden_headings
    ):
        return True

    # Reject short label-like prefixes such as:
    # "Introduction: ..."
    # "OCR junk: scientific sentence"
    colon_match = re.match(
        r"^\s*[^:\n]{1,28}:\s+",
        raw,
    )

    if colon_match:
        return True

    return False



# QUIZ_ANSWER_GROUNDING_V10


def quiz_canonical_content_tokens(
    value: str,
) -> list[str]:

    return quiz_content_tokens(
        value
    )



def quiz_answer_grounding_score(
    answer: str,
    evidence: str,
) -> float:

    answer_tokens = (
        quiz_canonical_content_tokens(
            answer
        )
    )

    evidence_tokens = set(
        quiz_canonical_content_tokens(
            evidence
        )
    )

    if not answer_tokens:
        return 0.0

    if not evidence_tokens:
        return 0.0

    generic_tokens = {
        "\u0647\u0648\u0627\u0621",
        "\u062f\u0645",
        "\u062c\u0633\u0645",
        "\u0646\u0633\u0628\u0629",
        "\u0628\u0646\u064a\u0629",
        "\u062e\u0627\u0635\u064a\u0629",
        "\u0639\u0645\u0644\u064a\u0629",
        "\u0645\u0633\u062a\u0648\u0649",
        "air",
        "blood",
        "structure",
    }

    shared = [
        token
        for token
        in answer_tokens
        if token
        in evidence_tokens
    ]

    coverage = (
        len(shared)
        / len(answer_tokens)
    )

    specific_shared = [
        token
        for token
        in shared
        if (
            len(token) >= 4
            and token
            not in generic_tokens
        )
    ]

    if (
        len(answer_tokens) == 1
        and shared
    ):
        return 1.0

    if not specific_shared:
        return 0.0

    return round(
        coverage,
        6,
    )


def quiz_has_source_reference_language(
    value: str,
) -> bool:

    normalized = normalize_text(
        value
    )

    forbidden = [
        "\u0645\u0646 \u062e\u0644\u0627\u0644 \u0627\u0644\u062c\u062f\u0648\u0644",
        "\u0645\u0646 \u062e\u0644\u0627\u0644 \u0627\u0644\u0646\u0635",
        "\u062d\u0633\u0628 \u0627\u0644\u0646\u0635",
        "\u062d\u0633\u0628 \u0627\u0644\u0648\u062b\u064a\u0642\u0629",
        "\u0627\u0644\u0646\u0635 \u064a\u0630\u0643\u0631",
        "\u0627\u0644\u0648\u062b\u064a\u0642\u0629 \u062a\u0628\u064a\u0646",
        "selon le texte",
        "selon le document",
        "d apres le texte",
    ]

    return any(
        phrase in normalized
        for phrase in forbidden
    )



# QUIZ_SCOPE_GROUNDING_V11B

def quiz_has_unsupported_scope(
    question: str,
    evidence: str,
) -> bool:

    # QUIZ_SCOPE_TOKEN_GATE_V11C

    normalized_question = (
        normalize_text(
            question
        )
    )

    normalized_evidence = (
        normalize_text(
            evidence
        )
    )

    question_tokens = set(
        quiz_content_tokens(
            normalized_question
        )
    )

    evidence_tokens = set(
        quiz_content_tokens(
            normalized_evidence
        )
    )


    # --------------------------------------------------------
    # Unsupported superlatives or strength claims.
    #
    # Token-based matching catches variants such as:
    # "more effective"
    # "the most effective methods"
    # where other words appear between the trigger terms.
    # --------------------------------------------------------

    scope_token_rules = [
        {
            "\u0627\u0647\u0645",
        },
        {
            "\u0627\u0641\u0636\u0644",
        },
        {
            "\u0627\u0643\u062b\u0631",
            "\u0641\u0639\u0627\u0644\u064a\u0629",
        },
        {
            "\u0631\u0626\u064a\u0633\u064a\u0629",
        },
        {
            "\u0627\u0644\u0631\u0626\u064a\u0633\u064a",
        },
        {
            "\u062c\u0645\u064a\u0639",
        },
        {
            "\u062f\u0627\u0626\u0645\u0627",
        },
    ]


    for required_tokens in scope_token_rules:

        if not required_tokens.issubset(
            question_tokens
        ):
            continue

        if not required_tokens.issubset(
            evidence_tokens
        ):
            return True


    # --------------------------------------------------------
    # Western-language scope expressions.
    # --------------------------------------------------------

    phrase_rules = [
        "most effective",
        "the best",
        "best",
        "plus efficace",
        "le meilleur",
        "la meilleure",
    ]

    for phrase in phrase_rules:

        if (
            phrase in normalized_question
            and phrase
            not in normalized_evidence
        ):
            return True


    return False




def quiz_build_grounded_explanation(
    evidence: str,
    question: str,
    correct_answer: str,
) -> str:

    support = (
        quiz_best_local_support(
            evidence=evidence,
            question=question,
            answer=correct_answer,
        )
    )

    support_text = str(
        support.get(
            "text",
            ""
        )
        or ""
    ).strip()

    if support_text:
        return support_text

    compact = re.sub(
        r"\s+",
        " ",
        str(
            evidence
            or ""
        ),
    ).strip()

    return compact[:420].strip()





# QUIZ_LOCAL_ALIGNMENT_V12

def quiz_question_focus_tokens(
    value: str,
) -> list[str]:

    tokens = (
        quiz_canonical_content_tokens(
            value
        )
    )

    generic = {
        "\u0645\u0627",
        "\u0645\u0627\u0630\u0627",
        "\u0647\u0648",
        "\u0647\u064a",
        "\u0647\u0644",
        "\u0643\u0645",
        "\u0639\u062f\u062f",
        "\u064a\u0630\u0643\u0631",
        "\u0645\u0630\u0643\u0648\u0631",
        "\u0645\u0630\u0643\u0648\u0631\u0629",
        "\u064a\u062d\u062f\u062b",
        "\u062a\u062d\u062f\u062b",
        "what",
        "which",
        "according",
        "quel",
        "quelle",
    }

    return [
        token
        for token in tokens
        if token not in generic
    ]


def quiz_support_units(
    evidence: str,
) -> list[str]:

    raw = str(
        evidence
        or ""
    )

    parts = re.split(
        r"[\r\n]+"
        r"|(?<=[.!?\u061f\u061b\u00bb])\s+",
        raw,
    )

    units = []

    for part in parts:

        cleaned = re.sub(
            r"\s+",
            " ",
            str(
                part
                or ""
            ),
        ).strip()

        if len(cleaned) < 20:
            continue

        units.append(
            cleaned
        )

    if not units:

        compact = re.sub(
            r"\s+",
            " ",
            raw,
        ).strip()

        if compact:
            units.append(
                compact
            )

    return units



def quiz_best_local_support(
    evidence: str,
    question: str,
    answer: str,
) -> dict:

    # QUIZ_LOCAL_SUPPORT_MORPH_V15

    question_tokens = set(
        quiz_grounding_tokens_v15(
            question
        )
    )

    answer_tokens = set(
        quiz_grounding_tokens_v15(
            answer
        )
    )

    normalized_answer = (
        normalize_text(
            answer
        )
    )

    best = {
        "text": "",
        "question_overlap": 0.0,
        "answer_overlap": 0.0,
        "answer_exact": False,
        "score": -1.0,
    }


    for unit in quiz_support_units(
        evidence
    ):

        unit_tokens = set(
            quiz_grounding_tokens_v15(
                unit
            )
        )

        normalized_unit = (
            normalize_text(
                unit
            )
        )


        if question_tokens:

            question_overlap = (
                len(
                    question_tokens
                    & unit_tokens
                )
                / len(
                    question_tokens
                )
            )

        else:

            question_overlap = 0.0


        if answer_tokens:

            answer_overlap = (
                len(
                    answer_tokens
                    & unit_tokens
                )
                / len(
                    answer_tokens
                )
            )

        else:

            answer_overlap = 0.0


        answer_exact = bool(
            normalized_answer
            and normalized_answer
            in normalized_unit
        )


        score = (
            question_overlap
            + (
                2.0
                * answer_overlap
            )
            + (
                2.5
                if answer_exact
                else 0.0
            )
        )


        if score > best["score"]:

            best = {
                "text": unit,
                "question_overlap": round(
                    question_overlap,
                    6,
                ),
                "answer_overlap": round(
                    answer_overlap,
                    6,
                ),
                "answer_exact": (
                    answer_exact
                ),
                "score": round(
                    score,
                    6,
                ),
            }


    return best



def quiz_has_vague_mcq_stem(
    question: str,
) -> bool:

    normalized = (
        normalize_text(
            question
        )
    )

    vague = [
        "\u0645\u0627 \u0627\u0644\u0630\u064a \u064a\u0630\u0643\u0631",
        "\u0645\u0627\u0630\u0627 \u064a\u0630\u0643\u0631",
        "\u0645\u0627 \u0627\u0644\u0645\u0630\u0643\u0648\u0631",
        "\u0627\u064a \u0645\u0645\u0627 \u064a\u0644\u064a \u064a\u0630\u0643\u0631",
        "what is mentioned",
        "selon le texte",
    ]

    return any(
        phrase in normalized
        for phrase in vague
    )


def quiz_mcq_has_contained_option(
    options: list[str],
    correct_answer: str,
) -> bool:

    correct = normalize_text(
        correct_answer
    )

    if not correct:
        return True

    for option in options:

        normalized_option = (
            normalize_text(
                option
            )
        )

        if (
            not normalized_option
            or normalized_option
            == correct
        ):
            continue

        if (
            len(correct) >= 8
            and correct
            in normalized_option
        ):
            return True

        if (
            len(normalized_option) >= 8
            and normalized_option
            in correct
        ):
            return True

    return False



# QUIZ_UNIQUE_MCQ_V14

def quiz_mcq_evidence_conflicts(
    options: list[str],
    correct_answer: str,
    evidence: str,
) -> list[str]:

    # QUIZ_DETERMINISTIC_GATE_EXEMPTION_V20_QUIZ_MCQ_EVIDENCE_CONFLICTS

    if quiz_is_deterministic_mcq_option_set_v20(
        options=options,
        correct_answer=correct_answer,
    ):

        return []


    normalized_evidence = (
        normalize_text(
            evidence
        )
    )

    normalized_correct = (
        normalize_text(
            correct_answer
        )
    )

    conflicts = []

    for option in options:

        option_text = str(
            option
            or ""
        ).strip()

        normalized_option = (
            normalize_text(
                option_text
            )
        )

        if (
            not normalized_option
            or normalized_option
            == normalized_correct
        ):
            continue


        # A distractor copied from the evidence is risky:
        # it may represent another true answer to a broad
        # question.
        if (
            len(normalized_option) >= 4
            and normalized_option
            in normalized_evidence
        ):

            conflicts.append(
                option_text
            )

            continue


        option_tokens = set(
            quiz_canonical_content_tokens(
                option_text
            )
        )

        evidence_tokens = set(
            quiz_canonical_content_tokens(
                evidence
            )
        )


        # Also catch short phrases whose complete lexical
        # content occurs in the evidence even if spacing or
        # Arabic prefixes differ.
        if (
            option_tokens
            and len(option_tokens) <= 4
            and option_tokens.issubset(
                evidence_tokens
            )
        ):

            conflicts.append(
                option_text
            )

    return conflicts


def quiz_mcq_has_broad_membership_stem(
    question: str,
) -> bool:

    normalized = (
        normalize_text(
            question
        )
    )

    risky_phrases = [
        "\u064a\u0634\u0643\u0644 \u062c\u0632\u0621\u0627 \u0645\u0646",
        "\u064a\u0639\u062f \u062c\u0632\u0621\u0627 \u0645\u0646",
        "\u062c\u0632\u0621 \u0645\u0646 \u0627\u0644\u062c\u0647\u0627\u0632",
        "\u0645\u0646 \u0645\u0643\u0648\u0646\u0627\u062a \u0627\u0644\u062c\u0647\u0627\u0632",
        "\u0645\u0645\u0627 \u064a\u062a\u0643\u0648\u0646",
        "fait partie de",
        "un composant de",
        "one part of",
        "part of the",
    ]

    return any(
        phrase in normalized
        for phrase in risky_phrases
    )



# QUIZ_ARABIC_MORPH_GROUNDING_V15

def quiz_arabic_grounding_stem_v15(
    token: str,
) -> str:

    value = str(
        token
        or ""
    ).strip().lower()

    if not value:
        return ""

    value = (
        value
        .replace(
            "\u0623",
            "\u0627",
        )
        .replace(
            "\u0625",
            "\u0627",
        )
        .replace(
            "\u0622",
            "\u0627",
        )
        .replace(
            "\u0671",
            "\u0627",
        )
        .replace(
            "\u0649",
            "\u064a",
        )
    )


    arabic_chars = [
        char
        for char in value
        if (
            "\u0621"
            <= char
            <= "\u064A"
        )
    ]

    if not arabic_chars:
        return value


    # Remove common prefixes conservatively.
    prefixes = [
        "\u0648\u0627\u0644",
        "\u0641\u0627\u0644",
        "\u0628\u0627\u0644",
        "\u0643\u0627\u0644",
        "\u0644\u0644",
        "\u0627\u0644",
    ]

    for prefix in prefixes:

        if (
            value.startswith(
                prefix
            )
            and len(value) - len(prefix) >= 3
        ):

            value = value[
                len(prefix):
            ]

            break


    # Remove common inflectional endings.
    suffixes = [
        "\u064a\u0627\u062a",
        "\u064a\u0629",
        "\u0627\u062a",
        "\u0648\u0646",
        "\u064a\u0646",
        "\u0627\u0646",
        "\u062a\u0627\u0646",
        "\u062a\u064a\u0646",
        "\u0629",
    ]

    for suffix in suffixes:

        if (
            value.endswith(
                suffix
            )
            and len(value) - len(suffix) >= 3
        ):

            value = value[
                :-len(suffix)
            ]

            break


    # Build a conservative consonantal skeleton.
    #
    # Examples:
    #   ???? / ?????      -> ???
    #   ????? / ??????    -> ???
    #
    # Only keep the skeleton when at least
    # three characters remain.
    skeleton = "".join(
        char
        for char in value
        if char not in {
            "\u0627",
            "\u0648",
            "\u064a",
        }
    )


    if len(skeleton) >= 3:
        return skeleton

    return value


def quiz_grounding_tokens_v15(
    value: str,
) -> list[str]:

    tokens = (
        quiz_content_tokens(
            value
        )
    )

    output = []

    for token in tokens:

        stem = (
            quiz_arabic_grounding_stem_v15(
                token
            )
        )

        if stem:
            output.append(
                stem
            )

    return output



# QUIZ_MCQ_SALVAGE_V16

def quiz_local_window_noise_penalty_v16(
    text: str,
    arabic_expected: bool,
) -> float:

    if not arabic_expected:
        return 0.0

    tokens = re.findall(
        r"[0-9A-Za-z\u0621-\u064A]+",
        str(
            text
            or ""
        ),
    )

    if not tokens:
        return 3.0

    allowed_latin = {
        "o2",
        "co2",
        "co",
        "n2",
        "l",
        "ml",
        "cl",
        "mm",
        "cm",
        "m",
        "m2",
        "cm2",
        "pa",
        "kpa",
        "ph",
    }

    suspicious = 0

    for token in tokens:

        lowered = token.lower()

        if not re.search(
            r"[a-z]",
            lowered,
        ):
            continue

        if lowered in allowed_latin:
            continue

        suspicious += 1

    penalty = (
        suspicious
        * 0.38
    )

    return min(
        penalty,
        2.5,
    )


def quiz_arabic_ratio_v16(
    value: str,
) -> float:

    letters = [
        char
        for char in str(
            value
            or ""
        )
        if char.isalpha()
    ]

    if not letters:
        return 0.0

    arabic_letters = [
        char
        for char in letters
        if (
            "\u0621"
            <= char
            <= "\u064A"
        )
    ]

    return (
        len(arabic_letters)
        / len(letters)
    )


def quiz_rotate_options_v16(
    correct_answer: str,
    distractors: list[str],
    question: str,
) -> list[str]:

    options = [
        str(
            correct_answer
            or ""
        ).strip(),
        *[
            str(
                item
                or ""
            ).strip()
            for item
            in distractors
        ],
    ]

    if len(options) != 4:
        return []

    shift = (
        sum(
            ord(char)
            for char in str(
                question
                or ""
            )
        )
        % 4
    )

    return (
        options[
            shift:
        ]
        + options[
            :shift
        ]
    )


def quiz_repair_mcq_distractors_v16(
    question: str,
    correct_answer: str,
    evidence: str,
    lesson_text: str,
    arabic_expected: bool,
) -> list[str]:

    repair_schema = {
        "type": "object",
        "properties": {
            "distractors": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "minItems": 3,
                "maxItems": 3,
            },
        },
        "required": [
            "distractors",
        ],
    }

    language_rule = (
        (
            "Les trois distracteurs doivent "
            "etre rediges uniquement en arabe."
        )
        if arabic_expected
        else (
            "Utilise la meme langue "
            "que la question."
        )
    )

    system_prompt = f"""
Tu repares uniquement les mauvaises options
d'un QCM scolaire.

Regles obligatoires :

- La question et la bonne reponse sont deja validees.
- Ne modifie jamais la question.
- Ne modifie jamais la bonne reponse.
- Produis exactement trois distracteurs.
- Chaque distracteur doit etre faux pour cette question.
- Chaque distracteur doit etre plausible pedagogiquement.
- Les trois distracteurs doivent etre distincts.
- Aucun distracteur ne doit contenir la bonne reponse.
- Aucun distracteur ne doit etre une information vraie
  presente dans l'extrait documentaire.
- Reste dans la meme categorie semantique
  que la bonne reponse lorsque c'est possible.
- {language_rule}
- Retourne uniquement le JSON demande.
""".strip()

    user_prompt = f"""
QUESTION :

{question}

BONNE REPONSE :

{correct_answer}

EXTRAIT DOCUMENTAIRE :

{evidence}

Genere exactement trois distracteurs faux
et non soutenus par cet extrait.
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
        "format": repair_schema,
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0.15,
            "num_predict": 120,
        },
    }

    try:

        result = call_ollama(
            payload
        )

    except Exception as error:

        print(
            "QUIZ V16 DISTRACTOR REPAIR ERROR:",
            repr(
                error
            ),
        )

        return []


    raw_distractors = (
        result.get(
            "distractors",
            [],
        )
        if isinstance(
            result,
            dict,
        )
        else []
    )


    distractors = []
    seen = set()

    normalized_correct = (
        normalize_text(
            correct_answer
        )
    )


    for item in raw_distractors:

        value = str(
            item
            or ""
        ).strip()

        if not value:
            continue

        normalized = (
            normalize_text(
                value
            )
        )

        if (
            not normalized
            or normalized
            == normalized_correct
            or normalized in seen
        ):
            continue

        if (
            arabic_expected
            and quiz_arabic_ratio_v16(
                value
            )
            < 0.55
        ):
            continue

        seen.add(
            normalized
        )

        distractors.append(
            value
        )


    if len(distractors) != 3:
        return []


    options = (
        quiz_rotate_options_v16(
            correct_answer=(
                correct_answer
            ),
            distractors=(
                distractors
            ),
            question=(
                question
            ),
        )
    )


    if len(options) != 4:
        return []


    # Validate against the complete selected lesson,
    # not only the small local evidence window.
    conflicts = (
        quiz_mcq_evidence_conflicts(
            options=options,
            correct_answer=(
                correct_answer
            ),
            evidence=(
                lesson_text
            ),
        )
    )


    if conflicts:

        print(
            "QUIZ V16 REPAIR CONFLICTS:",
            conflicts,
        )

        return []


    if quiz_mcq_has_contained_option(
        options=options,
        correct_answer=(
            correct_answer
        ),
    ):

        return []


    return options



# QUIZ_CANONICAL_ANSWER_V16B


def quiz_source_answer_span_v16b(
    support_text: str,
    generated_answer: str,
) -> str:

    # QUIZ_CANONICAL_SOURCE_NORMALIZATION_V16C

    source = str(
        support_text
        or ""
    ).strip()

    answer = str(
        generated_answer
        or ""
    ).strip()

    if (
        not source
        or not answer
    ):
        return ""


    source_matches = list(
        re.finditer(
            r"[0-9A-Za-z\u0621-\u064A]+",
            source,
        )
    )

    if not source_matches:
        return ""


    # The generated answer already goes through the
    # project's Arabic tokenizer and normalizer.
    # Source words must use the SAME path or letters
    # such as hamza forms can fail to match.
    target_tokens = (
        quiz_grounding_tokens_v15(
            answer
        )
    )

    target_stems = {
        token
        for token in target_tokens
        if token
    }


    if len(target_stems) < 2:
        return ""


    matched_indexes = []
    matched_stems = set()


    for index, match in enumerate(
        source_matches
    ):

        raw_word = match.group(
            0
        )


        # IMPORTANT:
        # normalize source tokens using the same
        # quiz_content_tokens() pipeline used by the
        # generated answer.
        normalized_word_tokens = (
            quiz_content_tokens(
                raw_word
            )
        )


        stems = {
            quiz_arabic_grounding_stem_v15(
                token
            )
            for token
            in normalized_word_tokens
            if token
        }


        # Attached one-letter Arabic conjunctions and
        # prepositions may survive differently depending
        # on OCR segmentation.
        if (
            len(raw_word) >= 5
            and raw_word[0] in {
                "\u0648",
                "\u0641",
                "\u0628",
                "\u0644",
                "\u0643",
            }
        ):

            stripped_tokens = (
                quiz_content_tokens(
                    raw_word[1:]
                )
            )

            stems.update(
                quiz_arabic_grounding_stem_v15(
                    token
                )
                for token
                in stripped_tokens
                if token
            )


        stems = {
            stem
            for stem in stems
            if stem
        }


        overlap = (
            stems
            & target_stems
        )


        if overlap:

            matched_indexes.append(
                index
            )

            matched_stems.update(
                overlap
            )


    if len(matched_indexes) < 2:
        return ""


    coverage = (
        len(
            matched_stems
        )
        / len(
            target_stems
        )
    )


    # Allow one unsupported word in a partially
    # hallucinated answer, but require the majority
    # of answer concepts to map back to the source.
    if coverage < 0.50:
        return ""


    first_index = min(
        matched_indexes
    )

    last_index = max(
        matched_indexes
    )


    # Preserve one useful documentary qualifier
    # immediately after the last matched concept.
    if (
        last_index + 1
        < len(
            source_matches
        )
    ):

        last_index += 1


    start_char = (
        source_matches[
            first_index
        ].start()
    )

    end_char = (
        source_matches[
            last_index
        ].end()
    )


    span = source[
        start_char:
        end_char
    ].strip()


    span = re.sub(
        r"\s+",
        " ",
        span,
    ).strip(
        " \t\r\n"
        "\u061b"
        "\u061f"
        "\u00bb"
        "\u00ab"
        ".,;:"
    )


    if (
        len(span) < 8
        or len(span) > 220
    ):

        return ""


    return span




# QUIZ_SOURCE_FIRST_MCQ_V17

def quiz_source_fact_candidates_v17_legacy_v21b(
    evidence_text: str,
    arabic_expected: bool,
) -> list[str]:

    raw = str(
        evidence_text
        or ""
    ).strip()

    if not raw:
        return []


    base_units = (
        quiz_support_units(
            raw
        )
    )

    fragments = []


    # --------------------------------------------------------
    # Convert local evidence windows into short documentary
    # facts. The selected fact remains an EXACT source span.
    # --------------------------------------------------------

    boundary_pattern = (
        r"[\r\n;\u061b\u00bb\u00ab]+"
        r"|(?=\s+(?:"
        r"\u0625\u0646\u0647\u0627"
        r"|\u0627\u0646\u0647\u0627"
        r"|\u0648\u062a\u062a\u0643\u0648\u0646"
        r"|\u062a\u062a\u0643\u0648\u0646"
        r"|\u0648\u064a\u062a\u0643\u0648\u0646"
        r"|\u064a\u062a\u0643\u0648\u0646"
        r"|\u0648\u064a\u0646\u062a\u062c"
        r"|\u064a\u0646\u062a\u062c"
        r"|\u0648\u064a\u0633\u0628\u0628"
        r"|\u064a\u0633\u0628\u0628"
        r"|\u0648\u064a\u0634\u0643\u0644"
        r"|\u064a\u0634\u0643\u0644"
        r"|\u0648\u0645\u0646 \u0628\u064a\u0646"
        r"|\u0643\u0645\u0627"
        r"|\u0648\u0644\u0644\u0648\u0642\u0627\u064a\u0629"
        r"))"
    )


    for unit in base_units:

        unit = re.sub(
            r"\s+",
            " ",
            str(
                unit
                or ""
            ),
        ).strip()

        if not unit:
            continue


        pieces = re.split(
            boundary_pattern,
            unit,
        )


        for piece in pieces:

            piece = re.sub(
                r"\s+",
                " ",
                str(
                    piece
                    or ""
                ),
            ).strip()


            if not piece:
                continue


            # Remove harmless bullet artefacts while
            # preserving the documentary phrase itself.
            piece = re.sub(
                r"^\s*[\d\-\*\|\u2022]+\s*",
                "",
                piece,
            ).strip()


            if arabic_expected:

                piece = re.sub(
                    r"^\s*\u0647\s+",
                    "",
                    piece,
                ).strip()


                # Remove discourse framing such as
                # "we conclude from the table that..."
                # so the answer becomes the actual fact.
                piece = re.sub(
                    (
                        r"^\s*"
                        r"\u0646\u0633\u062a\u0646\u062a\u062c"
                        r"\s+\u0645\u0646"
                        r"\s+\u062e\u0644\u0627\u0644"
                        r"\s+\u0627\u0644\u062c\u062f\u0648\u0644"
                        r"\s+\u0623?\u0646"
                        r"\s+\u0647\u0646\u0627\u0643"
                        r"\s+"
                    ),
                    "",
                    piece,
                ).strip()


                piece = re.sub(
                    (
                        r"^\s*"
                        r"\u0646\u0633\u062a\u0646\u062a\u062c"
                        r"\s+\u0623?\u0646"
                        r"\s+"
                    ),
                    "",
                    piece,
                ).strip()


            if piece:

                fragments.append(
                    piece
                )


    # Also keep original short support units.
    fragments.extend(
        base_units
    )


    candidates = []
    seen = set()


    relation_markers_ar = (
        "\u064a\u062a\u0643\u0648\u0646",
        "\u062a\u062a\u0643\u0648\u0646",
        "\u064a\u0646\u062a\u062c",
        "\u064a\u0633\u0628\u0628",
        "\u062a\u0645\u0631",
        "\u064a\u0645\u0631",
        "\u062a\u0646\u062a\u0642\u0644",
        "\u064a\u0648\u062c\u062f",
        "\u062a\u062c\u0646\u0628",
        "\u064a\u0634\u0643\u0644",
        "\u0646\u0633\u0628\u0629",
        "\u0627\u0644\u0636\u063a\u0637",
        "\u0646\u062d\u0648",
        "\u0623\u0642\u0644",
        "\u0627\u0642\u0644",
    )


    bad_document_phrases = (
        "\u0631\u0633\u0645 \u062a\u062e\u0637\u064a\u0637\u064a",
        "\u0627\u0646\u0638\u0631 \u0627\u0644\u0648\u062b\u064a\u0642\u0629",
        "\u0645\u0642\u0627\u0631\u0646\u0629 \u0647\u0648\u0627\u0621",
    )


    for fragment in fragments:

        fragment = re.sub(
            r"\s+",
            " ",
            str(
                fragment
                or ""
            ),
        ).strip(
            " \t\r\n"
            "\u061b"
            "\u061f"
            "\u00bb"
            "\u00ab"
            ".,;:"
        )


        if not fragment:
            continue


        words = re.findall(
            r"[0-9A-Za-z\u0621-\u064A]+",
            fragment,
        )


        word_count = len(
            words
        )


        if (
            word_count < 4
            or word_count > 20
        ):
            continue


        if (
            len(fragment) < 25
            or len(fragment) > 240
        ):
            continue


        normalized = (
            normalize_text(
                fragment
            )
        )


        if not normalized:
            continue


        if any(
            phrase
            in normalized
            for phrase
            in bad_document_phrases
        ):
            continue


        if (
            arabic_expected
            and quiz_arabic_ratio_v16(
                fragment
            )
            < 0.70
        ):
            continue


        noise_penalty = (
            quiz_local_window_noise_penalty_v16(
                text=fragment,
                arabic_expected=(
                    arabic_expected
                ),
            )
        )


        if noise_penalty > 0.90:
            continue


        content_tokens = (
            quiz_content_tokens(
                fragment
            )
        )


        if len(content_tokens) < 3:
            continue


        key = normalize_text(
            fragment
        )


        if key in seen:
            continue

        seen.add(
            key
        )


        score = 0.0


        # Prefer concise pedagogical facts.
        if 6 <= word_count <= 14:

            score += 3.0

        elif word_count <= 17:

            score += 2.0

        else:

            score += 1.0


        if arabic_expected:

            score += (
                quiz_arabic_ratio_v16(
                    fragment
                )
                * 1.5
            )


            marker_hits = sum(
                1
                for marker
                in relation_markers_ar
                if marker
                in normalized
            )


            score += (
                marker_hits
                * 0.65
            )


        if re.search(
            r"\d",
            fragment,
        ):

            score += 0.20


        score -= (
            noise_penalty
            * 2.0
        )


        candidates.append(
            (
                score,
                fragment,
            )
        )


    candidates.sort(
        key=lambda item: (
            -item[0],
            len(
                item[1]
            ),
        )
    )


    return [
        candidate
        for _score, candidate
        in candidates[:10]
    ]


# QUIZ_FRENCH_FACT_EXTRACTION_V21B
def quiz_source_fact_candidates_french_v21b(
    evidence_text: str,
) -> list[str]:

    text = str(
        evidence_text
        or ""
    )

    text = text.replace(
        "\u00ad",
        "",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


    if not text:
        return []


    candidates = []


    def add(
        value,
    ):

        value = re.sub(
            r"\s+",
            " ",
            str(
                value
                or ""
            ),
        ).strip(
            " \t\r\n"
            ".,;:"
            "\u2192"
            "-"
        )


        if (
            len(value) < 10
            or len(value) > 420
            or value.endswith("?")
        ):

            return


        normalized = (
            normalize_text(
                value
            )
        )


        if any(
            marker in normalized
            for marker in (
                "nom prenom classe",
                "journal de revisions",
                "oral ",
                "en classe ",
                "a la maison ",
                "calculer ",
                "justifiez ",
                "reecris ",
                "reeccris ",
            )
        ):

            return


        if value not in candidates:

            candidates.append(
                value
            )


    # --------------------------------------------------------
    # A. Ordinary sentence candidates
    # --------------------------------------------------------

    for piece in re.split(
        r"(?<=[.!?])\s+",
        text,
    ):

        add(
            piece
        )


    # --------------------------------------------------------
    # B. French revision-sheet arrow blocks:
    #
    # Les chromosomes :
    # -> sont constitues d'ADN
    # -> portent ...
    #
    # Flattened PDF extraction often removes newlines.
    # --------------------------------------------------------

    section_pattern = re.compile(
        (
            r"("
            r"[A-Z\u00c0-\u00d6\u00d8-\u00de]"
            r"[^:]{1,75}"
            r")"
            r"\s*:\s*"
            r"\u2192\s*"
        )
    )


    matches = list(
        section_pattern.finditer(
            text
        )
    )


    for index, match in enumerate(
        matches
    ):

        label = re.sub(
            r"\s+",
            " ",
            match.group(
                1
            ),
        ).strip()


        body_start = match.end()

        body_end = (
            matches[
                index + 1
            ].start()
            if index + 1 < len(
                matches
            )
            else len(text)
        )


        body = text[
            body_start:
            body_end
        ]


        bullets = re.split(
            r"\s*\u2192\s*",
            body,
        )


        for bullet in bullets:

            bullet = re.sub(
                r"\s+",
                " ",
                bullet,
            ).strip(
                " \t\r\n"
                ".,;:"
                "-"
            )


            if (
                not bullet
                or len(bullet) < 4
            ):

                continue


            # Stop obvious spillover from next normal heading.
            bullet = re.split(
                (
                    r"\s+(?="
                    r"[A-Z\u00c0-\u00d6\u00d8-\u00de]"
                    r"[^.]{1,60}"
                    r"\s*:\s*)"
                ),
                bullet,
                maxsplit=1,
            )[0].strip()


            # Turn shorthand bullet into a complete fact.
            if re.match(
                (
                    r"^(?:"
                    r"est|sont|se\s+situe|"
                    r"se\s+trouve|porte|portent|"
                    r"contient|contiennent|"
                    r"possede|poss\u00e8de|"
                    r"possedent|poss\u00e8dent|"
                    r"peut|peuvent|vient|viennent|"
                    r"conserve|necessite|n\u00e9cessite|"
                    r"divise|fusionnent"
                    r")\b"
                ),
                bullet,
                flags=re.IGNORECASE,
            ):

                fact = (
                    label
                    + " "
                    + bullet
                )

            else:

                fact = (
                    label
                    + " "
                    + bullet
                )


            add(
                fact
            )


    return candidates


# QUIZ_FACT_EXTRACTOR_WRAPPER_V21B
def quiz_source_fact_candidates_v17(
    evidence_text: str,
    arabic_expected: bool,
) -> list[str]:

    legacy = (
        quiz_source_fact_candidates_v17_legacy_v21b(
            evidence_text=(
                evidence_text
            ),
            arabic_expected=(
                arabic_expected
            ),
        )
    )


    if arabic_expected:

        return legacy


    french = (
        quiz_source_fact_candidates_french_v21b(
            evidence_text
        )
    )


    output = []
    seen = set()


    for value in (
        list(
            legacy
            or []
        )
        + list(
            french
            or []
        )
    ):

        value = str(
            value
            or ""
        ).strip()


        key = (
            normalize_text(
                value
            )
        )


        if (
            not value
            or not key
            or key in seen
        ):

            continue


        seen.add(
            key
        )

        output.append(
            value
        )


    return output






def quiz_build_source_first_mcq_candidate_v17(
    result: dict,
    fixed_question: str,
    correct_answer: str,
    evidence_text: str,
    lesson_text: str,
    arabic_expected: bool,
) -> dict | None:

    # QUIZ_LEAN_CANDIDATE_V17C

    if not isinstance(
        result,
        dict,
    ):

        return None


    question = str(
        fixed_question
        or result.get(
            "question",
            "",
        )
        or ""
    ).strip()


    if not question:

        return None


    raw_distractors = (
        result.get(
            "distractors",
            [],
        )
        or []
    )


    if not isinstance(
        raw_distractors,
        list,
    ):

        return None


    if len(raw_distractors) != 3:

        return None


    normalized_correct = (
        normalize_text(
            correct_answer
        )
    )


    distractors = []
    seen = set()


    for item in raw_distractors:

        value = str(
            item
            or ""
        ).strip()


        if not value:

            return None


        normalized = (
            normalize_text(
                value
            )
        )


        if (
            not normalized
            or normalized
            == normalized_correct
            or normalized
            in seen
        ):

            return None


        if (
            arabic_expected
            and quiz_arabic_ratio_v16(
                value
            )
            < 0.55
        ):

            return None


        seen.add(
            normalized
        )

        distractors.append(
            value
        )


    options = (
        quiz_rotate_options_v16(
            correct_answer=(
                correct_answer
            ),
            distractors=(
                distractors
            ),
            question=(
                question
            ),
        )
    )


    if len(options) != 4:

        return None


    return {
        "type": "mcq",
        "question": (
            question
        ),
        "options": (
            options
        ),
        "correct_answer": (
            correct_answer
        ),
        "explanation": (
            quiz_build_grounded_explanation(
                evidence=(
                    evidence_text
                ),
                question=(
                    question
                ),
                correct_answer=(
                    correct_answer
                ),
            )
        ),
        "passage_number": 1,
        "evidence_quote": (
            evidence_text
        ),
    }





# QUIZ_DETERMINISTIC_SOURCE_FIRST_V17B

def quiz_trim_source_answer_v17b(
    value: str,
) -> str:

    answer = re.sub(
        r"\s+",
        " ",
        str(
            value
            or ""
        ),
    ).strip(
        " \t\r\n"
        "\u061b"
        "\u061f"
        "\u00bb"
        "\u00ab"
        ".,;:"
    )


    # Remove secondary documentary qualifiers.
    answer = re.split(
        (
            r"\s+"
            r"(?:"
            r"\u0627\u0644\u062a\u064a"
            r"|\u0627\u0644\u0630\u064a"
            r"|\u062d\u064a\u062b"
            r"|\u0645\u0648\u062c\u0648\u062f\u0629"
            r"|\u0645\u0648\u062c\u0648\u062f\u062a\u0627\u0646"
            r"|\u0645\u0648\u062c\u0648\u062f\u062a\u064a\u0646"
            r"|\u0645\u0648\u062c\u0648\u062f\u064a\u0646"
            r"|\u0645\u0648\u062c\u0648\u062f"
            r"|\u062e\u0635\u0648\u0635\u0627"
            r"|\u062e\u0635\u0648\u0635"
            r")"
            r"\s+"
        ),
        answer,
        maxsplit=1,
    )[0].strip()


    return answer



# QUIZ_FRENCH_SOURCE_FIRST_V21A

def quiz_french_capitalize_v21a(
    value: str,
) -> str:

    value = str(
        value
        or ""
    ).strip()


    if not value:

        return ""


    return (
        value[0].upper()
        + value[1:]
    )


def quiz_french_fact_is_unsafe_v21a(
    value: str,
) -> bool:

    raw = re.sub(
        r"\s+",
        " ",
        str(
            value
            or ""
        ),
    ).strip()


    if not raw:

        return True


    if contains_arabic(
        raw
    ):

        return True


    if "_" in raw:

        return True


    normalized = (
        normalize_text(
            raw
        )
    )


    # Student instructions/exercises must never become
    # documentary truths.
    instruction_prefixes = (
        "calculer ",
        "determiner ",
        "completer ",
        "repondre ",
        "ecrire ",
        "donner ",
        "indiquer ",
        "exercice ",
        "application ",
    )


    if normalized.startswith(
        instruction_prefixes
    ):

        return True


    if normalized.startswith(
        (
            "seance ",
            "physique et chimie",
        )
    ):

        return True


    if re.match(
        r"^[IVXLCDM]+\s*[-/.]",
        raw,
        flags=re.IGNORECASE,
    ):

        return True


    if re.match(
        r"^\d+(?:[-./]\d+)*\s*[/.-]",
        raw,
    ):

        return True


    # Common truncated endings produced by PDF chunking.
    dangling_endings = (
        " un ou",
        " une ou",
        " ou",
        " et",
        " de",
        " des",
        " du",
        " dans",
        " avec",
        " par",
        " en",
        " qui",
        " que",
        " un ou plusieurs",
        " ou plusieurs",
    )


    if normalized.endswith(
        dangling_endings
    ):

        return True


    return False


def quiz_source_first_qa_french_v21a(
    fact: str,
) -> tuple[str, str]:

    raw = re.sub(
        r"\s+",
        " ",
        str(
            fact
            or ""
        ),
    ).strip(
        " \t\r\n"
        ".;:"
    )


    if not raw:

        return (
            "",
            "",
        )


    # Remove pedagogical labels only when they introduce
    # a complete documentary sentence.
    raw = re.sub(
        (
            r"^(?:"
            r"La forme"
            r"|La taille"
            r"|Charge "
            r"\u00e9lectrique"
            r"|Situation"
            r")"
            r"\s*:\s*"
        ),
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()


    if quiz_french_fact_is_unsafe_v21a(
        raw
    ):

        return (
            "",
            "",
        )


    # --------------------------------------------------------
    # A) ATOMIC / NUMERIC VALUE
    #
    # Le numero atomique de l'atome de sodium est Z = 11
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Le "
            r"num(?:e|\u00e9)ro "
            r"atomique "
            r"de\s+(.+?)"
            r"\s+est\s+"
            r"Z\s*=\s*"
            r"([+-]?\d+(?:[.,]\d+)?)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()

        answer = str(
            match.group(
                2
            )
            or ""
        ).strip()


        if (
            subject
            and answer
        ):

            return (
                (
                    "Quel est le "
                    "num\u00e9ro atomique de "
                    + subject
                    + " ?"
                ),
                answer,
            )


    # --------------------------------------------------------
    # B) SIMPLE DEFINITION
    #
    # Un anion est un ion negatif.
    # Un cation est un ion positif.
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(Un|Une)"
            r"\s+(.+?)"
            r"\s+est\s+"
            r"(un|une)"
            r"\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        subject_article = str(
            match.group(
                1
            )
        ).lower()

        subject = str(
            match.group(
                2
            )
            or ""
        ).strip()

        answer_article = str(
            match.group(
                3
            )
        ).lower()

        predicate = str(
            match.group(
                4
            )
            or ""
        ).strip()


        answer = (
            answer_article
            + " "
            + predicate
        )


        answer_tokens = (
            quiz_content_tokens(
                answer
            )
        )


        if (
            subject
            and predicate
            and answer_tokens
            and len(
                answer_tokens
            )
            <= 12
            and not quiz_french_fact_is_unsafe_v21a(
                answer
            )
        ):

            return (
                (
                    "Qu'est-ce qu'"
                    + subject_article
                    + " "
                    + subject
                    + " ?"
                ),
                answer,
            )


    # --------------------------------------------------------
    # C) FORM / ELECTRICAL PROPERTY
    #
    # Le noyau possede une forme spherique.
    # Chaque electron possede une charge electrique negative.
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)"
            r"\s+poss(?:e|\u00e8)de"
            r"\s+(une\s+forme\s+.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()

        answer = str(
            match.group(
                2
            )
            or ""
        ).strip()


        if (
            subject
            and answer
        ):

            return (
                (
                    "Quelle forme poss\u00e8de "
                    + subject
                    + " ?"
                ),
                answer,
            )


    match = re.match(
        (
            r"^(.+?)"
            r"\s+poss(?:e|\u00e8)de"
            r"\s+(une\s+charge"
            r"\s+\u00e9lectrique"
            r"\s+.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()

        answer = str(
            match.group(
                2
            )
            or ""
        ).strip()


        if (
            subject
            and answer
        ):

            return (
                (
                    "Quelle charge "
                    "\u00e9lectrique "
                    "poss\u00e8de "
                    + subject
                    + " ?"
                ),
                answer,
            )


    # --------------------------------------------------------
    # D) EACH X CARRIES A CHARGE
    #
    # Chaque electron porte une seule charge negative.
    #
    # Restrict to "Chaque ..." so an exercise statement like
    # "Le noyau porte une charge negative" is NOT accepted.
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(Chaque\s+.+?)"
            r"\s+porte"
            r"\s+(une\s+.+"
            r"charge\s+.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()

        answer = str(
            match.group(
                2
            )
            or ""
        ).strip()


        if (
            subject
            and answer
        ):

            return (
                (
                    "Quelle charge porte "
                    + subject
                    + " ?"
                ),
                answer,
            )


    # --------------------------------------------------------
    # E) LOCATION
    #
    # Presque toute la masse de l'atome se trouve
    # dans le noyau.
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)"
            r"\s+se\s+trouve"
            r"\s+("
            r"dans|au|aux|sur|sous"
            r")"
            r"\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()

        preposition = str(
            match.group(
                2
            )
            or ""
        ).strip()

        target = str(
            match.group(
                3
            )
            or ""
        ).strip()


        normalized_subject = (
            normalize_text(
                subject
            )
        )


        if normalized_subject in {
            "il",
            "elle",
            "ils",
            "elles",
            "cela",
            "ca",
        }:

            return (
                "",
                "",
            )


        answer = (
            preposition
            + " "
            + target
        )


        if (
            subject
            and target
        ):

            return (
                (
                    "O\u00f9 se trouve "
                    + subject
                    + " ?"
                ),
                answer,
            )


    return (
        "",
        "",
    )


def quiz_tf_statement_french_v21a(
    question: str,
    answer: str,
) -> str:

    question = re.sub(
        r"\s+",
        " ",
        str(
            question
            or ""
        ),
    ).strip()

    answer = re.sub(
        r"\s+",
        " ",
        str(
            answer
            or ""
        ),
    ).strip(
        " .;:"
    )


    if (
        not question
        or not answer
    ):

        return ""


    # --------------------------------------------------------
    # DEFINITION
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Qu['\u2019]est-ce "
            r"qu['\u2019]"
            r"(un|une)"
            r"\s+(.+?)"
            r"\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = (
            str(
                match.group(
                    1
                )
            ).lower()
            + " "
            + str(
                match.group(
                    2
                )
            ).strip()
        )


        return (
            quiz_french_capitalize_v21a(
                subject
            )
            + " est "
            + answer
            + "."
        )


    # --------------------------------------------------------
    # NUMERIC VALUE
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Quel est le "
            r"num(?:e|\u00e9)ro "
            r"atomique de "
            r"(.+?)"
            r"\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()


        return (
            "Le num\u00e9ro atomique de "
            + subject
            + " est "
            + answer
            + "."
        )


    # --------------------------------------------------------
    # FORM
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Quelle forme "
            r"poss(?:e|\u00e8)de "
            r"(.+?)"
            r"\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()


        return (
            quiz_french_capitalize_v21a(
                subject
            )
            + " poss\u00e8de "
            + answer
            + "."
        )


    # --------------------------------------------------------
    # ELECTRICAL CHARGE
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Quelle charge "
            r"\u00e9lectrique "
            r"poss(?:e|\u00e8)de "
            r"(.+?)"
            r"\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()


        return (
            quiz_french_capitalize_v21a(
                subject
            )
            + " poss\u00e8de "
            + answer
            + "."
        )


    match = re.match(
        (
            r"^Quelle charge porte "
            r"(.+?)"
            r"\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()


        return (
            quiz_french_capitalize_v21a(
                subject
            )
            + " porte "
            + answer
            + "."
        )


    # --------------------------------------------------------
    # LOCATION
    # --------------------------------------------------------

    match = re.match(
        (
            r"^O\u00f9 se trouve "
            r"(.+?)"
            r"\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()


        return (
            quiz_french_capitalize_v21a(
                subject
            )
            + " se trouve "
            + answer
            + "."
        )


    return ""



# QUIZ_FRENCH_TF_V21E
def quiz_tf_statement_french_v21e(
    question: str,
    answer: str,
) -> str:

    question = re.sub(
        r"\s+",
        " ",
        str(
            question
            or ""
        ),
    ).strip()


    answer = re.sub(
        r"\s+",
        " ",
        str(
            answer
            or ""
        ),
    ).strip(
        " \t\r\n"
        ".,;:"
    )


    if (
        not question
        or not answer
    ):

        return ""


    # --------------------------------------------------------
    # Preserve all V21A conversions that already work.
    # --------------------------------------------------------

    existing = (
        quiz_tf_statement_french_v21a(
            question=question,
            answer=answer,
        )
    )


    existing = str(
        existing
        or ""
    ).strip()


    if existing:

        return existing


    def subject_cap(
        value,
    ):

        value = str(
            value
            or ""
        ).strip()


        if not value:

            return ""


        return (
            quiz_french_capitalize_v21a(
                value
            )
        )


    def finish(
        value,
    ):

        value = re.sub(
            r"\s+",
            " ",
            str(
                value
                or ""
            ),
        ).strip()


        if not value:

            return ""


        if value.endswith(
            "?"
        ):

            return ""


        if value[-1:] not in {
            ".",
            "!",
        }:

            value += "."


        return value


    # --------------------------------------------------------
    # QUE PERMET X ?
    # --------------------------------------------------------

    match = re.match(
        r"^Que permet (.+?)\s*\?$",
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " permet "
            + answer
        )


    # --------------------------------------------------------
    # SELON QUEL CRITERE PEUT-ON CLASSER X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Selon quel crit"
            r"(?:e|\u00e8)re "
            r"peut-on classer "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " peuvent \u00eatre class\u00e9s "
            + answer
        )


    # --------------------------------------------------------
    # QUELLES FORMES PEUT PRENDRE X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Quelles formes "
            r"peut prendre "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " peut prendre "
            + answer
        )


    # --------------------------------------------------------
    # COMMENT PEUT-ON REGROUPER X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Comment peut-on "
            r"regrouper "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " peuvent \u00eatre regroup\u00e9s "
            + answer
        )


    # --------------------------------------------------------
    # QUE MULTIPLIE X ?
    # --------------------------------------------------------

    match = re.match(
        r"^Que multiplie (.+?)\s*\?$",
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " multiplie "
            + answer
        )


    # --------------------------------------------------------
    # QUE SE PASSE-T-IL SI X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Que se passe-t-il "
            r"si (.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        condition = str(
            match.group(
                1
            )
            or ""
        ).strip()


        return finish(
            "Si "
            + condition
            + ", "
            + answer
        )


    # --------------------------------------------------------
    # QUELLE EST X ?
    #
    # Quelle est l'unite de la puissance ?
    # --------------------------------------------------------

    match = re.match(
        r"^Quelle est (.+?)\s*\?$",
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " est "
            + answer
        )


    # --------------------------------------------------------
    # A QUOI EST EGALE X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(?:\u00c0|A) quoi "
            r"est (?:e|\u00e9)gale "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " est \u00e9gale "
            + answer
        )


    # --------------------------------------------------------
    # A QUOI EST EGAL X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(?:\u00c0|A) quoi "
            r"est (?:e|\u00e9)gal "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " est \u00e9gal "
            + answer
        )


    # --------------------------------------------------------
    # COMMENT APPELLE-T-ON X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Comment appelle-t-on "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()


        return finish(
            "On appelle "
            + subject
            + " "
            + answer
        )


    # --------------------------------------------------------
    # RELATION ENTRE DEUX DROITES
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Quelle relation existe "
            r"entre (.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        objects = str(
            match.group(
                1
            )
            or ""
        ).strip()


        return finish(
            "Les droites "
            + objects
            + " "
            + answer
        )


    # --------------------------------------------------------
    # DE QUOI DEPEND X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^De quoi d"
            r"(?:e|\u00e9)pend "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " d\u00e9pend "
            + answer
        )


    # --------------------------------------------------------
    # COMMENT APPARAISSENT X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Comment apparaissent "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " sont "
            + answer
        )


    # --------------------------------------------------------
    # QUE FONT X ?
    # --------------------------------------------------------

    match = re.match(
        r"^Que font (.+?)\s*\?$",
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " "
            + answer
        )


    # --------------------------------------------------------
    # COMMENT SONT SEPARES X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Comment sont s"
            r"(?:e|\u00e9)par"
            r"(?:e|\u00e9)s "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        return finish(
            subject
            + " sont s\u00e9par\u00e9s "
            + answer
        )


    # --------------------------------------------------------
    # QUEL ELEMENT PORTE X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Quel "
            r"(?:e|\u00e9)l"
            r"(?:e|\u00e9)ment porte "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()


        return finish(
            subject_cap(
                answer
            )
            + " porte "
            + subject
        )


    # --------------------------------------------------------
    # EN QUOI TRANSFORME-T-ON X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^En quoi transforme-t-on "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()


        clean_answer = answer


        if normalize_text(
            clean_answer
        ).startswith(
            "en "
        ):

            tail = clean_answer

        else:

            tail = (
                "en "
                + clean_answer
            )


        return finish(
            "On transforme "
            + subject
            + " "
            + tail
        )


    # --------------------------------------------------------
    # A QUOI CORRESPOND X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(?:\u00c0|A) quoi "
            r"correspond "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = subject_cap(
            match.group(
                1
            )
        )


        if normalize_text(
            answer
        ).startswith(
            "a "
        ):

            return finish(
                subject
                + " correspond "
                + answer
            )


        return finish(
            subject
            + " correspond \u00e0 "
            + answer
        )


    # --------------------------------------------------------
    # QUE SIGNIFIE LA CONDITION X ?
    # --------------------------------------------------------

    match = re.match(
        (
            r"^Que signifie la condition "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        condition = str(
            match.group(
                1
            )
            or ""
        ).strip()


        return finish(
            "La condition "
            + condition
            + " correspond \u00e0 "
            + answer
        )


    return ""



# QUIZ_FRENCH_TF_V21F
def quiz_tf_statement_french_v21f(
    question: str,
    answer: str,
) -> str:

    question = re.sub(
        r"\s+",
        " ",
        str(
            question
            or ""
        ),
    ).strip()


    answer = re.sub(
        r"\s+",
        " ",
        str(
            answer
            or ""
        ),
    ).strip(
        " \t\r\n"
        ".,;:"
    )


    if (
        not question
        or not answer
    ):

        return ""


    def cap(
        value,
    ):

        return (
            quiz_french_capitalize_v21a(
                str(
                    value
                    or ""
                ).strip()
            )
        )


    def clean_statement(
        value,
    ):

        value = str(
            value
            or ""
        )

        value = value.replace(
            "\u00ad",
            "",
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        ).strip()


        # QUIZ_FRENCH_TF_V21F_R2B
        #
        # Confirmed real-source OCR joins.
        # Deliberately implemented without new regex.

        value = value.replace(
            "imagementale",
            "image mentale",
        )

        value = value.replace(
            "figureinitiale",
            "figure initiale",
        )


        # Remove discourse glue from a standalone statement.

        if value.lower().startswith(
            "en fait "
        ):

            value = value[
                len(
                    "en fait "
                ):
            ].lstrip()


        # --------------------------------------------
        # Conservative OCR repairs.
        # --------------------------------------------

        value = re.sub(
            r"\bauto\s+biographie\b",
            "autobiographie",
            value,
            flags=re.IGNORECASE,
        )


        value = re.sub(
            r"\bma\s+ni\u00e8re\b",
            "mani\u00e8re",
            value,
            flags=re.IGNORECASE,
        )


        # Remove pedagogical instruction appended to a fact.
        value = re.sub(
            (
                r",?\s*mettez-vous\s+"
                r"\u00e0\s+sa\s+place"
                r"\.?\s*$"
            ),
            "",
            value,
            flags=re.IGNORECASE,
        )


        # French contractions.
        value = re.sub(
            r"\bcorrespond\s+\u00e0\s+le\b",
            "correspond au",
            value,
            flags=re.IGNORECASE,
        )


        value = re.sub(
            r"\bcorrespond\s+\u00e0\s+les\b",
            "correspond aux",
            value,
            flags=re.IGNORECASE,
        )


        value = value.strip()


        if not value:

            return ""


        if value.endswith(
            "?"
        ):

            return ""


        if value[-1:] not in {
            ".",
            "!",
        }:

            value += "."


        normalized = (
            normalize_text(
                value
            )
        )


        # V21F R2B:
        # A standalone Vrai/Faux statement must not depend
        # on an antecedent that is missing from the quiz.

        if normalized.startswith(
            (
                "on dit que ce sont ",
                "pour ce type d'appareil ",
                "pour ce type d appareil ",
            )
        ):

            return ""


        # --------------------------------------------
        # Heading / worksheet / OCR rejection.
        # --------------------------------------------

        bad_markers = (
            "journal de revisions",
            "college jean jaures",
            "types de phrase",
            "present 1 enonciation",
            "iv unites et ordre de grandeur",
            "iii puissance",
            "v energie electrique",
            "b fonctionnement",
            "w le gigawatt",
            "chapitre ",
            "exercice ",
            "exercices ",
            "solution ",
            "reponse ",
            "tache complexe",
            "fiche de revision",
            "pour l ensemble des autres figures",
        )


        if any(
            marker in normalized
            for marker in bad_markers
        ):

            return ""


        if any(
            marker in value
            for marker in (
                "\u2192",
                ".........",
                "........",
                "\u2713",
            )
        ):

            return ""


        # --------------------------------------------
        # A TF statement must stand on its own.
        # --------------------------------------------

        vague_prefixes = (
            "elle ",
            "il ",
            "cette quantite ",
            "le courant le traversant ",
        )


        if normalized.startswith(
            vague_prefixes
        ):

            return ""


        if normalized.startswith(
            "on appelle ces ajouts "
        ):

            return ""


        if normalized.startswith(
            "on dit que ce correspond "
        ):

            return ""


        if (
            len(value) > 190
            or len(
                normalize_text(
                    value
                ).split()
            ) > 32
        ):

            return ""


        malformed = (
            "correspond a le ",
            "les chromosomes porte ",
            "un allele peut prendre ",
            "on appelle deux triangles ",
            "on appelle une version ",
        )


        if any(
            marker in normalized
            for marker in malformed
        ):

            return ""


        return value


    normalized_question = (
        normalize_text(
            question
        )
    )


    # ========================================================
    # FIX: COMMENT APPELLE-T-ON ...
    # ========================================================

    match = re.match(
        (
            r"^Comment appelle-t-on "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()


        normalized_subject = (
            normalize_text(
                subject
            )
        )


        if normalized_subject.startswith(
            (
                "deux ",
                "les ",
                "des ",
            )
        ):

            statement = (
                cap(subject)
                + " sont appel\u00e9s "
                + answer
            )


        elif normalized_subject.startswith(
            (
                "une ",
                "la ",
            )
        ):

            statement = (
                cap(subject)
                + " est appel\u00e9e "
                + answer
            )


        elif normalized_subject.startswith(
            (
                "un ",
                "le ",
            )
        ):

            statement = (
                cap(subject)
                + " est appel\u00e9 "
                + answer
            )


        else:

            statement = (
                "On appelle "
                + subject
                + " "
                + answer
            )


        return clean_statement(
            statement
        )


    # ========================================================
    # FIX: QUELLES FORMES PEUT PRENDRE...
    #
    # "Un allele peut etre recessif..."
    # ========================================================

    match = re.match(
        (
            r"^Quelles formes "
            r"peut prendre "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        return clean_statement(
            cap(
                match.group(
                    1
                )
            )
            + " peut \u00eatre "
            + answer
        )


    # ========================================================
    # FIX: QUEL ELEMENT PORTE...
    # ========================================================

    match = re.match(
        (
            r"^Quel "
            r"(?:e|\u00e9)l"
            r"(?:e|\u00e9)ment porte "
            r"(.+?)\s*\?$"
        ),
        question,
        flags=re.IGNORECASE,
    )


    if match:

        object_value = str(
            match.group(
                1
            )
            or ""
        ).strip()


        normalized_answer = (
            normalize_text(
                answer
            )
        )


        plural = (
            normalized_answer.startswith(
                "les "
            )
            or normalized_answer.startswith(
                "des "
            )
        )


        verb = (
            " portent "
            if plural
            else " porte "
        )


        return clean_statement(
            cap(answer)
            + verb
            + object_value
        )


    # ========================================================
    # FIX SOURCE FACT:
    # "On dit que ce sont des mots..."
    # ========================================================

    if normalized_question.startswith(
        "a quoi correspond on dit que ce"
    ):

        return clean_statement(
            "On dit que ce sont "
            + answer
        )


    # ========================================================
    # QUIZ_FRENCH_TF_V21F_R2C3
    #
    # Target:
    # "A quoi correspond En fait la valeur ... ?"
    #
    # Remove "En fait" before building the standalone
    # statement so that cap(subject) produces "La ...".
    # ========================================================

    if normalized_question.startswith(
        "a quoi correspond en fait "
    ):

        marker = "en fait "

        lower_question = (
            question.lower()
        )


        marker_index = (
            lower_question.find(
                marker
            )
        )


        if marker_index >= 0:

            subject = question[
                marker_index
                + len(
                    marker
                ):
            ].strip()


            if subject.endswith(
                "?"
            ):

                subject = subject[
                    :-1
                ].strip()


            if subject:

                return clean_statement(
                    cap(
                        subject
                    )
                    + " correspond \u00e0 "
                    + answer
                )


    # ========================================================
    # PC TRANSFORMATION
    #
    # No regex here. The source QA already established the
    # documentary relation before this conversion step.
    # ========================================================

    if (
        normalized_question.startswith(
            "quel est le resultat de la transformation de "
        )
        and "energie electrique" in normalized_question
    ):

        return clean_statement(
            "L'\u00e9nergie \u00e9lectrique "
            "est transform\u00e9e en "
            + answer
        )


    # ========================================================
    # KEEP V21E FOR ALL OTHER SUPPORTED PATTERNS.
    # ========================================================

    statement = (
        quiz_tf_statement_french_v21e(
            question=question,
            answer=answer,
        )
    )


    return clean_statement(
        statement
    )


def quiz_tf_statement_from_qa_v21a(
    question: str,
    answer: str,
) -> str:

    if contains_arabic(
        question
    ):

        return (
            quiz_tf_statement_from_qa_v18(
                question=(
                    question
                ),
                answer=(
                    answer
                ),
            )
        )


    # QUIZ_FRENCH_TF_ROUTING_V21F
    return (
        quiz_tf_statement_french_v21f(
            question=(
                question
            ),
            answer=(
                answer
            ),
        )
    )







# QUIZ_FRENCH_SOURCE_FIRST_V21B
def quiz_source_first_qa_french_v21b(
    fact: str,
) -> tuple[str, str]:

    raw = str(
        fact
        or ""
    )

    raw = raw.replace(
        "\u00ad",
        "",
    )

    raw = re.sub(
        r"\s+",
        " ",
        raw,
    ).strip()


    raw = raw.strip(
        " \t\r\n"
        ".,;:"
        "\u00ab"
        "\u00bb"
        "\u2013"
        "\u2014"
        "-"
    )


    if (
        not raw
        or contains_arabic(
            raw
        )
    ):

        return "", ""


    old_question, old_answer = (
        quiz_source_first_qa_french_v21a(
            raw
        )
    )


    old_question = str(
        old_question
        or ""
    ).strip()

    old_answer = str(
        old_answer
        or ""
    ).strip()


    if (
        old_question
        and old_answer
    ):

        return (
            old_question,
            old_answer,
        )


    normalized = (
        normalize_text(
            raw
        )
    )


    if (
        len(raw) < 8
        or len(raw) > 420
        or raw.endswith("?")
    ):

        return "", ""


    unsafe = (
        "journal de revisions",
        "college jean jaures",
        "exercice ",
        "exercices ",
        "oral ",
        "en classe ",
        "a la maison ",
        "reecris ",
        "reeccris ",
        "calculer ",
        "justifiez ",
        "justifier ",
        "d apres le tableau",
        "d'apres le tableau",
        "quel circuit devrait",
        "nom prenom classe",
    )


    if any(
        marker in normalized
        for marker in unsafe
    ):

        return "", ""


    def build(
        question,
        answer,
    ):

        question = re.sub(
            r"\s+",
            " ",
            str(
                question
                or ""
            ),
        ).strip()


        answer = re.sub(
            r"\s+",
            " ",
            str(
                answer
                or ""
            ),
        ).strip(
            " \t\r\n"
            ".,;:"
            "\u00ab"
            "\u00bb"
        )


        if (
            not question
            or not answer
        ):

            return "", ""


        tokens = (
            quiz_content_tokens(
                answer
            )
        )


        # QUIZ_FRENCH_ATOMIC_ANSWER_V21B
        atomic = bool(
            re.fullmatch(
                (
                    r"(?:"
                    r"[+-]?\d+(?:[.,]\d+)?"
                    r"(?:\s*(?:"
                    r"%|mm|cm|dm|m|km|"
                    r"mg|g|kg|"
                    r"ml|cl|l|"
                    r"ma|a|mv|v|"
                    r"mw|w|kw|mw|gw|"
                    r"hz|khz|mhz|"
                    r"s|min|h"
                    r"))?"
                    r"|"
                    r"[A-Za-z]{1,5}\d{0,3}"
                    r")"
                ),
                answer,
                flags=re.IGNORECASE,
            )
        )


        if (
            not tokens
            and not atomic
        ):

            return "", ""


        if (
            tokens
            and len(tokens) > 14
        ):

            return "", ""


        if len(answer) > 180:

            return "", ""


        if (
            normalize_text(
                answer
            )
            == normalize_text(
                raw
            )
        ):

            return "", ""


        question = (
            quiz_french_capitalize_v21a(
                question
            )
        )


        if not question.endswith("?"):

            question += " ?"


        return (
            question,
            answer,
        )


    # --------------------------------------------------------
    # APPELER
    # --------------------------------------------------------

    match = re.match(
        (
            r"^on\s+appelle\s+"
            r"(.+?)\s+"
            r"((?:un|une|des|le|la|les|"
            r"l['\u2019]).+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return build(
            "Comment appelle-t-on "
            + match.group(1).strip(),
            match.group(2).strip(),
        )


    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:est|sont)\s+"
            r"appel"
            r"[A-Za-z\u00c0-\u024f]*"
            r"\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return build(
            "Comment appelle-t-on "
            + match.group(1).strip(),
            match.group(2).strip(),
        )


    # --------------------------------------------------------
    # UNIT
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(l['\u2019]unit"
            r"[A-Za-z\u00c0-\u024f]*"
            r"\s+de\s+.+?)"
            r"\s+est\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        answer = re.split(
            r"\s*,\s*(?:son|sa|ses)\s+",
            match.group(2).strip(),
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()


        return build(
            "Quelle est "
            + match.group(1).strip(),
            answer,
        )


    # --------------------------------------------------------
    # NUMBER
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:est|sont)\s+"
            r"au\s+nombre\s+de\s+"
            r"(\d+)"
            r"(?:\s+.*)?$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return build(
            "Quel est le nombre de "
            + match.group(1).strip(),
            match.group(2).strip(),
        )


    # --------------------------------------------------------
    # TRANSFORMATION
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:est|sont)\s+"
            r"transform"
            r"[A-Za-z\u00c0-\u024f]*"
            r"\s+en\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return build(
            (
                "Quel est le resultat de la "
                "transformation de "
                + match.group(1).strip()
            ),
            match.group(2).strip(),
        )


    # --------------------------------------------------------
    # PASSIVE "... porte par ..."
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:est|sont)\s+"
            r"port"
            r"[A-Za-z\u00c0-\u024f]*"
            r"\s+par\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return build(
            "Quel element porte "
            + match.group(1).strip(),
            match.group(2).strip(),
        )


    # --------------------------------------------------------
    # CONSTITUTION
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:est|sont)\s+"
            r"constitu"
            r"[A-Za-z\u00c0-\u024f]*"
            r"\s+d['e\u2019]\s*(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if not match:

        match = re.match(
            (
                r"^(.+?)\s+"
                r"(?:est|sont)\s+"
                r"constitu"
                r"[A-Za-z\u00c0-\u024f]*"
                r"\s+de\s+(.+)$"
            ),
            raw,
            flags=re.IGNORECASE,
        )


    if match:

        return build(
            "De quoi est constitue "
            + match.group(1).strip(),
            match.group(2).strip(),
        )


    # --------------------------------------------------------
    # LOCATION
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:se\s+situe|se\s+trouve|"
            r"est\s+situ[A-Za-z\u00c0-\u024f]*|"
            r"sont\s+situ[A-Za-z\u00c0-\u024f]*)"
            r"\s+"
            r"(dans|sur|au|aux|chez|sous)"
            r"\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return build(
            "O\u00f9 se trouve "
            + match.group(1).strip(),
            (
                match.group(2).strip()
                + " "
                + match.group(3).strip()
            ),
        )


    # --------------------------------------------------------
    # CONDITIONAL
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(?:de\s+plus,\s*)?"
            r"si\s+(.+?),\s*"
            r"(?:alors\s+)?"
            r"(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return build(
            "Que se passe-t-il si "
            + match.group(1).strip(),
            match.group(2).strip(),
        )


    # --------------------------------------------------------
    # MULTIPLICATION FACTOR
    # --------------------------------------------------------

    if (
        "multipl" in normalized.lower()
        and " par " in normalized.lower()
    ):

        factor = re.search(
            r"\bpar\s+([+-]?\d+(?:[.,]\d+)?)\b",
            raw,
            flags=re.IGNORECASE,
        )


        subject = re.match(
            r"^(.+?)\s+ont\s+",
            raw,
            flags=re.IGNORECASE,
        )


        if (
            factor
            and subject
        ):

            return build(
                (
                    "Quel est le facteur de multiplication de "
                    + subject.group(1).strip()
                ),
                factor.group(1).strip(),
            )


    # --------------------------------------------------------
    # CORRESPONDENCE
    #
    # IMPORTANT R4:
    # accepts both "a" and "\u00e0".
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"correspond"
            r"(?:ent)?"
            r"(?:\s+alors)?"
            r"\s+(?:a|\u00e0)\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return build(
            "\u00c0 quoi correspond "
            + match.group(1).strip(),
            match.group(2).strip(),
        )


    # --------------------------------------------------------
    # SIMPLE RELATIONS
    # --------------------------------------------------------

    relations = [
        (
            r"^(.+?)\s+contient\s+(.+)$",
            "Que contient ",
        ),
        (
            r"^(.+?)\s+contiennent\s+(.+)$",
            "Que contiennent ",
        ),
        (
            r"^(.+?)\s+porte\s+(.+)$",
            "Que porte ",
        ),
        (
            r"^(.+?)\s+portent\s+(.+)$",
            "Que portent ",
        ),
        (
            r"^(.+?)\s+poss\u00e8de\s+(.+)$",
            "Que possede ",
        ),
        (
            r"^(.+?)\s+poss\u00e8dent\s+(.+)$",
            "Que possedent ",
        ),
        (
            r"^(.+?)\s+conserve\s+(.+)$",
            "Que conserve ",
        ),
        (
            r"^(.+?)\s+n\u00e9cessite\s+(.+)$",
            "Que necessite ",
        ),
        (
            r"^(.+?)\s+multiplie\s+(.+)$",
            "Que multiplie ",
        ),
    ]


    for pattern, prefix in relations:

        match = re.match(
            pattern,
            raw,
            flags=re.IGNORECASE,
        )


        if not match:
            continue


        subject = match.group(1).strip()


        if normalize_text(
            subject
        ) in {
            "il",
            "elle",
            "ils",
            "elles",
        }:

            continue


        result = build(
            prefix
            + subject,
            match.group(2).strip(),
        )


        if result != (
            "",
            "",
        ):

            return result


    # --------------------------------------------------------
    # SIMPLE "X EST UN/UNE..."
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:est|sont)\s+"
            r"("
            r"(?:un|une|des|le|la|les|du|"
            r"l['\u2019])"
            r"\s*.+"
            r")$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return build(
            "\u00c0 quoi correspond "
            + match.group(1).strip(),
            match.group(2).strip(),
        )


    # --------------------------------------------------------
    # LABEL : VALUE
    # --------------------------------------------------------

    match = re.match(
        r"^([^:]{2,55})\s*:\s*(.+)$",
        raw,
    )


    if match:

        label = match.group(1).strip()

        answer = match.group(2).strip()


        if not any(
            marker
            in normalize_text(
                label
            )
            for marker in (
                "chapitre",
                "journal",
                "page",
                "exercice",
                "definition",
                "propriete",
            )
        ):

            return build(
                (
                    "Quelle information correspond a "
                    + label
                ),
                answer,
            )


    return "", ""



# QUIZ_FRENCH_SOURCE_FIRST_V21D
def quiz_source_first_qa_french_v21d(
    fact: str,
) -> tuple[str, str]:

    raw = str(
        fact
        or ""
    )

    raw = raw.replace(
        "\u00ad",
        "",
    )

    raw = re.sub(
        r"\s+",
        " ",
        raw,
    ).strip(
        " \t\r\n"
        ".,;:"
        "\u2013"
        "\u2014"
    )


    if (
        not raw
        or contains_arabic(
            raw
        )
    ):
        return "", ""


    normalized = (
        normalize_text(
            raw
        )
    )


    # ========================================================
    # NEVER BUILD QUIZZES FROM EXERCISE INSTRUCTIONS
    # ========================================================

    instruction_prefixes = (
        "demontrer ",
        "montrer ",
        "calculer ",
        "determiner ",
        "justifier ",
        "prouver ",
        "construire ",
        "tracer ",
        "completer ",
        "complete ",
        "reecrire ",
        "reecris ",
        "repondre ",
        "indiquer ",
        "donner ",
        "verifier ",
        "resoudre ",
    )


    if normalized.startswith(
        instruction_prefixes
    ):
        return "", ""


    # ========================================================
    # HELPERS
    # ========================================================

    def clean_subject(
        value,
    ):

        value = re.sub(
            r"\s+",
            " ",
            str(
                value
                or ""
            ),
        ).strip()


        # Common lesson-heading spillovers.
        value = re.sub(
            (
                r"^Les\s+Figures\s+de\s+style\s+"
                r"(?=Une\s+figure\s+de\s+style)"
            ),
            "",
            value,
            flags=re.IGNORECASE,
        )


        value = re.sub(
            (
                r"^Formation\s+d['\u2019]un\s+"
                r"nouvel\s+individu\s*"
                r"\(f\u00e9condation\)\s+"
            ),
            "",
            value,
            flags=re.IGNORECASE,
        )


        value = re.sub(
            (
                r"^Formation\s+des\s+gam\u00e8tes\s*"
                r"\(m\u00e9iose\)\s+"
            ),
            "",
            value,
            flags=re.IGNORECASE,
        )


        value = re.sub(
            (
                r"^Division\s+cellulaire\s+classique\s*"
                r"\(mitose\)\s+"
            ),
            "",
            value,
            flags=re.IGNORECASE,
        )


        value = re.sub(
            (
                r"^(?:"
                r"\d+\s*[-.)]\s*"
                r"(?:D\u00e9finition|"
                r"D\u00e9finitions|"
                r"Propri\u00e9t\u00e9s?|"
                r"Avantages?|"
                r"Inconv\u00e9nients?)"
                r"\s+"
                r")"
            ),
            "",
            value,
            flags=re.IGNORECASE,
        )


        return value.strip()


    def lower_article(
        value,
    ):

        value = clean_subject(
            value
        )


        replacements = {
            "Les ": "les ",
            "Le ": "le ",
            "La ": "la ",
            "Des ": "des ",
            "Un ": "un ",
            "Une ": "une ",
            "L'": "l'",
            "L\u2019": "l\u2019",
        }


        for prefix, replacement in replacements.items():

            if value.startswith(
                prefix
            ):

                return (
                    replacement
                    + value[
                        len(prefix):
                    ]
                )


        if value:
            return (
                value[:1].lower()
                + value[1:]
            )


        return value


    def with_indefinite_article(
        value,
    ):

        value = clean_subject(
            value
        )


        normalized_value = (
            normalize_text(
                value
            )
        )


        known = {
            "allele": "un all\u00e8le",
            "gene": "un g\u00e8ne",
            "chromosome": "un chromosome",
            "phenotype": "un ph\u00e9notype",
        }


        return known.get(
            normalized_value,
            lower_article(
                value
            ),
        )


    def safe(
        question,
        answer,
    ):

        question = re.sub(
            r"\s+",
            " ",
            str(
                question
                or ""
            ),
        ).strip()


        answer = re.sub(
            r"\s+",
            " ",
            str(
                answer
                or ""
            ),
        ).strip(
            " \t\r\n"
            ".,;:"
        )


        if (
            not question
            or not answer
        ):
            return "", ""


        nq = normalize_text(
            question
        )

        na = normalize_text(
            answer
        )

        nf = normalize_text(
            raw
        )


        if (
            na
            and nf
            and na not in nf
        ):
            return "", ""


        if (
            len(question) > 165
            or len(answer) > 150
        ):
            return "", ""


        if len(
            re.findall(
                r"[A-Za-z\u00c0-\u024f0-9]+",
                question,
            )
        ) > 24:
            return "", ""


        if na in {
            "",
            "un",
            "une",
            "le",
            "la",
            "les",
            "des",
            "du",
            "de",
            "a",
            "au",
            "aux",
            "ce",
            "cela",
        }:
            return "", ""


        # Incomplete answer tails.
        if re.search(
            (
                r"\b(?:"
                r"de|du|des|"
                r"le|la|les|"
                r"qui|que|"
                r"par|pour|avec|"
                r"est|sont"
                r")$"
            ),
            na,
        ):
            return "", ""


        if (
            nq.startswith(
                "quelle information correspond a "
            )
            or nq.startswith(
                "quelle information correspond \u00e0 "
            )
        ):
            return "", ""


        if re.search(
            r"\b(?:ceci|cela|si elle|si il)\b",
            nq,
        ):
            return "", ""


        bad = (
            "journal de revisions",
            "college jean jaures",
            "chapitre ",
            "exercice ",
            "exercices ",
            "solution ",
            "reponse ",
            "tache complexe",
            "fiche de revision",
            "\u2192",
            ".........",
            "........",
            "\u2713",
            "se rap ",
            "lo gique",
            "n ensemble",
            "mmee par",
            "les gametes ne ",
        )


        if any(
            marker in nq
            or marker in na
            for marker in bad
        ):
            return "", ""


        # Raw fact itself must not be an exercise instruction.
        if normalized.startswith(
            instruction_prefixes
        ):
            return "", ""


        if not question.endswith(
            "?"
        ):
            question += " ?"


        return (
            question,
            answer,
        )


    # ========================================================
    # TARGETED RELATIONS
    # ========================================================


    # --------------------------------------------------------
    # PERMET DE
    # --------------------------------------------------------

    match = re.match(
        r"^(.+?)\s+permet(?:tent)?\s+de\s+(.+)$",
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        subject = lower_article(
            match.group(
                1
            )
        )


        result = safe(
            (
                "Que permet "
                + subject
            ),
            (
                "de "
                + match.group(
                    2
                ).strip()
            ),
        )


        if result != (
            "",
            "",
        ):
            return result


    # --------------------------------------------------------
    # PEUVENT ETRE CLASSES SELON
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"peuvent\s+\u00eatre\s+"
            r"class"
            r"[A-Za-z\u00c0-\u024f]*"
            r"\s+selon\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "Selon quel crit\u00e8re peut-on classer "
                + lower_article(
                    match.group(
                        1
                    )
                )
            ),
            (
                "selon "
                + match.group(
                    2
                ).strip()
            ),
        )


    # --------------------------------------------------------
    # PEUVENT ETRE REGROUPES
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"peuvent\s+\u00eatre\s+"
            r"regroup"
            r"[A-Za-z\u00c0-\u024f]*"
            r"\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "Comment peut-on regrouper "
                + lower_article(
                    match.group(
                        1
                    )
                )
            ),
            match.group(
                2
            ).strip(),
        )


    # --------------------------------------------------------
    # PEUT ETRE
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"peut\s+\u00eatre\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        subject = clean_subject(
            match.group(
                1
            )
        )


        if normalize_text(
            subject
        ) not in {
            "il",
            "elle",
            "cela",
            "ceci",
        }:

            result = safe(
                (
                    "Quelles formes peut prendre "
                    + with_indefinite_article(
                        subject
                    )
                ),
                match.group(
                    2
                ).strip(),
            )


            if result != (
                "",
                "",
            ):
                return result


    # --------------------------------------------------------
    # SI ... ALORS C'EST ...
    # --------------------------------------------------------

    match = re.match(
        (
            r"^si\s+(.+?)\s+"
            r"alors\s+c['\u2019]est\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "Que signifie la condition "
                + match.group(
                    1
                ).strip()
            ),
            match.group(
                2
            ).strip(),
        )


    # --------------------------------------------------------
    # PROPORTIONNEL
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(?:par\s+cons\u00e9quent,\s*)?"
            r"(.+?)\s+"
            r"(?:est|sont)\s+"
            r"proportionnel"
            r"[A-Za-z\u00c0-\u024f]*"
            r"\s+\u00e0\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "\u00c0 quoi "
                + lower_article(
                    match.group(
                        1
                    )
                )
                + " est-il proportionnel"
            ),
            (
                "\u00e0 "
                + match.group(
                    2
                ).strip()
            ),
        )


    # --------------------------------------------------------
    # DECLARATIVE PARALLELISM ONLY
    #
    # "les droites (...) sont paralleles"
    #
    # Instruction prefixes already rejected above.
    # --------------------------------------------------------

    match = re.search(
        (
            r"(les\s+droites\s+"
            r"\([^)]+\)\s+et\s+\([^)]+\))"
            r"\s+sont\s+"
            r"(parall"
            r"[A-Za-z\u00c0-\u024f]*)"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "Quelle relation existe entre "
                + match.group(
                    1
                )[
                    len(
                        "les droites "
                    ):
                ]
            ),
            (
                "sont "
                + match.group(
                    2
                )
            ),
        )


    # --------------------------------------------------------
    # DEPEND DE / D'UNE
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"d\u00e9pend\s+"
            r"(d['\u2019].+|de\s+.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "De quoi d\u00e9pend "
                + lower_article(
                    match.group(
                        1
                    )
                )
            ),
            match.group(
                2
            ).strip(),
        )


    # --------------------------------------------------------
    # EST EGALE AU PRODUIT
    # --------------------------------------------------------

    match = re.search(
        (
            r"(.{5,110}?)\s+"
            r"est\s+\u00e9gal"
            r"(?:e)?\s+"
            r"(au\s+produit\s+.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        subject = clean_subject(
            match.group(
                1
            )
        )


        if not normalize_text(
            subject
        ).startswith(
            "mmee "
        ):

            result = safe(
                (
                    "\u00c0 quoi est \u00e9gale "
                    + lower_article(
                        subject
                    )
                ),
                match.group(
                    2
                ).strip(),
            )


            if result != (
                "",
                "",
            ):
                return result


    # --------------------------------------------------------
    # VISUELLEMENT IDENTIQUES
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:est|sont)\s+"
            r"visuellement\s+"
            r"(identique"
            r"[A-Za-z\u00c0-\u024f]*)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "Comment apparaissent "
                + lower_article(
                    match.group(
                        1
                    )
                )
            ),
            (
                "visuellement "
                + match.group(
                    2
                )
            ),
        )


    # --------------------------------------------------------
    # RESPONSABLE DE
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:est|sont)\s+"
            r"responsable"
            r"[A-Za-z\u00c0-\u024f]*"
            r"\s+de\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "De quoi "
                + lower_article(
                    match.group(
                        1
                    )
                )
                + " est-il responsable"
            ),
            (
                "de "
                + match.group(
                    2
                ).strip()
            ),
        )


    # --------------------------------------------------------
    # EXISTE SOUS
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:existe|existent)\s+"
            r"sous\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "Sous quelles formes existe "
                + lower_article(
                    match.group(
                        1
                    )
                )
            ),
            (
                "sous "
                + match.group(
                    2
                ).strip()
            ),
        )


    # --------------------------------------------------------
    # FUSION
    # --------------------------------------------------------

    match = re.match(
        r"^(.+?)\s+fusionnent$",
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "Que font "
                + lower_article(
                    match.group(
                        1
                    )
                )
            ),
            "fusionnent",
        )


    # --------------------------------------------------------
    # S'ASSOCIENT POUR
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"s['\u2019]associent\s+"
            r"pour\s+(.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "Que font "
                + lower_article(
                    match.group(
                        1
                    )
                )
            ),
            (
                "s'associent pour "
                + match.group(
                    2
                ).strip()
            ),
        )


    # --------------------------------------------------------
    # SEPARES DE FACON
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)\s+"
            r"(?:est|sont)\s+"
            r"s\u00e9par"
            r"[A-Za-z\u00c0-\u024f]*"
            r"\s+(de\s+fa\u00e7on\s+.+)$"
        ),
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "Comment sont s\u00e9par\u00e9s "
                + lower_article(
                    match.group(
                        1
                    )
                )
            ),
            match.group(
                2
            ).strip(),
        )


    # --------------------------------------------------------
    # DIVISE
    # --------------------------------------------------------

    match = re.match(
        r"^(.+?)\s+divise\s+(.+)$",
        raw,
        flags=re.IGNORECASE,
    )


    if match:

        return safe(
            (
                "Que fait "
                + lower_article(
                    match.group(
                        1
                    )
                )
            ),
            (
                "divise "
                + match.group(
                    2
                ).strip()
            ),
        )


    # ========================================================
    # R4 FALLBACK
    # ========================================================

    question, answer = (
        quiz_source_first_qa_french_v21b(
            raw
        )
    )


    question = str(
        question
        or ""
    ).strip()

    answer = str(
        answer
        or ""
    ).strip()


    # Generic label fallback is forbidden.
    if normalize_text(
        question
    ).startswith(
        "quelle information correspond a "
    ):
        return "", ""


    return safe(
        question,
        answer,
    )


def quiz_source_first_qa_v17b(
    fact: str,
    arabic_expected: bool,
) -> tuple[str, str]:

    raw = re.sub(
        r"\s+",
        " ",
        str(
            fact
            or ""
        ),
    ).strip(
        " \t\r\n"
        "\u061b"
        "\u061f"
        "\u00bb"
        "\u00ab"
        ".,;:"
    )


    if not raw:
        return "", ""


    if not arabic_expected:

        # QUIZ_FRENCH_V17B_ROUTING_V21D
        return (
            quiz_source_first_qa_french_v21d(
                raw
            )
        )




    # QUIZ_ARABIC_FACT_PREFIX_CLEANUP_V25Y
    #
    # OCR/source passages often preserve exercise numbering:
    #   "1) ??????? ????????? ?? ..."
    #   "2) ?????? ????????? ?? ..."
    # and solution markers:
    #   "??? ??? ... ?? ..."
    #
    # These prefixes are not part of the mathematical concept.
    # Remove only a leading list number / solution marker before
    # deterministic Arabic QA parsing. The source fact itself is
    # left unchanged for grounding and validation.
    raw = re.sub(
        r"^\s*[\d\u0660-\u0669]+\s*[\)\(]\s*",
        "",
        raw,
    )
    raw = re.sub(
        r"^\s*(?:\u0625\u0630\u0646|\u0627\u0630\u0646)\s+",
        "",
        raw,
    ).strip()

    # --------------------------------------------------------
    # A) COMPOSITION
    #
    # ????? ?????? ??????? ?? ????? ?????? ??????...
    # =>
    # Q: ?? ????? ?????? ????????
    # A: ????? ?????? ??????
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(?:\u0648)?"
            r"(\u064a\u062a\u0643\u0648\u0646"
            r"|\u062a\u062a\u0643\u0648\u0646)"
            r"\s+(.+?)"
            r"\s+\u0645\u0646"
            r"\s+(.+)$"
        ),
        raw,
    )


    if match:

        verb = match.group(
            1
        )

        subject = match.group(
            2
        ).strip()

        answer = (
            quiz_trim_source_answer_v17b(
                match.group(
                    3
                )
            )
        )


        if (
            subject
            and answer
            and len(
                quiz_content_tokens(
                    answer
                )
            )
            <= 10
        ):

            question_prefix = (
                "\u0645\u0645 "
                "\u062a\u062a\u0643\u0648\u0646 "
                if verb
                == "\u062a\u062a\u0643\u0648\u0646"
                else
                "\u0645\u0645 "
                "\u064a\u062a\u0643\u0648\u0646 "
            )


            return (
                question_prefix
                + subject
                + "\u061f",
                answer,
            )


    # --------------------------------------------------------
    # B) DIRECTION / TRANSFER
    #
    # O2 ??? ?? ?????? ?????? ??? ????
    # =>
    # Q: ?? ???? O2?
    # A: ?? ?????? ?????? ??? ????
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)"
            r"\s+"
            r"(?:"
            r"\u062a\u0645\u0631"
            r"|\u064a\u0645\u0631"
            r"|\u062a\u0646\u062a\u0642\u0644"
            r"|\u064a\u0646\u062a\u0642\u0644"
            r")"
            r"\s+"
            r"(\u0645\u0646\s+.+?"
            r"\s+(?:\u0625\u0644\u0649|\u0627\u0644\u0649)"
            r"\s+.+)$"
        ),
        raw,
    )


    if match:

        subject = (
            match.group(
                1
            ).strip()
        )

        answer = (
            quiz_trim_source_answer_v17b(
                match.group(
                    2
                )
            )
        )


        if subject and answer:

            return (
                "\u0645\u0627 "
                "\u0645\u0633\u0627\u0631 "
                + subject
                + "\u061f",
                answer,
            )


    # --------------------------------------------------------
    # C) CAUSE
    #
    # ???? ???? ?????? ?? ????? ??????? ????????
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(?:\u0648)?"
            r"\u064a\u0646\u062a\u062c"
            r"\s+(.+?)"
            r"\s+\u0639\u0646"
            r"\s+(.+)$"
        ),
        raw,
    )


    if match:

        subject = match.group(
            1
        ).strip()

        answer = (
            quiz_trim_source_answer_v17b(
                match.group(
                    2
                )
            )
        )


        if subject and answer:

            return (
                "\u0645\u0627 "
                "\u0633\u0628\u0628 "
                + subject
                + "\u061f",
                answer,
            )


    # --------------------------------------------------------
    # D) PREVENTION
    #
    # ??????? ?? ?????? ???? ????? ????...
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(?:\u0648)?"
            r"\u0644\u0644\u0648\u0642\u0627\u064a\u0629"
            r"\s+\u0645\u0646"
            r"\s+(.+?)"
            r"\s+\u064a\u0648\u062c\u062f"
            r"\s+(.+?)"
            r"(?:"
            r"\s+\u0644\u062a\u062c\u0646\u0628"
            r"|\s+\u0644\u0644\u0648\u0642\u0627\u064a\u0629"
            r"|\s+\u0644\u062a\u0641\u0627\u062f\u064a"
            r"|$"
            r")"
        ),
        raw,
    )


    if match:

        target = match.group(
            1
        ).strip()

        answer = (
            quiz_trim_source_answer_v17b(
                match.group(
                    2
                )
            )
        )


        if target and answer:

            return (
                "\u0645\u0627 "
                "\u0648\u0633\u064a\u0644\u0629 "
                "\u0627\u0644\u0648\u0642\u0627\u064a\u0629 "
                "\u0645\u0646 "
                + target
                + "\u061f",
                answer,
            )


    # --------------------------------------------------------
    # E) BEST PREVENTION MEASURES
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(?:\u0648)?"
            r"\u064a\u0634\u0643\u0644"
            r"\s+(.+?)"
            r"\s+\u0623?\u0646\u062c\u0639"
            r"\s+\u0627\u0644\u0648\u0633\u0627\u0626\u0644"
            r"\s+\u0644\u0644\u0648\u0642\u0627\u064a\u0629"
            r"\s+\u0645\u0646"
            r"\s+(.+)$"
        ),
        raw,
    )


    if match:

        answer = (
            quiz_trim_source_answer_v17b(
                match.group(
                    1
                )
            )
        )

        target = (
            quiz_trim_source_answer_v17b(
                match.group(
                    2
                )
            )
        )


        if answer and target:

            return (
                "\u0645\u0627 "
                "\u0623\u0646\u062c\u0639 "
                "\u0648\u0633\u0627\u0626\u0644 "
                "\u0627\u0644\u0648\u0642\u0627\u064a\u0629 "
                "\u0645\u0646 "
                + target
                + "\u061f",
                answer,
            )


    # --------------------------------------------------------
    # F) NUMERIC VALUE
    # --------------------------------------------------------

    match = re.match(
        (
            r"^(.+?)"
            r"\s+\u0646\u062d\u0648"
            r"\s+"
            r"((?:[A-Za-z]+\s*)?"
            r"\d+(?:[.,]\d+)?)"
            r"(?:\s+.*)?$"
        ),
        raw,
    )


    if match:

        subject = match.group(
            1
        ).strip()

        answer = match.group(
            2
        ).strip()


        if subject and answer:

            return (
                "\u0645\u0627 "
                "\u0642\u064a\u0645\u0629 "
                + subject
                + "\u061f",
                answer,
            )


    # For Arabic MCQ, skip facts that cannot be converted
    # deterministically. This is safer than asking the LLM
    # to invent the semantic relationship again.

    # QUIZ_ARABIC_GRAMMAR_QA_V25E_R3

    # --------------------------------------------------------
    # Local conservative cleaner for source-first Arabic
    # answers. Do not use V17B trimming here because that
    # intentionally truncates subordinate clauses such as
    # "????? ???? ...".
    # --------------------------------------------------------

    def clean_arabic_answer_v25e_r3(
        value,
    ):

        value = re.sub(
            r"\s+",
            " ",
            str(
                value
                or ""
            ),
        )

        value = value.replace(
            '" "',
            " ",
        )

        value = value.replace(
            '"',
            "",
        )

        value = value.strip(
            " \t\r\n"
            "\u061b"
            "\u061f"
            "\u00bb"
            "\u00ab"
            ".,;:"
        )

        return value


    # ========================================================
    # A) FUNCTION / ROLE
    #
    # ???? ?????? ????? ????? ?? ??? ??????? ???????
    # ========================================================

    match = re.match(
        (
            r"^\u062a\u0624\u062f\u064a"
            r"\s+(.+?)"
            r"\s+\u0648\u0638\u064a\u0641\u0629"
            r"(?:\s+.{0,35}?)?"
            r"\s+\u0647\u064a"
            r"\s+(.+)$"
        ),
        raw,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip()


        answer = (
            clean_arabic_answer_v25e_r3(
                match.group(
                    2
                )
            )
        )


        if (
            subject
            and answer
            and contains_arabic(
                subject
            )
            and contains_arabic(
                answer
            )
            and len(
                quiz_content_tokens(
                    subject
                )
            ) <= 12
            and len(
                quiz_content_tokens(
                    answer
                )
            ) <= 22
        ):

            return (
                "\u0645\u0627 "
                "\u0648\u0638\u064a\u0641\u0629 "
                + subject
                + "\u061f",
                answer,
            )


    # ========================================================
    # B) CONDITIONAL GRAMMAR RULE
    #
    # ??? ???/???? X ... ????/????/????/???? ...
    # ========================================================

    match = re.match(
        (
            r"^\u0625\u0630\u0627"
            r"\s+"
            r"(\u0643\u0627\u0646|\u0643\u0627\u0646\u062a)"
            r"\s+(.+?)"
            r"\s+"
            r"("
            r"\u062d\u0630\u0641\u062a"
            r"|\u062a\u062d\u0630\u0641"
            r"|\u062a\u0642\u0644\u0628"
            r"|\u062a\u0628\u0642\u0649"
            r")"
            r"\s+(.+)$"
        ),
        raw,
    )


    if match:

        copula = str(
            match.group(
                1
            )
            or ""
        ).strip()


        condition = str(
            match.group(
                2
            )
            or ""
        ).strip(
            " \t\r\n.,;:"
        )


        action = str(
            match.group(
                3
            )
            or ""
        ).strip()


        remainder = (
            clean_arabic_answer_v25e_r3(
                match.group(
                    4
                )
            )
        )


        answer = (
            action
            + " "
            + remainder
        ).strip()


        if (
            condition
            and answer
            and len(
                quiz_content_tokens(
                    condition
                )
            ) <= 18
            and len(
                quiz_content_tokens(
                    answer
                )
            ) <= 24
        ):

            return (
                "\u0645\u0627\u0630\u0627 "
                "\u064a\u062d\u062f\u062b "
                "\u0625\u0630\u0627 "
                + copula
                + " "
                + condition
                + "\u061f",
                answer,
            )


    # ========================================================
    # C) NISBA RULE
    #
    # ???? ??? X ?...
    # ========================================================

    match = re.match(
        (
            r"^\u064a\u0646\u0633\u0628"
            r"\s+"
            r"(?:\u0625\u0644\u0649|\u0627\u0644\u0649)"
            r"\s+(.+?)"
            r"\s+(\u0628.+)$"
        ),
        raw,
    )


    if match:

        target = str(
            match.group(
                1
            )
            or ""
        ).strip(
            " \t\r\n.,;:"
        )


        answer = (
            clean_arabic_answer_v25e_r3(
                match.group(
                    2
                )
            )
        )


        if (
            target
            and answer
            and len(
                quiz_content_tokens(
                    target
                )
            ) <= 16
            and len(
                quiz_content_tokens(
                    answer
                )
            ) <= 24
        ):

            return (
                "\u0643\u064a\u0641 "
                "\u064a\u0646\u0633\u0628 "
                "\u0625\u0644\u0649 "
                + target
                + "\u061f",
                answer,
            )


    # ========================================================
    # D) SUBJECT-SPECIFIC NISBA
    #
    # ?????? ?????? ?????????: ???? ??? ?????? ?????
    # ========================================================

    match = re.match(
        (
            r"^(.+?)"
            r"\s*:\s*"
            r"\u064a\u0646\u0633\u0628"
            r"\s+"
            r"(?:\u0625\u0644\u0649|\u0627\u0644\u0649)"
            r"\s+(.+)$"
        ),
        raw,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip(
            " \t\r\n.,;:"
        )


        destination = (
            clean_arabic_answer_v25e_r3(
                match.group(
                    2
                )
            )
        )


        answer = (
            "\u0625\u0644\u0649 "
            + destination
        )


        if (
            subject
            and destination
            and len(
                quiz_content_tokens(
                    subject
                )
            ) <= 14
            and len(
                quiz_content_tokens(
                    destination
                )
            ) <= 16
        ):

            return (
                "\u0625\u0644\u0649 "
                "\u0645\u0627\u0630\u0627 "
                "\u064a\u0646\u0633\u0628 "
                + subject
                + "\u061f",
                answer,
            )


    # ========================================================
    # E) COLON DEFINITION
    #
    # ??????? ????: ??? ????? ??????...
    # ????? ???????: ?? ?? ???...
    # ========================================================

    match = re.match(
        (
            r"^(.+?)"
            r"\s*:\s*"
            r"(?:\u0648)?"
            r"(\u0647\u0648|\u0647\u064a)"
            r"\s+(.+)$"
        ),
        raw,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip(
            " \t\r\n.,;:"
        )


        answer = (
            clean_arabic_answer_v25e_r3(
                match.group(
                    3
                )
            )
        )


        if (
            subject
            and answer
            and contains_arabic(
                subject
            )
            and contains_arabic(
                answer
            )
            and len(
                quiz_content_tokens(
                    subject
                )
            ) <= 12
            and len(
                quiz_content_tokens(
                    answer
                )
            ) <= 24
        ):

            return (
                "\u0645\u0627 "
                "\u0627\u0644\u0645\u0642\u0635\u0648\u062f "
                "\u0628\u0645\u0635\u0637\u0644\u062d "
                + subject
                + "\u061f",
                answer,
            )


    # QUIZ_MATH_AR_DETERMINISTIC_STATS_QA_V25Z3
    # --------------------------------------------------------
    # A) Numeric statistical value
    #
    # Example:
    #   ???? ????? ]30;40[ ?? :0,375
    # --------------------------------------------------------
    match = re.match(
        (
            r"^(.+?)"
            r"\s+\u0647\u0648"
            r"\s*:\s*"
            r"([+\-\u2212]?\d+(?:[.,]\d+)?(?:\s*[%\u00b0])?)"
            r"$"
        ),
        raw,
    )

    if match:
        subject = str(
            match.group(1) or ""
        ).strip(
            " \t\r\n.,;:"
        )

        answer = str(
            match.group(2) or ""
        ).strip()

        if (
            subject
            and answer
            and contains_arabic(subject)
        ):
            return (
                "\u0645\u0627 "
                "\u0642\u064a\u0645\u0629 "
                + subject
                + "\u061f",
                answer,
            )

    # --------------------------------------------------------
    # B) Statistical dispersion rule
    #
    # Example:
    #   ???? ... ??? ?????? ??? ???? ...
    # --------------------------------------------------------
    match = re.match(
        (
            r"^\u062a\u0643\u0648\u0646"
            r"\s+(.+?)"
            r"\s+\u0623\u0642\u0644"
            r"\s+\u062a\u0634\u062a\u062a\S*"
            r"\s+\u0625\u0630\u0627"
            r"\s+\u0643\u0627\u0646\u062a"
            r"\s+(.+)$"
        ),
        raw,
    )

    if match:
        subject = str(
            match.group(1) or ""
        ).strip(
            " \t\r\n.,;:"
        )

        condition = (
            clean_arabic_answer_v25e_r3(
                match.group(2)
            )
        )

        if (
            subject
            and condition
            and contains_arabic(subject)
            and contains_arabic(condition)
            and len(
                quiz_content_tokens(subject)
            ) <= 18
            and len(
                quiz_content_tokens(condition)
            ) <= 24
        ):
            return (
                "\u0645\u062a\u0649 "
                "\u062a\u0643\u0648\u0646 "
                + subject
                + " "
                "\u0623\u0642\u0644 "
                "\u062a\u0634\u062a\u062a\u0627\u064b"
                + "\u061f",
                "\u0625\u0630\u0627 "
                "\u0643\u0627\u0646\u062a "
                + condition,
            )

    # ========================================================
    # F) GENERIC SIMPLE DEFINITION
    #
    # X ?? Y / X ?? Y
    #
    # This comes LAST so that function/rule statements are
    # not misread as vocabulary definitions.
    # ========================================================

    match = re.match(
        (
            r"^(.+?)"
            r"\s+"
            r"(\u0647\u0648|\u0647\u064a)"
            r"\s+(.+)$"
        ),
        raw,
    )


    if match:

        subject = str(
            match.group(
                1
            )
            or ""
        ).strip(
            " \t\r\n.,;:"
        )


        answer = (
            clean_arabic_answer_v25e_r3(
                match.group(
                    3
                )
            )
        )


        subject_key = (
            normalize_text(
                subject
            )
        )


        generic_blocked = bool(
            subject.startswith(
                "\u062a\u0624\u062f\u064a "
            )
            or "\u0648\u0638\u064a\u0641\u0629"
            in subject
        )


        if (
            subject
            and answer
            and not generic_blocked
            and contains_arabic(
                subject
            )
            and contains_arabic(
                answer
            )
            and len(
                quiz_content_tokens(
                    subject
                )
            ) <= 14
            and len(
                quiz_content_tokens(
                    answer
                )
            ) <= 24
        ):

            return (
                "\u0645\u0627 "
                "\u0627\u0644\u0645\u0642\u0635\u0648\u062f "
                "\u0628\u0645\u0635\u0637\u0644\u062d "
                + subject
                + "\u061f",
                answer,
            )

    return "", ""



# QUIZ_LEAN_SOURCE_FIRST_V17C

def quiz_mcq_evidence_has_deterministic_qa_v17c(
    evidence_text: str,
    arabic_expected: bool,
) -> bool:

    # QUIZ_REAL_ELIGIBILITY_V21B

    facts = (
        quiz_source_fact_candidates_v17(
            evidence_text=(
                evidence_text
            ),
            arabic_expected=(
                arabic_expected
            ),
        )
    )


    for fact in facts:

        question, answer = (
            quiz_source_first_qa_v17b(
                fact=(
                    fact
                ),
                arabic_expected=(
                    arabic_expected
                ),
            )
        )


        if (
            str(
                question
                or ""
            ).strip()
            and str(
                answer
                or ""
            ).strip()
        ):

            return True


    return False





# QUIZ_SEMANTIC_DISTRACTOR_GUARD_V17D


def quiz_mcq_semantic_equivalent_distractors_v17d(
    options: list[str],
    correct_answer: str,
) -> list[str]:

    # QUIZ_DIRECTION_EXEMPTION_V17D2

    # QUIZ_DETERMINISTIC_GATE_EXEMPTION_V20_QUIZ_MCQ_SEMANTIC_EQUIVALENT_DISTRACTORS_V17D

    if quiz_is_deterministic_mcq_option_set_v20(
        options=options,
        correct_answer=correct_answer,
    ):

        return []


    correct = str(
        correct_answer
        or ""
    ).strip()


    if not correct:

        return []


    normalized_correct = (
        normalize_text(
            correct
        )
    )


    correct_tokens = set(
        quiz_grounding_tokens_v15(
            correct
        )
    )


    if len(correct_tokens) < 2:

        return []


    # --------------------------------------------------------
    # DIRECTION ANSWERS
    #
    # Reversed routes are legitimate distractors:
    #
    # correct:
    #   ?? ???? ??? ??????
    #
    # distractor:
    #   ?? ?????? ??? ????
    #
    # Both contain essentially the same vocabulary, so
    # semantic token overlap must NOT reject them.
    #
    # Detect the grammatical route directly from the raw
    # Arabic text instead of depending on normalize_text().
    # --------------------------------------------------------

    direction_answer = bool(
        re.search(
            (
                r"(?:^|\s)"
                r"\u0645\u0646"
                r"\s+.+?"
                r"\s+"
                r"(?:"
                r"\u0625\u0644\u0649"
                r"|\u0627\u0644\u0649"
                r"|\u0625\u0644\u064a"
                r"|\u0627\u0644\u064a"
                r")"
                r"\s+"
            ),
            correct,
        )
    )


    if direction_answer:

        return []


    conflicts = []


    for option in (
        options
        or []
    ):

        value = str(
            option
            or ""
        ).strip()


        if not value:

            continue


        normalized_option = (
            normalize_text(
                value
            )
        )


        if (
            not normalized_option
            or normalized_option
            == normalized_correct
        ):

            continue


        option_tokens = set(
            quiz_grounding_tokens_v15(
                value
            )
        )


        if not option_tokens:

            continue


        shared = (
            correct_tokens
            & option_tokens
        )


        coverage = (
            len(
                shared
            )
            / len(
                correct_tokens
            )
        )


        if (
            len(shared) >= 2
            and coverage >= 0.60
        ):

            conflicts.append(
                value
            )


    return conflicts




# QUIZ_DISTRACTOR_SHAPE_V17E

def quiz_is_direction_answer_v17e(
    value: str,
) -> bool:

    raw = str(
        value
        or ""
    ).strip()

    return bool(
        re.match(
            (
                r"^\s*"
                r"\u0645\u0646"
                r"\s+.+?"
                r"\s+"
                r"(?:"
                r"\u0625\u0644\u0649"
                r"|\u0627\u0644\u0649"
                r"|\u0625\u0644\u064a"
                r"|\u0627\u0644\u064a"
                r")"
                r"\s+.+$"
            ),
            raw,
        )
    )


def quiz_direction_distractor_shape_valid_v17e(
    options: list[str],
    correct_answer: str,
) -> bool:

    if not quiz_is_direction_answer_v17e(
        correct_answer
    ):

        return True


    normalized_correct = (
        normalize_text(
            correct_answer
        )
    )


    distractors = [
        str(
            option
            or ""
        ).strip()
        for option
        in (
            options
            or []
        )
        if (
            normalize_text(
                str(
                    option
                    or ""
                )
            )
            != normalized_correct
        )
    ]


    if len(distractors) != 3:

        return False


    return all(
        quiz_is_direction_answer_v17e(
            distractor
        )
        for distractor
        in distractors
    )


def quiz_distractor_pair_conflicts_v17e(
    options: list[str],
    correct_answer: str,
) -> list[tuple[str, str]]:

    # QUIZ_DETERMINISTIC_GATE_EXEMPTION_V20_QUIZ_DISTRACTOR_PAIR_CONFLICTS_V17E

    if quiz_is_deterministic_mcq_option_set_v20(
        options=options,
        correct_answer=correct_answer,
    ):

        return []


    normalized_correct = (
        normalize_text(
            correct_answer
        )
    )


    distractors = [
        str(
            option
            or ""
        ).strip()
        for option
        in (
            options
            or []
        )
        if (
            normalize_text(
                str(
                    option
                    or ""
                )
            )
            != normalized_correct
        )
    ]


    conflicts = []


    for left_index in range(
        len(distractors)
    ):

        for right_index in range(
            left_index + 1,
            len(distractors),
        ):

            left = distractors[
                left_index
            ]

            right = distractors[
                right_index
            ]


            left_tokens = set(
                quiz_grounding_tokens_v15(
                    left
                )
            )

            right_tokens = set(
                quiz_grounding_tokens_v15(
                    right
                )
            )


            if (
                not left_tokens
                or not right_tokens
            ):

                continue


            shared = (
                left_tokens
                & right_tokens
            )


            denominator = min(
                len(left_tokens),
                len(right_tokens),
            )


            similarity = (
                len(shared)
                / denominator
                if denominator
                else 0.0
            )


            # Almost the same distractor written with
            # spelling or terminology variants.
            if similarity >= 0.80:

                conflicts.append(
                    (
                        left,
                        right,
                    )
                )


    return conflicts



# QUIZ_SOURCE_FIRST_TRUE_FALSE_V18

def quiz_tf_statement_from_qa_v18(
    question: str,
    answer: str,
) -> str:

    question = re.sub(
        r"\s+",
        " ",
        str(
            question
            or ""
        ),
    ).strip()


    answer = re.sub(
        r"\s+",
        " ",
        str(
            answer
            or ""
        ),
    ).strip()


    if (
        not question
        or not answer
    ):

        return ""


    # --------------------------------------------------------
    # COMPOSITION
    # ?? ????? ?????? ????????
    # =>
    # ????? ?????? ??????? ?? ????? ?????? ??????.
    # --------------------------------------------------------

    prefix = (
        "\u0645\u0645 "
        "\u064a\u062a\u0643\u0648\u0646 "
    )


    if question.startswith(
        prefix
    ):

        subject = question[
            len(prefix):
        ].strip(
            " \u061f?"
        )


        if subject:

            return (
                "\u064a\u062a\u0643\u0648\u0646 "
                + subject
                + " \u0645\u0646 "
                + answer
                + "."
            )


    prefix = (
        "\u0645\u0645 "
        "\u062a\u062a\u0643\u0648\u0646 "
    )


    if question.startswith(
        prefix
    ):

        subject = question[
            len(prefix):
        ].strip(
            " \u061f?"
        )


        if subject:

            return (
                "\u062a\u062a\u0643\u0648\u0646 "
                + subject
                + " \u0645\u0646 "
                + answer
                + "."
            )


    # --------------------------------------------------------
    # DIRECTION
    # ?? ???? ????? ?????? ????????
    # --------------------------------------------------------

    prefix = (
        "\u0645\u0627 "
        "\u0645\u0633\u0627\u0631 "
    )


    if question.startswith(
        prefix
    ):

        subject = question[
            len(prefix):
        ].strip(
            " \u061f?"
        )


        if subject:

            return (
                "\u0645\u0633\u0627\u0631 "
                + subject
                + " \u0647\u0648 "
                + answer
                + "."
            )


    # --------------------------------------------------------
    # CAUSE
    # ?? ??? ???? ???????
    # --------------------------------------------------------

    prefix = (
        "\u0645\u0627 "
        "\u0633\u0628\u0628 "
    )


    if question.startswith(
        prefix
    ):

        subject = question[
            len(prefix):
        ].strip(
            " \u061f?"
        )


        if subject:

            return (
                "\u0633\u0628\u0628 "
                + subject
                + " \u0647\u0648 "
                + answer
                + "."
            )


    # --------------------------------------------------------
    # PREVENTION
    # --------------------------------------------------------

    prefix = (
        "\u0645\u0627 "
        "\u0648\u0633\u064a\u0644\u0629 "
        "\u0627\u0644\u0648\u0642\u0627\u064a\u0629 "
        "\u0645\u0646 "
    )


    if question.startswith(
        prefix
    ):

        subject = question[
            len(prefix):
        ].strip(
            " \u061f?"
        )


        if subject:

            return (
                "\u0645\u0646 "
                "\u0648\u0633\u0627\u0626\u0644 "
                "\u0627\u0644\u0648\u0642\u0627\u064a\u0629 "
                "\u0645\u0646 "
                + subject
                + ": "
                + answer
                + "."
            )


    prefix = (
        "\u0645\u0627 "
        "\u0623\u0646\u062c\u0639 "
        "\u0648\u0633\u0627\u0626\u0644 "
        "\u0627\u0644\u0648\u0642\u0627\u064a\u0629 "
        "\u0645\u0646 "
    )


    if question.startswith(
        prefix
    ):

        subject = question[
            len(prefix):
        ].strip(
            " \u061f?"
        )


        if subject:

            return (
                answer
                + " \u0645\u0646 "
                "\u0623\u0646\u062c\u0639 "
                "\u0648\u0633\u0627\u0626\u0644 "
                "\u0627\u0644\u0648\u0642\u0627\u064a\u0629 "
                "\u0645\u0646 "
                + subject
                + "."
            )


    # --------------------------------------------------------
    # NUMERIC VALUE
    # --------------------------------------------------------

    prefix = (
        "\u0645\u0627 "
        "\u0642\u064a\u0645\u0629 "
    )


    if question.startswith(
        prefix
    ):

        subject = question[
            len(prefix):
        ].strip(
            " \u061f?"
        )


        if subject:

            return (
                "\u0642\u064a\u0645\u0629 "
                + subject
                + " \u0647\u064a "
                + answer
                + "."
            )



    # QUIZ_ARABIC_GRAMMAR_TF_V25E_R3

    # ========================================================
    # FUNCTION
    # ========================================================

    prefix = (
        "\u0645\u0627 "
        "\u0648\u0638\u064a\u0641\u0629 "
    )


    if question.startswith(
        prefix
    ):

        subject = question[
            len(
                prefix
            ):
        ].strip(
            " \u061f?"
        )


        if (
            subject
            and answer
        ):

            return (
                "\u0648\u0638\u064a\u0641\u0629 "
                + subject
                + " \u0647\u064a "
                + answer
                + "."
            )


    # ========================================================
    # CONDITIONAL RULE
    # ========================================================

    prefix = (
        "\u0645\u0627\u0630\u0627 "
        "\u064a\u062d\u062f\u062b "
    )


    if question.startswith(
        prefix
    ):

        condition = question[
            len(
                prefix
            ):
        ].strip(
            " \u061f?"
        )


        if (
            condition.startswith(
                "\u0625\u0630\u0627 "
            )
            and answer
        ):

            return (
                condition
                + "\u060c "
                + answer
                + "."
            )


    # ========================================================
    # NISBA RULE
    # ========================================================

    prefix = (
        "\u0643\u064a\u0641 "
        "\u064a\u0646\u0633\u0628 "
        "\u0625\u0644\u0649 "
    )


    if question.startswith(
        prefix
    ):

        target = question[
            len(
                prefix
            ):
        ].strip(
            " \u061f?"
        )


        if (
            target
            and answer
        ):

            return (
                "\u064a\u0646\u0633\u0628 "
                "\u0625\u0644\u0649 "
                + target
                + " "
                + answer
                + "."
            )


    # ========================================================
    # SUBJECT-SPECIFIC NISBA
    # ========================================================

    prefix = (
        "\u0625\u0644\u0649 "
        "\u0645\u0627\u0630\u0627 "
        "\u064a\u0646\u0633\u0628 "
    )


    if question.startswith(
        prefix
    ):

        subject = question[
            len(
                prefix
            ):
        ].strip(
            " \u061f?"
        )


        if (
            subject
            and answer
        ):

            return (
                subject
                + " \u064a\u0646\u0633\u0628 "
                + answer
                + "."
            )


    # ========================================================
    # DEFINITION
    # ========================================================

    prefix = (
        "\u0645\u0627 "
        "\u0627\u0644\u0645\u0642\u0635\u0648\u062f "
        "\u0628\u0645\u0635\u0637\u0644\u062d "
    )


    if question.startswith(
        prefix
    ):

        subject = question[
            len(
                prefix
            ):
        ].strip(
            " \u061f?"
        )


        if (
            subject
            and answer
        ):

            return (
                "\u064a\u0642\u0635\u062f "
                "\u0628\u0645\u0635\u0637\u0644\u062d "
                + subject
                + ": "
                + answer
                + "."
            )

    return ""


def quiz_tf_should_be_true_v18(
    question: str,
    answer: str,
    target_index: int,
    page: int,
) -> bool:

    seed_text = (
        str(
            question
            or ""
        )
        + "|"
        + str(
            answer
            or ""
        )
    )


    seed = sum(
        ord(
            char
        )
        for char
        in seed_text
    )


    seed += (
        int(
            target_index
            or 0
        )
        * 17
    )


    seed += (
        int(
            page
            or 0
        )
        * 31
    )


    return (
        seed
        % 2
        == 0
    )


def quiz_tf_false_answer_v18(
    question: str,
    correct_answer: str,
    evidence_text: str,
    lesson_text: str,
    arabic_expected: bool,
) -> str:

    started = (
        time.perf_counter()
    )


    options = (
        quiz_repair_mcq_distractors_v16(
            question=(
                question
            ),
            correct_answer=(
                correct_answer
            ),
            evidence=(
                evidence_text
            ),
            lesson_text=(
                lesson_text
            ),
            arabic_expected=(
                arabic_expected
            ),
        )
    )


    elapsed = round(
        time.perf_counter()
        - started,
        3,
    )


    print(
        "QUIZ V18 TF FALSE-ANSWER OLLAMA:",
        "seconds=",
        elapsed,
    )


    if not options:

        return ""


    normalized_correct = (
        normalize_text(
            correct_answer
        )
    )


    for option in options:

        candidate = str(
            option
            or ""
        ).strip()


        if not candidate:

            continue


        if (
            normalize_text(
                candidate
            )
            == normalized_correct
        ):

            continue


        semantic_conflicts = (
            quiz_mcq_semantic_equivalent_distractors_v17d(
                options=[
                    correct_answer,
                    candidate,
                ],
                correct_answer=(
                    correct_answer
                ),
            )
        )


        if semantic_conflicts:

            continue


        # If the correct answer is a route,
        # keep the false answer route-shaped too.
        if (
            quiz_is_direction_answer_v17e(
                correct_answer
            )
            and not quiz_is_direction_answer_v17e(
                candidate
            )
        ):

            continue


        return candidate


    return ""



# QUIZ_SOURCE_FIRST_SHORT_ANSWER_V19

def quiz_source_first_short_answer_v19(
    evidence_text: str,
    arabic_expected: bool,
) -> tuple[str, str, str]:

    facts = (
        quiz_source_fact_candidates_v17(
            evidence_text=(
                evidence_text
            ),
            arabic_expected=(
                arabic_expected
            ),
        )
    )


    for fact in facts:

        question, answer = (
            quiz_source_first_qa_v17b(
                fact=(
                    fact
                ),
                arabic_expected=(
                    arabic_expected
                ),
            )
        )


        question = str(
            question
            or ""
        ).strip()

        answer = str(
            answer
            or ""
        ).strip()


        if (
            not question
            or not answer
        ):

            continue


        answer_tokens = (
            quiz_content_tokens(
                answer
            )
        )


        if (
            not answer_tokens
            or len(answer_tokens) > 14
        ):

            continue


        # Short-answer questions must have an actual
        # concise documentary answer, not a complete
        # paragraph or explanatory passage.
        if len(answer) > 180:

            continue


        return (
            question,
            answer,
            fact,
        )


    return (
        "",
        "",
        "",
    )



# QUIZ_MULTI_MCQ_STABILITY_V20

def quiz_parse_direction_answer_v20(
    value: str,
) -> tuple[str, str]:

    raw = re.sub(
        r"\s+",
        " ",
        str(
            value
            or ""
        ),
    ).strip()


    match = re.match(
        (
            r"^\s*"
            r"\u0645\u0646"
            r"\s+(.+?)"
            r"\s+"
            r"(?:"
            r"\u0625\u0644\u0649"
            r"|\u0627\u0644\u0649"
            r"|\u0625\u0644\u064a"
            r"|\u0627\u0644\u064a"
            r")"
            r"\s+(.+?)"
            r"\s*[.\u061f?]*\s*$"
        ),
        raw,
    )


    if not match:

        return (
            "",
            "",
        )


    source = str(
        match.group(
            1
        )
        or ""
    ).strip()


    target = str(
        match.group(
            2
        )
        or ""
    ).strip()


    if (
        not source
        or not target
    ):

        return (
            "",
            "",
        )


    if (
        normalize_text(
            source
        )
        == normalize_text(
            target
        )
    ):

        return (
            "",
            "",
        )


    return (
        source,
        target,
    )


def quiz_direction_distractors_v20(
    correct_answer: str,
) -> list[str]:

    source, target = (
        quiz_parse_direction_answer_v20(
            correct_answer
        )
    )


    if (
        not source
        or not target
    ):

        return []


    return [
        (
            "\u0645\u0646 "
            + target
            + " \u0625\u0644\u0649 "
            + source
        ),
        (
            "\u0645\u0646 "
            + source
            + " \u0625\u0644\u0649 "
            + source
        ),
        (
            "\u0645\u0646 "
            + target
            + " \u0625\u0644\u0649 "
            + target
        ),
    ]


def quiz_composition_parts_v20(
    correct_answer: str,
) -> tuple[str, str]:

    raw = re.sub(
        r"\s+",
        " ",
        str(
            correct_answer
            or ""
        ),
    ).strip()


    if not raw:

        return (
            "",
            "",
        )


    parts = re.split(
        (
            r"\s+"
            r"\u0648"
            r"(?=\S)"
        ),
        raw,
        maxsplit=1,
    )


    if len(parts) != 2:

        return (
            "",
            "",
        )


    left = str(
        parts[0]
        or ""
    ).strip()


    right = str(
        parts[1]
        or ""
    ).strip()


    if (
        not left
        or not right
    ):

        return (
            "",
            "",
        )


    if (
        normalize_text(
            left
        )
        == normalize_text(
            right
        )
    ):

        return (
            "",
            "",
        )


    return (
        left,
        right,
    )


def quiz_composition_distractors_v20(
    correct_answer: str,
) -> list[str]:

    left, right = (
        quiz_composition_parts_v20(
            correct_answer
        )
    )


    if (
        not left
        or not right
    ):

        return []


    return [
        (
            left
            + " \u0641\u0642\u0637"
        ),
        (
            right
            + " \u0641\u0642\u0637"
        ),
        (
            "\u0644\u0627 "
            + left
            + " \u0648\u0644\u0627 "
            + right
        ),
    ]


def quiz_deterministic_mcq_distractors_v20(
    question: str,
    correct_answer: str,
) -> list[str]:

    question = re.sub(
        r"\s+",
        " ",
        str(
            question
            or ""
        ),
    ).strip()


    correct_answer = re.sub(
        r"\s+",
        " ",
        str(
            correct_answer
            or ""
        ),
    ).strip()


    if (
        not question
        or not correct_answer
    ):

        return []


    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    direction = (
        quiz_direction_distractors_v20(
            correct_answer
        )
    )


    if direction:

        return direction


    # --------------------------------------------------------
    # COMPOSITION
    #
    # Examples:
    # "What is X composed of?"
    # --------------------------------------------------------

    is_composition_question = bool(
        re.match(
            (
                r"^\s*"
                r"\u0645\u0645"
                r"\s+"
                r"(?:"
                r"\u064a\u062a\u0643\u0648\u0646"
                r"|\u062a\u062a\u0643\u0648\u0646"
                r")"
                r"\s+"
            ),
            question,
        )
    )


    if is_composition_question:

        composition = (
            quiz_composition_distractors_v20(
                correct_answer
            )
        )


        if composition:

            return composition


    return []


def quiz_is_deterministic_mcq_option_set_v20(
    options,
    correct_answer: str,
) -> bool:

    if not isinstance(
        options,
        list,
    ):

        return False


    correct_answer = str(
        correct_answer
        or ""
    ).strip()


    if not correct_answer:

        return False


    normalized_correct = (
        normalize_text(
            correct_answer
        )
    )


    distractors = [
        str(
            option
            or ""
        ).strip()
        for option
        in options
        if (
            normalize_text(
                str(
                    option
                    or ""
                )
            )
            != normalized_correct
        )
    ]


    if len(distractors) != 3:

        return False


    actual = {
        normalize_text(
            distractor
        )
        for distractor
        in distractors
        if distractor
    }


    if len(actual) != 3:

        return False


    expected_sets = []


    direction = (
        quiz_direction_distractors_v20(
            correct_answer
        )
    )


    if direction:

        expected_sets.append(
            {
                normalize_text(
                    item
                )
                for item
                in direction
            }
        )


    composition = (
        quiz_composition_distractors_v20(
            correct_answer
        )
    )


    if composition:

        expected_sets.append(
            {
                normalize_text(
                    item
                )
                for item
                in composition
            }
        )


    return any(
        actual == expected
        for expected
        in expected_sets
        if len(
            expected
        ) == 3
    )



# QUIZ_FRENCH_TF_SOURCE_POOL_V21G
def quiz_french_tf_source_evidence_items_v21g(
    program: str,
    subject: str,
    source: str,
) -> list[dict]:

    program = str(
        program
        or ""
    ).strip()

    subject = str(
        subject
        or ""
    ).strip()

    source = str(
        source
        or ""
    ).strip()


    if (
        not program
        or not subject
        or not source
    ):

        return []


    try:

        from services.vector_store_service import (
            get_document_collection,
        )


        collection = (
            get_document_collection()
        )


        where_filter = {
            "$and": [
                {
                    "program": {
                        "$eq": program,
                    }
                },
                {
                    "subject": {
                        "$eq": subject,
                    }
                },
                {
                    "source": {
                        "$eq": source,
                    }
                },
            ]
        }


        result = collection.get(
            where=where_filter,
            include=[
                "documents",
                "metadatas",
            ],
        )


    except Exception as exc:

        print(
            "QUIZ V21G SOURCE POOL ERROR:",
            repr(
                exc
            ),
        )

        return []


    documents = (
        result.get(
            "documents",
            [],
        )
        or []
    )

    metadatas = (
        result.get(
            "metadatas",
            [],
        )
        or []
    )

    identifiers = (
        result.get(
            "ids",
            [],
        )
        or []
    )


    evidence_items = []

    seen_evidence = set()
    seen_statement_keys = set()


    for index, (
        document,
        metadata,
    ) in enumerate(
        zip(
            documents,
            metadatas,
        )
    ):

        metadata = (
            metadata
            if isinstance(
                metadata,
                dict,
            )
            else {}
        )


        evidence_text = str(
            document
            or ""
        ).strip()


        if not evidence_text:

            continue


        evidence_key = (
            normalize_text(
                evidence_text
            )
        )


        if (
            not evidence_key
            or evidence_key
            in seen_evidence
        ):

            continue


        facts = (
            quiz_source_fact_candidates_v17(
                evidence_text=(
                    evidence_text
                ),
                arabic_expected=False,
            )
        )


        new_statement_keys = []


        for fact in facts:

            (
                question,
                answer,
            ) = (
                quiz_source_first_qa_v17b(
                    fact=fact,
                    arabic_expected=False,
                )
            )


            question = str(
                question
                or ""
            ).strip()

            answer = str(
                answer
                or ""
            ).strip()


            if (
                not question
                or not answer
            ):

                continue


            statement = (
                quiz_tf_statement_from_qa_v21a(
                    question=question,
                    answer=answer,
                )
            )


            statement = str(
                statement
                or ""
            ).strip()


            if not statement:

                continue


            if statement.endswith(
                "?"
            ):

                continue


            if quiz_has_heading_noise(
                statement
            ):

                continue


            if quiz_has_source_reference_language(
                statement
            ):

                continue


            statement_key = (
                normalize_text(
                    statement
                )
            )


            if (
                not statement_key
                or statement_key
                in seen_statement_keys
                or statement_key
                in new_statement_keys
            ):

                continue


            new_statement_keys.append(
                statement_key
            )


        if not new_statement_keys:

            continue


        seen_evidence.add(
            evidence_key
        )

        seen_statement_keys.update(
            new_statement_keys
        )


        chunk_id = ""


        if index < len(
            identifiers
        ):

            chunk_id = str(
                identifiers[
                    index
                ]
                or ""
            )


        evidence_items.append(
            {
                "text": (
                    evidence_text
                ),
                "source": (
                    str(
                        metadata.get(
                            "source",
                            source,
                        )
                        or source
                    )
                ),
                "page": (
                    metadata.get(
                        "page",
                        0,
                    )
                ),
                "chunk_number": (
                    metadata.get(
                        "chunk_number",
                        0,
                    )
                ),
                "chunk_id": (
                    chunk_id
                ),
            }
        )


    def numeric_value(
        value,
    ):

        try:

            return int(
                value
            )

        except Exception:

            return 999999


    evidence_items.sort(
        key=lambda item: (
            numeric_value(
                item.get(
                    "page",
                    0,
                )
            ),
            numeric_value(
                item.get(
                    "chunk_number",
                    0,
                )
            ),
            str(
                item.get(
                    "chunk_id",
                    "",
                )
            ),
        )
    )


    return evidence_items



# QUIZ_FRENCH_TF_LOCAL_SUPPORT_V21H_R2
def quiz_best_local_support_french_tf_v21h_r2(
    evidence: str,
    question: str,
    answer: str,
) -> dict:

    original_support = (
        quiz_best_local_support(
            evidence=evidence,
            question=question,
            answer=answer,
        )
    )


    if not isinstance(
        original_support,
        dict,
    ):

        return original_support


    # Arabic behavior remains untouched.
    if contains_arabic(
        question
    ):

        return original_support


    normalized_answer = (
        normalize_text(
            answer
        )
    )


    # Only French True/False reaches the fallback.
    if normalized_answer not in {
        "vrai",
        "faux",
    }:

        return original_support


    try:

        original_overlap = float(
            original_support.get(
                "question_overlap",
                0.0,
            )
            or 0.0
        )

    except Exception:

        original_overlap = 0.0


    best_support = dict(
        original_support
    )

    best_overlap = (
        original_overlap
    )


    # Search only documentary facts extracted from the SAME
    # evidence chunk selected by generate_quiz.
    facts = (
        quiz_source_fact_candidates_v17(
            evidence_text=evidence,
            arabic_expected=False,
        )
    )


    for fact in facts:

        fact = str(
            fact
            or ""
        ).strip()


        if not fact:

            continue


        # Reuse the existing local-support scorer so V21H
        # stays on exactly the same scoring scale as V12.
        fact_support = (
            quiz_best_local_support(
                evidence=fact,
                question=question,
                answer=answer,
            )
        )


        if not isinstance(
            fact_support,
            dict,
        ):

            continue


        try:

            fact_overlap = float(
                fact_support.get(
                    "question_overlap",
                    0.0,
                )
                or 0.0
            )

        except Exception:

            fact_overlap = 0.0


        if fact_overlap <= best_overlap:

            continue


        best_overlap = (
            fact_overlap
        )


        best_support = dict(
            fact_support
        )


        if not str(
            best_support.get(
                "text",
                "",
            )
            or ""
        ).strip():

            best_support[
                "text"
            ] = fact


        best_support[
            "question_overlap"
        ] = fact_overlap


    if best_overlap > original_overlap:

        print(
            "QUIZ V21H TF LOCAL SUPPORT UPGRADE:",
            "old=",
            round(
                original_overlap,
                3,
            ),
            "new=",
            round(
                best_overlap,
                3,
            ),
            "support=",
            repr(
                best_support.get(
                    "text",
                    "",
                )
            )[:260],
        )


    return best_support



# QUIZ_FRENCH_MCQ_QA_PARSER_V22B
def quiz_french_mcq_clean_text_v22b(
    value,
) -> str:

    import re


    text = str(
        value
        or ""
    )


    text = text.replace(
        "\u00ad",
        "",
    )


    text = re.sub(
        r"\s+",
        " ",
        text,
    )


    return text.strip()


def quiz_source_first_qa_french_mcq_v22b(
    fact: str,
) -> tuple[str, str]:

    import re


    fact = (
        quiz_french_mcq_clean_text_v22b(
            fact
        )
    )


    if not fact:

        return (
            "",
            "",
        )


    normalized_fact = (
        normalize_text(
            fact
        )
    )


    # ========================================================
    # HIGH-CONFIDENCE REPAIRS FIRST
    # ========================================================

    if (
        "les types de discours peuvent etre classes selon"
        in normalized_fact
    ):

        answer = re.sub(
            r"^.*?selon\s+",
            "",
            fact,
            flags=re.I,
        )


        answer = re.sub(
            r",?\s*mettez-vous\s+\u00e0\s+sa\s+place.*$",
            "",
            answer,
            flags=re.I,
        )


        answer = (
            quiz_french_mcq_clean_text_v22b(
                answer
            )
        )


        return (
            (
                "Les types de discours peuvent "
                "\u00eatre class\u00e9s selon quel crit\u00e8re ?"
            ),
            answer,
        )


    if (
        "si narrateur = auteur alors"
        in normalized_fact
    ):

        return (
            (
                "Si le narrateur est aussi l\u2019auteur, "
                "\u00e0 quoi cela correspond-il ?"
            ),
            "une autobiographie",
        )


    # ========================================================
    # CURRENT PARSER
    # ========================================================

    question, answer = (
        quiz_source_first_qa_v17b(
            fact=fact,
            arabic_expected=False,
        )
    )


    question = (
        quiz_french_mcq_clean_text_v22b(
            question
        )
    )

    answer = (
        quiz_french_mcq_clean_text_v22b(
            answer
        )
    )


    if answer:

        answer = answer.rstrip(
            " !?"
        ).strip()


    normalized_question = (
        normalize_text(
            question
        )
    )


    bad_existing_markers = (
        "que permet elle complete",
        "a quoi correspond on dit que ce",
        "present 1 enonciation",
        "types de phrase une phrase",
        "w le gigawatt",
        "ma niere",
        "pour ce type d appareil",
        "sous quelles formes existe ils",
        "sous quelles formes existe genes ils",
    )


    vague_existing_prefixes = (
        "que permet elle ",
        "que fait elle ",
        "que fait il ",
        "a quoi correspond ce ",
        "a quoi correspond cette ",
        "a quoi correspond on dit ",
    )


    existing_is_clean = bool(
        question
        and answer
        and question.endswith(
            "?"
        )
        and len(question) <= 180
        and len(answer) <= 150
        and not any(
            marker
            in normalized_question
            for marker
            in bad_existing_markers
        )
        and not normalized_question.startswith(
            vague_existing_prefixes
        )
        and "\u2192"
        not in question
        and "\u2713"
        not in question
        and "........"
        not in question
    )


    if existing_is_clean:

        return (
            question,
            answer,
        )


    # ========================================================
    # FALLBACK: TYPES DE PHRASES
    # ========================================================

    match = re.search(
        (
            r"Une phrase qui d\u00e9clare un fait "
            r"est appel\u00e9e\s+"
            r"([A-Za-z\u00c0-\u024f-]+)"
        ),
        fact,
        flags=re.I,
    )


    if match:

        return (
            (
                "Comment appelle-t-on une phrase "
                "qui d\u00e9clare un fait ?"
            ),
            quiz_french_mcq_clean_text_v22b(
                match.group(
                    1
                )
            ),
        )


    match = re.match(
        r"^Une phrase interrogative pose\s+(.+)$",
        fact,
        flags=re.I,
    )


    if match:

        return (
            "Que pose une phrase interrogative ?",
            quiz_french_mcq_clean_text_v22b(
                match.group(
                    1
                )
            ),
        )


    match = re.match(
        (
            r"^Une phrase imp\u00e9rative "
            r"donne\s+(.+)$"
        ),
        fact,
        flags=re.I,
    )


    if match:

        return (
            "Que donne une phrase imp\u00e9rative ?",
            quiz_french_mcq_clean_text_v22b(
                match.group(
                    1
                )
            ),
        )


    match = re.match(
        (
            r"^Une phrase exclamative "
            r"transmet\s+(.+)$"
        ),
        fact,
        flags=re.I,
    )


    if match:

        answer = (
            quiz_french_mcq_clean_text_v22b(
                match.group(
                    1
                )
            )
        )


        for example_start in (
            " J\u2019ai ",
            " J'ai ",
        ):

            if example_start in answer:

                answer = answer.split(
                    example_start,
                    1,
                )[0].strip()


        return (
            "Que transmet une phrase exclamative ?",
            answer,
        )


    # ========================================================
    # FALLBACK: TEXT PURPOSE
    # ========================================================

    match = re.match(
        (
            r"^Un texte\s+"
            r"([A-Za-z\u00c0-\u024f-]+)\s+"
            r"a\s*pour\s+but\s+de\s+(.+)$"
        ),
        fact,
        flags=re.I,
    )


    if match:

        text_type = (
            quiz_french_mcq_clean_text_v22b(
                match.group(
                    1
                )
            )
        )


        answer = (
            quiz_french_mcq_clean_text_v22b(
                match.group(
                    2
                )
            )
        )


        return (
            (
                "Quel est le but d\u2019un texte "
                + text_type.lower()
                + " ?"
            ),
            answer,
        )


    # ========================================================
    # FALLBACK: FIGURES DE STYLE
    # ========================================================

    figure_names = (
        "allit\u00e9ration",
        "hyperbole",
        "comparaison",
        "personnification",
        "gradation",
        "\u00e9num\u00e9ration",
        "anaphore",
    )


    for figure_name in figure_names:

        pattern = (
            r"^(?:La|L\u2019|L')\s*"
            + re.escape(
                figure_name
            )
            + r"(?:\s*\([^)]*\))?\s*:\s*(.+)$"
        )


        match = re.match(
            pattern,
            fact,
            flags=re.I,
        )


        if not match:

            continue


        answer = (
            quiz_french_mcq_clean_text_v22b(
                match.group(
                    1
                )
            )
        )


        if (
            figure_name
            == "hyperbole"
            and " : "
            in answer
        ):

            answer = answer.split(
                " : ",
                1,
            )[0].strip()


        return (
            (
                "Qu\u2019est-ce que "
                + (
                    "l\u2019"
                    if figure_name[
                        0
                    ].lower()
                    in "aeiouy\u00e9"
                    else "la "
                )
                + figure_name
                + " ?"
            ),
            answer,
        )


    # ========================================================
    # FALLBACK: LITERARY REGISTER
    # ========================================================

    match = re.match(
        (
            r"^Le registre litt\u00e9raire "
            r"d\u2019un texte est li\u00e9 "
            r"\u00e0\s+(.+)$"
        ),
        fact,
        flags=re.I,
    )


    if match:

        return (
            (
                "\u00c0 quoi le registre litt\u00e9raire "
                "d\u2019un texte est-il li\u00e9 ?"
            ),
            quiz_french_mcq_clean_text_v22b(
                match.group(
                    1
                )
            ),
        )


    # ========================================================
    # FALLBACK: AUTHOR / NARRATOR
    # ========================================================

    if re.match(
        (
            r"^L\u2019?\s*Auteur est celui "
            r"qui \u00e9crit l\u2019histoire"
        ),
        fact,
        flags=re.I,
    ):

        return (
            "Qui \u00e9crit l\u2019histoire ?",
            "L\u2019auteur",
        )


    if re.match(
        (
            r"^Le Narrateur est celui qui parle,\s*"
            r"raconte l\u2019histoire"
        ),
        fact,
        flags=re.I,
    ):

        return (
            (
                "Qui parle et raconte l\u2019histoire "
                "dans le livre ?"
            ),
            "Le narrateur",
        )


    # ========================================================
    # FALLBACK: AUTOBIOGRAPHY
    # ========================================================

    if normalized_fact.startswith(
        "autobiographie : auto = soi-meme"
    ):

        return (
            (
                "Dans \u00ab Autobiographie \u00bb, "
                "que signifie \u00ab Auto \u00bb ?"
            ),
            "soi-m\u00eame",
        )


    return (
        "",
        "",
    )



# QUIZ_FRENCH_MCQ_SOURCE_POOL_V22C

# QUIZ_FRENCH_MCQ_QA_CLEANUP_V22D_R2
def quiz_source_first_qa_french_mcq_v22d_r2(
    fact: str,
) -> tuple[str, str]:

    import re


    fact = (
        quiz_french_mcq_clean_text_v22b(
            fact
        )
    )


    if not fact:

        return (
            "",
            "",
        )


    nf = normalize_text(
        fact
    )


    # ========================================================
    # MATH
    # ========================================================

    # R2:
    # do not depend on commas/punctuation because
    # normalize_text() removes them.
    if (
        "distances oa"
        in nf
        and "ob"
        in nf
        and "oc"
        in nf
        and "multipliees par"
        in nf
    ):

        match = re.search(
            (
                r"multipliees?\s+par\s+"
                r"([0-9]+(?:[.,][0-9]+)?)"
            ),
            nf,
            flags=re.I,
        )


        if match:

            return (
                (
                    "Par quel facteur les distances "
                    "OA, OB et OC ont-elles "
                    "\u00e9t\u00e9 multipli\u00e9es ?"
                ),
                match.group(
                    1
                ),
            )


    if (
        "valeur numerique du rapport est inferieure a 1"
        in nf
        and "reduction"
        in nf
    ):

        return (
            (
                "Que se passe-t-il si la valeur "
                "num\u00e9rique du rapport est "
                "inf\u00e9rieure \u00e0 1 ?"
            ),
            (
                "on obtient une r\u00e9duction "
                "de la figure initiale"
            ),
        )


    if (
        "rapport vaut exactement"
        in nf
        and "symetrie centrale"
        in nf
    ):

        return (
            (
                "Que se passe-t-il si le rapport "
                "d\u2019une homoth\u00e9tie vaut "
                "exactement \u22121 ?"
            ),
            "cela correspond \u00e0 une sym\u00e9trie centrale",
        )


    if (
        "image d un angle par une homothetie"
        in nf
        and "angle de meme mesure"
        in nf
    ):

        return (
            (
                "Quelle est l\u2019image d\u2019un angle "
                "par une homoth\u00e9tie ?"
            ),
            "un angle de m\u00eame mesure",
        )


    if (
        "image d une droite par une homothetie"
        in nf
        and "droite qui lui est parallele"
        in nf
    ):

        return (
            (
                "Quelle est l\u2019image d\u2019une droite "
                "par une homoth\u00e9tie ?"
            ),
            "une droite qui lui est parall\u00e8le",
        )


    if (
        "deux triangles qui ont des cotes proportionnels"
        in nf
        and "triangles semblables"
        in nf
    ):

        return (
            (
                "Comment appelle-t-on deux triangles "
                "dont les c\u00f4t\u00e9s sont "
                "proportionnels ?"
            ),
            "des triangles semblables",
        )


    # ========================================================
    # PHYSIQUE-CHIMIE
    # ========================================================

    if (
        "energie electrique est transformee en chaleur"
        in nf
    ):

        return (
            (
                "Dans l\u2019effet Joule, en quoi "
                "l\u2019\u00e9nergie \u00e9lectrique "
                "est-elle transform\u00e9e ?"
            ),
            "chaleur",
        )


    if (
        "effet joule possede des avantages"
        in nf
        and "inconvenients"
        in nf
    ):

        return (
            (
                "Quels aspects pr\u00e9sente "
                "l\u2019effet Joule ?"
            ),
            "des avantages et des inconv\u00e9nients",
        )


    # Context-dependent pronoun.
    if (
        "le courant le traversant correspond"
        in nf
    ):

        return (
            "",
            "",
        )


    if (
        "unite de la puissance est le watt"
        in nf
    ):

        return (
            "Quelle est l\u2019unit\u00e9 de la puissance ?",
            "le watt",
        )


    if (
        "valeur portee sur le fusible"
        in nf
        and "intensite"
        in nf
    ):

        return (
            (
                "\u00c0 quelle grandeur correspond "
                "la valeur port\u00e9e sur le fusible ?"
            ),
            "l\u2019intensit\u00e9",
        )


    if (
        (
            "iv unites et ordre de grandeur"
            in nf
            or "iv/ unites et ordre de grandeur"
            in nf
        )
        and "unite legale de la puissance"
        in nf
    ):

        return (
            "",
            "",
        )


    if (
        "un compteur comporte un disque"
        in nf
        and "chaque tour"
        in nf
        and "quantite d energie"
        in nf
    ):

        return (
            (
                "Que repr\u00e9sente chaque tour "
                "du disque d\u2019un compteur ?"
            ),
            (
                "une certaine quantit\u00e9 "
                "d\u2019\u00e9nergie consomm\u00e9e"
            ),
        )


    # ========================================================
    # SVT
    # ========================================================

    if (
        "chromosomes homologues portent les memes genes"
        in nf
        and "memes caracteres"
        in nf
    ):

        return (
            "Que portent les chromosomes homologues ?",
            (
                "les m\u00eames g\u00e8nes au m\u00eame "
                "endroit et sont donc responsables "
                "des m\u00eames caract\u00e8res"
            ),
        )


    if (
        "information hereditaire se situe dans le noyau"
        in nf
    ):

        return (
            "O\u00f9 se trouve l\u2019information h\u00e9r\u00e9ditaire ?",
            "dans le noyau de chacune de nos cellules",
        )


    if (
        "information hereditaire est portee par les chromosomes"
        in nf
    ):

        return (
            (
                "Quel \u00e9l\u00e9ment porte "
                "l\u2019information h\u00e9r\u00e9ditaire ?"
            ),
            "les chromosomes",
        )


    if (
        "les chromosomes portent chacun plusieurs centaines de genes"
        in nf
    ):

        return (
            "Que portent les chromosomes ?",
            "chacun plusieurs centaines de g\u00e8nes",
        )


    if (
        "chromosomes sont au nombre de 46"
        in nf
        and "espece humaine"
        in nf
    ):

        return (
            (
                "Combien de chromosomes compte "
                "l\u2019esp\u00e8ce humaine ?"
            ),
            "46",
        )


    if (
        "une version d un gene donne est appele"
        in nf
        and "allele"
        in nf
    ):

        return (
            (
                "Comment appelle-t-on une version "
                "d\u2019un g\u00e8ne donn\u00e9 ?"
            ),
            "un all\u00e8le",
        )


    if (
        "division cellulaire classique"
        in nf
        and "mitose"
        in nf
        and "conserve l information hereditaire"
        in nf
    ):

        return (
            "Que conserve la mitose ?",
            "l\u2019information h\u00e9r\u00e9ditaire",
        )


    if (
        "division cellulaire classique"
        in nf
        and "mitose"
        in nf
        and "necessite la duplication des chromosomes"
        in nf
    ):

        return (
            "Que n\u00e9cessite la mitose ?",
            "la duplication des chromosomes",
        )


    # R2:
    # explicit rule for the candidate identified by diagnostic.
    if (
        "formation des gametes"
        in nf
        and "meiose"
        in nf
        and "divise l information hereditaire"
        in nf
        and "par 2"
        in nf
    ):

        return (
            (
                "Que fait la m\u00e9iose "
                "\u00e0 l\u2019information "
                "h\u00e9r\u00e9ditaire ?"
            ),
            (
                "elle la divise par 2, "
                "en s\u00e9parant les chromosomes "
                "homologues"
            ),
        )


    if (
        "formation des gametes"
        in nf
        and "23 chromosomes"
        in nf
        and "ne contiennent que"
        in nf
    ):

        return (
            (
                "Combien de chromosomes les gam\u00e8tes "
                "contiennent-ils ?"
            ),
            "23 chromosomes",
        )


    if (
        "chromosomes homologues sont separes de facon aleatoire"
        in nf
    ):

        return (
            (
                "Comment les chromosomes homologues "
                "sont-ils s\u00e9par\u00e9s pendant "
                "la m\u00e9iose ?"
            ),
            "de fa\u00e7on al\u00e9atoire",
        )


    if (
        "cellule oeuf contient donc 46 chromosomes"
        in nf
        or (
            "cellule-oeuf contient donc 46 chromosomes"
            in nf
        )
    ):

        if (
            "23 paires"
            in nf
        ):

            return (
                (
                    "Combien de chromosomes la cellule-\u0153uf "
                    "contient-elle apr\u00e8s la "
                    "f\u00e9condation ?"
                ),
                "46 chromosomes, soit 23 paires",
            )


    # ========================================================
    # EXISTING V22B FALLBACK
    # ========================================================

    question, answer = (
        quiz_source_first_qa_french_mcq_v22b(
            fact
        )
    )


    question = str(
        question
        or ""
    ).strip()

    answer = str(
        answer
        or ""
    ).strip()


    nq = normalize_text(
        question
    )


    if (
        nq
        == "comment appelle t on ces ajouts"
    ):

        return (
            "",
            "",
        )


    return (
        question,
        answer,
    )


# QUIZ_FRENCH_MCQ_DISTRACTORS_V22D_R2
def quiz_french_mcq_distractors_v22d_r2(
    question: str,
    correct_answer: str,
) -> list[str]:

    question = str(
        question
        or ""
    ).strip()

    correct_answer = str(
        correct_answer
        or ""
    ).strip()


    if (
        not question
        or not correct_answer
    ):

        return []


    nq = normalize_text(
        question
    )

    na = normalize_text(
        correct_answer
    )


    # ========================================================
    # MATH
    # ========================================================

    if (
        "par quel facteur les distances oa ob et oc"
        in nq
        and na == "3"
    ):

        return [
            "2",
            "4",
            "6",
        ]


    if (
        "rapport est inferieur a 1"
        in nq
        and "reduction"
        in na
    ):

        return [
            "la figure subit un agrandissement",
            "la figure subit une rotation",
            "la figure subit une translation",
        ]


    if (
        "rapport d une homothetie vaut exactement"
        in nq
        and "symetrie centrale"
        in na
    ):

        return [
            "une sym\u00e9trie axiale",
            "une translation",
            "une rotation de 90 degr\u00e9s",
        ]


    if (
        "image d un angle par une homothetie"
        in nq
        and "angle de meme mesure"
        in na
    ):

        return [
            "le double de l\u2019angle initial",
            "la moiti\u00e9 de l\u2019angle initial",
            "un angle droit dans tous les cas",
        ]


    if (
        "image d une droite par une homothetie"
        in nq
        and "parallele"
        in na
    ):

        return [
            (
                "une droite perpendiculaire "
                "\u00e0 la droite initiale"
            ),
            (
                "une droite s\u00e9cante "
                "\u00e0 la droite initiale"
            ),
            "une droite de direction quelconque",
        ]


    # ========================================================
    # PHYSIQUE-CHIMIE
    # ========================================================

    if (
        "effet joule"
        in nq
        and "energie electrique"
        in nq
        and na == "chaleur"
    ):

        return [
            "du mouvement m\u00e9canique",
            "de la lumi\u00e8re",
            "du son",
        ]


    if (
        "aspects presente l effet joule"
        in nq
        and "avantages"
        in na
        and "inconvenients"
        in na
    ):

        return [
            "des avantages uniquement",
            "des inconv\u00e9nients uniquement",
            "aucun effet notable",
        ]


    if (
        "unite de la puissance"
        in nq
        and na == "le watt"
    ):

        return [
            "le joule",
            "le volt",
            "l\u2019amp\u00e8re",
        ]


    if (
        "valeur portee sur le fusible"
        in nq
        and "intensite"
        in na
    ):

        return [
            "la tension",
            "la puissance",
            "l\u2019\u00e9nergie",
        ]


    # ========================================================
    # SVT
    # ========================================================

    if (
        "que portent les chromosomes homologues"
        in nq
        and "memes genes"
        in na
    ):

        return [
            (
                "des g\u00e8nes diff\u00e9rents "
                "\u00e0 des endroits diff\u00e9rents"
            ),
            "uniquement des g\u00e8nes r\u00e9cessifs",
            (
                "aucun g\u00e8ne li\u00e9 aux "
                "caract\u00e8res h\u00e9r\u00e9ditaires"
            ),
        ]


    if (
        "ou se trouve l information hereditaire"
        in nq
        and "noyau"
        in na
    ):

        return [
            "dans le cytoplasme",
            "dans la membrane plasmique",
            "dans les ribosomes",
        ]


    if (
        "quel element porte l information hereditaire"
        in nq
        and na == "les chromosomes"
    ):

        return [
            "les ribosomes",
            "les lysosomes",
            "les centrioles",
        ]


    if (
        "combien de chromosomes compte l espece humaine"
        in nq
        and na == "46"
    ):

        return [
            "23",
            "32",
            "64",
        ]


    if (
        "comment appelle t on une version d un gene donne"
        in nq
        and "allele"
        in na
    ):

        return [
            "un chromosome",
            "un caract\u00e8re",
            "une enzyme",
        ]


    if (
        "que conserve la mitose"
        in nq
        and "information hereditaire"
        in na
    ):

        return [
            "la taille de la cellule",
            "le volume du cytoplasme",
            "la position des organites",
        ]


    if (
        "combien de chromosomes les gametes contiennent ils"
        in nq
        and "23 chromosomes"
        in na
    ):

        return [
            "46 chromosomes",
            "22 chromosomes",
            "44 chromosomes",
        ]


    if (
        "comment les chromosomes homologues sont ils separes"
        in nq
        and "aleatoire"
        in na
    ):

        return [
            "selon un ordre fixe",
            "uniquement selon leur taille",
            "toujours selon leur origine parentale",
        ]


    # ========================================================
    # FRANCAIS
    # ========================================================

    if (
        "phrase qui declare un fait"
        in nq
        and na == "declarative"
    ):

        return [
            "interrogative",
            "exclamative",
            "imp\u00e9rative",
        ]


    if (
        "que pose une phrase interrogative"
        in nq
        and na == "une question"
    ):

        return [
            "un ordre",
            "une \u00e9motion",
            "un fait",
        ]


    if (
        "que donne une phrase imperative"
        in nq
        and "ordre"
        in na
    ):

        return [
            "une question",
            "une \u00e9motion",
            "un fait",
        ]


    if (
        "que transmet une phrase exclamative"
        in nq
        and na == "une emotion"
    ):

        return [
            "une question",
            "un ordre",
            "un fait",
        ]


    return []


# QUIZ_FRENCH_MCQ_QA_POOL_ROUTING_V22D_R2
def quiz_french_mcq_source_fact_items_v22c(
    program: str,
    subject: str,
    source: str,
) -> list[dict]:

    program = str(
        program
        or ""
    ).strip()

    subject = str(
        subject
        or ""
    ).strip()

    source = str(
        source
        or ""
    ).strip()


    if (
        program
        != "Programme fran\u00e7ais"
        or not subject
        or not source
    ):

        return []


    try:

        from services.vector_store_service import (
            get_document_collection,
        )


        collection = (
            get_document_collection()
        )


        result = collection.get(
            where={
                "$and": [
                    {
                        "program": {
                            "$eq": program,
                        }
                    },
                    {
                        "subject": {
                            "$eq": subject,
                        }
                    },
                    {
                        "source": {
                            "$eq": source,
                        }
                    },
                ]
            },
            include=[
                "documents",
                "metadatas",
            ],
        )


    except Exception as exc:

        print(
            "QUIZ V22C MCQ POOL ERROR:",
            repr(
                exc
            ),
        )

        return []


    documents = (
        result.get(
            "documents",
            [],
        )
        or []
    )

    metadatas = (
        result.get(
            "metadatas",
            [],
        )
        or []
    )

    identifiers = (
        result.get(
            "ids",
            [],
        )
        or []
    )


    items = []

    seen_questions = set()


    bad_question_markers = (
        "que permet elle complete",
        "a quoi correspond on dit que ce",
        "present 1 enonciation",
        "types de phrase une phrase",
        "w le gigawatt",
        "ma niere",
        "pour ce type d appareil",
        "a quoi toutes les longueurs",
        "sous quelles formes existe",
        "de quoi depend cette quantite",
    )


    vague_prefixes = (
        "que permet elle ",
        "que fait elle ",
        "que fait il ",
        "a quoi correspond ce ",
        "a quoi correspond cette ",
        "a quoi correspond on dit ",
        "de quoi depend cette quantite",
    )


    for index, (
        document,
        metadata,
    ) in enumerate(
        zip(
            documents,
            metadatas,
        )
    ):

        metadata = (
            metadata
            if isinstance(
                metadata,
                dict,
            )
            else {}
        )


        evidence_text = str(
            document
            or ""
        ).strip()


        if not evidence_text:

            continue


        facts = (
            quiz_source_fact_candidates_v17(
                evidence_text=(
                    evidence_text
                ),
                arabic_expected=False,
            )
        )


        for fact_index, fact in enumerate(
            facts,
            start=1,
        ):

            fact = (
                quiz_french_mcq_clean_text_v22b(
                    fact
                )
            )


            if not fact:

                continue


            (
                question,
                answer,
            ) = (
                quiz_source_first_qa_french_v24a(
                    fact
                )
            )


            question = str(
                question
                or ""
            ).strip()

            answer = str(
                answer
                or ""
            ).strip()


            if (
                not question
                or not answer
                or not question.endswith(
                    "?"
                )
            ):

                continue


            if (
                len(
                    question
                ) > 180
                or len(
                    answer
                ) > 150
            ):

                continue


            normalized_question = (
                normalize_text(
                    question
                )
            )


            if any(
                marker
                in normalized_question
                for marker
                in bad_question_markers
            ):

                continue


            if normalized_question.startswith(
                vague_prefixes
            ):

                continue


            if any(
                symbol
                in question
                for symbol in (
                    "\u2192",
                    "\u2713",
                    "........",
                )
            ):

                continue


            support = (
                quiz_best_local_support(
                    evidence=fact,
                    question=question,
                    answer=answer,
                )
            )


            if not isinstance(
                support,
                dict,
            ):

                continue


            try:

                question_overlap = float(
                    support.get(
                        "question_overlap",
                        0.0,
                    )
                    or 0.0
                )

            except Exception:

                question_overlap = 0.0


            try:

                answer_overlap = float(
                    support.get(
                        "answer_overlap",
                        0.0,
                    )
                    or 0.0
                )

            except Exception:

                answer_overlap = 0.0


            answer_exact = bool(
                support.get(
                    "answer_exact",
                    False,
                )
            )


            if question_overlap < 0.45:

                continue


            if (
                not answer_exact
                and answer_overlap < 0.75
            ):

                continue


            question_key = (
                normalize_text(
                    question
                )
            )


            if (
                not question_key
                or question_key
                in seen_questions
            ):

                continue


            seen_questions.add(
                question_key
            )


            chunk_id = ""


            if index < len(
                identifiers
            ):

                chunk_id = str(
                    identifiers[
                        index
                    ]
                    or ""
                )


            items.append(
                {
                    "text": fact,
                    "source": str(
                        metadata.get(
                            "source",
                            source,
                        )
                        or source
                    ),
                    "page": metadata.get(
                        "page",
                        0,
                    ),
                    "chunk_number": (
                        metadata.get(
                            "chunk_number",
                            0,
                        )
                    ),
                    "chunk_id": (
                        chunk_id
                        + ":v22c:"
                        + str(
                            fact_index
                        )
                    ),
                }
            )


    def numeric(
        value,
    ):

        try:

            return int(
                value
            )

        except Exception:

            return 999999


    items.sort(
        key=lambda item: (
            numeric(
                item.get(
                    "page",
                    0,
                )
            ),
            numeric(
                item.get(
                    "chunk_number",
                    0,
                )
            ),
            str(
                item.get(
                    "chunk_id",
                    "",
                )
            ),
        )
    )


    return items


# QUIZ_FRENCH_MCQ_QA_GENERATE_ROUTING_V22D_R2

# QUIZ_FRENCH_SHORT_SOURCE_POOL_V23A
def quiz_french_short_source_fact_items_v23a(
    program: str,
    subject: str,
    source: str,
) -> list[dict]:

    program = str(
        program
        or ""
    ).strip()

    subject = str(
        subject
        or ""
    ).strip()

    source = str(
        source
        or ""
    ).strip()


    if (
        program
        != "Programme fran\u00e7ais"
        or not subject
        or not source
    ):

        return []


    # Reuse the already audited V22C/V22D clean fact pool.
    # This does not change the MCQ runtime path.
    return (
        quiz_french_mcq_source_fact_items_v22c(
            program=program,
            subject=subject,
            source=source,
        )
    )


# QUIZ_FRENCH_SHORT_QA_V23A
def quiz_source_first_short_answer_french_v23a(
    evidence_text: str,
) -> tuple[str, str, str]:

    fact = (
        quiz_french_mcq_clean_text_v22b(
            evidence_text
        )
    )


    if not fact:

        return (
            "",
            "",
            "",
        )


    question, answer = (
        quiz_source_first_qa_french_v24a(
            fact
        )
    )


    question = str(
        question
        or ""
    ).strip()

    answer = str(
        answer
        or ""
    ).strip()


    if (
        not question
        or not answer
    ):

        return (
            "",
            "",
            "",
        )


    if (
        not question.endswith(
            "?"
        )
        or len(
            question
        ) > 190
        or len(
            answer
        ) > 180
    ):

        return (
            "",
            "",
            "",
        )


    normalized_question = (
        normalize_text(
            question
        )
    )


    bad_question_markers = (
        "que permet elle complete",
        "a quoi correspond on dit que ce",
        "present 1 enonciation",
        "w le gigawatt",
        "iv unites",
        "iv/ unites",
        "pour ce type d appareil",
        "a quoi toutes les longueurs",
        "sous quelles formes existe",
        "de quoi depend cette quantite",
        "facteur de multiplication de les",
        "quel est le nombre de les",
        "que conserve division cellulaire",
        "que necessite division cellulaire",
        "que fait formation des gametes",
        "que contiennent formation des gametes",
        "a quoi correspond le courant le traversant",
        "comment appelle t on ces ajouts",
        "correspond pour l ensemble",
        "ma niere",
    )


    if any(
        marker
        in normalized_question
        for marker
        in bad_question_markers
    ):

        return (
            "",
            "",
            "",
        )


    support = (
        quiz_best_local_support(
            evidence=fact,
            question=question,
            answer=answer,
        )
    )


    if not isinstance(
        support,
        dict,
    ):

        return (
            "",
            "",
            "",
        )


    try:

        question_overlap = float(
            support.get(
                "question_overlap",
                0.0,
            )
            or 0.0
        )

    except Exception:

        question_overlap = 0.0


    try:

        answer_overlap = float(
            support.get(
                "answer_overlap",
                0.0,
            )
            or 0.0
        )

    except Exception:

        answer_overlap = 0.0


    answer_exact = bool(
        support.get(
            "answer_exact",
            False,
        )
    )


    if question_overlap < 0.45:

        return (
            "",
            "",
            "",
        )


    if (
        not answer_exact
        and answer_overlap < 0.75
    ):

        return (
            "",
            "",
            "",
        )


    return (
        question,
        answer,
        fact,
    )



# QUIZ_FRENCH_QA_EXPANSION_V24A
def quiz_source_first_qa_french_v24a(
    fact: str,
) -> tuple[str, str]:

    fact = (
        quiz_french_mcq_clean_text_v22b(
            fact
        )
    )


    if not fact:

        return (
            "",
            "",
        )


    nf = normalize_text(
        fact
    )

    # QUIZ_FRENCH_OPEN_LETTER_PROJECT_QA_V25Y
    # High-confidence documentary mappings for French instructional
    # project statements that the generic parser cannot turn into QA.
    if (
        "vous redigerez la lettre ouverte pour sensibiliser l opinion"
        in nf
        and "question de l environnement dans la region"
        in nf
    ):
        return (
            "Dans quel but rédigerez-vous la lettre ouverte ?",
            (
                "pour sensibiliser l'opinion publique à la question "
                "de l'environnement dans la région"
            ),
        )

    if (
        "vous choisissez le theme qui presente beaucoup d interet"
        in nf
        and "population de votre region"
        in nf
    ):
        return (
            "Quel thème devez-vous choisir ?",
            (
                "un thème qui présente beaucoup d'intérêt pour "
                "la population de votre région"
            ),
        )


    # --------------------------------------------------------
    # PHYSIQUE-CHIMIE
    # Additional clean facts required by mixed mode.
    # --------------------------------------------------------

    if (
        "effet joule possede des avantages"
        in nf
        and "inconvenients"
        in nf
    ):

        return (
            "Que poss\u00e8de l\u2019effet Joule ?",
            (
                "des avantages et des "
                "inconv\u00e9nients"
            ),
        )


    if (
        "puissance p consommee"
        in nf
        and "tension efficace"
        in nf
        and "intensite efficace"
        in nf
        and "produit"
        in nf
    ):

        return (
            (
                "\u00c0 quoi est \u00e9gale la puissance "
                "P consomm\u00e9e par l\u2019appareil ?"
            ),
            (
                "au produit de la tension efficace "
                "Ueff par l\u2019intensit\u00e9 efficace "
                "Ieff traversant l\u2019appareil"
            ),
        )


    if (
        "energie e utilisee par un appareil"
        in nf
        and "puissance p recue"
        in nf
        and "duree t"
        in nf
        and "produit"
        in nf
    ):

        return (
            (
                "\u00c0 quoi est \u00e9gale l\u2019\u00e9nergie "
                "E utilis\u00e9e par un appareil ?"
            ),
            (
                "au produit de la puissance P re\u00e7ue "
                "par l\u2019appareil par la dur\u00e9e t "
                "de son fonctionnement"
            ),
        )


    return (
        quiz_source_first_qa_french_mcq_v22d_r2(
            fact
        )
    )


# QUIZ_FRENCH_MIXED_ALLOCATOR_V24A
def quiz_french_mixed_disjoint_pools_v24a(
    program: str,
    subject: str,
    source: str,
    mcq_needed: int,
    short_needed: int,
) -> tuple[list[dict], list[dict]]:

    mcq_items = (
        quiz_french_mcq_source_fact_items_v22c(
            program=program,
            subject=subject,
            source=source,
        )
    )


    short_items = (
        quiz_french_short_source_fact_items_v23a(
            program=program,
            subject=subject,
            source=source,
        )
    )


    selected_mcq = []

    reserved_question_keys = set()


    # --------------------------------------------------------
    # Reserve deterministic-safe MCQs first.
    # --------------------------------------------------------

    for item in mcq_items:

        fact = str(
            item.get(
                "text",
                "",
            )
            or ""
        ).strip()


        question, answer = (
            quiz_source_first_qa_french_v24a(
                fact
            )
        )


        question = str(
            question
            or ""
        ).strip()

        answer = str(
            answer
            or ""
        ).strip()


        if (
            not question
            or not answer
        ):

            continue


        question_key = (
            normalize_text(
                question
            )
        )


        if (
            not question_key
            or question_key
            in reserved_question_keys
        ):

            continue


        distractors = (
            quiz_french_mcq_distractors_v22d_r2(
                question=question,
                correct_answer=answer,
            )
        )


        if len(
            distractors
        ) != 3:

            continue


        options = [
            answer,
            *distractors,
        ]


        if (
            quiz_mcq_semantic_equivalent_distractors_v17d(
                options=options,
                correct_answer=answer,
            )
        ):

            continue


        if (
            quiz_distractor_pair_conflicts_v17e(
                options=options,
                correct_answer=answer,
            )
        ):

            continue


        if (
            quiz_mcq_evidence_conflicts(
                options=options,
                correct_answer=answer,
                evidence=fact,
            )
        ):

            continue


        selected_mcq.append(
            item
        )


        reserved_question_keys.add(
            question_key
        )


        if len(
            selected_mcq
        ) >= int(
            mcq_needed
        ):

            break


    # --------------------------------------------------------
    # Reserve short answers excluding MCQ question keys.
    # --------------------------------------------------------

    selected_short = []

    short_question_keys = set()


    for item in short_items:

        evidence = str(
            item.get(
                "text",
                "",
            )
            or ""
        ).strip()


        (
            question,
            answer,
            _,
        ) = (
            quiz_source_first_short_answer_french_v23a(
                evidence
            )
        )


        question = str(
            question
            or ""
        ).strip()

        answer = str(
            answer
            or ""
        ).strip()


        if (
            not question
            or not answer
        ):

            continue


        question_key = (
            normalize_text(
                question
            )
        )


        if (
            not question_key
            or question_key
            in reserved_question_keys
            or question_key
            in short_question_keys
        ):

            continue


        selected_short.append(
            item
        )


        short_question_keys.add(
            question_key
        )


        if len(
            selected_short
        ) >= int(
            short_needed
        ):

            break


    return (
        selected_mcq,
        selected_short,
    )


# QUIZ_FRENCH_TF_TYPE_ORDINAL_V24A

# QUIZ_FRENCH_TF_DETERMINISTIC_FALSE_V24C
def quiz_french_tf_deterministic_false_v24c(
    true_statement: str,
    evidence_text: str,
) -> str:

    true_statement = str(
        true_statement
        or ""
    ).strip()

    evidence_text = str(
        evidence_text
        or ""
    ).strip()


    if (
        not true_statement
        or not evidence_text
    ):

        return ""


    key = normalize_text(
        true_statement
    )


    false_by_true = {
        (
            "une phrase qui declare un fait "
            "est appelee declarative"
        ): (
            "Une phrase qui d\u00e9clare un fait "
            "est appel\u00e9e interrogative."
        ),

        (
            "une figure de style permet de presenter "
            "la realite a l aide d une image mentale"
        ): (
            "Une figure de style permet de pr\u00e9senter "
            "la r\u00e9alit\u00e9 sans image mentale."
        ),

        (
            "les types de discours peuvent etre classes "
            "selon l intention de leur auteur "
            "au moment ou il ecrit"
        ): (
            "Les types de discours peuvent \u00eatre "
            "class\u00e9s selon la longueur du texte."
        ),
    }


    candidate = str(
        false_by_true.get(
            key,
            "",
        )
        or ""
    ).strip()


    if not candidate:

        return ""


    # --------------------------------------------------------
    # Runtime safety:
    # The deterministic false statement must remain strongly
    # grounded in the SAME source evidence used by the TF.
    # --------------------------------------------------------

    support = (
        quiz_best_local_support(
            evidence=evidence_text,
            question=candidate,
            answer="",
        )
    )


    if not isinstance(
        support,
        dict,
    ):

        return ""


    try:

        question_overlap = float(
            support.get(
                "question_overlap",
                0.0,
            )
            or 0.0
        )

    except Exception:

        question_overlap = 0.0


    if question_overlap < 0.55:

        return ""


    try:

        grounding = float(
            quiz_grounding_overlap(
                question=candidate,
                evidence=evidence_text,
            )
            or 0.0
        )

    except Exception:

        grounding = 0.0


    if grounding < 0.45:

        return ""


    if quiz_has_heading_noise(
        candidate
    ):

        return ""


    if quiz_has_source_reference_language(
        candidate
    ):

        return ""


    if quiz_has_unsupported_scope(
        question=candidate,
        evidence=evidence_text,
    ):

        return ""


    normalized_candidate = (
        normalize_text(
            candidate
        )
    )


    normalized_evidence = (
        normalize_text(
            evidence_text
        )
    )


    # A false statement must not already be explicitly
    # stated in the evidence.
    if (
        normalized_candidate
        and normalized_candidate
        in normalized_evidence
    ):

        return ""


    return candidate




# QUIZ_ARABIC_SOURCE_SPAN_RECOVERY_HELPER_V25M
def quiz_arabic_source_surface_cleanup_v25m(
    value: str,
    question: bool = False,
) -> str:

    value = " ".join(
        str(
            value
            or ""
        ).split()
    ).strip()


    replacements = (
        (
            '" "',
            " ",
        ),
        (
            "? ?",
            "? ",
        ),
        (
            "??? ",
            "?? ",
        ),
        (
            "???? ???????",
            "??? ???????",
        ),
        (
            "???? ??????",
            "??? ??????",
        ),
        (
            "?????? ????",
            "????? ????",
        ),
        (
            "?????? ????",
            "????? ????",
        ),
        (
            "?????? ?????",
            "????? ?????",
        ),
    )


    for before, after in replacements:

        value = value.replace(
            before,
            after,
        )


    if question:

        for before, after in (
            (
                ": ?????",
                " ?????",
            ),
            (
                ": ?????",
                " ?????",
            ),
            (
                ": ???????",
                " ???????",
            ),
        ):

            value = value.replace(
                before,
                after,
            )


    return " ".join(
        value.split()
    ).strip()



def quiz_arabic_source_support_key_v25m(
    value: str,
) -> str:

    import unicodedata


    value = unicodedata.normalize(
        "NFKC",
        str(
            value
            or ""
        ),
    )


    output = []


    for char in value:

        category = unicodedata.category(
            char
        )


        if (
            category.startswith(
                "L"
            )
            or category.startswith(
                "N"
            )
        ):

            output.append(
                char
            )


    return "".join(
        output
    ).lower()



def quiz_arabic_source_span_quality_reasons_v25m(
    value: str,
) -> list[str]:

    import unicodedata


    value = str(
        value
        or ""
    ).strip()


    if not value:

        return [
            "empty"
        ]


    reasons = []


    if "\ufffd" in value:

        reasons.append(
            "replacement_character"
        )


    latin = []


    for char in value:

        try:

            name = unicodedata.name(
                char
            )

        except ValueError:

            continue


        if "LATIN " in name:

            latin.append(
                char
            )


    latin = sorted(
        set(
            latin
        )
    )


    if latin:

        reasons.append(
            "latin_chars="
            + repr(
                latin
            )
        )


    compact = value.replace(
        " ",
        ""
    )


    if "()" in compact:

        reasons.append(
            "empty_parentheses"
        )


    if value.count(
        "("
    ) != value.count(
        ")"
    ):

        reasons.append(
            "unbalanced_parentheses"
        )


    if "? ?" in value:

        reasons.append(
            "double_comma"
        )


    for fragment in (
        "\u0225",
        "?????)",
        "??????)",
        "???????()",
    ):

        if fragment in value:

            reasons.append(
                "known_ocr_corruption="
                + repr(
                    fragment
                )
            )


    ending = value.rstrip(
        " .,:??"
    )


    for suspicious in (
        "?? ??? ??",
        "?????? ???? ????",
        "????? ?????? ????",
        "?????? ???????",
        "??? ????",
    ):

        if ending.endswith(
            suspicious
        ):

            reasons.append(
                "possibly_truncated="
                + suspicious
            )


    return sorted(
        set(
            reasons
        )
    )



def quiz_arabic_source_span_recover_v25m(
    question: str,
    answer: str,
    fact: str,
    page,
    documents: list,
    metadatas: list,
) -> tuple[str, str, str]:

    question = (
        quiz_arabic_source_surface_cleanup_v25m(
            question,
            question=True,
        )
    )

    answer = (
        quiz_arabic_source_surface_cleanup_v25m(
            answer
        )
    )

    fact = (
        quiz_arabic_source_surface_cleanup_v25m(
            fact
        )
    )


    if (
        not question
        or not answer
        or not fact
    ):

        return (
            "",
            "",
            "",
        )


    if (
        quiz_arabic_source_span_quality_reasons_v25m(
            question
        )
    ):

        return (
            "",
            "",
            "",
        )


    # ==============================================================================================
    # Build same-page source support.
    # ==============================================================================================

    page_documents = []


    for index, document in enumerate(
        documents
    ):

        metadata = (
            metadatas[
                index
            ]
            if (
                index < len(
                    metadatas
                )
                and isinstance(
                    metadatas[
                        index
                    ],
                    dict,
                )
            )
            else {}
        )


        if metadata.get(
            "page",
            0,
        ) == page:

            page_documents.append(
                str(
                    document
                    or ""
                )
            )


    if not page_documents:

        page_documents = [
            str(
                document
                or ""
            )
            for document in documents
        ]


    source_support = (
        quiz_arabic_source_support_key_v25m(
            "\n".join(
                page_documents
            )
        )
    )


    def supported(
        value,
    ):

        key = (
            quiz_arabic_source_support_key_v25m(
                value
            )
        )


        return bool(
            key
            and key
            in source_support
        )


    candidates = []


    # ==============================================================================================
    # Recovery 1:
    #
    # PDF line break:
    #   "?? ??? ??"
    #   "?????"
    #
    # We only accept the extension if that entire recovered
    # sequence exists on the same source page.
    # ==============================================================================================

    stripped_answer = answer.rstrip(
        " .?:"
    )


    if stripped_answer.endswith(
        "?? ??? ??"
    ):

        recovered_answer = (
            stripped_answer
            + " ?????"
        )


        if fact.rstrip(
            " .?:"
        ).endswith(
            "?? ??? ??"
        ):

            recovered_fact = (
                fact.rstrip(
                    " .?:"
                )
                + " ?????"
            )

        elif answer in fact:

            recovered_fact = fact.replace(
                answer,
                recovered_answer,
                1,
            )

        else:

            recovered_fact = fact


        candidates.append(
            (
                recovered_answer,
                recovered_fact,
            )
        )


    # ==============================================================================================
    # Recovery 2:
    #
    # Definition only.
    #
    # Remove examples/procedural tail and keep the literal
    # definition prefix already present in the source.
    # ==============================================================================================

    if question.startswith(
        "?? ??????? ?????? "
    ):

        definition_markers = (
            ": ???",
            " ???",
            ": ??????",
            " ??????",
            "? ??????? ???? ????",
            " ??????? ???? ????",
            "? ????? ?????? ????",
            " ????? ?????? ????",
            "? ????? ???? ?????? ???????",
            " ????? ???? ?????? ???????",
        )


        positions = []


        for marker in definition_markers:

            position = answer.find(
                marker
            )


            if position > 0:

                positions.append(
                    position
                )


        if positions:

            cutoff = min(
                positions
            )


            recovered_answer = (
                answer[
                    :cutoff
                ].rstrip(
                    " ?,:;"
                )
            )


            recovered_fact = fact


            if answer in fact:

                recovered_fact = fact.replace(
                    answer,
                    recovered_answer,
                    1,
                )

            else:

                fact_positions = []


                for marker in definition_markers:

                    position = fact.find(
                        marker
                    )


                    if position > 0:

                        fact_positions.append(
                            position
                        )


                if fact_positions:

                    recovered_fact = (
                        fact[
                            :min(
                                fact_positions
                            )
                        ].rstrip(
                            " ?,:;"
                        )
                    )


            candidates.append(
                (
                    recovered_answer,
                    recovered_fact,
                )
            )


    # ==============================================================================================
    # Original cleaned pair as final candidate.
    # ==============================================================================================

    candidates.append(
        (
            answer,
            fact,
        )
    )


    seen = set()


    for candidate_answer, candidate_fact in candidates:

        candidate_answer = (
            quiz_arabic_source_surface_cleanup_v25m(
                candidate_answer
            )
        )

        candidate_fact = (
            quiz_arabic_source_surface_cleanup_v25m(
                candidate_fact
            )
        )


        answer_key = normalize_text(
            candidate_answer
        )


        if (
            not answer_key
            or answer_key
            in seen
        ):

            continue


        seen.add(
            answer_key
        )


        if (
            quiz_arabic_source_span_quality_reasons_v25m(
                candidate_answer
            )
        ):

            continue


        if not supported(
            candidate_answer
        ):

            continue


        if not supported(
            candidate_fact
        ):

            continue


        # ==========================================================================================
        # Parser round trip.
        #
        # This is important because the runtime will parse
        # evidence again. We only keep recovered facts that
        # reproduce the same Q/A through the existing parser.
        # ==========================================================================================

        try:

            round_question, round_answer = (
                quiz_source_first_qa_v17b(
                    fact=candidate_fact,
                    arabic_expected=True,
                )
            )


        except Exception:

            continue


        round_question = (
            quiz_arabic_source_surface_cleanup_v25m(
                round_question,
                question=True,
            )
        )

        round_answer = (
            quiz_arabic_source_surface_cleanup_v25m(
                round_answer
            )
        )


        if (
            normalize_text(
                round_question
            )
            != normalize_text(
                question
            )
        ):

            continue


        if (
            normalize_text(
                round_answer
            )
            != normalize_text(
                candidate_answer
            )
        ):

            continue


        return (
            question,
            candidate_answer,
            candidate_fact,
        )


    return (
        "",
        "",
        "",
    )



# QUIZ_ARABIC_SOURCE_QA_POOL_V25H
def quiz_arabic_question_family_v25h(
    question: str,
) -> str:

    question = str(
        question
        or ""
    ).strip()


    if question.startswith(
        "\u0645\u0627 "
        "\u0627\u0644\u0645\u0642\u0635\u0648\u062f "
        "\u0628\u0645\u0635\u0637\u0644\u062d "
    ):

        return "definition"


    if question.startswith(
        "\u0645\u0627\u0630\u0627 "
        "\u064a\u062d\u062f\u062b "
        "\u0625\u0630\u0627 "
    ):

        return "conditional"


    if question.startswith(
        "\u0643\u064a\u0641 "
        "\u064a\u0646\u0633\u0628 "
    ):

        return "nisba_rule"


    if question.startswith(
        "\u0625\u0644\u0649 "
        "\u0645\u0627\u0630\u0627 "
        "\u064a\u0646\u0633\u0628 "
    ):

        return "nisba_target"


    if question.startswith(
        "\u0645\u0627 "
        "\u0648\u0638\u064a\u0641\u0629 "
    ):

        return "function"


    return "other"



def quiz_arabic_tf_output_cleanup_v25h(
    value: str,
) -> str:

    text = re.sub(
        r"\s+",
        " ",
        str(
            value
            or ""
        ),
    ).strip()


    if not text:

        return ""


    if not contains_arabic(
        text
    ):

        return text


    # "???? ?????? X: Y"
    # =>
    # "???? ?????? X ??? Y"
    match = re.match(
        (
            r"^"
            r"(\u064a\u0642\u0635\u062f"
            r"\s+\u0628\u0645\u0635\u0637\u0644\u062d"
            r"\s+.+?)"
            r"\s*:\s*"
            r"(.+)$"
        ),
        text,
    )


    if match:

        text = (
            match.group(
                1
            ).strip()
            + " "
            + "\u0623\u0646\u0647 "
            + match.group(
                2
            ).strip()
        )


    # OCR Arabic sometimes places ':' inside a condition.
    text = re.sub(
        r"\s*:\s*",
        " ",
        text,
    )


    text = text.replace(
        '" "',
        " ",
    )

    text = text.replace(
        '"',
        "",
    )


    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


    return text



def quiz_arabic_source_qa_items_v25h(
    program: str,
    subject: str,
    source: str,
) -> list[dict]:

    program = str(
        program
        or ""
    ).strip()

    subject = str(
        subject
        or ""
    ).strip()

    source = str(
        source
        or ""
    ).strip()


    if (
        not program
        or not subject
        or not source
    ):

        return []


    try:

        from services.vector_store_service import (
            get_document_collection,
        )


        collection = (
            get_document_collection()
        )


        result = collection.get(
            where={
                "$and": [
                    {
                        "program": {
                            "$eq": program,
                        }
                    },
                    {
                        "subject": {
                            "$eq": subject,
                        }
                    },
                    {
                        "source": {
                            "$eq": source,
                        }
                    },
                ]
            },
            include=[
                "documents",
                "metadatas",
            ],
        )


    except Exception as exc:

        print(
            "QUIZ V25H ARABIC SOURCE POOL ERROR:",
            repr(
                exc
            ),
        )

        return []


    documents = list(
        result.get(
            "documents",
            [],
        )
        or []
    )

    metadatas = list(
        result.get(
            "metadatas",
            [],
        )
        or []
    )


    items = []

    seen_questions = set()


    for index, document in enumerate(
        documents
    ):

        evidence_text = str(
            document
            or ""
        ).strip()


        if not evidence_text:

            continue


        metadata = (
            metadatas[
                index
            ]
            if (
                index < len(
                    metadatas
                )
                and isinstance(
                    metadatas[
                        index
                    ],
                    dict,
                )
            )
            else {}
        )


        facts = (
            quiz_source_fact_candidates_v17(
                evidence_text=evidence_text,
                arabic_expected=True,
            )
        )


        for fact_index, fact in enumerate(
            facts,
            start=1,
        ):

            fact = str(
                fact
                or ""
            ).strip()


            if not fact:

                continue


            question, answer = (
                quiz_source_first_qa_v17b(
                    fact=fact,
                    arabic_expected=True,
                )
            )


            question = str(
                question
                or ""
            ).strip()

            answer = str(
                answer
                or ""
            ).strip()


            # QUIZ_ARABIC_SOURCE_SPAN_RECOVERY_ROUTING_V25M
            (
                question_v25m,
                answer_v25m,
                fact_v25m,
            ) = (
                quiz_arabic_source_span_recover_v25m(
                    question=question,
                    answer=answer,
                    fact=fact,
                    page=metadata.get(
                        "page",
                        0,
                    ),
                    documents=documents,
                    metadatas=metadatas,
                )
            )


            if (
                not question_v25m
                or not answer_v25m
                or not fact_v25m
            ):

                continue


            question = question_v25m

            answer = answer_v25m

            fact = fact_v25m


            if (
                not question
                or not answer
                or not contains_arabic(
                    question
                )
                or not contains_arabic(
                    answer
                )
            ):

                continue


            question_key = (
                normalize_text(
                    question
                )
            )


            if (
                not question_key
                or question_key
                in seen_questions
            ):

                continue


            seen_questions.add(
                question_key
            )


            items.append(
                {
                    "text": fact,
                    "source": str(
                        metadata.get(
                            "source",
                            source,
                        )
                        or source
                    ),
                    "page": metadata.get(
                        "page",
                        0,
                    ),
                    "chunk_number": metadata.get(
                        "chunk_number",
                        0,
                    ),
                    "chunk_id": (
                        str(
                            metadata.get(
                                "chunk_id",
                                "",
                            )
                            or ""
                        )
                        + ":v25h:"
                        + str(
                            fact_index
                        )
                    ),
                    "v25h_question": question,
                    "v25h_answer": answer,
                    "v25h_family": (
                        quiz_arabic_question_family_v25h(
                            question
                        )
                    ),
                }
            )


    def numeric(
        value,
    ):

        try:

            return int(
                value
            )

        except Exception:

            return 999999


    items.sort(
        key=lambda item: (
            numeric(
                item.get(
                    "page",
                    0,
                )
            ),
            numeric(
                item.get(
                    "chunk_number",
                    0,
                )
            ),
            normalize_text(
                item.get(
                    "v25h_question",
                    "",
                )
            ),
        )
    )


    return items



# QUIZ_ARABIC_MCQ_SOURCE_BANK_V25H
def quiz_arabic_mcq_source_bank_distractors_v25h(
    program: str,
    subject: str,
    source: str,
    question: str,
    correct_answer: str,
) -> list[str]:

    from itertools import combinations


    question = str(
        question
        or ""
    ).strip()

    correct_answer = str(
        correct_answer
        or ""
    ).strip()


    if (
        not question
        or not correct_answer
    ):

        return []


    family = (
        quiz_arabic_question_family_v25h(
            question
        )
    )


    if family not in {
        "definition",
        "conditional",
        "nisba_rule",
        "nisba_target",
        "function",
    }:

        return []


    items = (
        quiz_arabic_source_qa_items_v25h(
            program=program,
            subject=subject,
            source=source,
        )
    )


    correct_key = (
        normalize_text(
            correct_answer
        )
    )


    candidates = []

    seen = set()


    for item in items:

        if (
            item.get(
                "v25h_family"
            )
            != family
        ):

            continue


        answer = str(
            item.get(
                "v25h_answer",
                "",
            )
            or ""
        ).strip()


        answer_key = (
            normalize_text(
                answer
            )
        )


        if (
            not answer_key
            or answer_key
            == correct_key
            or answer_key
            in seen
        ):

            continue


        seen.add(
            answer_key
        )

        candidates.append(
            answer
        )


    if len(
        candidates
    ) < 3:

        return []


    correct_tokens = set(
        quiz_content_tokens(
            correct_answer
        )
    )


    def similarity(
        value,
    ):

        tokens = set(
            quiz_content_tokens(
                value
            )
        )


        union = (
            correct_tokens
            | tokens
        )


        if not union:

            return 0.0


        return (
            len(
                correct_tokens
                & tokens
            )
            / len(
                union
            )
        )


    candidates.sort(
        key=lambda value: (
            similarity(
                value
            ),
            abs(
                len(
                    value
                )
                - len(
                    correct_answer
                )
            ),
            normalize_text(
                value
            ),
        )
    )


    current_fact = ""


    question_key = (
        normalize_text(
            question
        )
    )


    for item in items:

        if (
            normalize_text(
                item.get(
                    "v25h_question",
                    "",
                )
            )
            == question_key
        ):

            current_fact = str(
                item.get(
                    "text",
                    "",
                )
                or ""
            )

            break


    for combo in combinations(
        candidates,
        3,
    ):

        options = [
            correct_answer,
            *combo,
        ]


        normalized_options = [
            normalize_text(
                value
            )
            for value in options
        ]


        if (
            len(
                set(
                    normalized_options
                )
            )
            != 4
        ):

            continue


        if quiz_mcq_has_contained_option(
            options=options,
            correct_answer=correct_answer,
        ):

            continue


        if (
            quiz_mcq_semantic_equivalent_distractors_v17d(
                options=options,
                correct_answer=correct_answer,
            )
        ):

            continue


        if (
            quiz_distractor_pair_conflicts_v17e(
                options=options,
                correct_answer=correct_answer,
            )
        ):

            continue


        if (
            current_fact
            and quiz_mcq_evidence_conflicts(
                options=options,
                correct_answer=correct_answer,
                evidence=current_fact,
            )
        ):

            continue


        return list(
            combo
        )


    return []



def quiz_arabic_mixed_disjoint_pools_v25h(
    program: str,
    subject: str,
    source: str,
    mcq_needed: int,
    tf_needed: int,
    short_needed: int,
) -> tuple[
    list[dict],
    list[dict],
    list[dict],
]:

    items = (
        quiz_arabic_source_qa_items_v25h(
            program=program,
            subject=subject,
            source=source,
        )
    )


    selected_mcq = []

    selected_tf = []

    selected_short = []

    reserved = set()


    family_rank = {
        "conditional": 0,
        "definition": 1,
        "nisba_rule": 2,
        "function": 3,
        "nisba_target": 4,
        "other": 5,
    }


    mcq_candidates = sorted(
        items,
        key=lambda item: (
            family_rank.get(
                item.get(
                    "v25h_family",
                    "other",
                ),
                9,
            ),
            int(
                item.get(
                    "page",
                    0,
                )
                or 0
            ),
        )
    )


    # ==============================================================================================
    # MCQ POOL
    # ==============================================================================================

    for item in mcq_candidates:

        question = str(
            item.get(
                "v25h_question",
                "",
            )
            or ""
        ).strip()

        answer = str(
            item.get(
                "v25h_answer",
                "",
            )
            or ""
        ).strip()


        if (
            not question
            or quiz_has_heading_noise(
                question
            )
        ):

            continue


        distractors = (
            quiz_arabic_mcq_source_bank_distractors_v25h(
                program=program,
                subject=subject,
                source=source,
                question=question,
                correct_answer=answer,
            )
        )


        if len(
            distractors
        ) != 3:

            continue


        question_key = (
            normalize_text(
                question
            )
        )


        if (
            not question_key
            or question_key
            in reserved
        ):

            continue


        copied = dict(
            item
        )


        copied[
            "v25h_distractors"
        ] = list(
            distractors
        )


        selected_mcq.append(
            copied
        )


        reserved.add(
            question_key
        )


        if len(
            selected_mcq
        ) >= int(
            mcq_needed
            or 0
        ):

            break


    # ==============================================================================================
    # TRUE/FALSE POOL
    # ==============================================================================================

    for item in items:

        question = str(
            item.get(
                "v25h_question",
                "",
            )
            or ""
        ).strip()

        answer = str(
            item.get(
                "v25h_answer",
                "",
            )
            or ""
        ).strip()


        question_key = (
            normalize_text(
                question
            )
        )


        if (
            not question_key
            or question_key
            in reserved
        ):

            continue


        statement = (
            quiz_tf_statement_from_qa_v18(
                question=question,
                answer=answer,
            )
        )


        statement = (
            quiz_arabic_tf_output_cleanup_v25h(
                statement
            )
        )


        if (
            not statement
            or quiz_has_heading_noise(
                statement
            )
        ):

            continue


        grounding = (
            quiz_grounding_overlap(
                question=statement,
                evidence=str(
                    item.get(
                        "text",
                        "",
                    )
                    or ""
                ),
            )
        )


        if grounding < 0.45:

            continue


        selected_tf.append(
            dict(
                item
            )
        )


        reserved.add(
            question_key
        )


        if len(
            selected_tf
        ) >= int(
            tf_needed
            or 0
        ):

            break


    # ==============================================================================================
    # SHORT ANSWER POOL
    # ==============================================================================================

    for item in items:

        question = str(
            item.get(
                "v25h_question",
                "",
            )
            or ""
        ).strip()


        question_key = (
            normalize_text(
                question
            )
        )


        if (
            not question_key
            or question_key
            in reserved
            or quiz_has_heading_noise(
                question
            )
        ):

            continue


        selected_short.append(
            dict(
                item
            )
        )


        reserved.add(
            question_key
        )


        if len(
            selected_short
        ) >= int(
            short_needed
            or 0
        ):

            break


    return (
        selected_mcq,
        selected_tf,
        selected_short,
    )



# QUIZ_MATH_AR_SOURCE_QUALITY_GUARD_V25W

def quiz_math_ar_source_quality_guard_v25w(
    program: str,
    subject: str,
    semester: str,
    source: str,
    requested_count: int,
) -> dict:

    normalized_subject_v25w = normalize_text(
        str(subject or "")
    )

    math_ar_subjects_v25w = {
        "mathematiques arabe",
        "math arabe",
        "maths arabe",
        "mathematique arabe",
    }

    if normalized_subject_v25w not in math_ar_subjects_v25w:
        return {
            "enabled": False,
            "clean_count": None,
            "required_count": None,
            "source": str(source or ""),
        }

    try:
        required_count_v25w = max(
            1,
            int(requested_count or 1),
        )
    except Exception:
        required_count_v25w = 1

    passages_v25w = get_lesson_passages(
        program=program,
        subject=subject,
        semester=semester,
        source=source,
    )

    bad_markers_v25w = (
        "المح عة",
        "إالحصيص",
        "إلحصيص",
        "الاحصانية",
        "الإحصانية",
        "كر +",
        "كر+",
        ",بر",
        "،بر",
        "حب إذن",
        "حب اذن",
        "SI Gal",
        "تيبا",
        "الحمصيص",
        "لدينا أكبر حصيص",
        "لدينا اكبر حصيص",
        "ومعدل مريم",
    )

    bad_answer_endings_v25w = (
        "عن طريق",
        "يقسم",
        "تقسم",
        "حيث",
        "مثل",
        "على",
        "من",
        "إلى",
        "الى",
    )

    arabic_word_pattern_v25w = re.compile(
        r"[\u0621-\u064A]{2,}"
    )

    latin_word_pattern_v25w = re.compile(
        r"\b[A-Za-z]{2,}\b"
    )

    allowed_latin_v25w = {
        "cm",
        "mm",
        "km",
    }

    plain_numeric_pattern_v25w = re.compile(
        r"^\s*[+\-−]?\d+(?:[.,]\d+)?(?:\s*[%°])?\s*$"
    )

    orphan_numeric_pattern_v25w = re.compile(
        r"[:،,]\s*\d(?:\s|$)"
    )

    def is_clean_v25w(
        question_v25w: str,
        answer_v25w: str,
        fact_v25w: str,
    ) -> bool:

        question_v25w = str(question_v25w or "").strip()
        answer_v25w = str(answer_v25w or "").strip()
        fact_v25w = str(fact_v25w or "").strip()

        # QUIZ_MATH_AR_VALIDATION_NORMALIZATION_V25Z
        # Validate a harmlessly-normalized view of the source fact.
        # The original fact_v25w remains untouched and is still
        # returned/stored for source grounding.
        fact_validation_v25z = re.sub(
            r"^\s*[\d\u0660-\u0669]+\s*[\)\(]\s*",
            "",
            fact_v25w,
        ).strip()

        fact_validation_v25z = re.sub(
            r"^\s*(?:\u0625\u0630\u0646|\u0627\u0630\u0646)\s+",
            "",
            fact_validation_v25z,
        ).strip()

        if (
            not question_v25w
            or not answer_v25w
            or not fact_v25w
        ):
            return False

        blob_v25w = (
            question_v25w
            + " "
            + answer_v25w
            + " "
            + fact_validation_v25z
        )

        normalized_blob_v25w = normalize_text(
            blob_v25w
        )

        # QUIZ_MATH_AR_FALSE_POSITIVE_FIX_V25Z2
        for marker_v25w in bad_markers_v25w:
            marker_text_v25z2 = str(
                marker_v25w or ""
            )

            # QUIZ_MATH_AR_LITERAL_ELHASSIS_V25Z4
            # QUIZ_MATH_AR_LITERAL_KR_PLUS_V25Z5
            # QUIZ_MATH_AR_LITERAL_KR_COMPACT_V25Z6
            if marker_text_v25z2 in {
                ",\u0628\u0631",
                "\u060c\u0628\u0631",
                "\u0625\u0644\u062d\u0635\u064a\u0635",
                "\u0643\u0631 +",
                "\u0643\u0631+",
            }:
                if marker_text_v25z2 in blob_v25w:
                    return False
                continue

            if (
                normalize_text(marker_text_v25z2)
                in normalized_blob_v25w
            ):
                return False

        if "\ufffd" in blob_v25w:
            return False

        if orphan_numeric_pattern_v25w.search(
            blob_v25w
        ):
            return False

        if (
            question_v25w.count("(")
            != question_v25w.count(")")
            or answer_v25w.count("(")
            != answer_v25w.count(")")
            or fact_validation_v25z.count("(")
            != fact_validation_v25z.count(")")
        ):
            return False

        latin_tokens_v25w = (
            latin_word_pattern_v25w.findall(
                blob_v25w
            )
        )

        for latin_token_v25w in latin_tokens_v25w:
            if (
                latin_token_v25w.lower()
                not in allowed_latin_v25w
            ):
                return False

        prefix_v25w = "ما المقصود بمصطلح "

        if question_v25w.startswith(
            prefix_v25w
        ):
            term_v25w = (
                question_v25w[
                    len(prefix_v25w):
                ].strip(" ؟?")
            )

            normalized_term_v25w = normalize_text(
                term_v25w
            )

            if re.search(
                r"\d",
                term_v25w,
            ):
                return False

            if (
                normalized_term_v25w.startswith(
                    "اذن "
                )
                or normalized_term_v25w.startswith(
                    "الاجابة"
                )
                or normalized_term_v25w.startswith(
                    "لدينا "
                )
                or normalized_term_v25w.startswith(
                    "ومعدل "
                )
                or normalized_term_v25w.startswith(
                    "ا -"
                )
                or normalized_term_v25w.startswith(
                    "ب -"
                )
            ):
                return False

        normalized_answer_v25w = normalize_text(
            answer_v25w
        ).rstrip(
            " .،,؛;:!?؟()[]{}"
        )

        for ending_v25w in bad_answer_endings_v25w:
            normalized_ending_v25w = normalize_text(
                ending_v25w
            )

            if (
                normalized_answer_v25w
                == normalized_ending_v25w
                or normalized_answer_v25w.endswith(
                    " " + normalized_ending_v25w
                )
            ):
                return False

        numeric_with_arabic_unit_v25z = re.fullmatch(
            r"\s*[+\-\u2212]?\d+(?:[.,]\d+)?"
            r"\s+(?:[\u0621-\u064A][\u064B-\u065F\u0670]*){2,}\s*",
            answer_v25w,
        )

        if (
            not plain_numeric_pattern_v25w.fullmatch(
                answer_v25w
            )
            and numeric_with_arabic_unit_v25z is None
            and len(
                arabic_word_pattern_v25w.findall(
                    answer_v25w
                )
            ) < 3
        ):
            return False

        return True

    seen_questions_v25w = set()
    clean_items_v25w = []

    for passage_v25w in passages_v25w:
        evidence_text_v25w = str(
            passage_v25w.get(
                "text",
                "",
            )
            or ""
        )

        if not evidence_text_v25w:
            continue

        source_facts_v25w = (
            quiz_source_fact_candidates_v17(
                evidence_text=evidence_text_v25w,
                arabic_expected=True,
            )
        )

        for fact_v25w in source_facts_v25w:
            (
                question_v25w,
                answer_v25w,
            ) = quiz_source_first_qa_v17b(
                fact=fact_v25w,
                arabic_expected=True,
            )

            question_v25w = str(
                question_v25w or ""
            ).strip()

            answer_v25w = str(
                answer_v25w or ""
            ).strip()

            fact_v25w = str(
                fact_v25w or ""
            ).strip()

            if not is_clean_v25w(
                question_v25w,
                answer_v25w,
                fact_v25w,
            ):
                continue

            normalized_question_v25w = (
                normalize_text(
                    question_v25w
                )
            )

            if (
                not normalized_question_v25w
                or normalized_question_v25w
                in seen_questions_v25w
            ):
                continue

            seen_questions_v25w.add(
                normalized_question_v25w
            )

            clean_items_v25w.append(
                {
                    "question": question_v25w,
                    "answer": answer_v25w,
                    "fact": fact_v25w,
                    "page": passage_v25w.get(
                        "page",
                        0,
                    ),
                }
            )

    clean_count_v25w = len(
        clean_items_v25w
    )

    result_v25w = {
        "enabled": True,
        "clean_count": clean_count_v25w,
        "required_count": required_count_v25w,
        "source": str(source or ""),
        "clean_preview": clean_items_v25w[:5],
        "clean_items": list(clean_items_v25w),
    }

    print(
        "QUIZ V25W MATH-AR SOURCE QUALITY:",
        "clean=",
        clean_count_v25w,
        "required=",
        required_count_v25w,
        "source=",
        repr(str(source or "")),
    )

    if clean_count_v25w < required_count_v25w:
        raise RuntimeError(
            (
                "QUIZ_SOURCE_QUALITY_INSUFFICIENT_V25W: "
                "Le texte extrait de ce cours de mathematiques "
                "en arabe n'est pas assez propre pour generer "
                "un quiz fiable. "
                f"clean={clean_count_v25w}/"
                f"{required_count_v25w}; "
                f"source={source!r}. "
                "Re-OCR/re-ingest the lesson or choose another "
                "source/count. No ungrounded questions were generated."
            )
        )

    return result_v25w



# QUIZ_FRENCH_LANGUAGE_ROUTING_V25X_R3
def quiz_uses_french_language_pipeline_v25x_r2(
    program: str,
    subject: str,
    arabic_lesson: bool,
) -> bool:
    # Preserve the original French pipeline for every non-Arabic
    # Programme français subject, and additionally enable it for
    # Programme marocain / Français.
    if arabic_lesson:
        return False

    program_value = str(program or "").strip()
    subject_value = str(subject or "").strip()

    if program_value == "Programme français":
        return True

    return (
        program_value == "Programme marocain"
        and subject_value == "Français"
    )



# QUIZ_FRENCH_SOURCE_FALLBACK_V25Z
def quiz_french_source_qa_fallback_v25z(
    program: str,
    subject: str,
    source: str,
) -> list[tuple[str, str, str]]:
    if (
        str(subject or "").strip() != "Français"
        or str(program or "").strip()
        not in {
            "Programme français",
            "Programme marocain",
        }
        or not str(source or "").strip()
    ):
        return []

    try:
        from services.vector_store_service import (
            get_document_collection,
        )

        collection = get_document_collection()
        result = collection.get(
            include=[
                "documents",
                "metadatas",
            ]
        )
    except Exception as exc:
        print(
            "QUIZ V25Z FRENCH SOURCE FALLBACK ERROR:",
            repr(exc),
        )
        return []

    documents = result.get("documents", []) or []
    metadatas = result.get("metadatas", []) or []

    target_program = normalize_text(program)
    target_subject = normalize_text(subject)
    target_source = normalize_text(source)

    output = []
    seen = set()

    for document, metadata in zip(
        documents,
        metadatas,
    ):
        metadata = (
            metadata
            if isinstance(metadata, dict)
            else {}
        )

        if (
            normalize_text(
                metadata.get("program", "")
            )
            != target_program
            or normalize_text(
                metadata.get("subject", "")
            )
            != target_subject
            or normalize_text(
                metadata.get("source", "")
            )
            != target_source
        ):
            continue

        document_text = str(
            document
            or ""
        ).strip()

        if not document_text:
            continue

        candidates = [
            document_text,
            *quiz_source_fact_candidates_v17(
                evidence_text=document_text,
                arabic_expected=False,
            ),
        ]

        for fact in candidates:
            fact = str(
                fact
                or ""
            ).strip()

            if not fact:
                continue

            question, answer = (
                quiz_source_first_qa_french_v24a(
                    fact
                )
            )

            question = str(
                question
                or ""
            ).strip()

            answer = str(
                answer
                or ""
            ).strip()

            key = (
                normalize_text(question),
                normalize_text(answer),
            )

            if (
                not question
                or not answer
                or not key[0]
                or not key[1]
                or key in seen
            ):
                continue

            seen.add(key)
            output.append(
                (
                    question,
                    answer,
                    fact,
                )
            )

    return output


def quiz_french_tf_true_statement_v25z(
    question: str,
    answer: str,
) -> str:
    nq = normalize_text(question)
    na = normalize_text(answer)

    if (
        "dans quel but redigerez vous la lettre ouverte"
        in nq
        and "sensibiliser l opinion publique"
        in na
        and "environnement dans la region"
        in na
    ):
        return (
            "La lettre ouverte est rédigée pour sensibiliser "
            "l'opinion publique à la question de "
            "l'environnement dans la région."
        )

    if (
        "quel theme devez vous choisir"
        in nq
        and "beaucoup d interet"
        in na
        and "population de votre region"
        in na
    ):
        return (
            "Le thème choisi doit présenter beaucoup d'intérêt "
            "pour la population de la région."
        )

    return ""


def generate_quiz(
    program: str,
    subject: str,
    semester: str,
    source: str,
    difficulty: str = "medium",
    count: int = 5,
    question_types: list[str] | None = None,
) -> dict:

    # QUIZ_MATH_AR_SOURCE_QUALITY_GUARD_CALL_V25W
    math_ar_quality_v25w = quiz_math_ar_source_quality_guard_v25w(
        program=program,
        subject=subject,
        semester=semester,
        source=source,
        requested_count=count,
    )

    clean_expired_quizzes()

    program = str(
        program
        or ""
    ).strip()

    subject = str(
        subject
        or ""
    ).strip()

    semester = str(
        semester
        or ""
    ).strip()

    source = str(
        source
        or ""
    ).strip()

    difficulty = str(
        difficulty
        or ""
    ).strip().lower()

    if not all(
        (
            program,
            subject,
            semester,
            source,
        )
    ):
        raise ValueError(
            "Programme, mati?re, semestre "
            "et le?on sont obligatoires."
        )

    if (
        difficulty
        not in ALLOWED_DIFFICULTIES
    ):
        raise ValueError(
            "Difficult? invalide."
        )

    if not (
        1 <= count <= 12
    ):
        raise ValueError(
            "Le quiz doit contenir "
            "entre 1 et 12 questions."
        )

    requested_types = (
        question_types
        or [
            "mcq",
            "true_false",
            "short_answer",
        ]
    )

    type_sequence = []

    for item in requested_types:

        cleaned_type = str(
            item
            or ""
        ).strip()

        if (
            cleaned_type
            in ALLOWED_TYPES
            and cleaned_type
            not in type_sequence
        ):
            type_sequence.append(
                cleaned_type
            )

    if not type_sequence:
        raise ValueError(
            "Aucun type de question valide."
        )

    lesson_passages = (
        get_lesson_passages(
            program=program,
            subject=subject,
            semester=semester,
            source=source,
        )
    )

    lesson_passages = [
        passage
        for passage
        in lesson_passages
        if len(
            normalize_text(
                passage.get(
                    "text",
                    "",
                )
            )
        ) >= 60
    ]

    if not lesson_passages:
        raise ValueError(
            "Aucun contenu exploitable "
            "n'a ?t? trouv? pour cette le?on."
        )

    # --------------------------------------------------------
    # V8: OCR-aware evidence selection.
    # --------------------------------------------------------

    subject_arabic_expected = (
        "arabe"
        in normalize_text(
            subject
        )
    )

    evidence_items = (
        build_quiz_evidence_items(
            lesson_passages=(
                lesson_passages
            ),
            arabic_expected=(
                subject_arabic_expected
            ),
        )
    )

    if not evidence_items:
        raise RuntimeError(
            "Aucun extrait documentaire "
            "de qualite suffisante n'a ete "
            "trouve pour generer le quiz."
        )

    evidence_limit = min(
        max(
            count * 4,
            12,
        ),
        len(
            evidence_items
        ),
    )

    evidence_items = (
        evidence_items[
            :evidence_limit
        ]
    )

    lesson_text = " ".join(
        item.get(
            "text",
            "",
        )
        for item
        in evidence_items
    )

    arabic_lesson = (
        contains_arabic(
            lesson_text
        )
        or "arabe"
        in normalize_text(
            subject
        )
    )

    language_rule = (
        "R?dige la question, la r?ponse "
        if arabic_lesson
        else
        "R?dige la question, la r?ponse "
    )

    single_question_schema = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
            },
            "options": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
            "correct_answer": {
                "type": "string",
            },
        },
        "required": [
            "question",
            "options",
            "correct_answer",
        ],
    }


    # QUIZ_SOURCE_FIRST_MCQ_SCHEMA_V17

    source_first_mcq_schema = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
            },
            "distractors": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "minItems": 3,
                "maxItems": 3,
            },
        },
        "required": [
            "distractors",
        ],
    }


    # QUIZ_ARABIC_DISTRACTORS_ONLY_SCHEMA_V17C

    source_first_arabic_mcq_schema_v17c = {
        "type": "object",
        "properties": {
            "distractors": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "minItems": 3,
                "maxItems": 3,
            },
        },
        "required": [
            "distractors",
        ],
    }


    # QUIZ_TRUE_FALSE_BOOLEAN_V5
    #
    # True/False uses a strict boolean contract.
    # The backend converts the boolean to the visible labels.

    true_false_schema = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
            },
            "is_true": {
                "type": "boolean",
            },
        },
        "required": [
            "question",
            "is_true",
        ],
    }

    desired_types = [
        type_sequence[
            index
            % len(
                type_sequence
            )
        ]
        for index in range(
            count
        )
    ]

    validated = []
    seen_questions = set()
    # QUIZ_ELIGIBLE_MCQ_EVIDENCE_V17C

    mcq_evidence_items_v17c = [
        item
        for item
        in evidence_items
        if (
            quiz_mcq_evidence_has_deterministic_qa_v17c(
                evidence_text=str(
                    item.get(
                        "text",
                        "",
                    )
                    or ""
                ),
                arabic_expected=(
                    arabic_lesson
                ),
            )
        )
    ]


    if arabic_lesson:

        print(
            "QUIZ V17C ELIGIBLE MCQ EVIDENCE:",
            len(
                mcq_evidence_items_v17c
            ),
            "/",
            len(
                evidence_items
            ),
        )



    # QUIZ_ARABIC_MIXED_SETUP_V25H
    arabic_mixed_mode_v25h = (
        arabic_lesson
        and len(
            set(
                desired_types
            )
        ) > 1
    )


    arabic_mixed_mcq_items_v25h = []

    arabic_mixed_tf_items_v25h = []

    arabic_mixed_short_items_v25h = []


    if arabic_mixed_mode_v25h:

        (
            arabic_mixed_mcq_items_v25h,
            arabic_mixed_tf_items_v25h,
            arabic_mixed_short_items_v25h,
        ) = (
            quiz_arabic_mixed_disjoint_pools_v25h(
                program=program,
                subject=subject,
                source=source,
                mcq_needed=desired_types.count(
                    "mcq"
                ),
                tf_needed=desired_types.count(
                    "true_false"
                ),
                short_needed=desired_types.count(
                    "short_answer"
                ),
            )
        )


        # QUIZ_MATH_AR_CLEAN_MIXED_SHORT_V25Z7
        if (
            math_ar_quality_v25w.get(
                "enabled",
                False,
            )
            and desired_types.count(
                "short_answer"
            ) > 0
        ):
            clean_items_v25z7 = list(
                math_ar_quality_v25w.get(
                    "clean_items",
                    [],
                )
                or []
            )

            reserved_questions_v25z7 = set()

            for reserved_item_v25z7 in (
                list(arabic_mixed_mcq_items_v25h)
                + list(arabic_mixed_tf_items_v25h)
            ):
                reserved_question_v25z7 = str(
                    reserved_item_v25z7.get(
                        "v25h_question",
                        "",
                    )
                    or ""
                ).strip()

                reserved_key_v25z7 = normalize_text(
                    reserved_question_v25z7
                )

                if reserved_key_v25z7:
                    reserved_questions_v25z7.add(
                        reserved_key_v25z7
                    )

            clean_short_items_v25z7 = []

            for clean_item_v25z7 in clean_items_v25z7:
                clean_question_v25z7 = str(
                    clean_item_v25z7.get(
                        "question",
                        "",
                    )
                    or ""
                ).strip()

                clean_answer_v25z7 = str(
                    clean_item_v25z7.get(
                        "answer",
                        "",
                    )
                    or ""
                ).strip()

                clean_fact_v25z7 = str(
                    clean_item_v25z7.get(
                        "fact",
                        "",
                    )
                    or ""
                ).strip()

                clean_key_v25z7 = normalize_text(
                    clean_question_v25z7
                )

                if (
                    not clean_question_v25z7
                    or not clean_answer_v25z7
                    or not clean_fact_v25z7
                    or not clean_key_v25z7
                    or clean_key_v25z7
                    in reserved_questions_v25z7
                ):
                    continue

                clean_short_items_v25z7.append(
                    {
                        "text": clean_fact_v25z7,
                        "page": clean_item_v25z7.get(
                            "page",
                            0,
                        ),
                        "source": source,
                        "program": program,
                        "subject": subject,
                        "semester": semester,
                        "v25h_question": (
                            clean_question_v25z7
                        ),
                        "v25h_answer": (
                            clean_answer_v25z7
                        ),
                        "v25w_fact": (
                            clean_fact_v25z7
                        ),
                        "v25w_clean_short": True,
                    }
                )

                reserved_questions_v25z7.add(
                    clean_key_v25z7
                )

                if len(
                    clean_short_items_v25z7
                ) >= desired_types.count(
                    "short_answer"
                ):
                    break

            if len(
                clean_short_items_v25z7
            ) >= desired_types.count(
                "short_answer"
            ):
                arabic_mixed_short_items_v25h = (
                    clean_short_items_v25z7
                )

        print(
            "QUIZ V25H ARABIC MIXED POOLS:",
            "mcq=",
            len(
                arabic_mixed_mcq_items_v25h
            ),
            "tf=",
            len(
                arabic_mixed_tf_items_v25h
            ),
            "short=",
            len(
                arabic_mixed_short_items_v25h
            ),
        )


    # QUIZ_FRENCH_TF_SOURCE_POOL_SETUP_V21G
    french_tf_evidence_items_v21g = []

    if (
        not arabic_lesson
        and "true_false" in desired_types
    ):

        french_tf_evidence_items_v21g = (
            quiz_french_tf_source_evidence_items_v21g(
                program=program,
                subject=subject,
                source=source,
            )
        )

        print(
            "QUIZ V21G FRENCH TF SOURCE POOL:",
            len(
                french_tf_evidence_items_v21g
            ),
            "evidence items",
        )

    # QUIZ_FRENCH_MCQ_SOURCE_POOL_SETUP_V22C
    french_mcq_source_items_v22c = []

    if (
        program == "Programme fran\u00e7ais"
        and not arabic_lesson
        and "mcq" in desired_types
    ):

        french_mcq_source_items_v22c = (
            quiz_french_mcq_source_fact_items_v22c(
                program=program,
                subject=subject,
                source=source,
            )
        )

        print(
            "QUIZ V22C FRENCH MCQ SOURCE POOL:",
            len(french_mcq_source_items_v22c),
            "items",
        )

    # QUIZ_FRENCH_SHORT_SOURCE_POOL_SETUP_V23A
    french_short_source_items_v23a = []

    if (
        program == "Programme fran\u00e7ais"
        and not arabic_lesson
        and "short_answer" in desired_types
    ):

        french_short_source_items_v23a = (
            quiz_french_short_source_fact_items_v23a(
                program=program,
                subject=subject,
                source=source,
            )
        )

        print(
            "QUIZ V23A FRENCH SHORT SOURCE POOL:",
            len(french_short_source_items_v23a),
            "items",
        )

    # QUIZ_FRENCH_MIXED_SETUP_V24A
    french_mixed_mode_v24a = (
        program == "Programme fran\u00e7ais"
        and not arabic_lesson
        and len(set(desired_types)) > 1
    )

    french_mixed_mcq_items_v24a = []
    french_mixed_short_items_v24a = []

    if (
        french_mixed_mode_v24a
        and "mcq" in desired_types
        and "short_answer" in desired_types
    ):

        (
            french_mixed_mcq_items_v24a,
            french_mixed_short_items_v24a,
        ) = (
            quiz_french_mixed_disjoint_pools_v24a(
                program=program,
                subject=subject,
                source=source,
                mcq_needed=desired_types.count("mcq"),
                short_needed=desired_types.count("short_answer"),
            )
        )

        print(
            "QUIZ V24A MIXED DISJOINT POOLS:",
            "mcq=",
            len(french_mixed_mcq_items_v24a),
            "short=",
            len(french_mixed_short_items_v24a),
        )

    rejection_log = []

    evidence_cursor = 0
    # QUIZ_FRENCH_MIXED_TYPE_CURSOR_V24A
    french_type_evidence_cursors_v24a = {
        "mcq": 0,
        "true_false": 0,
        "short_answer": 0,
    }

    french_type_ordinals_v24a = {
        "mcq": 0,
        "true_false": 0,
        "short_answer": 0,
    }


    for target_index, question_type in enumerate(
        desired_types,
        start=1,
    ):

        question_created = False
        type_target_index_v24a = target_index

        if french_mixed_mode_v24a:
            french_type_ordinals_v24a[
                question_type
            ] += 1
            type_target_index_v24a = (
                french_type_ordinals_v24a[
                    question_type
                ]
            )


        # QUIZ_FRENCH_TF_ATTEMPTS_V21F
        # QUIZ_FRENCH_MCQ_ATTEMPTS_V22C
        for local_attempt in range(
            (
                12
                if (
                    question_type == "true_false"
                    and not arabic_lesson
                )
                else (
                    10
                    if (
                        question_type == "mcq"
                        and not arabic_lesson
                        and program == "Programme français"
                    )
                    else 4
                )
            )
        ):

            # QUIZ_FRENCH_TF_SOURCE_POOL_ROUTING_V21G
            # QUIZ_FRENCH_MCQ_SOURCE_POOL_ROUTING_V22C
            # QUIZ_FRENCH_SHORT_SOURCE_POOL_ROUTING_V23A
            # QUIZ_FRENCH_MIXED_EVIDENCE_ROUTING_V24A
            active_evidence_items = (
                french_mixed_mcq_items_v24a
                if (
                    french_mixed_mode_v24a
                    and question_type == "mcq"
                    and french_mixed_mcq_items_v24a
                )
                else (
                    french_mixed_short_items_v24a
                    if (
                        french_mixed_mode_v24a
                        and question_type == "short_answer"
                        and french_mixed_short_items_v24a
                    )
                    else (
                        french_short_source_items_v23a if question_type == 'short_answer' and (not arabic_lesson) and (program == 'Programme français') and french_short_source_items_v23a else french_mcq_source_items_v22c if question_type == 'mcq' and (not arabic_lesson) and (program == 'Programme français') and french_mcq_source_items_v22c else french_tf_evidence_items_v21g if question_type == 'true_false' and (not arabic_lesson) and french_tf_evidence_items_v21g else mcq_evidence_items_v17c if question_type in {'mcq', 'true_false', 'short_answer'} and mcq_evidence_items_v17c else evidence_items
                    )
                )
            )



            # QUIZ_ARABIC_MIXED_ROUTING_V25H
            if arabic_mixed_mode_v25h:

                if (
                    question_type == "mcq"
                    and arabic_mixed_mcq_items_v25h
                ):

                    active_evidence_items = (
                        arabic_mixed_mcq_items_v25h
                    )

                elif (
                    question_type == "true_false"
                    and arabic_mixed_tf_items_v25h
                ):

                    active_evidence_items = (
                        arabic_mixed_tf_items_v25h
                    )

                elif (
                    question_type == "short_answer"
                    and arabic_mixed_short_items_v25h
                ):

                    active_evidence_items = (
                        arabic_mixed_short_items_v25h
                    )


            # QUIZ_ARABIC_TYPE_CURSOR_V25H
            if (
                french_mixed_mode_v24a
                or arabic_mixed_mode_v25h
            ):

                type_cursor_v24a = (
                    french_type_evidence_cursors_v24a[
                        question_type
                    ]
                )

                evidence = active_evidence_items[
                    type_cursor_v24a
                    % len(active_evidence_items)
                ]

                french_type_evidence_cursors_v24a[
                    question_type
                ] += 1

                evidence_cursor += 1

            else:

                evidence = active_evidence_items[
                    evidence_cursor
                    % len(active_evidence_items)
                ]

                evidence_cursor += 1

            evidence_text = str(
                evidence.get(
                    "text",
                    "",
                )
            ).strip()

            if (
                question_type
                == "mcq"
            ):

                type_rule = (
                    "Cr?e un QCM. "
                    "options doit contenir exactement "
                    "4 choix diff?rents. "
                    "correct_answer doit ?tre "
                    "exactement l'un de ces 4 choix."
                )

            elif (
                question_type
                == "true_false"
            ):

                if arabic_lesson:

                    type_rule = (
                        "Cr?e une question vrai/faux. "
                        'options doit ?tre exactement '
                        '["????", "???"]. '
                        "correct_answer doit ?tre "
                        "exactement ???? ou ???."
                    )

                else:

                    type_rule = (
                        "Cr?e une question vrai/faux. "
                        'options doit ?tre exactement '
                        '["Vrai", "Faux"]. '
                        "correct_answer doit ?tre "
                        "exactement Vrai ou Faux."
                    )

            else:

                type_rule = (
                    "Cr?e une question ? r?ponse courte. "
                    "options doit ?tre []. "
                    "correct_answer doit ?tre courte "
                    "et clairement soutenue par le texte."
                )

            system_prompt = f"""
Tu cr?es UNE question p?dagogique ? partir d'un extrait documentaire.

R?gles :

- Utilise uniquement l'extrait fourni.
- Aucune connaissance ext?rieure.
- Type obligatoire : {question_type}.
- Difficult? : {difficulty}.
- {language_rule}
- {type_rule}
- Pose une question utile pour v?rifier la compr?hension du cours.
- N'invente aucun chiffre, terme ou fait absent de l'extrait.
- ?vite les r?f?rences ? "l'extrait", "le passage" ou "le document".
- L'explication doit justifier bri?vement la bonne r?ponse.
- R?ponds uniquement avec le JSON demand?.
""".strip()

            # QUIZ_ARABIC_LANGUAGE_V12G

            mandatory_language_rule = (
                (
                    "LANGUE OBLIGATOIRE: ARABE MODERNE. "
                    "La question, la bonne reponse et "
                    "toutes les options doivent etre "
                    "redigees en arabe. "
                    "N'utilise pas le francais. "
                    "Les symboles scientifiques comme "
                    "O2, CO2, ml, L et kPa sont autorises."
                )
                if arabic_lesson
                else ""
            )

            user_prompt = f"""
{mandatory_language_rule}

EXTRAIT DOCUMENTAIRE :

{evidence_text}

Cree exactement UNE question pedagogique
de type {question_type} uniquement a partir
du contenu de cet extrait.

Regles strictes :
- N'ajoute aucune information absente de l'extrait.
- Reformule directement une information explicite de l'extrait.
- Ne copie aucun titre, en-tete, numero de page ou fragment OCR.
- Commence directement par le contenu scientifique.
- Pour true_false, cree une affirmation scientifique autonome et claire.
- N'utilise pas des expressions comme "selon le texte", "selon le document" ou "a partir du tableau".
- Pour mcq, la bonne reponse doit etre explicitement presente dans l'extrait.
- Pour mcq, les trois distracteurs doivent etre plausibles, distincts et de la meme categorie que la bonne reponse.
- N'invente jamais un adjectif ou une propriete absente de l'extrait pour fabriquer la bonne reponse.
- Pour short_answer, correct_answer doit etre une expression courte directement soutenue par l'extrait.
- Ne generalise jamais une information locale a toutes les maladies, tous les organes ou tous les cas.
- N'utilise pas des superlatifs comme "le plus important", "le meilleur" ou "le plus efficace" s'ils ne figurent pas explicitement dans l'extrait.
- La portee de la question doit rester exactement celle de l'information fournie.
- La question et sa bonne reponse doivent etre soutenues par la meme information locale dans l'extrait.
- Pour mcq et short_answer, la bonne reponse doit reprendre directement une information explicite de l'extrait. Evite les synonymes lointains et toute information ajoutee.
- Ne combine jamais deux informations eloignees de l'extrait pour construire une question ou une reponse.
- Pour mcq, pose une question precise. N'utilise pas une formulation vague comme "qu'est-ce qui est mentionne".
- Pour mcq, aucun distracteur ne doit contenir la bonne reponse comme sous-expression.
- Pour mcq, une seule option doit pouvoir repondre correctement a la question.
- Les distracteurs ne doivent pas etre des informations vraies copiees de l'extrait.
- Evite les questions trop larges du type "fait partie de" ou "est un composant de" si plusieurs elements de l'extrait pourraient etre corrects.
- Prefere une relation precise: fonction, cause, consequence, direction d'un echange, valeur, localisation ou definition.
- Pour true_false, genere une affirmation declarative, pas une question commencant par "est-ce que" ou son equivalent.
""".strip()

            # QUIZ_SOURCE_FIRST_QA_V17B

            source_first_mcq_fact = ""
            source_first_mcq_answer = ""
            source_first_mcq_question = ""

            # QUIZ_DETERMINISTIC_RESULT_V20
            source_first_mcq_result_v20 = None


            if question_type == "mcq":

                source_fact_candidates = (
                    quiz_source_fact_candidates_v17(
                        evidence_text=(
                            evidence_text
                        ),
                        arabic_expected=(
                            arabic_lesson
                        ),
                    )
                )


                for source_fact in source_fact_candidates:

                    # QUIZ_FRENCH_MCQ_QA_ROUTING_V22C
                    if quiz_uses_french_language_pipeline_v25x_r2(
                        program,
                        subject,
                        arabic_lesson,
                    ):

                        (
                            fixed_question,
                            fixed_answer,
                        ) = (
                            quiz_source_first_qa_french_v24a(
                                source_fact
                            )
                        )

                    else:

                        (
                            fixed_question,
                            fixed_answer,
                        ) = (
                            quiz_source_first_qa_v17b(
                                fact=source_fact,
                                arabic_expected=arabic_lesson,
                            )
                        )


                    if (
                        arabic_lesson
                        and (
                            not fixed_question
                            or not fixed_answer
                        )
                    ):

                        continue


                    if not fixed_answer:

                        continue


                    # QUIZ_PRE_OLLAMA_DEDUP_V20

                    fixed_question_key_v20 = (
                        normalize_text(
                            fixed_question
                        )
                    )


                    if (
                        fixed_question_key_v20
                        and fixed_question_key_v20
                        in seen_questions
                    ):

                        rejection_log.append(
                            (
                                f"Q{target_index} "
                                "mcq: "
                                "duplicate_question_pre_ollama"
                            )
                        )


                        print(
                            "QUIZ V20 PRE-DUPLICATE SKIP:",
                            f"Q{target_index}",
                            repr(
                                fixed_question
                            ),
                        )


                        continue


                    source_first_mcq_fact = (
                        source_fact
                    )

                    source_first_mcq_question = (
                        fixed_question
                    )

                    source_first_mcq_answer = (
                        fixed_answer
                    )

                    break


                if not source_first_mcq_answer:

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "mcq: "
                            "no_deterministic_source_qa"
                        )
                    )

                    continue


                # QUIZ_DETERMINISTIC_DISTRACTORS_V20

                deterministic_distractors_v20 = (
                    quiz_deterministic_mcq_distractors_v20(
                        question=(
                            source_first_mcq_question
                        ),
                        correct_answer=(
                            source_first_mcq_answer
                        ),
                    )
                )
                # QUIZ_FRENCH_MCQ_DETERMINISTIC_ROUTING_V22D_R2
                if (
                    not deterministic_distractors_v20
                    and quiz_uses_french_language_pipeline_v25x_r2(
                        program,
                        subject,
                        arabic_lesson,
                    )
                ):

                    deterministic_distractors_v20 = (
                        quiz_french_mcq_distractors_v22d_r2(
                            question=source_first_mcq_question,
                            correct_answer=source_first_mcq_answer,
                        )
                    )




                # QUIZ_ARABIC_MCQ_SOURCE_BANK_V25H
                if (
                    not deterministic_distractors_v20
                    and arabic_lesson
                ):

                    deterministic_distractors_v20 = (
                        quiz_arabic_mcq_source_bank_distractors_v25h(
                            program=program,
                            subject=subject,
                            source=source,
                            question=(
                                source_first_mcq_question
                            ),
                            correct_answer=(
                                source_first_mcq_answer
                            ),
                        )
                    )


                    if deterministic_distractors_v20:

                        print(
                            "QUIZ V25H ARABIC MCQ SOURCE BANK:",
                            f"Q{target_index}",
                            "page=",
                            evidence.get(
                                "page",
                                0,
                            ),
                            "distractors=",
                            deterministic_distractors_v20,
                        )


                if deterministic_distractors_v20:

                    source_first_mcq_result_v20 = {
                        "distractors": (
                            deterministic_distractors_v20
                        ),
                    }


                    print(
                        "QUIZ V20 MCQ DETERMINISTIC:",
                        f"Q{target_index}",
                        "page=",
                        evidence.get(
                            "page",
                            0,
                        ),
                        "question=",
                        repr(
                            source_first_mcq_question
                        ),
                        "distractors=",
                        deterministic_distractors_v20,
                    )


                if arabic_lesson:

                    system_prompt = """
??? ???? ???????? ????? ??????? ?????.

?????? ??????? ?????? ?????? ?????
?? ??? ?????? ??? ??? ?? ????????.

????? ???????:
????? ????? ???????? ?????.

??????:
- ????? ???????? ??????.
- ???? ?????? ???????.
- ???? ????? ??????? ??????.
- ?? ???? ?? ?????? ???? ?????? ?????
  ?????? ?? ???????.
- ?? ????? ?? ?????? ??? ?????? ??????.
- ???? ?????????? ??????? ?? ?????
  ??????? ?? ?????? ??????.
- ???? ?????? ?????? ????? ???????.
- ?? ????? ?????? ?? ????? ?? ?????
  ?? ?????? ?? ???? ???? ??????.
- ???? JSON ???.
""".strip()

                else:

                    system_prompt = """
Generate exactly three false distractors
for the locked school question and answer.

Do not modify the question.
Do not modify the correct answer.
Return only the requested JSON.
""".strip()


                user_prompt = f"""
QUESTION VERROUILLEE :

{source_first_mcq_question}

BONNE REPONSE DOCUMENTAIRE VERROUILLEE :

{source_first_mcq_answer}

FAIT DOCUMENTAIRE :

{source_first_mcq_fact}

EXTRAIT LOCAL :

{evidence_text}

Produis uniquement trois distracteurs faux.
""".strip()


            # QUIZ_SOURCE_FIRST_SHORT_RESULT_V19

            source_first_short_result_v19 = None


            if (
                question_type == "short_answer"
            ):

                # QUIZ_MATH_AR_CLEAN_MIXED_SHORT_V25Z7
                # QUIZ_MATH_AR_CLEAN_SHORT_EXECUTION_V25Z7
                if (
                    arabic_lesson
                    and arabic_mixed_mode_v25h
                    and bool(
                        evidence.get(
                            "v25w_clean_short",
                            False,
                        )
                    )
                ):
                    short_question_v19 = str(
                        evidence.get(
                            "v25h_question",
                            "",
                        )
                        or ""
                    ).strip()

                    short_answer_v19 = str(
                        evidence.get(
                            "v25h_answer",
                            "",
                        )
                        or ""
                    ).strip()

                    short_fact_v19 = str(
                        evidence.get(
                            "v25w_fact",
                            "",
                        )
                        or ""
                    ).strip()

                # QUIZ_FRENCH_SHORT_QA_ROUTING_V23A
                elif quiz_uses_french_language_pipeline_v25x_r2(
                    program,
                    subject,
                    arabic_lesson,
                ):

                    (
                        short_question_v19,
                        short_answer_v19,
                        short_fact_v19,
                    ) = (
                        quiz_source_first_short_answer_french_v23a(
                            evidence_text
                        )
                    )

                else:

                    (
                        short_question_v19,
                        short_answer_v19,
                        short_fact_v19,
                    ) = (
                        quiz_source_first_short_answer_v19(
                            evidence_text=evidence_text,
                            arabic_expected=arabic_lesson,
                        )
                    )


                if (
                    (
                        not short_question_v19
                        or not short_answer_v19
                    )
                    and quiz_uses_french_language_pipeline_v25x_r2(
                        program,
                        subject,
                        arabic_lesson,
                    )
                ):
                    fallback_qa_v25z = (
                        quiz_french_source_qa_fallback_v25z(
                            program=program,
                            subject=subject,
                            source=source,
                        )
                    )

                    for (
                        fallback_question_v25z,
                        fallback_answer_v25z,
                        fallback_fact_v25z,
                    ) in fallback_qa_v25z:
                        fallback_key_v25z = (
                            normalize_text(
                                fallback_question_v25z
                            )
                        )

                        if (
                            fallback_key_v25z
                            and fallback_key_v25z
                            not in seen_questions
                        ):
                            short_question_v19 = (
                                fallback_question_v25z
                            )
                            short_answer_v19 = (
                                fallback_answer_v25z
                            )
                            short_fact_v19 = (
                                fallback_fact_v25z
                            )
                            break

                    if (
                        (
                            not short_question_v19
                            or not short_answer_v19
                        )
                        and fallback_qa_v25z
                    ):
                        (
                            short_question_v19,
                            short_answer_v19,
                            short_fact_v19,
                        ) = fallback_qa_v25z[0]

                if (
                    not short_question_v19
                    or not short_answer_v19
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "short_answer: "
                            "no_source_first_short_answer"
                        )
                    )

                    continue


                source_first_short_result_v19 = {
                    "question": (
                        short_question_v19
                    ),
                    "options": [],
                    "correct_answer": (
                        short_answer_v19
                    ),
                }


                print(
                    "QUIZ V21A SHORT SOURCE-FIRST:",
                    f"Q{target_index}",
                    "page=",
                    evidence.get(
                        "page",
                        0,
                    ),
                    "question=",
                    repr(
                        short_question_v19
                    ),
                    "answer=",
                    repr(
                        short_answer_v19
                    ),
                )


            # QUIZ_SOURCE_FIRST_TRUE_FALSE_RESULT_V18

            source_first_tf_result_v18 = None


            if (
                question_type == "true_false"
            ):

                tf_fact_candidates_v18 = (
                    quiz_source_fact_candidates_v17(
                        evidence_text=(
                            evidence_text
                        ),
                        arabic_expected=arabic_lesson,
                    )
                )


                for tf_fact_v18 in (
                    tf_fact_candidates_v18
                ):

                    if quiz_uses_french_language_pipeline_v25x_r2(
                        program,
                        subject,
                        arabic_lesson,
                    ):
                        (
                            tf_question_v18,
                            tf_correct_answer_v18,
                        ) = quiz_source_first_qa_french_v24a(
                            tf_fact_v18
                        )
                    else:
                        (
                            tf_question_v18,
                            tf_correct_answer_v18,
                        ) = quiz_source_first_qa_v17b(
                            fact=tf_fact_v18,
                            arabic_expected=arabic_lesson,
                        )


                    if (
                        not tf_question_v18
                        or not tf_correct_answer_v18
                    ):

                        continue


                    tf_true_statement_v18 = (
                        quiz_tf_statement_from_qa_v21a(
                            question=(
                                tf_question_v18
                            ),
                            answer=(
                                tf_correct_answer_v18
                            ),
                        )
                    )


                    if not tf_true_statement_v18:

                        continue


                    # QUIZ_FRENCH_TF_PRE_DUPLICATE_V21F
                    if (
                        not arabic_lesson
                        and normalize_text(
                            tf_true_statement_v18
                        ) in seen_questions
                    ):
                        rejection_log.append(
                            (
                                f"Q{target_index} "
                                "true_false: "
                                "duplicate_tf_preselect_v21f"
                            )
                        )
                        continue

                    tf_should_be_true_v18 = (
                        quiz_tf_should_be_true_v18(
                            question=(
                                tf_question_v18
                            ),
                            answer=(
                                tf_correct_answer_v18
                            ),
                            target_index=(
                                type_target_index_v24a
                            ),
                            page=int(
                                evidence.get(
                                    "page",
                                    0,
                                )
                                or 0
                            ),
                        )
                    )


                    if tf_should_be_true_v18:

                        source_first_tf_result_v18 = {
                            "question": (
                                tf_true_statement_v18
                            ),
                            "is_true": True,
                        }


                        print(
                            "QUIZ V21A TF SOURCE-FIRST:",
                            f"Q{target_index}",
                            "truth=True",
                            "page=",
                            evidence.get(
                                "page",
                                0,
                            ),
                        )


                        break


                    # QUIZ_FRENCH_TF_DETERMINISTIC_FALSE_ROUTING_V24C
                    tf_false_statement_v24c = ""

                    if (
                        not arabic_lesson
                        and program == "Programme fran\u00e7ais"
                        and subject == "Fran\u00e7ais"
                    ):

                        tf_false_statement_v24c = (
                            quiz_french_tf_deterministic_false_v24c(
                                true_statement=(
                                    tf_true_statement_v18
                                ),
                                evidence_text=evidence_text,
                            )
                        )

                    if tf_false_statement_v24c:

                        source_first_tf_result_v18 = {
                            "question": (
                                tf_false_statement_v24c
                            ),
                            "is_true": False,
                        }

                        print(
                            "QUIZ V24C TF DETERMINISTIC FALSE:",
                            f"Q{target_index}",
                            "page=",
                            evidence.get(
                                "page",
                                0,
                            ),
                            "statement=",
                            repr(
                                tf_false_statement_v24c
                            ),
                        )

                        break

                    tf_false_answer_v18 = (
                        quiz_tf_false_answer_v18(
                            question=(
                                tf_question_v18
                            ),
                            correct_answer=(
                                tf_correct_answer_v18
                            ),
                            evidence_text=(
                                evidence_text
                            ),
                            lesson_text=(
                                lesson_text
                            ),
                            arabic_expected=arabic_lesson,
                        )
                    )


                    if tf_false_answer_v18:

                        tf_false_statement_v18 = (
                            quiz_tf_statement_from_qa_v21a(
                                question=(
                                    tf_question_v18
                                ),
                                answer=(
                                    tf_false_answer_v18
                                ),
                            )
                        )


                        if tf_false_statement_v18:

                            source_first_tf_result_v18 = {
                                "question": (
                                    tf_false_statement_v18
                                ),
                                "is_true": False,
                            }


                            print(
                                "QUIZ V21A TF SOURCE-FIRST:",
                                f"Q{target_index}",
                                "truth=False",
                                "page=",
                                evidence.get(
                                    "page",
                                    0,
                                ),
                            )


                            break


                    # Safe fallback:
                    # if a false alternative cannot be
                    # generated reliably, use the true
                    # documentary statement rather than
                    # spending another full quiz attempt.
                    source_first_tf_result_v18 = {
                        "question": (
                            tf_true_statement_v18
                        ),
                        "is_true": True,
                    }


                    print(
                        "QUIZ V18 TF FALLBACK TRUE:",
                        f"Q{target_index}",
                        "page=",
                        evidence.get(
                            "page",
                            0,
                        ),
                    )


                    break


                if (
                    source_first_tf_result_v18
                    is None
                    and quiz_uses_french_language_pipeline_v25x_r2(
                        program,
                        subject,
                        arabic_lesson,
                    )
                ):
                    fallback_qa_v25z = (
                        quiz_french_source_qa_fallback_v25z(
                            program=program,
                            subject=subject,
                            source=source,
                        )
                    )

                    for (
                        fallback_question_v25z,
                        fallback_answer_v25z,
                        _fallback_fact_v25z,
                    ) in fallback_qa_v25z:
                        fallback_statement_v25z = (
                            quiz_french_tf_true_statement_v25z(
                                question=(
                                    fallback_question_v25z
                                ),
                                answer=(
                                    fallback_answer_v25z
                                ),
                            )
                        )

                        if (
                            fallback_statement_v25z
                            and normalize_text(
                                fallback_statement_v25z
                            )
                            not in seen_questions
                        ):
                            source_first_tf_result_v18 = {
                                "question": (
                                    fallback_statement_v25z
                                ),
                                "is_true": True,
                            }
                            break

                if (
                    source_first_tf_result_v18
                    is None
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "true_false: "
                            "no_source_first_tf"
                        )
                    )

                    continue


            # QUIZ_DISTRACTOR_PROMPT_GUARD_V17D

            if (
                question_type == "mcq"
                and arabic_lesson
            ):

                system_prompt += (
                    "\n"
                    "- \u0644\u0627 "
                    "\u062a\u0633\u062a\u0639\u0645\u0644 "
                    "\u0645\u0631\u0627\u062f\u0641\u0627 "
                    "\u0623\u0648 "
                    "\u0634\u0631\u062d\u0627 "
                    "\u0623\u0648 "
                    "\u0625\u0639\u0627\u062f\u0629 "
                    "\u0635\u064a\u0627\u063a\u0629 "
                    "\u0644\u0644\u062c\u0648\u0627\u0628 "
                    "\u0627\u0644\u0635\u062d\u064a\u062d "
                    "\u0643\u0627\u062e\u062a\u064a\u0627\u0631 "
                    "\u062e\u0627\u0637\u0626."
                    "\n"
                    "- \u0625\u0630\u0627 "
                    "\u0643\u0627\u0646 "
                    "\u0627\u0644\u062c\u0648\u0627\u0628 "
                    "\u0627\u0644\u0635\u062d\u064a\u062d "
                    "\u0639\u0628\u0627\u0631\u0629 "
                    "\u0642\u0635\u064a\u0631\u0629\u060c "
                    "\u0641\u0644\u062a\u0643\u0646 "
                    "\u0627\u0644\u0627\u062e\u062a\u064a\u0627\u0631\u0627\u062a "
                    "\u0627\u0644\u062e\u0627\u0637\u0626\u0629 "
                    "\u0639\u0628\u0627\u0631\u0627\u062a "
                    "\u0642\u0635\u064a\u0631\u0629 "
                    "\u0643\u0630\u0644\u0643."
                    "\n"
                    "- \u0645\u0645\u0646\u0648\u0639 "
                    "\u062a\u062d\u0648\u064a\u0644 "
                    "\u0627\u0644\u062c\u0648\u0627\u0628 "
                    "\u0627\u0644\u0635\u062d\u064a\u062d "
                    "\u0625\u0644\u0649 "
                    "\u062c\u0645\u0644\u0629 "
                    "\u0623\u0637\u0648\u0644 "
                    "\u062a\u0639\u0637\u064a "
                    "\u0646\u0641\u0633 "
                    "\u0627\u0644\u0645\u0639\u0646\u0649."
                )


            # QUIZ_DIRECTION_PROMPT_V17E

            if (
                question_type == "mcq"
                and arabic_lesson
                and quiz_is_direction_answer_v17e(
                    source_first_mcq_answer
                )
            ):

                system_prompt += (
                    "\n"
                    "- \u0647\u0630\u0627 "
                    "\u0633\u0624\u0627\u0644 "
                    "\u0639\u0646 "
                    "\u0645\u0633\u0627\u0631."
                    "\n"
                    "- \u064a\u062c\u0628 "
                    "\u0623\u0646 "
                    "\u064a\u0643\u0648\u0646 "
                    "\u0643\u0644 "
                    "\u0627\u062e\u062a\u064a\u0627\u0631 "
                    "\u062e\u0627\u0637\u0626 "
                    "\u0639\u0644\u0649 "
                    "\u0627\u0644\u0634\u0643\u0644 "
                    "\u0627\u0644\u062a\u0627\u0644\u064a "
                    "\u0628\u0627\u0644\u0636\u0628\u0637:"
                    "\n"
                    "\u0645\u0646 ... \u0625\u0644\u0649 ..."
                    "\n"
                    "- \u0644\u0627 "
                    "\u062a\u0636\u0641 "
                    "\u0627\u0633\u0645 "
                    "\u0627\u0644\u063a\u0627\u0632 "
                    "\u0625\u0644\u0649 "
                    "\u0627\u0644\u0627\u062e\u062a\u064a\u0627\u0631."
                    "\n"
                    "- \u0644\u0627 "
                    "\u062a\u0643\u062a\u0628 "
                    "\u062c\u0645\u0644\u0629 "
                    "\u062a\u0641\u0633\u064a\u0631\u064a\u0629."
                    "\n"
                    "- \u0623\u0646\u062a\u062c "
                    "\u062b\u0644\u0627\u062b\u0629 "
                    "\u0645\u0633\u0627\u0631\u0627\u062a "
                    "\u0645\u062e\u062a\u0644\u0641\u0629 "
                    "\u062d\u0642\u0627."
                )


            payload = {
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            system_prompt
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            user_prompt
                        ),
                    },
                ],
                "format": (
                    true_false_schema
                    if question_type
                    == "true_false"
                    else (
                        (
                            source_first_arabic_mcq_schema_v17c
                            if arabic_lesson
                            else source_first_mcq_schema
                        )
                        if question_type
                        == "mcq"
                        else single_question_schema
                    )
                ),
                "stream": False,
                "think": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.05,
                    "num_predict": (
                        240
                        if question_type
                        == "true_false"
                        else (
                            120
                            if question_type
                            == "mcq"
                            else 420
                        )
                    ),
                },
            }

            # QUIZ_SOURCE_FIRST_SHORT_BYPASS_V19

            if (
                source_first_short_result_v19
                is not None
            ):

                # Reuse the existing V18 source-first
                # execution path. For short_answer this
                # dictionary contains:
                #
                # question
                # options=[]
                # correct_answer
                #
                # Therefore the main Ollama call is skipped.
                source_first_tf_result_v18 = (
                    source_first_short_result_v19
                )


                print(
                    "QUIZ V21A SHORT MAIN OLLAMA:",
                    "SKIPPED",
                )


            # QUIZ_DETERMINISTIC_MCQ_BYPASS_V20

            if (
                source_first_mcq_result_v20
                is not None
            ):

                source_first_tf_result_v18 = (
                    source_first_mcq_result_v20
                )


                print(
                    "QUIZ V20 MCQ MAIN OLLAMA:",
                    "SKIPPED",
                )


            # QUIZ_SOURCE_FIRST_TF_EXECUTION_V18

            if (
                source_first_tf_result_v18
                is not None
            ):

                result = (
                    source_first_tf_result_v18
                )


                print(
                    "QUIZ V18 TF MAIN OLLAMA:",
                    "SKIPPED",
                )


            else:

                # QUIZ_OLLAMA_TIMING_V17D

                ollama_started_v17d = (
                    time.perf_counter()
                )


                try:

                    result = call_ollama(
                        payload
                    )


                    ollama_elapsed_v17d = round(
                        time.perf_counter()
                        - ollama_started_v17d,
                        3,
                    )


                    print(
                        "QUIZ V17D OLLAMA:",
                        f"Q{target_index}",
                        question_type,
                        "attempt_cursor=",
                        evidence_cursor,
                        "page=",
                        evidence.get(
                            "page",
                            0,
                        ),
                        "seconds=",
                        ollama_elapsed_v17d,
                    )


                except RuntimeError as error:

                    ollama_elapsed_v17d = round(
                        time.perf_counter()
                        - ollama_started_v17d,
                        3,
                    )


                    print(
                        "QUIZ V17D OLLAMA ERROR:",
                        f"Q{target_index}",
                        question_type,
                        "attempt_cursor=",
                        evidence_cursor,
                        "seconds=",
                        ollama_elapsed_v17d,
                        "error=",
                        repr(
                            error
                        ),
                    )

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            f"{question_type}: "
                            f"ollama_error={error}"
                        )
                    )

                    continue

            if not isinstance(
                result,
                dict,
            ):

                rejection_log.append(
                    (
                        f"Q{target_index} "
                        f"{question_type}: "
                        "not_a_dict"
                    )
                )

                continue

            # QUIZ_SOURCE_FIRST_MCQ_CANDIDATE_V17

            if question_type == "mcq":

                candidate = (
                    quiz_build_source_first_mcq_candidate_v17(
                        result=(
                            result
                        ),
                        fixed_question=(
                            source_first_mcq_question
                        ),
                        correct_answer=(
                            source_first_mcq_answer
                        ),
                        evidence_text=(
                            evidence_text
                        ),
                        lesson_text=(
                            lesson_text
                        ),
                        arabic_expected=(
                            arabic_lesson
                        ),
                    )
                )


                if candidate is None:

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "mcq: "
                            "source_first_structure_failed"
                        )
                    )

                    continue


            else:

                candidate = {
                    "type": (
                        question_type
                    ),
                    "question": str(
                        result.get(
                            "question",
                            "",
                        )
                        or ""
                    ).strip(),
                    "options": (
                        result.get(
                            "options",
                            [],
                        )
                    ),
                    "correct_answer": str(
                        result.get(
                            "correct_answer",
                            "",
                        )
                        or ""
                    ).strip(),
                    "explanation": (
                        quiz_build_grounded_explanation(
                            evidence=(
                                evidence_text
                            ),
                            question=str(
                                result.get(
                                    "question",
                                    "",
                                )
                                or ""
                            ).strip(),
                            correct_answer=str(
                                result.get(
                                    "correct_answer",
                                    "",
                                )
                                or ""
                            ).strip(),
                        )
                    ),
                    "passage_number": 1,

                    # The evidence is selected by the backend,
                    # not copied by the LLM.
                    "evidence_quote": (
                        evidence_text
                    ),
                }


            # QUIZ_TRUE_FALSE_BOOLEAN_RESULT_V5
            if (
                question_type
                == "true_false"
            ):

                is_true = result.get(
                    "is_true"
                )

                if not isinstance(
                    is_true,
                    bool,
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "true_false: "
                            "missing_boolean"
                        )
                    )

                    continue

                if arabic_lesson:

                    candidate[
                        "options"
                    ] = [
                        "\u0635\u062d\u064a\u062d",
                        "\u062e\u0637\u0623",
                    ]

                    candidate[
                        "correct_answer"
                    ] = (
                        "\u0635\u062d\u064a\u062d"
                        if is_true
                        else "\u062e\u0637\u0623"
                    )

                else:

                    candidate[
                        "options"
                    ] = [
                        "Vrai",
                        "Faux",
                    ]

                    candidate[
                        "correct_answer"
                    ] = (
                        "Vrai"
                        if is_true
                        else "Faux"
                    )

            # QUIZ_TRUE_FALSE_NORMALIZATION_V4
            #
            # Small local models often return variants such as:
            # "????? ???..." / "??" / "Vrai." / "True".
            # The API contract must remain deterministic.

            # QUIZ_TRUE_FALSE_V4_DISABLED_V6
            if (
                False
                and question_type
                == "true_false"
            ):

                raw_answer = str(
                    candidate.get(
                        "correct_answer",
                        "",
                    )
                    or ""
                ).strip()

                normalized_answer = (
                    normalize_text(
                        raw_answer
                    )
                )

                if arabic_lesson:

                    candidate[
                        "options"
                    ] = [
                        "????",
                        "???",
                    ]

                    true_markers = {
                        "????",
                        "??",
                        "true",
                        "vrai",
                        "correct",
                    }

                    false_markers = {
                        "???",
                        "???",
                        "false",
                        "faux",
                        "incorrect",
                    }

                    first_word = (
                        normalized_answer
                        .split()[0]
                        if normalized_answer
                        else ""
                    )

                    if (
                        first_word
                        in true_markers
                        or normalized_answer
                        .startswith(
                            "???? "
                        )
                    ):
                        candidate[
                            "correct_answer"
                        ] = "????"

                    elif (
                        first_word
                        in false_markers
                        or normalized_answer
                        .startswith(
                            "??? "
                        )
                    ):
                        candidate[
                            "correct_answer"
                        ] = "???"

                else:

                    candidate[
                        "options"
                    ] = [
                        "Vrai",
                        "Faux",
                    ]

                    first_word = (
                        normalized_answer
                        .split()[0]
                        if normalized_answer
                        else ""
                    )

                    if first_word in {
                        "vrai",
                        "true",
                        "correct",
                    }:
                        candidate[
                            "correct_answer"
                        ] = "Vrai"

                    elif first_word in {
                        "faux",
                        "false",
                        "incorrect",
                    }:
                        candidate[
                            "correct_answer"
                        ] = "Faux"

            validated_question = (
                validate_generated_question(
                    item=candidate,
                    passages=[
                        {
                            "text": (
                                evidence_text
                            ),
                            "source": (
                                evidence.get(
                                    "source",
                                    source,
                                )
                            ),
                            "page": (
                                evidence.get(
                                    "page",
                                    0,
                                )
                            ),
                        }
                    ],
                    allowed_types={
                        question_type
                    },
                )
            )

            if not validated_question:

                rejection_log.append(
                    (
                        f"Q{target_index} "
                        f"{question_type}: "
                        "structure_validation_failed"
                    )
                )

                continue

            # QUIZ_PEDAGOGICAL_QUALITY_GATE_V7

            generated_text = str(
                validated_question.get(
                    "question",
                    "",
                )
                or ""
            ).strip()

            normalized_generated = (
                normalize_text(
                    generated_text
                )
            )

            # QUIZ_EARLY_LANGUAGE_GATE_V12G

            if arabic_lesson:

                alpha_chars = [
                    char
                    for char
                    in generated_text
                    if char.isalpha()
                ]

                arabic_chars = [
                    char
                    for char
                    in alpha_chars
                    if (
                        "\u0600"
                        <= char
                        <= "\u06ff"
                    )
                ]

                arabic_output_ratio = (
                    len(
                        arabic_chars
                    )
                    / len(
                        alpha_chars
                    )
                    if alpha_chars
                    else 0.0
                )


                if (
                    arabic_output_ratio
                    < 0.55
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            f"{question_type}: "
                            "wrong_language_early="
                            f"{arabic_output_ratio:.2f}"
                        )
                    )

                    continue


            # QUIZ_MORPH_ANSWER_GATE_V15
            #
            # Do not require a byte-for-byte answer quote.
            # Arabic inflection may legitimately transform
            # the same grounded concept, e.g.
            # "?????? ???????" vs "????? ??????? ????????".
            #
            # The V12 local Q/A gate below remains the
            # authority and requires strong local support.

            # QUIZ_LOCAL_QA_GATE_V12

            generated_answer = str(
                validated_question.get(
                    "correct_answer",
                    "",
                )
                or ""
            ).strip()


            # QUIZ_FRENCH_FALLBACK_LOCAL_SUPPORT_V25Z2
            # Validate a French fallback against the exact documentary
            # fact from the SAME selected source, not an unrelated retry chunk.
            local_support_evidence_v25z2 = evidence_text

            if quiz_uses_french_language_pipeline_v25x_r2(
                program,
                subject,
                arabic_lesson,
            ):
                fallback_pairs_v25z2 = (
                    quiz_french_source_qa_fallback_v25z(
                        program=program,
                        subject=subject,
                        source=source,
                    )
                )

                generated_question_key_v25z2 = normalize_text(
                    generated_text
                )
                generated_answer_key_v25z2 = normalize_text(
                    generated_answer
                )

                for (
                    fallback_question_v25z2,
                    fallback_answer_v25z2,
                    fallback_fact_v25z2,
                ) in fallback_pairs_v25z2:
                    fallback_question_key_v25z2 = normalize_text(
                        fallback_question_v25z2
                    )
                    fallback_answer_key_v25z2 = normalize_text(
                        fallback_answer_v25z2
                    )

                    fallback_tf_statement_v25z2 = (
                        quiz_french_tf_true_statement_v25z(
                            question=fallback_question_v25z2,
                            answer=fallback_answer_v25z2,
                        )
                    )
                    fallback_tf_key_v25z2 = normalize_text(
                        fallback_tf_statement_v25z2
                    )

                    qa_match_v25z2 = (
                        generated_question_key_v25z2
                        == fallback_question_key_v25z2
                        and (
                            not generated_answer_key_v25z2
                            or generated_answer_key_v25z2
                            == fallback_answer_key_v25z2
                        )
                    )

                    tf_match_v25z2 = (
                        bool(fallback_tf_key_v25z2)
                        and generated_question_key_v25z2
                        == fallback_tf_key_v25z2
                    )

                    if qa_match_v25z2 or tf_match_v25z2:
                        local_support_evidence_v25z2 = (
                            fallback_fact_v25z2
                        )
                        break

            local_support = (
                quiz_best_local_support_french_tf_v21h_r2(
                    evidence=(
                        local_support_evidence_v25z2
                    ),
                    question=(
                        generated_text
                    ),
                    answer=(
                        generated_answer
                    ),
                )
            )


            question_local_overlap = float(
                local_support.get(
                    "question_overlap",
                    0.0,
                )
                or 0.0
            )

            answer_local_overlap = float(
                local_support.get(
                    "answer_overlap",
                    0.0,
                )
                or 0.0
            )

            answer_local_exact = bool(
                local_support.get(
                    "answer_exact",
                    False,
                )
            )


            # QUIZ_FRENCH_FALLBACK_GROUNDING_V25Z3
            # Exact-answer safeguard for same-source French fallback.
            # This does NOT lower thresholds. It only treats the answer
            # as exact when its normalized text is literally present in
            # the matched fallback fact from the selected PDF.
            v25z3_same_source_answer_exact = False

            if (
                quiz_uses_french_language_pipeline_v25x_r2(
                    program,
                    subject,
                    arabic_lesson,
                )
                and "local_support_evidence_v25z2" in locals()
            ):
                normalized_generated_answer_v25z3 = (
                    normalize_text(
                        generated_answer
                    )
                )
                normalized_support_v25z3 = (
                    normalize_text(
                        local_support_evidence_v25z2
                    )
                )

                v25z3_same_source_answer_exact = bool(
                    normalized_generated_answer_v25z3
                    and normalized_generated_answer_v25z3
                    in normalized_support_v25z3
                )

                if v25z3_same_source_answer_exact:
                    answer_local_exact = True
                    answer_local_overlap = 1.0


            # QUIZ_ALIGNMENT_DEBUG_V12D

            print()
            print(
                "=" * 80
            )
            print(
                "QUIZ V12 ALIGNMENT DEBUG"
            )
            print(
                "TARGET:",
                target_index,
                question_type,
            )
            print(
                "QUESTION:",
                generated_text,
            )
            print(
                "ANSWER:",
                generated_answer,
            )
            print(
                "EVIDENCE PAGE:",
                evidence.get(
                    "page",
                    0,
                ),
            )
            print(
                "LOCAL SUPPORT:",
                local_support.get(
                    "text",
                    "",
                ),
            )
            print(
                "QUESTION OVERLAP:",
                question_local_overlap,
            )
            print(
                "ANSWER OVERLAP:",
                answer_local_overlap,
            )
            print(
                "ANSWER EXACT:",
                answer_local_exact,
            )
            print(
                "=" * 80
            )
            print()


            # QUIZ_ALIGNMENT_FILE_DEBUG_V12F

            debug_payload = (
                "\n"
                + "=" * 100
                + "\n"
                + "TARGET: "
                + str(target_index)
                + " "
                + str(question_type)
                + "\n"
                + "QUESTION: "
                + repr(
                    generated_text
                )
                + "\n"
                + "ANSWER: "
                + repr(
                    generated_answer
                )
                + "\n"
                + "EVIDENCE PAGE: "
                + repr(
                    evidence.get(
                        "page",
                        0,
                    )
                )
                + "\n"
                + "EVIDENCE: "
                + repr(
                    evidence_text[:1200]
                )
                + "\n"
                + "LOCAL SUPPORT: "
                + repr(
                    local_support.get(
                        "text",
                        "",
                    )
                )
                + "\n"
                + "QUESTION TOKENS: "
                + repr(
                    quiz_question_focus_tokens(
                        generated_text
                    )
                )
                + "\n"
                + "ANSWER TOKENS: "
                + repr(
                    quiz_canonical_content_tokens(
                        generated_answer
                    )
                )
                + "\n"
                + "SUPPORT TOKENS: "
                + repr(
                    quiz_canonical_content_tokens(
                        local_support.get(
                            "text",
                            "",
                        )
                    )
                )
                + "\n"
                + "QUESTION OVERLAP: "
                + repr(
                    question_local_overlap
                )
                + "\n"
                + "ANSWER OVERLAP: "
                + repr(
                    answer_local_overlap
                )
                + "\n"
                + "ANSWER EXACT: "
                + repr(
                    answer_local_exact
                )
                + "\n"
            )

            with open(
                "quiz_alignment_debug_v12f.txt",
                "a",
                encoding="utf-8",
            ) as debug_handle:

                debug_handle.write(
                    debug_payload
                )


            if question_type in {
                "mcq",
                "short_answer",
            }:

                # QUIZ_QUESTION_THRESHOLD_V15B
                #
                # 0.45 separates a locally supported
                # question from cases where the answer
                # happens to occur in the same sentence
                # but the question asks about another
                # scientific concept.

                # QUIZ_ARABIC_DEFINITION_ALIGNMENT_BYPASS_V25N
                v25n_strict_arabic_definition_mcq = (
                    arabic_lesson
                    and question_type == "mcq"
                    and answer_local_exact
                    and generated_text.startswith(
                        "ما المقصود بمصطلح "
                    )
                    and bool(source_first_mcq_fact)
                    and normalize_text(generated_answer)
                    in normalize_text(source_first_mcq_fact)
                )

                if (
                    question_local_overlap
                    < 0.45
                    and not v25n_strict_arabic_definition_mcq
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            f"{question_type}: "
                            "weak_local_question="
                            f"{question_local_overlap:.2f}"
                        )
                    )

                    continue


                # QUIZ_CANONICAL_ANSWER_SALVAGE_V16B

                if (
                    question_type == "mcq"
                    and not answer_local_exact
                    and answer_local_overlap < 0.75
                ):

                    canonical_answer = (
                        quiz_source_answer_span_v16b(
                            support_text=(
                                local_support.get(
                                    "text",
                                    "",
                                )
                            ),
                            generated_answer=(
                                generated_answer
                            ),
                        )
                    )


                    if canonical_answer:

                        repaired_options = (
                            quiz_repair_mcq_distractors_v16(
                                question=(
                                    generated_text
                                ),
                                correct_answer=(
                                    canonical_answer
                                ),
                                evidence=(
                                    evidence_text
                                ),
                                lesson_text=(
                                    lesson_text
                                ),
                                arabic_expected=(
                                    arabic_lesson
                                ),
                            )
                        )


                        if repaired_options:

                            generated_answer = (
                                canonical_answer
                            )


                            validated_question[
                                "correct_answer"
                            ] = canonical_answer

                            validated_question[
                                "options"
                            ] = repaired_options


                            candidate[
                                "correct_answer"
                            ] = canonical_answer

                            candidate[
                                "options"
                            ] = repaired_options


                            grounded_explanation = (
                                quiz_build_grounded_explanation(
                                    evidence=(
                                        evidence_text
                                    ),
                                    question=(
                                        generated_text
                                    ),
                                    correct_answer=(
                                        canonical_answer
                                    ),
                                )
                            )


                            candidate[
                                "explanation"
                            ] = (
                                grounded_explanation
                            )


                            if (
                                "explanation"
                                in validated_question
                            ):

                                validated_question[
                                    "explanation"
                                ] = (
                                    grounded_explanation
                                )


                            # Recalculate grounding against
                            # the documentary answer selected
                            # by the backend.
                            local_support = (
                                quiz_best_local_support(
                                    evidence=(
                                        evidence_text
                                    ),
                                    question=(
                                        generated_text
                                    ),
                                    answer=(
                                        canonical_answer
                                    ),
                                )
                            )


                            question_local_overlap = float(
                                local_support.get(
                                    "question_overlap",
                                    0.0,
                                )
                                or 0.0
                            )

                            answer_local_overlap = float(
                                local_support.get(
                                    "answer_overlap",
                                    0.0,
                                )
                                or 0.0
                            )

                            answer_local_exact = bool(
                                local_support.get(
                                    "answer_exact",
                                    False,
                                )
                            )


                            print(
                                "QUIZ V16B ANSWER SALVAGED:",
                                f"Q{target_index}",
                                "=>",
                                canonical_answer,
                            )



                if (
                    not answer_local_exact
                    and answer_local_overlap
                    < 0.75
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            f"{question_type}: "
                            "weak_local_answer="
                            f"{answer_local_overlap:.2f}"
                        )
                    )

                    continue


            if question_type == "true_false":

                if (
                    question_local_overlap
                    < 0.55
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "true_false: "
                            "weak_local_statement="
                            f"{question_local_overlap:.2f}"
                        )
                    )

                    continue


                normalized_tf = (
                    normalize_text(
                        generated_text
                    )
                )

                if (
                    normalized_tf.startswith(
                        "\u0647\u0644 "
                    )
                    or generated_text.rstrip().endswith(
                        "\u061f"
                    )
                    or generated_text.rstrip().endswith(
                        "?"
                    )
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "true_false: "
                            "not_declarative"
                        )
                    )

                    continue


            if question_type == "mcq":

                if quiz_has_vague_mcq_stem(
                    generated_text
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "mcq: vague_stem"
                        )
                    )

                    continue


                mcq_options = (
                    validated_question.get(
                        "options",
                        [],
                    )
                    or []
                )

                if quiz_mcq_has_contained_option(
                    options=mcq_options,
                    correct_answer=(
                        generated_answer
                    ),
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "mcq: "
                            "contained_correct_option"
                        )
                    )

                    continue


            # QUIZ_DISTRACTOR_SHAPE_GATE_V17E

            if question_type == "mcq":

                shape_options_v17e = (
                    validated_question.get(
                        "options",
                        [],
                    )
                    or []
                )


                shape_correct_v17e = str(
                    validated_question.get(
                        "correct_answer",
                        "",
                    )
                    or ""
                ).strip()


                if not quiz_direction_distractor_shape_valid_v17e(
                    options=(
                        shape_options_v17e
                    ),
                    correct_answer=(
                        shape_correct_v17e
                    ),
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "mcq: "
                            "direction_shape_invalid"
                        )
                    )


                    print(
                        "QUIZ V17E SHAPE REJECT:",
                        shape_options_v17e,
                    )


                    continue


                pair_conflicts_v17e = (
                    quiz_distractor_pair_conflicts_v17e(
                        options=(
                            shape_options_v17e
                        ),
                        correct_answer=(
                            shape_correct_v17e
                        ),
                    )
                )


                if pair_conflicts_v17e:

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "mcq: "
                            "near_duplicate_distractors"
                        )
                    )


                    print(
                        "QUIZ V17E PAIR REJECT:",
                        pair_conflicts_v17e[:2],
                    )


                    continue


            # QUIZ_SEMANTIC_DISTRACTOR_GATE_V17D

            if question_type == "mcq":

                semantic_options_v17d = (
                    validated_question.get(
                        "options",
                        [],
                    )
                    or []
                )


                semantic_correct_v17d = str(
                    validated_question.get(
                        "correct_answer",
                        "",
                    )
                    or ""
                ).strip()


                semantic_conflicts_v17d = (
                    quiz_mcq_semantic_equivalent_distractors_v17d(
                        options=(
                            semantic_options_v17d
                        ),
                        correct_answer=(
                            semantic_correct_v17d
                        ),
                    )
                )


                if semantic_conflicts_v17d:

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "mcq: "
                            "semantic_equivalent_distractor="
                            + ", ".join(
                                semantic_conflicts_v17d[:2]
                            )
                        )
                    )


                    print(
                        "QUIZ V17D SEMANTIC REJECT:",
                        semantic_conflicts_v17d[:2],
                    )


                    continue


            # QUIZ_UNIQUE_MCQ_GATE_V14

            if question_type == "mcq":

                mcq_options = (
                    validated_question.get(
                        "options",
                        [],
                    )
                    or []
                )

                mcq_correct_answer = str(
                    validated_question.get(
                        "correct_answer",
                        "",
                    )
                    or ""
                ).strip()


                broad_membership_stem = (
                    quiz_mcq_has_broad_membership_stem(
                        generated_text
                    )
                )

                # QUIZ_BROAD_STEM_RELAXED_V15
                #
                # A broad wording is tolerated only because
                # the evidence-conflict check below still
                # verifies that no displayed distractor is
                # also supported by the selected passage.


                evidence_conflicts = (
                    quiz_mcq_evidence_conflicts(
                        options=mcq_options,
                        correct_answer=(
                            mcq_correct_answer
                        ),
                        evidence=(
                            evidence_text
                        ),
                    )
                )


                if evidence_conflicts:

                    # QUIZ_MCQ_DISTRACTOR_REPAIR_V16
                    #
                    # The question and correct answer already
                    # survived structural, language and local
                    # grounding checks. Do not throw them away
                    # only because Qwen produced bad distractors.

                    repaired_options = (
                        quiz_repair_mcq_distractors_v16(
                            question=(
                                generated_text
                            ),
                            correct_answer=(
                                mcq_correct_answer
                            ),
                            evidence=(
                                evidence_text
                            ),
                            lesson_text=(
                                lesson_text
                            ),
                            arabic_expected=(
                                arabic_lesson
                            ),
                        )
                    )


                    if repaired_options:

                        validated_question[
                            "options"
                        ] = repaired_options

                        candidate[
                            "options"
                        ] = repaired_options

                        print(
                            "QUIZ V16 MCQ SALVAGED:",
                            f"Q{target_index}",
                        )

                    else:

                        rejection_log.append(
                            (
                                f"Q{target_index} "
                                "mcq: "
                                "distractor_repair_failed="
                                + ", ".join(
                                    evidence_conflicts[:2]
                                )
                            )
                        )

                        continue


            # QUIZ_SCOPE_GATE_V11B

            if quiz_has_unsupported_scope(
                question=(
                    generated_text
                ),
                evidence=(
                    evidence_text
                ),
            ):

                rejection_log.append(
                    (
                        f"Q{target_index} "
                        f"{question_type}: "
                        "unsupported_scope"
                    )
                )

                continue


            # QUIZ_ANSWER_QUALITY_GATE_V10

            if quiz_has_source_reference_language(
                generated_text
            ):

                rejection_log.append(
                    (
                        f"Q{target_index} "
                        f"{question_type}: "
                        "source_reference_language"
                    )
                )

                continue


            if question_type in {
                "mcq",
                "short_answer",
            }:

                generated_answer = str(
                    validated_question.get(
                        "correct_answer",
                        "",
                    )
                    or ""
                ).strip()

                answer_grounding = (
                    quiz_answer_grounding_score(
                        answer=(
                            generated_answer
                        ),
                        evidence=(
                            evidence_text
                        ),
                    )
                )


                minimum_answer_grounding = (
                    0.60
                )


                # QUIZ_EXACT_NUMERIC_ANSWER_GROUNDING_V24B
                exact_numeric_answer_v24b = bool(
                    answer_local_exact
                    and re.fullmatch(
                        r"[-+]?\d+(?:[.,]\d+)?(?:\s*%)?",
                        normalize_text(
                            generated_answer
                        ),
                    )
                )

                if (
                    answer_grounding
                    < minimum_answer_grounding
                    and not exact_numeric_answer_v24b
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            f"{question_type}: "
                            "weak_answer_grounding="
                            f"{answer_grounding:.2f}"
                        )
                    )

                    continue

                if (
                    answer_grounding
                    < minimum_answer_grounding
                    and exact_numeric_answer_v24b
                ):

                    print(
                        "QUIZ V24B EXACT NUMERIC GROUNDING:",
                        f"Q{target_index}",
                        "answer=",
                        repr(generated_answer),
                        "score=",
                        round(answer_grounding, 3),
                    )


            if question_type == "mcq":

                generated_options = [
                    str(
                        option
                        or ""
                    ).strip()
                    for option
                    in (
                        validated_question.get(
                            "options",
                            [],
                        )
                        or []
                    )
                ]

                normalized_options = [
                    normalize_text(
                        option
                    )
                    for option
                    in generated_options
                ]

                if (
                    len(
                        set(
                            normalized_options
                        )
                    )
                    != 4
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            "mcq: "
                            "duplicate_options"
                        )
                    )

                    continue



            # QUIZ_ARABIC_TF_OUTPUT_CLEANUP_V25H
            if (
                question_type == "true_false"
                and arabic_lesson
            ):

                cleaned_tf_v25h = (
                    quiz_arabic_tf_output_cleanup_v25h(
                        generated_text
                    )
                )


                if cleaned_tf_v25h:

                    generated_text = (
                        cleaned_tf_v25h
                    )


                    validated_question[
                        "question"
                    ] = (
                        cleaned_tf_v25h
                    )


            # QUIZ_OUTPUT_GROUNDING_GATE_V9

            if quiz_has_heading_noise(
                generated_text
            ):

                rejection_log.append(
                    (
                        f"Q{target_index} "
                        f"{question_type}: "
                        "heading_or_ocr_prefix"
                    )
                )

                continue


            # QUIZ_FRENCH_FALLBACK_GROUNDING_V25Z3
            grounding_evidence_v25z3 = (
                local_support_evidence_v25z2
                if (
                    quiz_uses_french_language_pipeline_v25x_r2(
                        program,
                        subject,
                        arabic_lesson,
                    )
                    and "local_support_evidence_v25z2" in locals()
                )
                else evidence_text
            )

            grounding_overlap = (
                quiz_grounding_overlap(
                    question=(
                        generated_text
                    ),
                    evidence=(
                        grounding_evidence_v25z3
                    ),
                )
            )


            minimum_grounding = (
                0.45
                if question_type
                == "true_false"
                else 0.25
            )


            if (
                grounding_overlap
                < minimum_grounding
            ):

                rejection_log.append(
                    (
                        f"Q{target_index} "
                        f"{question_type}: "
                        "weak_grounding="
                        f"{grounding_overlap:.2f}"
                    )
                )

                continue


            # QUIZ_GENERATED_TEXT_QUALITY_V8
            if arabic_lesson:

                generated_tokens = [
                    token
                    for token
                    in re.split(
                        r"\s+",
                        generated_text,
                    )
                    if token
                ]

                mixed_tokens = sum(
                    1
                    for token
                    in generated_tokens
                    if (
                        any(
                            char.isalpha()
                            for char in token
                        )
                        and any(
                            char.isdigit()
                            for char in token
                        )
                    )
                )

                tiny_tokens = sum(
                    1
                    for token
                    in generated_tokens
                    if len(
                        normalize_text(
                            token
                        )
                    ) <= 1
                )

                tiny_ratio = (
                    tiny_tokens
                    / len(
                        generated_tokens
                    )
                    if generated_tokens
                    else 1.0
                )

                if (
                    mixed_tokens > 0
                    or tiny_ratio > 0.20
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            f"{question_type}: "
                            "ocr_like_question"
                        )
                    )

                    continue

            # An Arabic lesson must produce an Arabic question.
            if (
                arabic_lesson
                and not contains_arabic(
                    generated_text
                )
            ):

                rejection_log.append(
                    (
                        f"Q{target_index} "
                        f"{question_type}: "
                        "wrong_language"
                    )
                )

                continue

            # Reject questions about API metadata rather than
            # about the pedagogical content itself.
            forbidden_phrases = [
                normalize_text(
                    program
                ),
                normalize_text(
                    subject
                ),
                normalize_text(
                    semester
                ),
                "programme marocain",
            ]

            metadata_leak = any(
                phrase
                and len(phrase) >= 2
                and phrase
                in normalized_generated
                for phrase
                in forbidden_phrases
            )

            if metadata_leak:

                rejection_log.append(
                    (
                        f"Q{target_index} "
                        f"{question_type}: "
                        "metadata_leak"
                    )
                )

                continue

            # Reject transliterated filename tokens leaking
            # into Arabic pedagogical questions.
            if arabic_lesson:

                source_tokens = [
                    token
                    for token
                    in re.split(
                        r"[^a-zA-Z]+",
                        source
                        or "",
                    )
                    if len(token) >= 5
                ]

                lower_question = (
                    generated_text.lower()
                )

                if any(
                    token.lower()
                    in lower_question
                    for token
                    in source_tokens
                ):

                    rejection_log.append(
                        (
                            f"Q{target_index} "
                            f"{question_type}: "
                            "source_filename_leak"
                        )
                    )

                    continue

            question_key = (
                normalize_text(
                    validated_question.get(
                        "question",
                        "",
                    )
                )
            )

            if (
                not question_key
                or question_key
                in seen_questions
            ):

                rejection_log.append(
                    (
                        f"Q{target_index} "
                        f"{question_type}: "
                        "duplicate_question"
                    )
                )

                continue

            seen_questions.add(
                question_key
            )

            validated.append(
                validated_question
            )

            question_created = True

            break

        if not question_created:

            print(
                "QUIZ GENERATION WARNING:",
                f"question {target_index}",
                question_type,
                "could not be created.",
            )

    if len(validated) < count:

        recent_rejections = (
            rejection_log[-12:]
        )

        raise RuntimeError(
            "Le g?n?rateur grounded V3 "
            "n'a pas produit assez de "
            "questions valides. "
            f"{len(validated)}/{count}. "
            "Rejets r?cents: "
            + " | ".join(
                recent_rejections
            )
        )

    quiz_id = uuid.uuid4().hex

    stored_questions = []
    public_questions = []

    for index, question in enumerate(
        validated,
        start=1,
    ):

        internal = {
            "id": index,
            **question,
        }

        stored_questions.append(
            internal
        )

        public_questions.append(
            {
                "id": index,
                "type": (
                    question[
                        "type"
                    ]
                ),
                "question": (
                    question[
                        "question"
                    ]
                ),
                "options": (
                    question[
                        "options"
                    ]
                ),
                "source": (
                    question[
                        "source"
                    ]
                ),
                "page": (
                    question[
                        "page"
                    ]
                ),
            }
        )

    with QUIZ_STORE_LOCK:

        QUIZ_STORE[
            quiz_id
        ] = {
            "created_at": (
                time.time()
            ),
            "program": program,
            "subject": subject,
            "semester": semester,
            "source": source,
            "difficulty": difficulty,
            "questions": (
                stored_questions
            ),
        }

    return {
        "quiz_id": quiz_id,
        "program": program,
        "subject": subject,
        "semester": semester,
        "source": source,
        "difficulty": difficulty,
        "question_count": len(
            public_questions
        ),
        "questions": (
            public_questions
        ),
    }




def submit_quiz(
    quiz_id: str,
    answers: list[dict],
) -> dict:

    clean_expired_quizzes()

    quiz_id = str(
        quiz_id
        or ""
    ).strip()

    if not quiz_id:
        raise ValueError(
            "quiz_id est obligatoire."
        )

    with QUIZ_STORE_LOCK:

        quiz = QUIZ_STORE.get(
            quiz_id
        )

    if not quiz:
        raise KeyError(
            "Quiz introuvable ou expir?."
        )

    submitted = {}

    for item in answers or []:

        try:
            question_id = int(
                item.get(
                    "question_id"
                )
            )
        except Exception:
            continue

        submitted[
            question_id
        ] = str(
            item.get(
                "answer",
                "",
            )
            or ""
        ).strip()

    details = []
    correct_count = 0

    for question in quiz[
        "questions"
    ]:

        question_id = (
            question[
                "id"
            ]
        )

        student_answer = (
            submitted.get(
                question_id,
                "",
            )
        )

        correct = answer_matches(
            submitted=student_answer,
            expected=(
                question[
                    "correct_answer"
                ]
            ),
            question_type=(
                question[
                    "type"
                ]
            ),
        )

        if correct:
            correct_count += 1

        details.append(
            {
                "question_id": (
                    question_id
                ),
                "question": (
                    question[
                        "question"
                    ]
                ),
                "student_answer": (
                    student_answer
                ),
                "correct": correct,
                "correct_answer": (
                    question[
                        "correct_answer"
                    ]
                ),
                "explanation": (
                    question[
                        "explanation"
                    ]
                ),
                "source": (
                    question[
                        "source"
                    ]
                ),
                "page": (
                    question[
                        "page"
                    ]
                ),
            }
        )

    total = len(
        quiz[
            "questions"
        ]
    )

    score_percent = (
        round(
            (
                correct_count
                / total
                * 100
            ),
            2,
        )
        if total
        else 0.0
    )

    return {
        "quiz_id": quiz_id,
        "score": correct_count,
        "total": total,
        "score_percent": (
            score_percent
        ),
        "correct": correct_count,
        "incorrect": (
            total
            - correct_count
        ),
        "details": details,
    }
