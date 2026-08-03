import csv
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

API_BASE_URL = "http://127.0.0.1:8000"
PROGRAM = "Programme marocain"
SUBJECT = "Arabe"
SEMESTER = None
EXPECTED_SOURCE = "aslob-alndaa.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120

JSON_REPORT = Path("alndaa_test_results.json")
CSV_REPORT = Path("alndaa_test_results.csv")

ARABIC_TRANSLATION_TABLE = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
        "ـ": "",
    }
)

TEST_CASES = [
    {
        "category": "تعريف",
        "endpoint": "/ask",
        "question": "ما تعريف أسلوب النداء؟",
        "expected_status": "success",
        "required_groups": [
            ["خطاب"],
            ["منادى"],
            ["يقبل", "ينصت", "ينتبه"],
        ],
    },
    {
        "category": "عناصر",
        "endpoint": "/ask",
        "question": "ما عناصر أسلوب النداء؟",
        "expected_status": "success",
        "required_groups": [
            ["اداه"],
            ["منادى"],
            ["عنصرين", "عنصر"],
        ],
    },
    {
        "category": "أدوات النداء",
        "endpoint": "/ask",
        "question": "ما أدوات النداء المستعملة لنداء القريب؟",
        "expected_status": "success",
        "required_groups": [
            ["همزه", "ا"],
            ["اي"],
            ["قريب"],
        ],
    },
    {
        "category": "أدوات النداء",
        "endpoint": "/ask",
        "question": "ما الأداة التي تستعمل لنداء القريب والبعيد معا؟",
        "expected_status": "success",
        "required_groups": [
            ["يا"],
            ["قريب"],
            ["بعيد"],
        ],
    },
    {
        "category": "أدوات النداء",
        "endpoint": "/ask",
        "question": "اذكر بعض أدوات نداء البعيد.",
        "expected_status": "success",
        "required_groups": [
            ["ايا"],
            ["هيا"],
            ["بعيد"],
        ],
    },
    {
        "category": "الفعل المحذوف",
        "endpoint": "/ask",
        "question": "عن أي فعل تنوب أدوات النداء؟",
        "expected_status": "success",
        "required_groups": [
            ["محذوف"],
            ["وجوب"],
            ["انادي", "ادعو"],
        ],
    },
    {
        "category": "أنواع المنادى",
        "endpoint": "/ask",
        "question": "ما أنواع المنادى في أسلوب النداء؟",
        "expected_status": "success",
        "required_groups": [
            ["علم"],
            ["نكره مقصوده"],
            ["مضاف"],
            ["شبيه"],
            ["غير مقصوده"],
        ],
    },
    {
        "category": "العلم المفرد",
        "endpoint": "/ask",
        "question": "ما المقصود بالمنادى العلم المفرد؟",
        "expected_status": "success",
        "required_groups": [
            ["شخص"],
            ["اسم"],
            ["كلمه واحده", "مفرد"],
        ],
    },
    {
        "category": "العلم المفرد",
        "endpoint": "/ask",
        "question": "ما حكم المنادى العلم المفرد إذا دل على المفرد والمثنى والجمع؟",
        "expected_status": "success",
        "required_groups": [
            ["ضم"],
            ["الف"],
            ["واو"],
            ["مبني"],
        ],
    },
    {
        "category": "النكرة المقصودة",
        "endpoint": "/ask",
        "question": "ما تعريف النكرة المقصودة في النداء؟",
        "expected_status": "success",
        "required_groups": [
            ["نكره"],
            ["يقصد"],
            ["نداء", "منادى"],
        ],
    },
    {
        "category": "النكرة المقصودة",
        "endpoint": "/ask",
        "question": "ما حكم النكرة المقصودة؟",
        "expected_status": "success",
        "required_groups": [
            ["علم"],
            ["مبني"],
        ],
    },
    {
        "category": "المضاف",
        "endpoint": "/ask",
        "question": "ما تعريف المنادى المضاف وما حكمه؟",
        "expected_status": "success",
        "required_groups": [
            ["مضاف"],
            ["منصوب"],
            ["مضاف اليه"],
            ["مجرور"],
        ],
    },
    {
        "category": "الشبيه بالمضاف",
        "endpoint": "/ask",
        "question": "ما المقصود بالمنادى الشبيه بالمضاف وما حكمه؟",
        "expected_status": "success",
        "required_groups": [
            ["يحتاج"],
            ["يتمم", "تمام"],
            ["منصوب", "نصب"],
        ],
    },
    {
        "category": "النكرة غير المقصودة",
        "endpoint": "/ask",
        "question": "ما تعريف النكرة غير المقصودة وما حكمها؟",
        "expected_status": "success",
        "required_groups": [
            ["لا يدل", "غير"],
            ["شخص", "بعينه"],
            ["منصوب"],
        ],
    },
    {
        "category": "الإعراب",
        "endpoint": "/ask",
        "question": "كيف يعرب المنادى بصفة عامة؟",
        "expected_status": "success",
        "required_groups": [
            ["مفعول"],
            ["منصوب"],
            ["فعل"],
            ["محذوف"],
            ["انادي", "ادعو"],
        ],
    },
    {
        "category": "المعرف بأل",
        "endpoint": "/ask",
        "question": "كيف ننادي الاسم المعرف بأل؟",
        "expected_status": "success",
        "required_groups": [
            ["اي"],
            ["ايه"],
            ["مذكر"],
            ["مونث"],
        ],
    },
    {
        "category": "المعرف بأل",
        "endpoint": "/ask",
        "question": "كيف يعرب الاسم الذي يأتي بعد أيها أو أيتها في النداء؟",
        "expected_status": "success",
        "required_groups": [
            ["نعت", "صفه", "عطف بيان"],
        ],
    },
    {
        "category": "المعرف بأل",
        "endpoint": "/ask",
        "question": "كيف تعرب أي وأية في أسلوب النداء؟",
        "expected_status": "success",
        "required_groups": [
            ["منادى"],
            ["مبني"],
            ["ضم"],
            ["محل نصب"],
        ],
    },
    {
        "category": "حذف الأداة",
        "endpoint": "/ask",
        "question": "هل يجوز حذف أداة النداء؟",
        "expected_status": "success",
        "required_groups": [
            ["تحذف", "حذف"],
            ["سياق"],
            ["دال"],
        ],
    },
    {
        "category": "اللهم",
        "endpoint": "/ask",
        "question": "بماذا تعوض أداة النداء مع اسم الجلالة في كلمة اللهم؟",
        "expected_status": "success",
        "required_groups": [
            ["ميم"],
            ["مشدد"],
            ["الله", "جلاله"],
        ],
    },
    {
        "category": "مثال تطبيقي",
        "endpoint": "/ask",
        "question": "أعرب محمد في جملة: يا محمد اجمع المحاصيل.",
        "expected_status": "success",
        "required_groups": [
            ["محمد"],
            ["منادى"],
            ["مبني"],
            ["ضم"],
            ["محل نصب"],
        ],
    },
    {
        "category": "مثال تطبيقي",
        "endpoint": "/ask",
        "question": "أعرب رجلا في جملة: يا رجلا خذ بيدي.",
        "expected_status": "success",
        "required_groups": [
            ["رجلا"],
            ["منادى"],
            ["منصوب"],
            ["فتحه"],
        ],
    },
    {
        "category": "مثال تطبيقي",
        "endpoint": "/ask",
        "question": "أعرب فاعل الخير في جملة: يا فاعل الخير أقبل.",
        "expected_status": "success",
        "required_groups": [
            ["فاعل"],
            ["منادى"],
            ["منصوب"],
            ["مضاف"],
            ["الخير"],
            ["مجرور"],
        ],
    },
    {
        "category": "مثال تطبيقي",
        "endpoint": "/ask",
        "question": "ما نوع المنادى في جملة: يا محبا وطنه أبشر؟",
        "expected_status": "success",
        "required_groups": [
            ["شبيه"],
            ["مضاف"],
            ["منصوب"],
        ],
    },
    {
        "category": "صياغة مختلفة",
        "endpoint": "/ask",
        "question": "اشرح قاعدة النداء باختصار.",
        "expected_status": "success",
        "required_groups": [
            ["اداه"],
            ["منادى"],
            ["مبني", "منصوب"],
        ],
    },
    {
        "category": "خطأ إملائي",
        "endpoint": "/ask",
        "question": "ما انواء المنادا واحكامه؟",
        "expected_status": "success",
        "required_groups": [
            ["علم"],
            ["نكره"],
            ["مضاف"],
        ],
    },
    {
        "category": "تلخيص",
        "endpoint": "/summarize",
        "question": "لخص درس أسلوب النداء.",
        "expected_status": "success",
        "required_groups": [
            ["نداء"],
            ["اداه"],
            ["منادى"],
            ["مبني", "منصوب"],
        ],
    },
    {
        "category": "تلخيص",
        "endpoint": "/summarize",
        "question": "لخص أنواع المنادى وأحكامها.",
        "expected_status": "success",
        "required_groups": [
            ["علم"],
            ["نكره"],
            ["مضاف"],
            ["شبيه"],
            ["منصوب", "مبني"],
        ],
    },
    {
        "category": "تلخيص",
        "endpoint": "/summarize",
        "question": "لخص قاعدة نداء المعرف بأل.",
        "expected_status": "success",
        "required_groups": [
            ["اي"],
            ["ايه"],
            ["نعت", "صفه"],
            ["منادى"],
        ],
    },
    {
        "category": "رفض صحيح",
        "endpoint": "/ask",
        "question": "ما درجة غليان الماء؟",
        "expected_status": "insufficient_context",
        "required_groups": [],
    },
]


