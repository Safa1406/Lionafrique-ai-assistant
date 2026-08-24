from __future__ import annotations

import py_compile
from pathlib import Path

SEP = "=" * 120
ROOT = Path(__file__).resolve().parent
SERVICE = ROOT / "services" / "orientation_service.py"


def main() -> int:
    print(SEP)
    print("ORIENTATION V1 - CORE ENGINE TEST")
    print(SEP)

    py_compile.compile(str(SERVICE), doraise=True)
    print("PY_COMPILE => PASS")

    from services.orientation_service import analyze_orientation

    results = [
        {
            "subject": "Mathématiques",
            "lesson": "Équations",
            "concept": "Équations du premier degré",
            "source": "equations.pdf",
            "activity_type": "quiz",
            "score": 4,
            "total": 10,
        },
        {
            "subject": "Mathématiques",
            "lesson": "Équations",
            "concept": "Équations du premier degré",
            "source": "equations.pdf",
            "activity_type": "exercise",
            "score": 5,
            "total": 10,
        },
        {
            "subject": "Français",
            "lesson": "Grammaire",
            "concept": "Accord du participe passé",
            "source": "grammaire.pdf",
            "activity_type": "quiz",
            "score": 6,
            "total": 10,
        },
        {
            "subject": "Physique",
            "lesson": "Électricité",
            "concept": "Loi d'Ohm",
            "source": "electricite.pdf",
            "activity_type": "quiz",
            "score": 9,
            "total": 10,
        },
    ]

    output = analyze_orientation(results, target_mastery=85)

    assert output["status"] == "success"
    assert output["attempt_count"] == 4
    assert output["overall_mastery"] == 60.0
    assert len(output["diagnostics"]) == 3
    assert len(output["weak_areas"]) == 2
    assert len(output["strengths"]) == 1

    first = output["revision_plan"][0]
    assert first["subject"] == "Mathématiques"
    assert first["concept"] == "Équations du premier degré"
    assert first["current_mastery"] == 45.0
    assert first["priority"] == "high"

    second = output["revision_plan"][1]
    assert second["subject"] == "Français"
    assert second["current_mastery"] == 60.0
    assert second["priority"] == "medium"

    strength = output["strengths"][0]
    assert strength["subject"] == "Physique"
    assert strength["mastery"] == 90.0
    assert strength["status"] == "mastered"

    empty = analyze_orientation([])
    assert empty["status"] == "success"
    assert empty["attempt_count"] == 0
    assert empty["overall_mastery"] is None

    print("DIAGNOSTIC GROUPING => PASS")
    print("WEAK AREA DETECTION => PASS")
    print("PRIORITY RANKING => PASS")
    print("REVISION PLAN => PASS")
    print("STRENGTH DETECTION => PASS")
    print("EMPTY RESULTS SAFE => PASS")
    print()
    print("FINAL => PASS")
    print(SEP)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
