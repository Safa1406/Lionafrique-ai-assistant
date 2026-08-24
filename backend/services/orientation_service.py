from __future__ import annotations

from typing import Any

ORIENTATION_V1_VERSION = "1.0.0"


def _safe_text(value: Any, default: str = "Non défini") -> str:
    text = str(value or "").strip()
    return text if text else default


def _safe_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _status_from_mastery(mastery: float) -> str:
    if mastery < 50.0:
        return "critical"
    if mastery < 70.0:
        return "review"
    if mastery < 85.0:
        return "developing"
    return "mastered"


def _priority_from_mastery(mastery: float) -> str:
    if mastery < 50.0:
        return "high"
    if mastery < 70.0:
        return "medium"
    if mastery < 85.0:
        return "low"
    return "maintenance"


def _actions_for_status(status: str) -> list[str]:
    if status == "critical":
        return [
            "review_lesson",
            "review_summary",
            "practice_easy",
            "practice_medium",
            "retake_quiz",
        ]

    if status == "review":
        return [
            "review_summary",
            "review_mistakes",
            "practice_medium",
            "retake_quiz",
        ]

    if status == "developing":
        return [
            "review_mistakes",
            "practice_targeted",
            "retake_quiz",
        ]

    return ["maintenance_practice"]


def _message_for_status(
    status: str,
    subject: str,
    topic: str,
    mastery: float,
) -> str:
    rounded = round(mastery, 1)

    if status == "critical":
        return (
            f"عندك نقص واضح في {topic} ضمن مادة {subject} ({rounded}%). "
            "راجع الدرس من البداية، ثم الملخص، ودير تمارين سهلة قبل ما تعاود الـQuiz."
        )

    if status == "review":
        return (
            f"المستوى في {topic} ضمن مادة {subject} مازال خاصو مراجعة ({rounded}%). "
            "ركز على الأخطاء السابقة، ثم دير تمارين متوسطة وعاود الـQuiz."
        )

    if status == "developing":
        return (
            f"المستوى في {topic} ضمن مادة {subject} متوسط ومزيان نسبياً ({rounded}%). "
            "دير تمارين موجهة على الأخطاء باش توصل للإتقان."
        )

    return (
        f"المستوى في {topic} ضمن مادة {subject} متمكن ({rounded}%). "
        "حافظ على المستوى بتمارين خفيفة."
    )


def _normalize_attempt(raw: dict[str, Any]) -> dict[str, Any]:
    subject = _safe_text(raw.get("subject"))
    source = _safe_text(raw.get("source"), "")
    lesson = _safe_text(raw.get("lesson"), source or "الدرس")
    concept = _safe_text(raw.get("concept"), lesson)

    score = _safe_number(raw.get("score"))
    total = _safe_number(raw.get("total"))

    if total <= 0:
        raise ValueError("Every orientation result must have total > 0.")

    score = max(0.0, min(score, total))

    return {
        "subject": subject,
        "source": source,
        "lesson": lesson,
        "concept": concept,
        "score": score,
        "total": total,
        "activity_type": _safe_text(
            raw.get("activity_type"),
            "quiz",
        ).lower(),
        "timestamp": raw.get("timestamp"),
    }


