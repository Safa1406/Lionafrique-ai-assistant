import json
import re
import unicodedata

import httpx


OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3:1.7b"

REFUSAL_ANSWER = (
    "Les documents disponibles ne contiennent pas "
    "une réponse suffisamment précise à cette question."
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

STOP_WORDS = {
    "avec",
    "aux",
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
    "quelles",
    "quelle",
    "quels",
    "quel",
    "sont",
    "sur",
    "une",
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


def normalize_text(text: str) -> str:
    """
    Normalise un texte pour effectuer des comparaisons fiables.
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
        r"[^a-z0-9\s]",
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
    Détecte la relation principale demandée.
    """

    normalized_question = normalize_text(question)

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

    for intent, words in INTENT_WORDS.items():
        if question_words.intersection(words):
            return intent

    return None


def extract_topic_keywords(
    question: str,
) -> set[str]:
    """
    Extrait les mots décrivant le sujet de la question.
    """

    excluded_words = set(STOP_WORDS)

    for intent_words in INTENT_WORDS.values():
        excluded_words.update(intent_words)

    return {
        word
        for word in normalize_text(question).split()
        if len(word) >= 4
        and word not in excluded_words
    }

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
            r"(?<=[.!?])\s+",
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
                    (".", "!", "?")
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

def build_context(passages: list[dict]) -> str:
    """
    Prépare les passages avec leur numéro et leur source.
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

    return "\n\n".join(context_parts)


def call_ollama(payload: dict) -> dict:
    """
    Envoie une requête à Ollama et retourne le JSON produit.
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

        return json.loads(content)

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
    Demande au modèle d'extraire uniquement les preuves directes.
    """

    context = build_context(passages)

    system_prompt = """
Tu es un vérificateur de preuves documentaires.

Ta mission n'est pas de répondre immédiatement à la question.
Tu dois uniquement vérifier si les passages contiennent des
informations directes permettant de répondre.

Règles obligatoires :

- Utilise uniquement les passages documentaires fournis.
- N'utilise aucune connaissance générale.
- N'effectue aucune supposition ni déduction.
- Chaque citation doit être copiée mot pour mot depuis un passage.
- Chaque citation doit contenir entre 4 et 45 mots.
- Indique le numéro exact du passage contenant chaque citation.
- Une simple présence du même sujet ne suffit pas.

Pour une question sur les causes :
- Accepte uniquement les passages qui présentent explicitement
  une cause, une origine, une raison ou un facteur.
- Une conséquence, une date, une phase ou une définition
  ne constitue pas une cause.

Pour une question sur les conséquences :
- Accepte uniquement les passages qui décrivent explicitement
  un effet, un résultat, un bilan ou une conséquence.

Pour une question de définition :
- Accepte une phrase qui définit directement le terme demandé.
- Le mot « définition » ne doit pas obligatoirement apparaître.

Pour une question sur les rôles :
- Accepte les passages qui décrivent les catégories,
  les fonctions, l'utilité ou l'action du sujet demandé.
- Le mot « rôle » ne doit pas obligatoirement apparaître.
- Par exemple, les formulations « aliments bâtisseurs »,
  « aliments énergétiques » et « aliments protecteurs »
  constituent des preuves directes sur les rôles des aliments.

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
            "num_predict": 400,
        },
    }

    return call_ollama(payload)


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

        if passage_number > len(passages):
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

    combined_evidence = normalize_text(
        " ".join(
            item["quote"]
            for item in validated_evidence
        )
    )

    evidence_words = set(
        combined_evidence.split()
    )

    intent = detect_question_intent(
        question
    )

    # Les questions sur les causes et les conséquences
    # nécessitent une relation explicite.
    #
    # Pour une définition ou un rôle, la formulation
    # documentaire peut répondre sans contenir
    # littéralement les mots « définition » ou « rôle ».
    intents_requiring_explicit_markers = {
        "causes",
        "consequences",
    }

    if (
        intent
        in intents_requiring_explicit_markers
    ):
        intent_words = INTENT_WORDS.get(
            intent,
            set(),
        )

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
    Construit une réponse uniquement avec les citations validées.
    """

    unique_quotes = []
    seen_quotes = set()

    for item in evidence:
        quote = re.sub(
            r"\s+",
            " ",
            item.get("quote", ""),
        ).strip()

        normalized_quote = normalize_text(quote)

        if not normalized_quote:
            continue

        if normalized_quote in seen_quotes:
            continue

        seen_quotes.add(normalized_quote)
        unique_quotes.append(quote)

    if not unique_quotes:
        return REFUSAL_ANSWER

    intent = detect_question_intent(question)

    if intent == "definition":
        return (
            "D'après le document : "
            f"« {unique_quotes[0]} »"
        )

    if len(unique_quotes) == 1:
        return (
            "D'après le document : "
            f"« {unique_quotes[0]} »"
        )

    answer_lines = [
        "D'après les documents :"
    ]

    for quote in unique_quotes[:5]:
        answer_lines.append(
            f"- {quote}"
        )

    return "\n".join(answer_lines)


def generate_answer(
    question: str,
    passages: list[dict],
) -> dict:
    """
    Extrait les preuves, les valide
    puis produit une réponse documentaire.
    """

    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError(
            "La question ne peut pas être vide."
        )

    if not passages:
        return {
            "answerable": False,
            "answer": REFUSAL_ANSWER,
            "sources": [],
            "evidence": [],
        }

    intent = detect_question_intent(
        cleaned_question
    )

    validated_evidence = []

    if intent == "roles":
        validated_evidence = (
            extract_role_evidence_from_passages(
                question=cleaned_question,
                passages=passages,
            )
        )

    if not validated_evidence:
        extraction = extract_evidence(
            question=cleaned_question,
            passages=passages,
        )

        if not extraction.get(
            "answerable",
            False,
        ):
            return {
                "answerable": False,
                "answer": REFUSAL_ANSWER,
                "sources": [],
                "evidence": [],
            }

        validated_evidence = validate_evidence(
            question=cleaned_question,
            passages=passages,
            evidence_items=extraction.get(
                "evidence",
                [],
            ),
        )

    if not validated_evidence:
        return {
            "answerable": False,
            "answer": REFUSAL_ANSWER,
            "sources": [],
            "evidence": [],
        }

    if intent == "definition":
        validated_evidence = (
            validated_evidence[:1]
        )

    answer = write_answer(
        question=cleaned_question,
        evidence=validated_evidence,
    )

    if answer == REFUSAL_ANSWER:
        return {
            "answerable": False,
            "answer": REFUSAL_ANSWER,
            "sources": [],
            "evidence": [],
        }

    sources = []

    for item in validated_evidence:
        source = {
            "file": item["source"],
            "page": item["page"],
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