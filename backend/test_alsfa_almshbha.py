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
EXPECTED_SOURCE = "alsfa-almshbha.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-sifa-mushabbaha-baseline"

JSON_REPORT = Path("alsfa_almshbha_test_results.json")
CSV_REPORT = Path("alsfa_almshbha_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الصفة المشبهة',
  'endpoint': '/ask',
  'question': 'ما تعريف الصفة المشبهة حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['صفه'],
                      ['معني ثابت'],
                      ['الموصوف'],
                      ['ثبوتا عاما'],
                      ['ملازما له'],
                      ['غير مرتبط بزمان معين']]},
 {'category': 'دلالة الثبوت',
  'endpoint': '/ask',
  'question': 'على ماذا تدل الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['معني ثابت'], ['الموصوف'], ['ملازما']]},
 {'category': 'علاقتها بالزمان',
  'endpoint': '/ask',
  'question': 'هل ترتبط الصفة المشبهة بزمان معين؟',
  'expected_status': 'success',
  'required_groups': [['غير مرتبط'], ['زمان معين']]},
 {'category': 'مصدر صياغتها',
  'endpoint': '/ask',
  'question': 'مم تصاغ الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['مصدر الفعل الثلاثي'], ['المتصرف'], ['اللازم']]},
 {'category': 'وزن أفعل',
  'endpoint': '/ask',
  'question': 'متى تصاغ الصفة المشبهة على وزن أفعل، وما مؤنثه؟',
  'expected_status': 'success',
  'required_groups': [['وزن افعل'], ['مونثه فعلاء'], ['لون'], ['عيب'], ['حليه']]},
 {'category': 'دلالة أفعل',
  'endpoint': '/ask',
  'question': 'ما الدلالات التي يعبر عنها وزن أفعل في الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['لون'], ['عيب'], ['حليه']]},
 {'category': 'مؤنث أفعل',
  'endpoint': '/ask',
  'question': 'ما مؤنث وزن أفعل في الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['فعلاء']]},
 {'category': 'وزن فعل',
  'endpoint': '/ask',
  'question': 'متى تصاغ الصفة المشبهة على وزن فعل، وما مؤنثه؟',
  'expected_status': 'success',
  'required_groups': [['وزن فعل'], ['مونثه فعله'], ['فرح'], ['حزن']]},
 {'category': 'مؤنث فعل',
  'endpoint': '/ask',
  'question': 'ما مؤنث وزن فعل في الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['فعله']]},
 {'category': 'وزن فعلان',
  'endpoint': '/ask',
  'question': 'متى تصاغ الصفة المشبهة على وزن فعلان، وما مؤنثه؟',
  'expected_status': 'success',
  'required_groups': [['وزن فعلان'], ['مونثه فعلي'], ['خلو'], ['امتلاء']]},
 {'category': 'دلالة فعلان',
  'endpoint': '/ask',
  'question': 'ما الدلالات التي يعبر عنها وزن فعلان في الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['خلو'], ['امتلاء']]},
 {'category': 'مؤنث فعلان',
  'endpoint': '/ask',
  'question': 'ما مؤنث وزن فعلان في الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['فعلي']]},
 {'category': 'الأوزان الثلاثة',
  'endpoint': '/ask',
  'question': 'ما الأوزان الثلاثة الأساسية لصياغة الصفة المشبهة الواردة في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['افعل'], ['فعل'], ['فعلان']]},
 {'category': 'أوزان أخرى',
  'endpoint': '/ask',
  'question': 'هل تأتي الصفة المشبهة على أوزان أخرى غير الأوزان الثلاثة الأساسية؟',
  'expected_status': 'success',
  'required_groups': [['اوزان اخري'], ['سماعيه']]},
 {'category': 'الأوزان الكثيرة',
  'endpoint': '/ask',
  'question': 'ما بعض الأوزان الأخرى المذكورة لصياغة الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['فعيل'], ['فعال'], ['فعل']]},
 {'category': 'عمل الصفة المشبهة',
  'endpoint': '/ask',
  'question': 'ماذا تعمل الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['عمل اسم الفاعل'], ['المتعدي لواحد']]},
 {'category': 'رفع ما بعدها',
  'endpoint': '/ask',
  'question': 'متى ترفع الصفة المشبهة الاسم الذي يأتي بعدها؟',
  'expected_status': 'success',
  'required_groups': [['ترفع الاسم'], ['فاعل']]},
 {'category': 'نصب المعرفة',
  'endpoint': '/ask',
  'question': 'كيف تعرب الصفة المشبهة الاسم المعرفة الذي يأتي بعدها؟',
  'expected_status': 'success',
  'required_groups': [['تنصبه'], ['مفعول به'], ['معرفه']]},
 {'category': 'نصب النكرة',
  'endpoint': '/ask',
  'question': 'كيف تعرب الصفة المشبهة الاسم النكرة الذي يأتي بعدها؟',
  'expected_status': 'success',
  'required_groups': [['تنصبه'], ['تمييز'], ['شبيه بالمفعول به'], ['نكره']]},
 {'category': 'الجر بالإضافة',
  'endpoint': '/ask',
  'question': 'كيف يمكن للصفة المشبهة أن تجر الاسم الذي يأتي بعدها؟',
  'expected_status': 'success',
  'required_groups': [['تجره'], ['الاضافه']]},
 {'category': 'صور عملها',
  'endpoint': '/ask',
  'question': 'ما صور إعراب الاسم الواقع بعد الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['فاعل'], ['مفعول به'], ['تمييز'], ['شبيه بالمفعول به'], ['الاضافه']]},
 {'category': 'شرط الاعتماد',
  'endpoint': '/ask',
  'question': 'ما الشرط الأساسي لعمل الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['لا بد'], ['تعتمد']]},
 {'category': 'الاعتماد على المبتدأ',
  'endpoint': '/ask',
  'question': 'هل تعمل الصفة المشبهة إذا اعتمدت على مبتدأ أو ما أصله مبتدأ؟',
  'expected_status': 'success',
  'required_groups': [['مبتدا'], ['ما اصله مبتدا']]},
 {'category': 'الاعتماد على النفي',
  'endpoint': '/ask',
  'question': 'هل تعمل الصفة المشبهة إذا اعتمدت على نفي؟',
  'expected_status': 'success',
  'required_groups': [['نفي']]},
 {'category': 'الاعتماد على الاستفهام',
  'endpoint': '/ask',
  'question': 'هل تعمل الصفة المشبهة إذا اعتمدت على استفهام؟',
  'expected_status': 'success',
  'required_groups': [['استفهام']]},
 {'category': 'الاعتماد على النداء',
  'endpoint': '/ask',
  'question': 'هل تعمل الصفة المشبهة إذا اعتمدت على نداء؟',
  'expected_status': 'success',
  'required_groups': [['نداء']]},
 {'category': 'شروط العمل كاملة',
  'endpoint': '/ask',
  'question': 'على ماذا يجب أن تعتمد الصفة المشبهة لكي تعمل؟',
  'expected_status': 'success',
  'required_groups': [['مبتدا'], ['ما اصله مبتدا'], ['نفي'], ['استفهام'], ['نداء']]},
 {'category': 'أمثلة الوثيقة',
  'endpoint': '/ask',
  'question': 'ما الأمثلة الواردة في الوثيقة على عمل الصفة المشبهة؟',
  'expected_status': 'success',
  'required_groups': [['حسن سلوكه'], ['الحسن سلوكا'], ['الحسن السلوك'], ['حسن السلوك']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس الصفة المشبهة مع تعريفها وصياغتها وأوزانها وعملها وشروط عملها.',
  'expected_status': 'success',
  'required_groups': [['الصفه المشبهه'],
                      ['معني ثابت'],
                      ['غير مرتبط بزمان'],
                      ['الفعل الثلاثي'],
                      ['اللازم'],
                      ['افعل'],
                      ['فعلاء'],
                      ['فعل'],
                      ['فعله'],
                      ['فعلان'],
                      ['فعلي'],
                      ['اسم الفاعل'],
                      ['فاعل'],
                      ['مفعول به'],
                      ['تمييز'],
                      ['الاضافه'],
                      ['مبتدا'],
                      ['نفي'],
                      ['استفهام'],
                      ['نداء']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما عدد كواكب المجموعة الشمسية؟',
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
        "الاختبار الأولي لدرس الصفة المشبهة"
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
        "فلتر المصدر: alsfa-almshbha.pdf"
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
