import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


API_BASE_URL = "http://127.0.0.1:8000"

PROGRAM = "Programme marocain"
SUBJECT = "Arabe"
SEMESTER = None

NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120

OUTPUT_JSON = Path("arabic_full_test_results.json")
OUTPUT_CSV = Path("arabic_full_test_results.csv")


TEST_CASES = [
    # 1. أسئلة مباشرة من الدرس
    {
        "category": "أسئلة مباشرة",
        "endpoint": "/ask",
        "question": "ما تعريف أسلوب المدح؟",
        "expected_status": "success",
    },
    {
        "category": "أسئلة مباشرة",
        "endpoint": "/ask",
        "question": "ما تعريف أسلوب الذم؟",
        "expected_status": "success",
    },
    {
        "category": "أسئلة مباشرة",
        "endpoint": "/ask",
        "question": "ما هي عناصر أسلوب المدح؟",
        "expected_status": "success",
    },
    {
        "category": "أسئلة مباشرة",
        "endpoint": "/ask",
        "question": "ما هي عناصر أسلوب الذم؟",
        "expected_status": "success",
    },
    {
        "category": "أسئلة مباشرة",
        "endpoint": "/ask",
        "question": "مم يتكون أسلوب المدح والذم؟",
        "expected_status": "success",
    },

    # 2. أسئلة على القواعد
    {
        "category": "القواعد",
        "endpoint": "/ask",
        "question": "ما حالات فاعل نعم وبئس؟",
        "expected_status": "success",
    },
    {
        "category": "القواعد",
        "endpoint": "/ask",
        "question": "كيف يأتي فاعل نعم وبئس؟",
        "expected_status": "success",
    },
    {
        "category": "القواعد",
        "endpoint": "/ask",
        "question": "ما إعراب المخصوص بالمدح أو الذم؟",
        "expected_status": "success",
    },
    {
        "category": "القواعد",
        "endpoint": "/ask",
        "question": "متى تستعمل حبذا؟",
        "expected_status": "success",
    },
    {
        "category": "القواعد",
        "endpoint": "/ask",
        "question": "متى تستعمل لا حبذا؟",
        "expected_status": "success",
    },
    {
        "category": "القواعد",
        "endpoint": "/ask",
        "question": "ما إعراب ذا في حبذا؟",
        "expected_status": "success",
    },

    # 3. صياغات مختلفة
    {
        "category": "صياغات مختلفة",
        "endpoint": "/ask",
        "question": "اشرح مكونات أسلوب المدح.",
        "expected_status": "success",
    },
    {
        "category": "صياغات مختلفة",
        "endpoint": "/ask",
        "question": "اذكر العناصر التي يتألف منها أسلوب الذم.",
        "expected_status": "success",
    },
    {
        "category": "صياغات مختلفة",
        "endpoint": "/ask",
        "question": "ما وظيفة أسلوب المدح؟",
        "expected_status": "success",
    },
    {
        "category": "صياغات مختلفة",
        "endpoint": "/ask",
        "question": "لماذا يستعمل أسلوب الذم؟",
        "expected_status": "success",
    },
    {
        "category": "صياغات مختلفة",
        "endpoint": "/ask",
        "question": "ما الفرق بين أسلوب المدح وأسلوب الذم؟",
        "expected_status": "success",
    },
    {
        "category": "صياغات مختلفة",
        "endpoint": "/ask",
        "question": "قارن بين حبذا ولا حبذا.",
        "expected_status": "success",
    },

    # 4. أسئلة على الأمثلة
    {
        "category": "الأمثلة",
        "endpoint": "/ask",
        "question": (
            "في جملة نعم الابن البار، ما فعل المدح "
            "وما فاعله وما المخصوص بالمدح؟"
        ),
        "expected_status": "success",
    },
    {
        "category": "الأمثلة",
        "endpoint": "/ask",
        "question": (
            "في جملة بئس الرفيق المنافق، "
            "حدد عناصر أسلوب الذم."
        ),
        "expected_status": "success",
    },
    {
        "category": "الأمثلة",
        "endpoint": "/ask",
        "question": (
            "ما المخصوص بالمدح في جملة نعم الابن البار؟"
        ),
        "expected_status": "success",
    },
    {
        "category": "الأمثلة",
        "endpoint": "/ask",
        "question": (
            "ما المخصوص بالذم في جملة بئس الرفيق المنافق؟"
        ),
        "expected_status": "success",
    },

    # 5. أسئلة الإعراب
    {
        "category": "الإعراب",
        "endpoint": "/ask",
        "question": (
            "أعرب المخصوص بالمدح في جملة نعم الابن البار."
        ),
        "expected_status": "success",
    },
    {
        "category": "الإعراب",
        "endpoint": "/ask",
        "question": (
            "أعرب المخصوص بالذم في جملة بئس الرفيق المنافق."
        ),
        "expected_status": "success",
    },
    {
        "category": "الإعراب",
        "endpoint": "/ask",
        "question": (
            "ما إعراب الفاعل في أسلوب المدح والذم؟"
        ),
        "expected_status": "success",
    },
    {
        "category": "الإعراب",
        "endpoint": "/ask",
        "question": "كيف تعرب جملة حبذا النضال؟",
        "expected_status": "success",
    },

    # 6. اختبار التلخيص
    {
        "category": "التلخيص",
        "endpoint": "/summarize",
        "question": "لخص درس أسلوب المدح والذم.",
        "expected_status": "success",
    },
    {
        "category": "التلخيص",
        "endpoint": "/summarize",
        "question": (
            "قدم ملخصا عن عناصر المدح والذم وإعرابهما."
        ),
        "expected_status": "success",
    },
    {
        "category": "التلخيص",
        "endpoint": "/summarize",
        "question": "لخص حالات فاعل نعم وبئس.",
        "expected_status": "success",
    },
    {
        "category": "التلخيص",
        "endpoint": "/summarize",
        "question": "لخص استعمال حبذا ولا حبذا.",
        "expected_status": "success",
    },

    # 7. كتابة بدون همزات أو تشكيل
    {
        "category": "بدون همزات",
        "endpoint": "/ask",
        "question": "ما عناصر اسلوب المدح؟",
        "expected_status": "success",
    },
    {
        "category": "بدون همزات",
        "endpoint": "/ask",
        "question": "ما اعراب المخصوص بالذم؟",
        "expected_status": "success",
    },
    {
        "category": "بدون همزات",
        "endpoint": "/ask",
        "question": "مم يتكون اسلوب الذم؟",
        "expected_status": "success",
    },

    # 8. أخطاء إملائية بسيطة
    {
        "category": "أخطاء إملائية",
        "endpoint": "/ask",
        "question": "ما هي عناصر اسلوب المذح؟",
        "expected_status": "success",
    },
    {
        "category": "أخطاء إملائية",
        "endpoint": "/ask",
        "question": "ما هو اعراب المخصوص بالمدح والدم؟",
        "expected_status": "success",
    },
    {
        "category": "أخطاء إملائية",
        "endpoint": "/ask",
        "question": "ما الفرق بين المدح والدم؟",
        "expected_status": "success",
    },

    # 9. أسئلة خارج الوثائق
    {
        "category": "رفض صحيح",
        "endpoint": "/ask",
        "question": "ما هي عاصمة اليابان؟",
        "expected_status": "insufficient_context",
    },
    {
        "category": "رفض صحيح",
        "endpoint": "/ask",
        "question": "اشرح قانون فيثاغورس.",
        "expected_status": "insufficient_context",
    },
    {
        "category": "رفض صحيح",
        "endpoint": "/ask",
        "question": "ما أسباب الحرب العالمية الثانية؟",
        "expected_status": "insufficient_context",
    },
]