def analyze_orientation(
    results: list[dict[str, Any]],
    *,
    target_mastery: float = 85.0,
    max_plan_items: int = 5,
) -> dict[str, Any]:
    # Learning Orientation only:
    # analyze quiz/exercise results, detect weaknesses,
    # rank revision priorities, and propose improvement actions.

    if not isinstance(results, list):
        raise ValueError("results must be a list.")

    normalized = [
        _normalize_attempt(item)
        for item in results
        if isinstance(item, dict)
    ]

    if not normalized:
        return {
            "status": "success",
            "version": ORIENTATION_V1_VERSION,
            "attempt_count": 0,
            "overall_mastery": None,
            "diagnostics": [],
            "weak_areas": [],
            "strengths": [],
            "revision_plan": [],
            "message": "لا توجد نتائج كافية لبناء خطة مراجعة حالياً.",
        }

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}

    for item in normalized:
        key = (
            item["subject"],
            item["lesson"],
            item["concept"],
        )

        if key not in grouped:
            grouped[key] = {
                "subject": item["subject"],
                "lesson": item["lesson"],
                "concept": item["concept"],
                "sources": set(),
                "score_sum": 0.0,
                "total_sum": 0.0,
                "attempts": 0,
                "activity_types": set(),
            }

        bucket = grouped[key]
        bucket["score_sum"] += item["score"]
        bucket["total_sum"] += item["total"]
        bucket["attempts"] += 1

        if item["source"]:
            bucket["sources"].add(item["source"])

        bucket["activity_types"].add(item["activity_type"])

    diagnostics = []

    for bucket in grouped.values():
        mastery = (
            bucket["score_sum"] / bucket["total_sum"] * 100.0
            if bucket["total_sum"] > 0
            else 0.0
        )

        status = _status_from_mastery(mastery)
        priority = _priority_from_mastery(mastery)

        diagnostics.append(
            {
                "subject": bucket["subject"],
                "lesson": bucket["lesson"],
                "concept": bucket["concept"],
                "sources": sorted(bucket["sources"]),
                "activity_types": sorted(bucket["activity_types"]),
                "attempts": bucket["attempts"],
                "score": round(bucket["score_sum"], 2),
                "total": round(bucket["total_sum"], 2),
                "mastery": round(mastery, 2),
                "target_mastery": round(float(target_mastery), 2),
                "gap_to_target": round(
                    max(0.0, float(target_mastery) - mastery),
                    2,
                ),
                "status": status,
                "priority": priority,
                "actions": _actions_for_status(status),
                "recommendation": _message_for_status(
                    status,
                    bucket["subject"],
                    bucket["concept"],
                    mastery,
                ),
            }
        )

    diagnostics.sort(
        key=lambda item: (
            item["mastery"],
            -item["attempts"],
            item["subject"],
            item["concept"],
        )
    )

    weak_areas = [
        item
        for item in diagnostics
        if item["mastery"] < float(target_mastery)
    ]

    strengths = [
        item
        for item in diagnostics
        if item["mastery"] >= float(target_mastery)
    ]

    revision_plan = []

    for rank, item in enumerate(
        weak_areas[: max(1, int(max_plan_items))],
        start=1,
    ):
        revision_plan.append(
            {
                "rank": rank,
                "subject": item["subject"],
                "lesson": item["lesson"],
                "concept": item["concept"],
                "current_mastery": item["mastery"],
                "target_mastery": item["target_mastery"],
                "priority": item["priority"],
                "actions": item["actions"],
                "recommendation": item["recommendation"],
            }
        )

    total_score = sum(item["score"] for item in normalized)
    total_questions = sum(item["total"] for item in normalized)

    overall_mastery = (
        total_score / total_questions * 100.0
        if total_questions > 0
        else 0.0
    )

    if weak_areas:
        first = weak_areas[0]
        message = (
            f"أكبر أولوية حالياً هي {first['concept']} "
            f"في مادة {first['subject']} بنسبة إتقان {first['mastery']}%."
        )
    else:
        message = (
            "ما كاين حتى نقص مهم حالياً حسب النتائج المتوفرة. "
            "حافظ على المستوى وواصل التمارين."
        )

    return {
        "status": "success",
        "version": ORIENTATION_V1_VERSION,
        "attempt_count": len(normalized),
        "overall_mastery": round(overall_mastery, 2),
        "target_mastery": round(float(target_mastery), 2),
        "diagnostics": diagnostics,
        "weak_areas": weak_areas,
        "strengths": strengths,
        "revision_plan": revision_plan,
        "message": message,
    }

# ORIENTATION_V2_RESULT_STORE

ORIENTATION_RESULT_STORE_V2: dict[str, list[dict]] = {}


def record_orientation_result_v2(
    *,
    student_id: str,
    subject: str,
    lesson: str,
    concept: str,
    score: float,
    total: float,
    activity_type: str = "quiz",
    source: str = "",
    timestamp=None,
) -> dict:
    student_id = str(student_id or "").strip()

    if not student_id:
        raise ValueError("student_id is required.")

    item = _normalize_attempt(
        {
            "subject": subject,
            "lesson": lesson,
            "concept": concept,
            "score": score,
            "total": total,
            "activity_type": activity_type,
            "source": source,
            "timestamp": timestamp,
        }
    )

    ORIENTATION_RESULT_STORE_V2.setdefault(
        student_id,
        [],
    ).append(item)

    return {
        "status": "success",
        "student_id": student_id,
        "stored_count": len(
            ORIENTATION_RESULT_STORE_V2[student_id]
        ),
        "result": item,
    }


def get_orientation_results_v2(
    student_id: str,
) -> list[dict]:
    student_id = str(student_id or "").strip()

    if not student_id:
        return []

    return list(
        ORIENTATION_RESULT_STORE_V2.get(
            student_id,
            [],
        )
    )


def analyze_student_orientation_v2(
    student_id: str,
    *,
    target_mastery: float = 85.0,
    max_plan_items: int = 5,
) -> dict:
    output = analyze_orientation(
        get_orientation_results_v2(student_id),
        target_mastery=target_mastery,
        max_plan_items=max_plan_items,
    )

    output["student_id"] = str(
        student_id or ""
    ).strip()

    return output


def reset_orientation_results_v2(
    student_id: str,
) -> dict:
    student_id = str(student_id or "").strip()

    removed = len(
        ORIENTATION_RESULT_STORE_V2.get(
            student_id,
            [],
        )
    )

    ORIENTATION_RESULT_STORE_V2.pop(
        student_id,
        None,
    )

    return {
        "status": "success",
        "student_id": student_id,
        "removed": removed,
    }
