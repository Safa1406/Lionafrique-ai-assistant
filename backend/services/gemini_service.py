from __future__ import annotations

import os
from typing import Any

from google import genai
from google.genai.types import HttpOptions

GEMINI_MODEL = os.getenv(
    "LIONAFRIQUE_GEMINI_MODEL",
    "gemini-3.1-flash-lite",
)

GEMINI_BASE_URL = os.getenv(
    "LIONAFRIQUE_GEMINI_BASE_URL",
    "https://aigw.qalqul.io/genai",
)


def _get_api_key() -> str:
    # GEMINI_DIRECT_API_KEY_V3
    direct_key = 'sk-bf-9fb569d1-5884-4e9d-aa6c-b1faea7335ef'.strip()
    if direct_key:
        return direct_key

    key = (
        os.getenv("LIONAFRIQUE_GEMINI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or ""
    ).strip()

    if not key:
        raise RuntimeError(
            "Missing Gemini API key. Set LIONAFRIQUE_GEMINI_API_KEY."
        )

    return key


def get_gemini_client():
    return genai.Client(
        api_key=_get_api_key(),
        http_options=HttpOptions(
            base_url=GEMINI_BASE_URL,
        ),
    )


def gemini_generate_text(
    prompt: str,
    *,
    model: str | None = None,
) -> str:
    prompt = str(prompt or "").strip()

    if not prompt:
        raise ValueError("prompt must not be empty.")

    client = get_gemini_client()

    response = client.models.generate_content(
        model=model or GEMINI_MODEL,
        contents=prompt,
    )

    text = str(
        getattr(response, "text", "")
        or ""
    ).strip()

    if not text:
        raise RuntimeError(
            "Gemini returned an empty text response."
        )

    return text


def gemini_healthcheck() -> dict[str, Any]:
    text = gemini_generate_text(
        "Reply with exactly: LIONAFRIQUE_GEMINI_OK"
    )

    return {
        "status": "success",
        "model": GEMINI_MODEL,
        "base_url": GEMINI_BASE_URL,
        "response": text,
    }

# GEMINI_GROUNDED_QUIZ_ORIENTATION_V2

import json
import re


def _gemini_json_object_v2(text: str) -> dict:
    raw = str(text or "").strip()

    if raw.startswith("```"):
        raw = re.sub(
            r"^```(?:json)?\s*",
            "",
            raw,
            flags=re.IGNORECASE,
        )
        raw = re.sub(
            r"\s*```$",
            "",
            raw,
        )

    start = raw.find("{")
    end = raw.rfind("}")

    if start < 0 or end < start:
        raise ValueError(
            "Gemini did not return a JSON object."
        )

    parsed = json.loads(
        raw[start : end + 1]
    )

    if not isinstance(parsed, dict):
        raise ValueError(
            "Gemini JSON response must be an object."
        )

    return parsed


def _question_grounding_text_v2(
    item: dict,
) -> str:
    preferred_keys = (
        "evidence",
        "evidence_text",
        "local_support",
        "support",
        "support_text",
        "source_span",
        "source_text",
        "context",
        "passage",
    )

    chunks = []

    for key in preferred_keys:
        value = item.get(key)

        if isinstance(value, str):
            value = value.strip()

            if value:
                chunks.append(value)

    if chunks:
        return "\n".join(chunks)[:6000]

    question = str(
        item.get("question", "")
        or ""
    ).strip()

    answer = str(
        item.get("correct_answer", "")
        or ""
    ).strip()

    return (
        "Grounded validated blueprint.\n"
        f"Question: {question}\n"
        f"Validated answer: {answer}"
    )


def gemini_enhance_quiz_result_v2(
    result: dict,
    quiz_store: dict,
) -> dict:
    """
    Gemini generates the final wording of grounded quiz questions.

    The existing LIONAFRIQUE quiz engine remains responsible for:
    - source retrieval
    - validated answers
    - question type
    - options
    - grounding/safety
    - answer storage

    Gemini is only allowed to regenerate the question wording without
    changing the validated answer or adding new facts.
    """

    if not isinstance(result, dict):
        return result

    quiz_id = str(
        result.get("quiz_id", "")
        or ""
    ).strip()

    if not quiz_id:
        return result

    quiz_entry = (
        quiz_store.get(quiz_id)
        if isinstance(quiz_store, dict)
        else None
    )

    if not isinstance(quiz_entry, dict):
        return result

    internal_questions = quiz_entry.get(
        "questions",
        [],
    )

    public_questions = result.get(
        "questions",
        [],
    )

    if (
        not isinstance(internal_questions, list)
        or not isinstance(public_questions, list)
        or not internal_questions
    ):
        return result

    candidates = []

    for item in internal_questions:
        if not isinstance(item, dict):
            continue

        qtype = str(
            item.get("type", "")
            or ""
        ).strip()

        # True/False wording is deliberately left unchanged because
        # a paraphrase can accidentally flip truth conditions.
        if qtype not in {
            "mcq",
            "short_answer",
        }:
            continue

        question = str(
            item.get("question", "")
            or ""
        ).strip()

        answer = str(
            item.get("correct_answer", "")
            or ""
        ).strip()

        if not question or not answer:
            continue

        candidates.append(
            {
                "id": item.get("id"),
                "type": qtype,
                "original_question": question,
                "validated_answer": answer,
                "grounding": _question_grounding_text_v2(
                    item
                ),
            }
        )

    if not candidates:
        result["gemini_status"] = "no_eligible_questions"
        result["generation_engine"] = (
            "lionafrique-grounded"
        )
        result["gemini_questions_generated"] = 0
        return result

    prompt_payload = json.dumps(
        {
            "task": (
                "Regenerate only the wording of each quiz question."
            ),
            "rules": [
                (
                    "Use only the provided grounding and validated answer."
                ),
                (
                    "Do not introduce any fact that is not supported by grounding."
                ),
                (
                    "The validated answer must remain correct after regeneration."
                ),
                (
                    "Do not reveal the answer inside the question."
                ),
                (
                    "Keep the same language as the original question."
                ),
                (
                    "Keep the same question type."
                ),
                (
                    "Do not generate options; options stay controlled by the existing engine."
                ),
                (
                    "Return strict JSON only."
                ),
            ],
            "output_schema": {
                "questions": [
                    {
                        "id": "same id",
                        "question": "new grounded question wording",
                    }
                ]
            },
            "items": candidates,
        },
        ensure_ascii=False,
    )

    raw = gemini_generate_text(
        (
            "You are the grounded quiz-question generator for "
            "LIONAFRIQUE AI ASSISTANT.\n\n"
            + prompt_payload
        )
    )

    parsed = _gemini_json_object_v2(
        raw
    )

    generated_items = parsed.get(
        "questions",
        [],
    )

    if not isinstance(generated_items, list):
        raise ValueError(
            "Gemini questions must be a list."
        )

    generated_by_id = {}

    for item in generated_items:
        if not isinstance(item, dict):
            continue

        item_id = str(
            item.get("id", "")
        )

        question = str(
            item.get("question", "")
            or ""
        ).strip()

        if item_id and question:
            generated_by_id[item_id] = question

    changed = 0

    for internal in internal_questions:
        if not isinstance(internal, dict):
            continue

        item_id = str(
            internal.get("id", "")
        )

        new_question = generated_by_id.get(
            item_id
        )

        if not new_question:
            continue

        original = str(
            internal.get("question", "")
            or ""
        ).strip()

        if not original:
            continue

        # Prevent obvious answer leakage.
        answer = str(
            internal.get("correct_answer", "")
            or ""
        ).strip()

        if (
            answer
            and len(answer) >= 4
            and answer.casefold()
            in new_question.casefold()
        ):
            continue

        internal["question"] = new_question
        internal["generation_engine"] = "gemini"

        for public in public_questions:
            if not isinstance(public, dict):
                continue

            if str(
                public.get("id", "")
            ) == item_id:
                public["question"] = new_question
                public["generation_engine"] = "gemini"
                break

        changed += 1

    result["gemini_status"] = (
        "success"
        if changed > 0
        else "no_safe_changes"
    )

    result["generation_engine"] = (
        "gemini-grounded-hybrid"
        if changed > 0
        else "lionafrique-grounded"
    )

    result["gemini_questions_generated"] = changed

    return result


def gemini_orientation_guidance_v2(
    analysis: dict,
) -> str:
    if not isinstance(analysis, dict):
        raise ValueError(
            "analysis must be a dictionary."
        )

    weak_areas = analysis.get(
        "weak_areas",
        [],
    )

    revision_plan = analysis.get(
        "revision_plan",
        [],
    )

    if not weak_areas:
        return (
            "مستواك الحالي مزيان حسب النتائج المتوفرة. "
            "حافظ على المراجعة الخفيفة وواصل التمارين باش يبقى المستوى ثابت."
        )

    compact = {
        "overall_mastery": analysis.get(
            "overall_mastery"
        ),
        "target_mastery": analysis.get(
            "target_mastery"
        ),
        "weak_areas": [
            {
                "subject": item.get("subject"),
                "lesson": item.get("lesson"),
                "concept": item.get("concept"),
                "mastery": item.get("mastery"),
                "priority": item.get("priority"),
            }
            for item in weak_areas[:5]
            if isinstance(item, dict)
        ],
        "revision_plan": [
            {
                "rank": item.get("rank"),
                "subject": item.get("subject"),
                "concept": item.get("concept"),
                "current_mastery": item.get(
                    "current_mastery"
                ),
                "target_mastery": item.get(
                    "target_mastery"
                ),
                "actions": item.get("actions"),
            }
            for item in revision_plan[:5]
            if isinstance(item, dict)
        ],
    }

    prompt = (
        "You are the learning-orientation assistant inside "
        "LIONAFRIQUE AI ASSISTANT. This is NOT career guidance. "
        "Use only the deterministic learning results below. "
        "Do not change scores, priorities, subjects, lessons, or concepts. "
        "Write a concise personalized revision recommendation in Moroccan "
        "Arabic written in Arabic script. Explain what the learner should "
        "review first, what practice to do, and when to retake a quiz. "
        "Do not mention university, careers, or post-baccalaureate choices. "
        "Return plain text only.\n\n"
        + json.dumps(
            compact,
            ensure_ascii=False,
        )
    )

    return gemini_generate_text(
        prompt
    )

# GEMINI_ORIENTATION_FRENCH_ONLY_V4
def gemini_orientation_guidance_v2(analysis):
    import json

    compact = {
        "student_id": analysis.get("student_id"),
        "overall_mastery": analysis.get("overall_mastery"),
        "attempt_count": analysis.get("attempt_count"),
        "weak_areas": analysis.get("weak_areas", [])[:5],
        "strengths": analysis.get("strengths", [])[:5],
        "revision_plan": analysis.get("revision_plan", [])[:5],
    }

    prompt = (
        "Tu es l'assistant pédagogique de LIONAFRIQUE.\n\n"
        "IMPORTANT :\n"
        "- Réponds UNIQUEMENT en français.\n"
        "- N'utilise ni arabe, ni darija, ni anglais, même si la matière étudiée est en arabe.\n"
        "- Le conseil doit être clair, naturel et adapté à un élève.\n"
        "- Base-toi uniquement sur les résultats fournis.\n"
        "- Ne donne aucun conseil d'orientation scolaire, universitaire ou professionnelle.\n"
        "- Il s'agit uniquement d'un profil d'apprentissage.\n"
        "- Indique brièvement ce que l'élève maîtrise bien, ce qu'il doit revoir en priorité, "
        "l'action concrète à faire ensuite et quand refaire un quiz si cela est pertinent.\n"
        "- Reste concis : 2 à 4 phrases.\n\n"
        "Données du profil :\n"
        + json.dumps(compact, ensure_ascii=False)
        + "\n\nRetourne uniquement le conseil final en français, sans titre et sans JSON."
    )

    text = gemini_generate_text(prompt)
    text = str(text or "").strip()

    if not text:
        raise RuntimeError("Empty Gemini orientation guidance.")

    return text
