import json
import re
import sys
import unicodedata
import time
import urllib.error
import urllib.request

import services.summary_service as summary_service


API_URL = "http://127.0.0.1:8000/summarize"
EXPECTED_VERSION = "v4-arabic-topic-linked-coverage"


TESTS = [
    {
        "question": "لخص درس أسلوب المدح والذم.",
        "required": [
            "المدح",
            "الذم",
            "ثلاثة",
        ],
        "forbidden": [],
        "maximum_points": 4,
    },
    {
        "question": (
            "قدم ملخصا عن عناصر "
            "المدح والذم وإعرابهما."
        ),
        "required": [
            "المخصوص",
            "مبتدأ",
        ],
        "forbidden": [],
        "maximum_points": 2,
    },
    {
        "question": "لخص حالات فاعل نعم وبئس.",
        "required": [
            "فاعل",
            "نعم",
            "بئس",
        ],
        "forbidden": [
            "حبذا",
        ],
        "maximum_points": 2,
    },
    {
        "question": "لخص استعمال حبذا ولا حبذا.",
        "required": [
            "حبذا",
            "المدح",
            "الذم",
        ],
        "forbidden": [
            "ثلاثة عناصر",
        ],
        "maximum_points": 2,
    },
]


def configure_console() -> None:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8"
        )
    except AttributeError:
        pass


def send_summary(question: str) -> dict:
    payload = {
        "question": question,
        "number_of_results": 5,
        "program": "Programme marocain",
        "subject": "Arabe",
        "semester": None,
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def count_points(summary: str) -> int:
    return sum(
        1
        for line in summary.splitlines()
        if line.strip().startswith("-")
    )


def normalize_for_test(text: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        text.lower(),
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(
            character
        )
    )

    normalized = normalized.translate(
        str.maketrans(
            {
                "أ": "ا",
                "إ": "ا",
                "آ": "ا",
                "ى": "ي",
                "ؤ": "و",
                "ئ": "ي",
                "ة": "ه",
                "ـ": "",
            }
        )
    )

    normalized = re.sub(
        r"[^\w\s]",
        " ",
        normalized,
    )

    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


def normalize_required_term(
    term: str,
) -> str:
    normalized = normalize_for_test(
        term
    )

    if (
        normalized.startswith("ال")
        and len(normalized) > 3
    ):
        normalized = normalized[2:]

    return normalized


def main() -> None:
    configure_console()

    active_version = getattr(
        summary_service,
        "SUMMARY_SERVICE_VERSION",
        "ancienne version",
    )

    print("=" * 94)
    print("اختبار التلخيص العربي السريع والمركز v4")
    print("=" * 94)
    print("النسخة النشطة:", active_version)

    if active_version != EXPECTED_VERSION:
        print("النسخة الجديدة غير نشطة ❌")
        return

    passed = 0
    failed = 0

    try:
        send_summary(TESTS[0]["question"])
    except Exception:
        pass

    for index, test in enumerate(TESTS, start=1):
        print()
        print("-" * 94)
        print(f"[{index}/{len(TESTS)}]")
        print("الطلب:", test["question"])

        started_at = time.perf_counter()

        try:
            result = send_summary(
                test["question"]
            )
        except (
            urllib.error.URLError,
            TimeoutError,
        ) as error:
            failed += 1
            print("خطأ في الاتصال:", error)
            continue

        duration = round(
            time.perf_counter() - started_at,
            3,
        )

        status = result.get("status", "")
        summary = result.get("summary", "")

        normalized_summary = normalize_for_test(
            summary
        )

        missing_terms = [
            term
            for term in test["required"]
            if normalize_required_term(
                term
            )
            not in normalized_summary
        ]

        forbidden_terms = [
            term
            for term in test["forbidden"]
            if normalize_required_term(
                term
            )
            in normalized_summary
        ]

        points = count_points(summary)

        success = (
            status == "success"
            and not missing_terms
            and not forbidden_terms
            and points <= test["maximum_points"]
            and duration < 10
        )

        print("الحالة:", status)
        print("المدة:", duration, "ثانية")
        print("عدد النقط:", points)
        print()
        print(summary)

        if missing_terms:
            print("الكلمات الناقصة:", missing_terms)

        if forbidden_terms:
            print(
                "معلومات غير مطلوبة:",
                forbidden_terms,
            )

        if success:
            passed += 1
            print()
            print("النتيجة: ناجح ✅")
        else:
            failed += 1
            print()
            print("النتيجة: فاشل ❌")

    print()
    print("=" * 94)
    print("النتيجة النهائية")
    print("=" * 94)
    print("الناجحة:", passed)
    print("الفاشلة:", failed)
    print("المجموع:", len(TESTS))


if __name__ == "__main__":
    main()