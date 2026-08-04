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
EXPECTED_SOURCE = "alidhafa.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-idafa-baseline"

JSON_REPORT = Path("alidhafa_test_results.json")
CSV_REPORT = Path("alidhafa_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الإضافة',
  'endpoint': '/ask',
  'question': 'ما تعريف الإضافة حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['نسبه بين اسمين'], ['الاول مضاف'], ['الثاني مضاف اليه']]},
 {'category': 'حكم المضاف إليه',
  'endpoint': '/ask',
  'question': 'ما الحكم الإعرابي للمضاف إليه؟',
  'expected_status': 'success',
  'required_groups': [['مجرور'], ['بالاضافه'], ['دائما']]},
 {'category': 'نوعا الإضافة',
  'endpoint': '/ask',
  'question': 'ما نوعا الإضافة؟',
  'expected_status': 'success',
  'required_groups': [['اضافه معنويه'], ['اضافه لفظيه']]},
 {'category': 'الإضافة المعنوية',
  'endpoint': '/ask',
  'question': 'ماذا تفيد الإضافة المعنوية للمضاف؟',
  'expected_status': 'success',
  'required_groups': [['التعريف'], ['التخصيص'], ['التخفيف'], ['حذف التنوين'], ['النون']]},
 {'category': 'أمثلة المعنوية',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة الإضافة المعنوية الواردة في الجدول.',
  'expected_status': 'success',
  'required_groups': [['مدرسه الحياه'], ['فلاحا القريه'], ['فلاحو القريه'], ['كل عام']]},
 {'category': 'الإضافة اللفظية',
  'endpoint': '/ask',
  'question': 'ماذا تفيد الإضافة اللفظية للمضاف؟',
  'expected_status': 'success',
  'required_groups': [['التخفيف'], ['حذف التنوين'], ['النون']]},
 {'category': 'أمثلة اللفظية',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة الإضافة اللفظية الواردة في الوثيقة.',
  'expected_status': 'success',
  'required_groups': [['صانعه الاجيال'], ['غفار الذنوب'], ['محمودو الخصال'], ['سمح الطبع']]},
 {'category': 'الحذف عند الإضافة',
  'endpoint': '/ask',
  'question': 'ماذا يحذف من الاسم عند إضافته إذا كان مفردا أو مثنى أو جمع مذكر سالما؟',
  'expected_status': 'success',
  'required_groups': [['يحذف التنوين'], ['المفرد'], ['النون'], ['المثني'], ['جمع مذكر سالم']]},
 {'category': 'أل والإضافة اللفظية',
  'endpoint': '/ask',
  'question': 'متى تدخل أل على المضاف في الإضافة اللفظية؟',
  'expected_status': 'success',
  'required_groups': [['مثني'],
                      ['جمع مذكر سالما'],
                      ['مفردا مضافا لما فيه ال'],
                      ['اسم مضاف لمعرف بال']]},
 {'category': 'أمثلة أل',
  'endpoint': '/ask',
  'question': 'ما أمثلة اقتران أل بالمضاف في الإضافة اللفظية؟',
  'expected_status': 'success',
  'required_groups': [['الخادما وطنهما'],
                      ['المحسنو عملهم'],
                      ['العزيز النفس'],
                      ['المحب فعل الخير']]},
 {'category': 'الظروف الملازمة',
  'endpoint': '/ask',
  'question': 'ما الظروف الملازمة للإضافة إلى الجمل حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['اذ'], ['اذا'], ['حيث'], ['لما'], ['منذ']]},
 {'category': 'حكم الجملة المضافة',
  'endpoint': '/ask',
  'question': 'ما الحكم الإعرابي للجملة الواقعة بعد الظروف الملازمة للإضافة؟',
  'expected_status': 'success',
  'required_groups': [['مبنيه'], ['في محل جر'], ['مضاف اليه']]},
 {'category': 'حين ويوم ووقت',
  'endpoint': '/ask',
  'question': 'إلى ماذا تضاف حين ويوم ووقت؟',
  'expected_status': 'success',
  'required_groups': [['تضاف الي الجمل'], ['الاسم المفرد'], ['علي حد سواء']]},
 {'category': 'أمثلة الجمل',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة الإضافة إلى الجمل الواردة في الجدول.',
  'expected_status': 'success',
  'required_groups': [['اذ طلع الفجر'],
                      ['اذا اجتهد العامل'],
                      ['حيث يجلس اخي'],
                      ['لما كان عائدا'],
                      ['منذ سافر اخوك'],
                      ['حين نجحت']]},
 {'category': 'ياء المتكلم المجموعة الأولى',
  'endpoint': '/ask',
  'question': 'ما أنواع الأسماء التي تكسر أواخرها عند إضافتها إلى ياء المتكلم؟',
  'expected_status': 'success',
  'required_groups': [['المفرد الصحيح'],
                      ['الشبيه بالصحيح'],
                      ['معتل الاخر'],
                      ['جمع التكسير'],
                      ['جمع المونث السالم']]},
 {'category': 'حكم الياء المجموعة الأولى',
  'endpoint': '/ask',
  'question': 'ما حكم ياء المتكلم مع المفرد الصحيح وشبهه وجمع التكسير وجمع المؤنث السالم؟',
  'expected_status': 'success',
  'required_groups': [['يجوز'], ['البناء علي السكون'], ['الفتح'], ['في محل جر مضاف اليه']]},
 {'category': 'ياء المتكلم المجموعة الثانية',
  'endpoint': '/ask',
  'question': 'ما أنواع الأسماء التي يجب بناؤها على السكون عند إضافتها إلى ياء المتكلم؟',
  'expected_status': 'success',
  'required_groups': [['المثني'],
                      ['الاسم المقصور'],
                      ['الاسم المنقوص'],
                      ['جمع المذكر السالم'],
                      ['السكون']]},
 {'category': 'حكم الياء المجموعة الثانية',
  'endpoint': '/ask',
  'question': 'ما حكم ياء المتكلم مع المثنى والمقصور والمنقوص وجمع المذكر السالم؟',
  'expected_status': 'success',
  'required_groups': [['يجب'], ['البناء علي الفتح'], ['في محل جر مضاف اليه']]},
 {'category': 'أمثلة المجموعة الأولى',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة الإضافة إلى ياء المتكلم للمفرد الصحيح وشبهه وجمع التكسير وجمع المؤنث '
              'السالم.',
  'expected_status': 'success',
  'required_groups': [['وطني'], ['صفوي'], ['اقلامي'], ['تلميذاتي']]},
 {'category': 'أمثلة المجموعة الثانية',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة الإضافة إلى ياء المتكلم للمثنى والمقصور والمنقوص وجمع المذكر السالم.',
  'expected_status': 'success',
  'required_groups': [['يداي'], ['هداي'], ['هادي'], ['معاوني']]},
 {'category': 'التعريف والتخصيص',
  'endpoint': '/ask',
  'question': 'متى تفيد الإضافة التعريف، ومتى تفيد التخصيص؟',
  'expected_status': 'success',
  'required_groups': [['اذا كان الثاني معرفه'], ['التعريف'], ['اذا كان نكره'], ['التخصيص']]},
 {'category': 'كتاب سعيد وقلم حبر',
  'endpoint': '/ask',
  'question': 'كيف تفسر الوثيقة مثالي كتاب سعيد وقلم حبر؟',
  'expected_status': 'success',
  'required_groups': [['كتاب'], ['تعرفت'], ['سعيد'], ['قلم'], ['تخصصت'], ['حبر']]},
 {'category': 'إعراب حين',
  'endpoint': '/ask',
  'question': 'ما إعراب حين في جملة أحترمك حين تحترمني؟',
  'expected_status': 'success',
  'required_groups': [['مفعول فيه'],
                      ['منصوب'],
                      ['الظرفيه الزمانيه'],
                      ['الفتحه'],
                      ['وهو مضاف']]},
 {'category': 'جملة تحترمني',
  'endpoint': '/ask',
  'question': 'ما محل جملة تحترمني في أحترمك حين تحترمني؟',
  'expected_status': 'success',
  'required_groups': [['جمله فعليه'], ['في محل جر'], ['مضاف اليه']]},
 {'category': 'إعراب إذ',
  'endpoint': '/ask',
  'question': 'ما إعراب إذ في جملة يؤلمني حالك إذ تمرض؟',
  'expected_status': 'success',
  'required_groups': [['ظرف زمان'],
                      ['مبني علي السكون'],
                      ['في محل نصب'],
                      ['مفعول فيه'],
                      ['وهو مضاف']]},
 {'category': 'إعراب يوم',
  'endpoint': '/ask',
  'question': 'ما إعراب يوم في جملة أكون في انتظارك يوم تعود؟',
  'expected_status': 'success',
  'required_groups': [['مفعول فيه'],
                      ['منصوب'],
                      ['الظرفيه الزمانيه'],
                      ['الفتحه'],
                      ['وهو مضاف']]},
 {'category': 'إعراب إذا',
  'endpoint': '/ask',
  'question': 'ما إعراب إذا في جملة والدي إذا يغضب يشدد في العقوبة؟',
  'expected_status': 'success',
  'required_groups': [['ظرف زمان'],
                      ['متضمن معني الشرط'],
                      ['مبني علي السكون'],
                      ['في محل نصب'],
                      ['مفعول فيه'],
                      ['وهو مضاف']]},
 {'category': 'إعراب مذ',
  'endpoint': '/ask',
  'question': 'ما إعراب مذ وجملة طلعت الشمس في سافر أخي مذ طلعت الشمس؟',
  'expected_status': 'success',
  'required_groups': [['مذ ظرف زمان'],
                      ['مبني علي السكون'],
                      ['في محل نصب'],
                      ['مفعول فيه'],
                      ['طلعت الشمس'],
                      ['في محل جر'],
                      ['مضاف اليه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس الإضافة مع أنواعها وأحكامها وأهم الأمثلة.',
  'expected_status': 'success',
  'required_groups': [['الاضافه'],
                      ['المضاف'],
                      ['المضاف اليه'],
                      ['مجرور'],
                      ['معنويه'],
                      ['لفظيه'],
                      ['التعريف'],
                      ['التخصيص'],
                      ['حذف التنوين'],
                      ['النون'],
                      ['ال'],
                      ['الظروف'],
                      ['الجمل'],
                      ['ياء المتكلم'],
                      ['مدرسه الحياه'],
                      ['غفار الذنوب'],
                      ['اذ'],
                      ['حيث'],
                      ['وطني'],
                      ['يداي']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما عاصمة اليابان؟',
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
        "الاختبار الأولي لدرس الإضافة"
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
        "فلتر المصدر: alidhafa.pdf"
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