def configure_console() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        (text or "").lower(),
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(
            character
        )
    )

    normalized = normalized.translate(
        ARABIC_TRANSLATION_TABLE
    )

    normalized = re.sub(
        r"[^\w\s-]",
        " ",
        normalized,
        flags=re.UNICODE,
    )

    normalized_words = []

    for word in re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip().split():
        for prefix in (
            "وال",
            "بال",
            "كال",
            "فال",
            "لل",
            "ال",
        ):
            if (
                word.startswith(prefix)
                and len(word) - len(prefix) >= 2
            ):
                word = word[len(prefix):]
                break

        normalized_words.append(word)

    return " ".join(normalized_words)


def make_request(endpoint: str, question: str) -> dict:
    payload = {
        "question": question,
        "number_of_results": NUMBER_OF_RESULTS,
        "program": PROGRAM,
        "subject": SUBJECT,
        "semester": SEMESTER,
        "source": EXPECTED_SOURCE,
    }

    request = urllib.request.Request(
        f"{API_BASE_URL}{endpoint}",
        data=json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT_SECONDS,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def extract_response_text(
    endpoint: str,
    response_data: dict,
) -> str:
    if endpoint == "/summarize":
        return response_data.get("summary", "")
    return response_data.get("answer", "")


def source_is_correct(
    sources: list[dict],
) -> bool:
    if not sources:
        return False

    return all(
        source.get("file", "")
        == EXPECTED_SOURCE
        for source in sources
    )


def find_missing_groups(
    response_text: str,
    required_groups: list[list[str]],
) -> list[list[str]]:
    normalized_response = normalize_text(response_text)
    missing_groups = []

    for group in required_groups:
        normalized_alternatives = [
            normalize_text(term)
            for term in group
        ]

        if not any(
            alternative
            and alternative in normalized_response
            for alternative in normalized_alternatives
        ):
            missing_groups.append(group)

    return missing_groups


def format_sources(
    sources: list[dict],
) -> str:
    return " ; ".join(
        (
            f"{source.get('file', 'مصدر غير معروف')}"
            f" | الصفحة "
            f"{source.get('page', '?')}"
        )
        for source in sources
    )


def main() -> None:
    configure_console()

    print("=" * 98)
    print("الاختبار النهائي لدرس أسلوب النداء")
    print("=" * 98)
    print("عدد الاختبارات:", len(TEST_CASES))
    print("المصدر المنتظر:", EXPECTED_SOURCE)
    print("فلتر المصدر: مفعل")

    results = []
    passed_count = 0
    failed_count = 0
    category_totals = {}
    category_passed = {}

    for index, test_case in enumerate(
        TEST_CASES,
        start=1,
    ):
        category = test_case["category"]
        endpoint = test_case["endpoint"]
        question = test_case["question"]
        expected_status = test_case[
            "expected_status"
        ]

        category_totals[category] = (
            category_totals.get(category, 0)
            + 1
        )

        print()
        print("-" * 98)
        print(
            f"[{index}/{len(TEST_CASES)}] "
            f"[{category}]"
        )
        print("السؤال:", question)

        started_at = time.perf_counter()

        actual_status = ""
        response_text = ""
        sources = []
        error_text = ""

        try:
            response_data = make_request(
                endpoint=endpoint,
                question=question,
            )
            actual_status = response_data.get(
                "status",
                "",
            )
            response_text = extract_response_text(
                endpoint=endpoint,
                response_data=response_data,
            )
            sources = (
                response_data.get("sources")
                or []
            )

        except TimeoutError:
            error_text = (
                "انتهت مهلة الطلب بعد "
                f"{TIMEOUT_SECONDS} ثانية."
            )

        except urllib.error.URLError as error:
            error_text = (
                "تعذر الاتصال بـFastAPI: "
                f"{error}"
            )

        except Exception as error:
            error_text = (
                "خطأ غير متوقع: "
                f"{error}"
            )

        duration = round(
            time.perf_counter()
            - started_at,
            3,
        )

        missing_groups = find_missing_groups(
            response_text=response_text,
            required_groups=test_case[
                "required_groups"
            ],
        )

        requires_source = (
            expected_status == "success"
        )

        correct_source = (
            source_is_correct(sources)
            if requires_source
            else True
        )

        test_passed = (
            not error_text
            and actual_status
            == expected_status
            and not missing_groups
            and correct_source
        )

        if test_passed:
            passed_count += 1
            category_passed[category] = (
                category_passed.get(
                    category,
                    0,
                )
                + 1
            )
            result_label = "ناجح ✅"
        else:
            failed_count += 1
            result_label = "فاشل ❌"

        print(
            "الحالة المتوقعة:",
            expected_status,
        )
        print(
            "الحالة الفعلية:",
            actual_status or "لا توجد",
        )
        print(
            "المدة:",
            duration,
            "ثانية",
        )

        if response_text:
            print()
            print("الجواب:")
            print(response_text)

        if sources:
            print()
            print(
                "المصادر:",
                format_sources(sources),
            )

        if missing_groups:
            print()
            print(
                "المفاهيم الناقصة:",
                missing_groups,
            )

        if (
            requires_source
            and not correct_source
        ):
            print()
            print("المصدر الصحيح غير موجود.")

        if error_text:
            print()
            print(error_text)

        print()
        print(
            "نتيجة الاختبار:",
            result_label,
        )

        results.append(
            {
                "number": index,
                "category": category,
                "endpoint": endpoint,
                "question": question,
                "expected_status": expected_status,
                "actual_status": actual_status,
                "test_passed": (
                    "نعم"
                    if test_passed
                    else "لا"
                ),
                "duration_seconds": duration,
                "response": response_text,
                "missing_groups": json.dumps(
                    missing_groups,
                    ensure_ascii=False,
                ),
                "correct_source": (
                    "نعم"
                    if correct_source
                    else "لا"
                ),
                "sources": format_sources(
                    sources
                ),
                "error": error_text,
            }
        )

    category_summary = {}

    for category, total in (
        category_totals.items()
    ):
        passed = category_passed.get(
            category,
            0,
        )
        category_summary[category] = {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        }

    report = {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "source": EXPECTED_SOURCE,
        "total_tests": len(TEST_CASES),
        "passed_tests": passed_count,
        "failed_tests": failed_count,
        "categories": category_summary,
        "results": results,
    }

    JSON_REPORT.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with CSV_REPORT.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        fieldnames = list(results[0].keys())
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(results)

    print()
    print("=" * 98)
    print("النتيجة النهائية")
    print("=" * 98)
    print("الناجحة:", passed_count)
    print("الفاشلة:", failed_count)
    print("المجموع:", len(TEST_CASES))

    print()
    print("النتائج حسب المجموعة:")

    for category, summary in (
        category_summary.items()
    ):
        print(
            f"- {category}: "
            f"{summary['passed']}/"
            f"{summary['total']}"
        )

    print()
    print("تم حفظ التقريرين:")
    print(JSON_REPORT.resolve())
    print(CSV_REPORT.resolve())


if __name__ == "__main__":
    main()