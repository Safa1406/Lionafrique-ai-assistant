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
EXPECTED_SOURCE = "aslob-alakhtsas.pdf"

NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120

JSON_REPORT = Path(
    "ikhtisas_test_results.json"
)

CSV_REPORT = Path(
    "ikhtisas_test_results.csv"
)


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
        "question": "ما تعريف أسلوب الاختصاص؟",
        "expected_status": "success",
        "required_groups": [
            ["اختصاص"],
            ["ثلاث"],
            ["ضمير"],
            ["مختص", "مخصوص"],
        ],
    },
    {
        "category": "عناصر",
        "endpoint": "/ask",
        "question": "ما عناصر أسلوب الاختصاص؟",
        "expected_status": "success",
        "required_groups": [
            ["ضمير"],
            ["فعل"],
            ["محذوف"],
            ["اسم"],
            ["مختص", "مخصوص"],
        ],
    },
    {
        "category": "الاسم المختص",
        "endpoint": "/ask",
        "question": "ما وظيفة الاسم المختص في أسلوب الاختصاص؟",
        "expected_status": "success",
        "required_groups": [
            ["تقييد", "تخصيص"],
            ["ضمير"],
            ["توضيح", "بيان"],
            ["غموض"],
        ],
    },
    {
        "category": "الضمير",
        "endpoint": "/ask",
        "question": "ما نوع الضمير المستعمل غالبا في أسلوب الاختصاص؟",
        "expected_status": "success",
        "required_groups": [
            ["متكلم"],
            ["انا"],
            ["نحن"],
        ],
    },
    {
        "category": "الضمير",
        "endpoint": "/ask",
        "question": "هل يمكن استعمال ضمير المخاطب في أسلوب الاختصاص؟",
        "expected_status": "success",
        "required_groups": [
            ["مخاطب"],
            ["انت", "انتم"],
        ],
    },
    {
        "category": "الفعل المحذوف",
        "endpoint": "/ask",
        "question": "ما تقدير الفعل المحذوف في أسلوب الاختصاص؟",
        "expected_status": "success",
        "required_groups": [
            ["اخص", "اعني", "اقصد"],
            ["محذوف"],
            ["وجوب"],
        ],
    },
    {
        "category": "أحوال الاسم المختص",
        "endpoint": "/ask",
        "question": "ما أحوال الاسم المختص وأنواعه؟",
        "expected_status": "success",
        "required_groups": [
            ["ال"],
            ["مضاف"],
            ["معرف"],
            ["اي", "ايه"],
        ],
    },
    {
        "category": "أيها وأيتها",
        "endpoint": "/ask",
        "question": "ما الشرط في الاسم الذي يأتي بعد أيها أو أيتها؟",
        "expected_status": "success",
        "required_groups": [
            ["معرف"],
            ["ال"],
            ["نعت"],
        ],
    },
    {
        "category": "الحكم الإعرابي",
        "endpoint": "/ask",
        "question": "ما الحكم الإعرابي للاسم المختص؟",
        "expected_status": "success",
        "required_groups": [
            ["منصوب", "محل نصب"],
            ["مفعول"],
            ["محذوف"],
        ],
    },
    {
        "category": "الحكم الإعرابي",
        "endpoint": "/ask",
        "question": "كيف يعرب الاسم المختص المقترن بأل؟",
        "expected_status": "success",
        "required_groups": [
            ["مفعول"],
            ["منصوب"],
            ["فتحه"],
            ["اخص", "اعني", "اقصد"],
        ],
    },
    {
        "category": "أيها وأيتها",
        "endpoint": "/ask",
        "question": "كيف تعرب أي في قولنا: أنا أيها التلميذ؟",
        "expected_status": "success",
        "required_groups": [
            ["مفعول"],
            ["مبني"],
            ["ضم"],
            ["محل نصب"],
        ],
    },
    {
        "category": "أيها وأيتها",
        "endpoint": "/ask",
        "question": "كيف يعرب التلميذ بعد أيها؟",
        "expected_status": "success",
        "required_groups": [
            ["نعت"],
            ["مرفوع"],
            ["ضمه"],
        ],
    },
    {
        "category": "مثال تطبيقي",
        "endpoint": "/ask",
        "question": "حدد عناصر الاختصاص في جملة: نحن العمال نعاني من ساعات العمل الطويلة.",
        "expected_status": "success",
        "required_groups": [
            ["نحن"],
            ["عمال"],
            ["اخص", "اعني", "اقصد"],
        ],
    },
    {
        "category": "مثال تطبيقي",
        "endpoint": "/ask",
        "question": "ما نوع الاسم المختص في جملة: نحن رجال المطافئ نقاوم الحرائق؟",
        "expected_status": "success",
        "required_groups": [
            ["رجال"],
            ["مضاف"],
            ["معرف"],
        ],
    },
    {
        "category": "مثال تطبيقي",
        "endpoint": "/ask",
        "question": "أعرب المغاربة في جملة: نحن المغاربة متسامحون.",
        "expected_status": "success",
        "required_groups": [
            ["مغاربه"],
            ["مفعول"],
            ["محذوف"],
            ["اخص"],
        ],
    },
    {
        "category": "مثال تطبيقي",
        "endpoint": "/ask",
        "question": "ما محل الجملة الفعلية المحذوفة في أسلوب الاختصاص؟",
        "expected_status": "success",
        "required_groups": [
            ["لا محل"],
            ["اعتراضي"],
        ],
    },
    {
        "category": "صياغة مختلفة",
        "endpoint": "/ask",
        "question": "اشرح قاعدة الاختصاص باختصار.",
        "expected_status": "success",
        "required_groups": [
            ["ضمير"],
            ["مختص", "مخصوص"],
            ["محذوف"],
            ["منصوب", "نصب"],
        ],
    },
    {
        "category": "خطأ إملائي",
        "endpoint": "/ask",
        "question": "ما عناصير اسلوب الاختصاس؟",
        "expected_status": "success",
        "required_groups": [
            ["ضمير"],
            ["فعل"],
            ["مختص", "مخصوص"],
        ],
    },
    {
        "category": "تلخيص",
        "endpoint": "/summarize",
        "question": "لخص درس أسلوب الاختصاص.",
        "expected_status": "success",
        "required_groups": [
            ["اختصاص"],
            ["ضمير"],
            ["مختص", "مخصوص"],
            ["محذوف"],
        ],
    },
    {
        "category": "تلخيص",
        "endpoint": "/summarize",
        "question": "لخص عناصر أسلوب الاختصاص.",
        "expected_status": "success",
        "required_groups": [
            ["ضمير"],
            ["فعل"],
            ["محذوف"],
            ["مختص", "مخصوص"],
        ],
    },
    {
        "category": "تلخيص",
        "endpoint": "/summarize",
        "question": "لخص أحوال الاسم المختص وحكمه الإعرابي.",
        "expected_status": "success",
        "required_groups": [
            ["ال"],
            ["مضاف"],
            ["اي", "ايه"],
            ["منصوب", "محل نصب"],
        ],
    },
    {
        "category": "رفض صحيح",
        "endpoint": "/ask",
        "question": "ما مساحة قارة إفريقيا؟",
        "expected_status": "insufficient_context",
        "required_groups": [],
    },
]


def configure_console() -> None:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8"
        )
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
        "number_of_results": (
            NUMBER_OF_RESULTS
        ),
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
            "Content-Type": (
                "application/json"
            ),
        },
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT_SECONDS,
    ) as response:
        return json.loads(
            response.read().decode(
                "utf-8"
            )
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
        source.get(
            "file",
            "",
        )
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
            for alternative in (
                normalized_alternatives
            )
        ):
            missing_groups.append(
                group
            )

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
        "الاختبار النهائي لدرس أسلوب الاختصاص"
    )
    print("=" * 98)
    print(
        "عدد الاختبارات:",
        len(TEST_CASES),
    )
    print(
        "المصدر المنتظر:",
        EXPECTED_SOURCE,
    )
    print(
        "فلتر المصدر:",
        "مفعل",
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
        expected_status = (
            test_case["expected_status"]
        )

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

        missing_groups = (
            find_missing_groups(
                response_text=response_text,
                required_groups=test_case[
                    "required_groups"
                ],
            )
        )

        requires_source = (
            expected_status
            == "success"
        )

        correct_source = (
            source_is_correct(
                sources
            )
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
                "duration_seconds": (
                    duration
                ),
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