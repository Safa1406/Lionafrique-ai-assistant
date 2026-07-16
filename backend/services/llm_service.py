import httpx


OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3:1.7b"


def build_context(passages: list[dict]) -> str:
    """
    Prépare le contexte documentaire envoyé au modèle.
    """

    context_parts = []

    for index, passage in enumerate(passages, start=1):
        context_parts.append(
            (
                f"Document {index}\n"
                f"Source : {passage['source']}\n"
                f"Page : {passage['page']}\n"
                f"Contenu : {passage['text']}"
            )
        )

    return "\n\n".join(context_parts)


def generate_answer(
    question: str,
    passages: list[dict],
) -> str:
    """
    Génère une réponse pédagogique à partir des passages trouvés.
    """

    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError(
            "La question ne peut pas être vide."
        )

    if not passages:
        return (
            "Je n'ai trouvé aucune information pertinente "
            "dans les documents disponibles."
        )

    context = build_context(passages)

    system_prompt = """
Tu es un assistant pédagogique destiné aux élèves de troisième année
du collège de l'établissement LionAfrique.

Respecte strictement les règles suivantes :
- Réponds uniquement à partir du contexte documentaire fourni.
- N'utilise pas tes connaissances générales.
- N'invente aucune information.
- Utilise un français simple et adapté à un collégien.
- Donne une réponse courte, claire et structurée.
- Si le contexte ne permet pas de répondre, indique que l'information
  n'est pas disponible dans les documents.
- Ne montre jamais ton raisonnement interne.
- Ne crée pas de sources qui ne figurent pas dans le contexte.
""".strip()

    user_prompt = f"""
Contexte documentaire :

{context}

Question de l'élève :

{cleaned_question}

Rédige une réponse pédagogique en français.
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
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0.1,
        },
    }

    try:
        response = httpx.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=180.0,
        )

        response.raise_for_status()
        data = response.json()

        answer = data.get("message", {}).get("content", "").strip()

        if not answer:
            raise RuntimeError(
                "Ollama n'a retourné aucune réponse."
            )

        return answer

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
            "Ollama a retourné une erreur pendant "
            "la génération de la réponse."
        ) from error