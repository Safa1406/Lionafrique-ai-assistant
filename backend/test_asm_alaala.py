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
EXPECTED_SOURCE = "asm-alaala.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-instrument-noun-baseline"

JSON_REPORT = Path("asm_alaala_test_results.json")
CSV_REPORT = Path("asm_alaala_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف',
  'endpoint': '/ask',
  'question': 'ما تعريف اسم الآلة؟',
  'expected_status': 'success',
  'required_groups': [['اسم مشتق'], ['الاداه', 'الاله'], ['ينجز بها الفعل']]},
 {'category': 'دلالة',
  'endpoint': '/ask',
  'question': 'على ماذا تدل أسماء المحراث والمعول والمشذب والقادوم؟',
  'expected_status': 'success',
  'required_groups': [['ادوات', 'وسائل'], ['ينجز بها'], ['الفلاح'], ['عمله']]},
 {'category': 'الأوزان القياسية',
  'endpoint': '/ask',
  'question': 'ما الأوزان القياسية الأربعة لاسم الآلة؟',
  'expected_status': 'success',
  'required_groups': [['مفعل'], ['مفعال'], ['مفعله'], ['فعاله']]},
 {'category': 'وزن مفعل',
  'endpoint': '/ask',
  'question': 'اذكر وزن مفعل وأمثلة عليه في اسم الآلة.',
  'expected_status': 'success',
  'required_groups': [['مفعل'], ['مقلع', 'مبرد']]},
 {'category': 'وزن مفعال',
  'endpoint': '/ask',
  'question': 'اذكر وزن مفعال وأمثلة عليه في اسم الآلة.',
  'expected_status': 'success',
  'required_groups': [['مفعال'], ['منشار', 'محراث']]},
 {'category': 'وزن مفعلة',
  'endpoint': '/ask',
  'question': 'اذكر وزن مفعلة وأمثلة عليه في اسم الآلة.',
  'expected_status': 'success',
  'required_groups': [['مفعله'], ['مجرفه', 'معزفه']]},
 {'category': 'وزن فعالة',
  'endpoint': '/ask',
  'question': 'اذكر وزن فعالة وأمثلة عليه في اسم الآلة.',
  'expected_status': 'success',
  'required_groups': [['فعاله'], ['ثلاجه', 'غساله']]},
 {'category': 'مصدر الاشتقاق',
  'endpoint': '/ask',
  'question': 'من أي نوع من الأفعال يصاغ اسم الآلة غالبا؟',
  'expected_status': 'success',
  'required_groups': [['فعل ثلاثي'], ['متصرف'], ['متعد'], ['غالبا']]},
 {'category': 'مصدر الاشتقاق',
  'endpoint': '/ask',
  'question': 'هل يصاغ اسم الآلة من الفعل الثلاثي اللازم؟',
  'expected_status': 'success',
  'required_groups': [['نعم', 'قد يصاغ'], ['ثلاثي'], ['متصرف'], ['لازم']]},
 {'category': 'مصدر الاشتقاق',
  'endpoint': '/ask',
  'question': 'هل يصاغ اسم الآلة من الفعل غير الثلاثي؟',
  'expected_status': 'success',
  'required_groups': [['نعم', 'قد يصاغ'], ['غير الثلاثي', 'رباعي']]},
 {'category': 'مصدر الاشتقاق',
  'endpoint': '/ask',
  'question': 'هل يمكن صياغة اسم الآلة من اسم جامد؟',
  'expected_status': 'success',
  'required_groups': [['نعم', 'قد يصاغ'],
                      ['اسم جامد', 'الاسم الجامد'],
                      ['مقلمه', 'محبره']]},
 {'category': 'تحليل مثال',
  'endpoint': '/ask',
  'question': 'ما وزن منظار، وما فعله، وما نوع الفعل؟',
  'expected_status': 'success',
  'required_groups': [['منظار'], ['مفعال'], ['نظر'], ['ثلاثي'], ['متصرف'], ['لازم']]},
 {'category': 'تحليل مثال',
  'endpoint': '/ask',
  'question': 'ما وزن مبرد، وما فعله، وما نوع الفعل؟',
  'expected_status': 'success',
  'required_groups': [['مبرد'], ['مفعل'], ['برد'], ['ثلاثي'], ['متصرف'], ['متعد']]},
 {'category': 'تحليل مثال',
  'endpoint': '/ask',
  'question': 'ما وزن مزمار، وما فعله، وما نوع الفعل؟',
  'expected_status': 'success',
  'required_groups': [['مزمار'], ['مفعال'], ['زمر'], ['رباعي'], ['متصرف'], ['لازم']]},
 {'category': 'تحليل مثال',
  'endpoint': '/ask',
  'question': 'ما وزن مكنسة، وما فعلها، وما نوع الفعل؟',
  'expected_status': 'success',
  'required_groups': [['مكنسه'], ['مفعله'], ['كنس'], ['رباعي'], ['متصرف'], ['متعد']]},
 {'category': 'اسم جامد',
  'endpoint': '/ask',
  'question': 'مم اشتق اسم الآلة محبرة، وما وزنه؟',
  'expected_status': 'success',
  'required_groups': [['محبره'], ['مفعله'], ['حبر'], ['اسم جامد']]},
 {'category': 'اسم جامد',
  'endpoint': '/ask',
  'question': 'مم اشتق اسم الآلة مقلمة، وما وزنه؟',
  'expected_status': 'success',
  'required_groups': [['مقلمه'], ['مفعله'], ['قلم'], ['اسم جامد']]},
 {'category': 'أوزان مضافة',
  'endpoint': '/ask',
  'question': 'ما الأوزان القياسية الأخرى التي أضافها مجمع اللغة العربية؟',
  'expected_status': 'success',
  'required_groups': [['مجمع اللغه العربيه'], ['فعاله'], ['فاعله'], ['فاعول']]},
 {'category': 'السماعي',
  'endpoint': '/ask',
  'question': 'ما المقصود بصياغة اسم الآلة سماعا؟',
  'expected_status': 'success',
  'required_groups': [['غير الاوزان', 'غير قياسيه'],
                      ['تستعمل في الكلام'],
                      ['لا يقاس عليها']]},
 {'category': 'السماعي',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة على أسماء الآلة السماعية.',
  'expected_status': 'success',
  'required_groups': [['سيف'], ['سكين'], ['رمح'], ['ازميل']]},
 {'category': 'وزن سماعي',
  'endpoint': '/ask',
  'question': 'ما وزن اسم الآلة سكين؟',
  'expected_status': 'success',
  'required_groups': [['سكين'], ['فعيل']]},
 {'category': 'وزن سماعي',
  'endpoint': '/ask',
  'question': 'ما وزن اسم الآلة رمح؟',
  'expected_status': 'success',
  'required_groups': [['رمح'], ['فعل']]},
 {'category': 'وزن سماعي',
  'endpoint': '/ask',
  'question': 'ما وزن اسم الآلة سيف؟',
  'expected_status': 'success',
  'required_groups': [['سيف'], ['فعل']]},
 {'category': 'وزن سماعي',
  'endpoint': '/ask',
  'question': 'ما وزن اسم الآلة إزميل؟',
  'expected_status': 'success',
  'required_groups': [['ازميل'], ['فعليل']]},
 {'category': 'وزن سماعي',
  'endpoint': '/ask',
  'question': 'ما وزن اسم الآلة قلم في الجدول السماعي؟',
  'expected_status': 'success',
  'required_groups': [['قلم'], ['فعل']]},
 {'category': 'صياغة مختلفة',
  'endpoint': '/ask',
  'question': 'اشرح قاعدة صياغة اسم الآلة باختصار.',
  'expected_status': 'success',
  'required_groups': [['اسم مشتق'],
                      ['مفعل'],
                      ['مفعال'],
                      ['مفعله'],
                      ['فعاله'],
                      ['ثلاثي'],
                      ['اسم جامد'],
                      ['سماعي']]},
 {'category': 'خطأ إملائي',
  'endpoint': '/ask',
  'question': 'ما تعريف اسم الاله وما اوزانه القياسيه؟',
  'expected_status': 'success',
  'required_groups': [['اسم مشتق'],
                      ['الاداه', 'الاله'],
                      ['مفعل'],
                      ['مفعال'],
                      ['مفعله'],
                      ['فعاله']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس اسم الآلة.',
  'expected_status': 'success',
  'required_groups': [['اسم مشتق'],
                      ['مفعل'],
                      ['مفعال'],
                      ['مفعله'],
                      ['فعاله'],
                      ['ثلاثي'],
                      ['سماعي']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص الصياغة القياسية والسماعية لاسم الآلة.',
  'expected_status': 'success',
  'required_groups': [['قياسي'],
                      ['مفعل'],
                      ['مفعال'],
                      ['مفعله'],
                      ['فعاله'],
                      ['سماعي'],
                      ['لا يقاس']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما عاصمة الأرجنتين؟',
  'expected_status': 'insufficient_context',
  'required_groups': []}]


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
        "الاختبار الأولي لدرس اسم الآلة"
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
