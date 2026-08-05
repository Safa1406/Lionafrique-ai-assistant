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
EXPECTED_SOURCE = "altsghir.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-diminutive-baseline"

JSON_REPORT = Path("altsghir_test_results.json")
CSV_REPORT = Path("altsghir_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف التصغير',
  'endpoint': '/ask',
  'question': 'ما تعريف التصغير حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الاسم'],
                      ['المحول'],
                      ['صيغه فعيل'],
                      ['فعيعل'],
                      ['فعيعيل'],
                      ['الاسم المصغر']]},
 {'category': 'أوزان التصغير',
  'endpoint': '/ask',
  'question': 'ما أوزان التصغير المذكورة في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['فعيل'], ['فعيعل'], ['فعيعيل']]},
 {'category': 'أغراض التصغير',
  'endpoint': '/ask',
  'question': 'ما أغراض التصغير المذكورة في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['صغر الحجم'],
                      ['تقليل العدد'],
                      ['قرب الزمان'],
                      ['قرب المكان'],
                      ['التحقير'],
                      ['التعظيم'],
                      ['التحبيب']]},
 {'category': 'صغر الحجم',
  'endpoint': '/ask',
  'question': 'كيف يدل التصغير على صغر الحجم، وما أمثلته؟',
  'expected_status': 'success',
  'required_groups': [['صغر حجمه'], ['كليب'], ['كتيب'], ['لقيمه']]},
 {'category': 'تقليل العدد',
  'endpoint': '/ask',
  'question': 'كيف يدل التصغير على تقليل العدد، وما أمثلته؟',
  'expected_status': 'success',
  'required_groups': [['تقليل عدده'], ['وريقات'], ['دريهمات'], ['لقيمات']]},
 {'category': 'قرب الزمان',
  'endpoint': '/ask',
  'question': 'كيف يدل التصغير على قرب الزمان، وما المثال الوارد؟',
  'expected_status': 'success',
  'required_groups': [['قرب زمانه'], ['قبيل العشاء']]},
 {'category': 'قرب المكان',
  'endpoint': '/ask',
  'question': 'كيف يدل التصغير على قرب المكان، وما المثال الوارد؟',
  'expected_status': 'success',
  'required_groups': [['قرب مكانه'], ['دوين الرف']]},
 {'category': 'التحقير',
  'endpoint': '/ask',
  'question': 'كيف يستعمل التصغير للدلالة على التحقير؟',
  'expected_status': 'success',
  'required_groups': [['التحقير'], ['الشويعر']]},
 {'category': 'التعظيم',
  'endpoint': '/ask',
  'question': 'كيف يستعمل التصغير للدلالة على التعظيم؟',
  'expected_status': 'success',
  'required_groups': [['التعظيم'], ['دويهيه'], ['اذهلتهم']]},
 {'category': 'التحبيب',
  'endpoint': '/ask',
  'question': 'كيف يستعمل التصغير للدلالة على التحبيب؟',
  'expected_status': 'success',
  'required_groups': [['التحبيب'], ['جويريه'], ['الغزيل']]},
 {'category': 'صورة التصغير',
  'endpoint': '/ask',
  'question': 'كيف تصاغ صورة التصغير من حيث الحركات وزيادة الياء؟',
  'expected_status': 'success',
  'required_groups': [['يضم اول الاسم'], ['يفتح الثاني'], ['تزاد ياء'], ['رجيل'], ['كليب']]},
 {'category': 'ما زاد على ثلاثة أحرف',
  'endpoint': '/ask',
  'question': 'ماذا يحدث إذا زاد الاسم المراد تصغيره على ثلاثة أحرف؟',
  'expected_status': 'success',
  'required_groups': [['كسر الحرف'], ['يلي ياء التصغير'], ['دريهم'], ['عصيفير']]},
 {'category': 'وزن الثلاثي',
  'endpoint': '/ask',
  'question': 'ما وزن تصغير الاسم الثلاثي؟',
  'expected_status': 'success',
  'required_groups': [['الثلاثي'], ['فعيل']]},
 {'category': 'وزن ما فوق الثلاثي',
  'endpoint': '/ask',
  'question': 'ما وزن تصغير ما فوق الثلاثي، وما أمثلته؟',
  'expected_status': 'success',
  'required_groups': [['فعيعل'], ['دريهم'], ['سفيرج'], ['درهم'], ['سفرجل']]},
 {'category': 'وزن فعيعيل',
  'endpoint': '/ask',
  'question': 'متى يستعمل وزن فعيعيل في التصغير، وما أمثلته؟',
  'expected_status': 'success',
  'required_groups': [['فعيعيل'], ['منهاج'], ['عصفور'], ['منيهيج'], ['عصيفير']]},
 {'category': 'التصغير والتكسير',
  'endpoint': '/ask',
  'question': 'ما العلاقة بين التصغير والتكسير حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['التصغير كالتكسير'],
                      ['دارهم'],
                      ['سفارج'],
                      ['مناهج'],
                      ['عصافير'],
                      ['دريهم'],
                      ['سفيرج'],
                      ['منيهيج'],
                      ['عصيفير']]},
 {'category': 'الحذف وقلب حرف العلة',
  'endpoint': '/ask',
  'question': 'ما التغييرات المشتركة بين التصغير والتكسير في سفرجل ومنهاج وعصفور؟',
  'expected_status': 'success',
  'required_groups': [['حذفنا'],
                      ['لام سفرجل'],
                      ['قلبنا حرف العله'],
                      ['قبل الاخر'],
                      ['ياء'],
                      ['التصغير'],
                      ['التكسير']]},
 {'category': 'ما لا يعتد به',
  'endpoint': '/ask',
  'question': 'ما الزوائد التي لا يعتد بها عند التصغير؟',
  'expected_status': 'success',
  'required_groups': [['تاء التانيث'],
                      ['الفها المقصوره'],
                      ['الفها الممدوده'],
                      ['الالف والنون'],
                      ['ياء النسب'],
                      ['الف مثل كلمه اصحاب']]},
 {'category': 'أمثلة عدم الاعتداد',
  'endpoint': '/ask',
  'question': 'كيف تصغر ورقة وفضلى وصحراء وخضراء وعطشان وأصحاب؟',
  'expected_status': 'success',
  'required_groups': [['وريقه'], ['فضيلي'], ['صحيراء'], ['خضيراء'], ['عطيشان'], ['اصيحاب']]},
 {'category': 'أمثلة لا يحذف فيها',
  'endpoint': '/ask',
  'question': 'كيف تصغر حنظلة وأربعاء وعبقري وزعفران؟',
  'expected_status': 'success',
  'required_groups': [['حنيظله'], ['اريبعاء'], ['عبيقري'], ['زعفران'], ['دون ان يحذفوا']]},
 {'category': 'الثلاثي المؤنث معنويا',
  'endpoint': '/ask',
  'question': 'كيف يصغر الاسم الثلاثي المؤنث تأنيثا معنويا؟',
  'expected_status': 'success',
  'required_groups': [['تزاد في اخره تاء'],
                      ['شمس'],
                      ['ارض'],
                      ['دعد'],
                      ['شميسه'],
                      ['اريضه'],
                      ['دعيده']]},
 {'category': 'رد الحرف المحذوف',
  'endpoint': '/ask',
  'question': 'ماذا يحدث للحرف المحذوف من الاسم عند التصغير؟',
  'expected_status': 'success',
  'required_groups': [['يرد اليه المحذوف'],
                      ['دم'],
                      ['عده'],
                      ['ابن'],
                      ['اب'],
                      ['اخت'],
                      ['يد'],
                      ['دمي'],
                      ['وعيد'],
                      ['بني'],
                      ['ابي'],
                      ['اخيه'],
                      ['يديه']]},
 {'category': 'رد حرف العلة إلى أصله',
  'endpoint': '/ask',
  'question': 'كيف يصغر الاسم إذا كان حرفه الثاني حرف علة منقلبا عن غيره؟',
  'expected_status': 'success',
  'required_groups': [['رد الي اصله'],
                      ['ميزان'],
                      ['دينار'],
                      ['باب'],
                      ['ناب'],
                      ['مويزين'],
                      ['دنينير'],
                      ['بويب'],
                      ['نييب']]},
 {'category': 'قلب الألف واوا',
  'endpoint': '/ask',
  'question': 'متى تقلب الألف واوا في التصغير، وما الأمثلة؟',
  'expected_status': 'success',
  'required_groups': [['الالف الزايده'],
                      ['اسم الفاعل'],
                      ['المنقلبه عن همزه'],
                      ['ادم'],
                      ['المجهوله الاصل'],
                      ['عاج'],
                      ['واوا'],
                      ['شويعر'],
                      ['اويدم'],
                      ['عويج']]},
 {'category': 'اختصاص التصغير',
  'endpoint': '/ask',
  'question': 'بماذا يختص التصغير؟',
  'expected_status': 'success',
  'required_groups': [['الاسماء المعربه']]},
 {'category': 'شذوذ أسماء الإشارة',
  'endpoint': '/ask',
  'question': 'ما أمثلة تصغير أسماء الإشارة الواردة شذوذا؟',
  'expected_status': 'success',
  'required_groups': [['ذيا'], ['تصغير ذا'], ['هولياء'], ['تصغير هولاء']]},
 {'category': 'شذوذ الأسماء الموصولة',
  'endpoint': '/ask',
  'question': 'ما أمثلة تصغير الأسماء الموصولة الواردة شذوذا؟',
  'expected_status': 'success',
  'required_groups': [['اللذيا'], ['اللتيا'], ['تصغير الذي والتي']]},
 {'category': 'شذوذ أفعال التعجب',
  'endpoint': '/ask',
  'question': 'ما المثال الوارد على تصغير فعل التعجب؟',
  'expected_status': 'success',
  'required_groups': [['ما اميليح الغزال'],
                      ['افعال التعجب'],
                      ['يقتصر'],
                      ['ما سمع'],
                      ['لا يقاس عليه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس التصغير مع تعريفه وأغراضه وأوزانه وأهم أحكامه وشواذه.',
  'expected_status': 'success',
  'required_groups': [['التصغير'],
                      ['الاسم المصغر'],
                      ['فعيل'],
                      ['فعيعل'],
                      ['فعيعيل'],
                      ['صغر الحجم'],
                      ['تقليل العدد'],
                      ['قرب الزمان'],
                      ['قرب المكان'],
                      ['التحقير'],
                      ['التعظيم'],
                      ['التحبيب'],
                      ['تاء التانيث'],
                      ['يرد'],
                      ['حرف العله'],
                      ['الاسماء المعربه'],
                      ['شذوذا'],
                      ['لا يقاس عليه']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما أعلى جبل في العالم؟',
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
        "الاختبار الأولي لدرس التصغير"
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
        "فلتر المصدر: altsghir.pdf"
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