def configure_console() -> None:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8"
        )
    except AttributeError:
        pass


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
    }

    request = urllib.request.Request(
        f"{API_BASE_URL}{endpoint}",
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


def format_sources(
    sources: list[dict],
) -> str:
    formatted_sources = []

    for source in sources:
        formatted_sources.append(
            (
                f"{source.get('file', 'مصدر غير معروف')}"
                f" | الصفحة {source.get('page', '?')}"
            )
        )

    return " ; ".join(
        formatted_sources
    )


def save_json_report(
    report: dict,
) -> None:
    OUTPUT_JSON.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_csv_report(
    results: list[dict],
) -> None:
    fieldnames = [
        "number",
        "category",
        "endpoint",
        "question",
        "expected_status",
        "actual_status",
        "test_passed",
        "response",
        "evidence_count",
        "sources",
        "duration_seconds",
        "error",
    ]

    with OUTPUT_CSV.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(results)


def main() -> None:
    configure_console()

    print("=" * 96)
    print("الاختبار الشامل لمادة العربية")
    print("=" * 96)
    print("عدد الأسئلة:", len(TEST_CASES))
    print("البرنامج:", PROGRAM)
    print("المادة:", SUBJECT)
    print()

    results = []

    passed_count = 0
    failed_count = 0
    connection_error_count = 0

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

        print("-" * 96)
        print(
            f"[{index}/{len(TEST_CASES)}]"
            f" [{category}]"
        )
        print("السؤال:", question)
        print("المسار:", endpoint)

        started_at = time.perf_counter()

        actual_status = ""
        response_text = ""
        evidence_count = 0
        sources_text = ""
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

            evidence = (
                response_data.get("evidence")
                or []
            )

            sources = (
                response_data.get("sources")
                or []
            )

            evidence_count = len(evidence)
            sources_text = format_sources(
                sources
            )

        except urllib.error.URLError as error:
            error_text = (
                "تعذر الاتصال بـFastAPI: "
                f"{error}"
            )

            connection_error_count += 1

        except Exception as error:
            error_text = (
                "خطأ غير متوقع: "
                f"{error}"
            )

        duration_seconds = round(
            time.perf_counter()
            - started_at,
            3,
        )

        test_passed = (
            not error_text
            and actual_status
            == expected_status
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

            result_label = "ناجح"

        else:
            failed_count += 1
            result_label = "فاشل"

        print("الحالة المتوقعة:", expected_status)
        print(
            "الحالة الفعلية:",
            actual_status or "لا توجد",
        )
        print("نتيجة الاختبار:", result_label)
        print(
            "المدة:",
            duration_seconds,
            "ثانية",
        )

        if response_text:
            print()
            print("الجواب:")
            print(response_text)

        if sources_text:
            print()
            print("المصادر:", sources_text)

        if error_text:
            print()
            print(error_text)

        print()

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
                "response": response_text,
                "evidence_count": (
                    evidence_count
                ),
                "sources": sources_text,
                "duration_seconds": (
                    duration_seconds
                ),
                "error": error_text,
            }
        )

    category_summary = {}

    for category, total in category_totals.items():
        category_summary[category] = {
            "total": total,
            "passed": category_passed.get(
                category,
                0,
            ),
            "failed": (
                total
                - category_passed.get(
                    category,
                    0,
                )
            ),
        }

    report = {
        "generated_at": (
            datetime.now().isoformat(
                timespec="seconds"
            )
        ),
        "api_base_url": API_BASE_URL,
        "program": PROGRAM,
        "subject": SUBJECT,
        "semester": SEMESTER,
        "total_tests": len(TEST_CASES),
        "passed_tests": passed_count,
        "failed_tests": failed_count,
        "connection_errors": (
            connection_error_count
        ),
        "categories": category_summary,
        "results": results,
    }

    save_json_report(report)
    save_csv_report(results)

    print("=" * 96)
    print("النتيجة النهائية")
    print("=" * 96)
    print("مجموع الاختبارات:", len(TEST_CASES))
    print("الاختبارات الناجحة:", passed_count)
    print("الاختبارات الفاشلة:", failed_count)
    print(
        "أخطاء الاتصال:",
        connection_error_count,
    )
    print()

    print("النتائج حسب المجموعة:")

    for category, summary in (
        category_summary.items()
    ):
        print(
            f"- {category}: "
            f"{summary['passed']}/"
            f"{summary['total']} ناجحة"
        )

    print()
    print(
        "تم حفظ التقرير المفصل في:"
    )
    print(
        "-",
        OUTPUT_JSON.resolve(),
    )
    print(
        "-",
        OUTPUT_CSV.resolve(),
    )


if __name__ == "__main__":
    main()
