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
EXPECTED_SOURCE = "aslob-altajb.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v4-fair-gendered-arabic-validation"

JSON_REPORT = Path("altajb_test_results.json")
CSV_REPORT = Path("altajb_test_results.csv")

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
        "question": "ما تعريف أسلوب التعجب؟",
        "expected_status": "success",
        "required_groups": [
            ["شعور"],
            ["داخلي"],
            ["تنفعل", "انفعال"],
            ["سلبا", "ايجابا"],
        ],
    },
    {
        "category": "الصيغ القياسية",
        "endpoint": "/ask",
        "question": "ما صيغتا التعجب القياسيتان؟",
        "expected_status": "success",
        "required_groups": [
            ["ما افعل"],
            ["افعل ب"],
        ],
    },
    {
        "category": "الصيغة الأولى",
        "endpoint": "/ask",
        "question": "على أي وزن جاءت جملة: ما أجمل الربيع؟",
        "expected_status": "success",
        "required_groups": [
            ["ما افعل"],
            ["اجمل"],
        ],
    },
    {
        "category": "الصيغة الثانية",
        "endpoint": "/ask",
        "question": "على أي وزن جاءت جملة: أعظم بأيام الشباب؟",
        "expected_status": "success",
        "required_groups": [
            ["افعل ب"],
            ["اعظم"],
        ],
    },
    {
        "category": "شروط مباشرة",
        "endpoint": "/ask",
        "question": "ما الشروط الأساسية لصياغة التعجب مباشرة من الفعل؟",
        "expected_status": "success",
        "required_groups": [
            ["ثلاثي"],
            ["متصرف"],
            ["تام"],
            ["مثبت"],
            ["مبني"],
            ["للمعلوم"],
            [
                "قابل للتفاضل",
                "قابلا للتفاضل",
                "قابل للتفاوت",
            ],
        ],
    },
    {
        "category": "شروط مباشرة",
        "endpoint": "/ask",
        "question": "ما الشرط المتعلق باللون والعيب والحلية في فعل التعجب؟",
        "expected_status": "success",
        "required_groups": [
            ["لون"],
            ["عيب"],
            ["حليه"],
            ["افعل"],
            ["فعلاء"],
        ],
    },
    {
        "category": "شروط مباشرة",
        "endpoint": "/ask",
        "question": "لماذا لا يصاغ التعجب مباشرة من الفعل دحرج؟",
        "expected_status": "success",
        "required_groups": [
            ["غير ثلاثي", "زائد"],
            ["مصدر"],
            ["مساعد"],
        ],
    },
    {
        "category": "شروط مباشرة",
        "endpoint": "/ask",
        "question": "لماذا لا يصاغ التعجب مباشرة من نعم وبئس؟",
        "expected_status": "success",
        "required_groups": [
            ["جامد", "غير متصرف"],
        ],
    },
    {
        "category": "شروط مباشرة",
        "endpoint": "/ask",
        "question": "لماذا لا يصاغ التعجب مباشرة من فني ومات؟",
        "expected_status": "success",
        "required_groups": [
            [
                "قابل للتفاضل",
                "قابلا للتفاضل",
                "غير قابل",
            ],
        ],
    },
    {
        "category": "شروط مباشرة",
        "endpoint": "/ask",
        "question": "لماذا لا يصاغ التعجب مباشرة من كان وظل وبات وصار؟",
        "expected_status": "success",
        "required_groups": [
            ["ناقص"],
        ],
    },
    {
        "category": "صياغة غير مباشرة",
        "endpoint": "/ask",
        "question": "كيف نصوغ التعجب من فعل لا يستوفي شروط الصياغة المباشرة؟",
        "expected_status": "success",
        "required_groups": [
            ["مساعد"],
            ["ما افعل", "افعل ب"],
            [
                "مصدر صريح",
                "المصدر الصريح",
            ],
            [
                "مصدر مول",
                "مصدر موول",
                "المصدر المول",
                "المصدر الموول",
                "المول",
                "الموول",
            ],
        ],
    },
    {
        "category": "صياغة غير مباشرة",
        "endpoint": "/ask",
        "question": "كيف صيغ التعجب من الفعل استفاد في المثال الوارد بالدرس؟",
        "expected_status": "success",
        "required_groups": [
            ["اعظم"],
            ["استفاده"],
            ["غير ثلاثي"],
        ],
    },
    {
        "category": "صياغة غير مباشرة",
        "endpoint": "/ask",
        "question": "كيف صيغ التعجب من الفعل المنفي لا نفرط؟",
        "expected_status": "success",
        "required_groups": [
            ["ما احسن"],
            ["الا نفرط", "ان لا نفرط"],
            [
                "مصدر مول",
                "مصدر موول",
                "المصدر المول",
                "المصدر الموول",
                "المول",
                "الموول",
            ],
        ],
    },
    {
        "category": "صياغة غير مباشرة",
        "endpoint": "/ask",
        "question": "كيف نتعجب من الفعل المبني للمجهول بطريقة غير مباشرة؟",
        "expected_status": "success",
        "required_groups": [
            ["مساعد", "اشد", "اعظم"],
            ["مصدر"],
            ["مبني للمجهول"],
        ],
    },
    {
        "category": "حدود التعجب",
        "endpoint": "/ask",
        "question": "هل يجوز التعجب من الفعل الجامد أو غير القابل للتفاضل؟",
        "expected_status": "success",
        "required_groups": [
            ["لا"],
            ["جامد"],
            ["غير قابل"],
            ["تفاضل"],
        ],
    },
    {
        "category": "التعجب السماعي",
        "endpoint": "/ask",
        "question": "ما المقصود بالتعجب السماعي؟",
        "expected_status": "success",
        "required_groups": [
            ["غير قياسي", "سماعي"],
            ["سياق"],
            ["يفهم"],
        ],
    },
    {
        "category": "التعجب السماعي",
        "endpoint": "/ask",
        "question": "كيف قد يأتي التعجب السماعي في صورة النداء؟",
        "expected_status": "success",
        "required_groups": [
            ["نداء"],
            ["يعرب"],
            ["منادى"],
        ],
    },
    {
        "category": "تمييز الصيغة",
        "endpoint": "/ask",
        "question": "حدد صيغة التعجب في جملة: ما أجمل شواطئ المغرب.",
        "expected_status": "success",
        "required_groups": [
            ["ما افعل"],
            ["ما اجمل"],
        ],
    },
    {
        "category": "إعراب",
        "endpoint": "/ask",
        "question": "أعرب ما في جملة: ما أجمل شواطئ المغرب.",
        "expected_status": "success",
        "required_groups": [
            ["اسم نكره تامه", "نكره تامه"],
            ["مبني"],
            ["سكون"],
            ["محل رفع"],
            ["مبتدا"],
        ],
    },
    {
        "category": "إعراب",
        "endpoint": "/ask",
        "question": "أعرب أجمل في جملة: ما أجمل شواطئ المغرب.",
        "expected_status": "success",
        "required_groups": [
            ["فعل ماض"],
            ["فتح"],
            ["فعل التعجب"],
            ["فاعل"],
            ["مستتر"],
        ],
    },
    {
        "category": "إعراب",
        "endpoint": "/ask",
        "question": "أعرب شواطئ المغرب في جملة: ما أجمل شواطئ المغرب.",
        "expected_status": "success",
        "required_groups": [
            ["شواطي"],
            ["مفعول به"],
            ["منصوب"],
            ["المغرب"],
            ["مضاف اليه"],
            ["مجرور"],
        ],
    },
    {
        "category": "إعراب",
        "endpoint": "/ask",
        "question": "أعرب أعظم في جملة: أعظم بأرضك الخصبة.",
        "expected_status": "success",
        "required_groups": [
            ["فعل ماض"],
            ["صوره الامر", "صيغه الامر"],
            ["فتح مقدر"],
            ["فعل التعجب"],
        ],
    },
    {
        "category": "إعراب",
        "endpoint": "/ask",
        "question": "أعرب الباء وأرضك في جملة: أعظم بأرضك الخصبة.",
        "expected_status": "success",
        "required_groups": [
            ["حرف جر زائد"],
            ["ارضك"],
            ["فاعل"],
            [
                "مجرور لفظا",
                "مجرور بالباء لفظا",
            ],
            ["مرفوع محلا"],
        ],
    },
    {
        "category": "إعراب",
        "endpoint": "/ask",
        "question": "أعرب تعلق المغاربة في جملة: ما أشد تعلق المغاربة بأرضهم.",
        "expected_status": "success",
        "required_groups": [
            ["تعلق"],
            ["مفعول به"],
            ["منصوب"],
            ["المغاربه"],
            ["مضاف اليه"],
            ["مجرور"],
        ],
    },
    {
        "category": "صياغة مختلفة",
        "endpoint": "/ask",
        "question": "اشرح قاعدة التعجب باختصار.",
        "expected_status": "success",
        "required_groups": [
            ["ما افعل"],
            ["افعل ب"],
            ["شروط"],
            ["مباشر", "غير مباشر"],
        ],
    },
    {
        "category": "خطأ إملائي",
        "endpoint": "/ask",
        "question": "ما سيغ التعجب القياسيه وشروت صياغتها؟",
        "expected_status": "success",
        "required_groups": [
            ["ما افعل"],
            ["افعل ب"],
            ["ثلاثي"],
            ["متصرف"],
        ],
    },
    {
        "category": "تلخيص",
        "endpoint": "/summarize",
        "question": "لخص درس أسلوب التعجب.",
        "expected_status": "success",
        "required_groups": [
            ["تعجب"],
            ["ما افعل"],
            ["افعل ب"],
            ["شروط"],
        ],
    },
    {
        "category": "تلخيص",
        "endpoint": "/summarize",
        "question": "لخص الصياغة المباشرة وغير المباشرة للتعجب.",
        "expected_status": "success",
        "required_groups": [
            [
                "مباشر",
                "المباشره",
            ],
            [
                "غير مباشر",
                "غير المباشره",
            ],
            ["مصدر"],
            ["ما افعل", "افعل ب"],
        ],
    },
    {
        "category": "تلخيص",
        "endpoint": "/summarize",
        "question": "لخص إعراب صيغتي ما أفعل وأفعل به.",
        "expected_status": "success",
        "required_groups": [
            ["مبتدا"],
            ["فعل ماض"],
            ["مفعول به"],
            ["حرف جر زائد"],
            ["فاعل"],
        ],
    },
    {
        "category": "رفض صحيح",
        "endpoint": "/ask",
        "question": "ما عاصمة كندا؟",
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
        if not unicodedata.combining(character)
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
    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


def make_request(
    endpoint: str,
    question: str,
) -> dict:
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
        headers={
            "Content-Type": "application/json"
        },
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
        return response_data.get(
            "summary",
            "",
        )
    return response_data.get(
        "answer",
        "",
    )


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
    normalized_response = normalize_text(
        response_text
    )
    missing_groups = []

    for group in required_groups:
        normalized_alternatives = [
            normalize_text(term)
            for term in group
        ]

        if not any(
            alternative
            and alternative
            in normalized_response
            for alternative
            in normalized_alternatives
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
    print(
        "الاختبار النهائي لدرس أسلوب التعجب"
    )
    print("=" * 98)
    print(
        "نسخة الاختبار:",
        TEST_VERSION,
    )
    print(
        "عدد الاختبارات:",
        len(TEST_CASES),
    )
    print(
        "المصدر المنتظر:",
        EXPECTED_SOURCE,
    )
    print(
        "فلتر المصدر: مفعل"
    )

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
            category_totals.get(
                category,
                0,
            )
            + 1
        )

        print()
        print("-" * 98)
        print(
            f"[{index}/{len(TEST_CASES)}] "
            f"[{category}]"
        )
        print(
            "السؤال:",
            question,
        )

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
            response_text = (
                extract_response_text(
                    endpoint=endpoint,
                    response_data=response_data,
                )
            )
            sources = (
                response_data.get(
                    "sources"
                )
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
            actual_status
            or "لا توجد",
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
                format_sources(
                    sources
                ),
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
            print(
                "المصدر الصحيح غير موجود."
            )

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
                "expected_status": (
                    expected_status
                ),
                "actual_status": (
                    actual_status
                ),
                "test_passed": (
                    "نعم"
                    if test_passed
                    else "لا"
                ),
                "duration_seconds": duration,
                "response": response_text,
                "missing_groups": (
                    json.dumps(
                        missing_groups,
                        ensure_ascii=False,
                    )
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
        "generated_at": (
            datetime.now().isoformat(
                timespec="seconds"
            )
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
        fieldnames = list(
            results[0].keys()
        )
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
    print(
        "الناجحة:",
        passed_count,
    )
    print(
        "الفاشلة:",
        failed_count,
    )
    print(
        "المجموع:",
        len(TEST_CASES),
    )

    print()
    print(
        "النتائج حسب المجموعة:"
    )

    for category, summary in (
        category_summary.items()
    ):
        print(
            f"- {category}: "
            f"{summary['passed']}/"
            f"{summary['total']}"
        )

    print()
    print(
        "تم حفظ التقريرين:"
    )
    print(
        JSON_REPORT.resolve()
    )
    print(
        CSV_REPORT.resolve()
    )


if __name__ == "__main__":
    main()
