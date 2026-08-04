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
EXPECTED_SOURCE = "otni-ns-shari.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-my-homeland-poem-baseline"

JSON_REPORT = Path("otni_ns_shari_test_results.json")
CSV_REPORT = Path("otni_ns_shari_test_results.csv")

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

TEST_CASES = [{'category': 'صاحب النص',
  'endpoint': '/ask',
  'question': 'من صاحب قصيدة وطني، وما مصدرها؟',
  'expected_status': 'success',
  'required_groups': [['محمود درويش'], ['اخر الليل'], ['الاعمال الكامله']]},
 {'category': 'تعريف الشعر',
  'endpoint': '/ask',
  'question': 'ما تعريف الشعر حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الكلام الموزون'], ['المقفي'], ['الدال علي معني']]},
 {'category': 'أنواع الشعر',
  'endpoint': '/ask',
  'question': 'ما أنواع الشعر المذكورة في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الشعر العمودي'], ['الشعر الحر'], ['قصيده النثر']]},
 {'category': 'الشعر العمودي',
  'endpoint': '/ask',
  'question': 'ما خصائص الشعر العمودي حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['نظام الشطرين'],
                      ['الصدر'],
                      ['العجز'],
                      ['وحده الوزن'],
                      ['القافيه'],
                      ['الروي']]},
 {'category': 'حياة محمود درويش',
  'endpoint': '/ask',
  'question': 'أين ومتى ولد محمود درويش؟',
  'expected_status': 'success',
  'required_groups': [['قريه البروه'], ['فلسطين'], ['1941']]},
 {'category': 'اللجوء والعودة',
  'endpoint': '/ask',
  'question': 'متى لجأ محمود درويش إلى لبنان، ومتى عاد إلى فلسطين؟',
  'expected_status': 'success',
  'required_groups': [['1948'], ['لبنان'], ['1949'], ['عاد الي فلسطين'], ['متسللا']]},
 {'category': 'تعليم محمود درويش',
  'endpoint': '/ask',
  'question': 'أين تابع محمود درويش تعليمه الابتدائي والثانوي؟',
  'expected_status': 'success',
  'required_groups': [['مدرسه دير الاسد'], ['مدرسه يني الثانويه']]},
 {'category': 'نشاطه ووفاته',
  'endpoint': '/ask',
  'question': 'ما أبرز نشاط محمود درويش، ومتى وأين توفي؟',
  'expected_status': 'success',
  'required_groups': [['رييس رابطه الكتاب والصحفيين الفلسطينيين'],
                      ['الولايات المتحده الامريكيه'],
                      ['2008']]},
 {'category': 'مؤلفات الشاعر',
  'endpoint': '/ask',
  'question': 'اذكر بعض مؤلفات محمود درويش الواردة في الوثيقة.',
  'expected_status': 'success',
  'required_groups': [['اوراق الزيتون'],
                      ['عاشق من فلسطين'],
                      ['اخر الليل'],
                      ['اعراس'],
                      ['حصار لمدايح البحر'],
                      ['لماذا تركت الحصان وحيدا'],
                      ['حاله حصار'],
                      ['اثر الفراشه']]},
 {'category': 'مجال النص',
  'endpoint': '/ask',
  'question': 'إلى أي مجال ينتمي نص وطني؟',
  'expected_status': 'success',
  'required_groups': [['القيم الوطنيه'], ['الانسانيه']]},
 {'category': 'نوعية النص',
  'endpoint': '/ask',
  'question': 'ما نوع نص وطني؟',
  'expected_status': 'success',
  'required_groups': [['قصيده شعريه عموديه'], ['بعد وطني']]},
 {'category': 'بنية القصيدة',
  'endpoint': '/ask',
  'question': 'كم عدد أبيات القصيدة، وما رويها؟',
  'expected_status': 'success',
  'required_groups': [['9 ابيات'], ['حرف اللام'], ['اشبع'], ['الابيات الثلاثه الاخيره']]},
 {'category': 'دلالة العنوان',
  'endpoint': '/ask',
  'question': 'ما دلالة عنوان وطني من حيث التركيب والمعنى؟',
  'expected_status': 'success',
  'required_groups': [['مركب اضافي'],
                      ['ضمير المتكلم'],
                      ['الياء'],
                      ['ارتباط'],
                      ['عدم افتراقهما'],
                      ['الوطن'],
                      ['المواطن']]},
 {'category': 'حذف أداة النداء',
  'endpoint': '/ask',
  'question': 'ماذا يدل حذف أداة النداء في عنوان وطني؟',
  'expected_status': 'success',
  'required_groups': [['الارتباط الوثيق'], ['المنادي'], ['المنادى'], ['قرب']]},
 {'category': 'بداية القصيدة',
  'endpoint': '/ask',
  'question': 'ماذا يعبر الشاعر في بداية القصيدة؟',
  'expected_status': 'success',
  'required_groups': [['قرب المسافه النفسيه'],
                      ['وطنه'],
                      ['العنف ضد العدو الصهيوني'],
                      ['الرقه'],
                      ['فلسطين'],
                      ['الحريه']]},
 {'category': 'نهاية القصيدة',
  'endpoint': '/ask',
  'question': 'ماذا يعبر الشاعر في نهاية القصيدة؟',
  'expected_status': 'success',
  'required_groups': [['بعد المسافه النفسيه'],
                      ['العدو الصهيوني'],
                      ['يكرهه'],
                      ['يتحداه'],
                      ['الصبر'],
                      ['الصمود']]},
 {'category': 'فرضية القراءة',
  'endpoint': '/ask',
  'question': 'ما فرضية القراءة المقترحة للقصيدة؟',
  'expected_status': 'success',
  'required_groups': [['ارتباط الشاعر بوطنه'], ['الصمود'], ['التحدي'], ['نيل الحريه']]},
 {'category': 'الإيضاح اللغوي',
  'endpoint': '/ask',
  'question': 'ما معنى الكلمات: زنزانة، جدائل، أنامل، صرير؟',
  'expected_status': 'success',
  'required_groups': [['سجن انفرادي'],
                      ['ج جديله'],
                      ['جريد النخل'],
                      ['اصابع'],
                      ['صوت السلاسل']]},
 {'category': 'المضمون العام',
  'endpoint': '/ask',
  'question': 'ما المضمون العام لقصيدة وطني؟',
  'expected_status': 'success',
  'required_groups': [['حب الشاعر لوطنه'],
                      ['تعلقه به'],
                      ['التحدي'],
                      ['الصمود'],
                      ['شمس الحريه'],
                      ['الاستقلال']]},
 {'category': 'حقل الألم',
  'endpoint': '/ask',
  'question': 'ما أبرز ألفاظ حقل الألم في القصيدة؟',
  'expected_status': 'success',
  'required_groups': [['سلاسل'],
                      ['عنف'],
                      ['عاصفه'],
                      ['زنزانه'],
                      ['قاتلي'],
                      ['العذاب'],
                      ['الظلام'],
                      ['هزيمتي'],
                      ['زلازل'],
                      ['صرير']]},
 {'category': 'حقل الأمل',
  'endpoint': '/ask',
  'question': 'ما أبرز ألفاظ حقل الأمل في القصيدة؟',
  'expected_status': 'success',
  'required_groups': [['رقه'],
                      ['المتفائل'],
                      ['عرس جداول'],
                      ['شمس'],
                      ['مرج'],
                      ['سنابل'],
                      ['جدائل'],
                      ['ظلال']]},
 {'category': 'دلالة المعجم',
  'endpoint': '/ask',
  'question': 'ما دلالة الجمع بين حقل الألم وحقل الأمل؟',
  'expected_status': 'success',
  'required_groups': [['بطش العدو الصهيوني'],
                      ['التحدي'],
                      ['الصمود'],
                      ['الامل'],
                      ['يخفف'],
                      ['معاناته'],
                      ['زنزانته']]},
 {'category': 'الأفعال وردود الأفعال',
  'endpoint': '/ask',
  'question': 'ما الأفعال التي قام بها العدو، وما أبرز ردود فعل الشاعر؟',
  'expected_status': 'success',
  'required_groups': [['سدوا علي النور'],
                      ['كتبوا علي الجدران رقم بطاقتي'],
                      ['رسموا علي الجدران صوره قاتلي'],
                      ['توهجت في القلب'],
                      ['نما علي الجدران مرج سنابل'],
                      ['حفرت بالاسنان رسمك'],
                      ['كتبت اغنيه العذاب الراحل']]},
 {'category': 'دلالة ردود الأفعال',
  'endpoint': '/ask',
  'question': 'ماذا تدل هيمنة ردود الأفعال على الأفعال في القصيدة؟',
  'expected_status': 'success',
  'required_groups': [['غضب الشاعر'],
                      ['انتصاره المعنوي'],
                      ['العدو الصهيوني'],
                      ['معاناته'],
                      ['السجن']]},
 {'category': 'مقاطع القصيدة',
  'endpoint': '/ask',
  'question': 'ما مضامين المقاطع الثلاثة للقصيدة؟',
  'expected_status': 'success',
  'required_groups': [['البيتان 1 و2'],
                      ['الصمود'],
                      ['التفاؤل'],
                      ['من البيت 3 الي البيت 5'],
                      ['اشكال التعذيب'],
                      ['من البيت 6 الي البيت 9'],
                      ['المواجهه'],
                      ['الامل في المستقبل']]},
 {'category': 'الخصائص الفنية',
  'endpoint': '/ask',
  'question': 'ما أبرز الخصائص الفنية في القصيدة ودلالاتها؟',
  'expected_status': 'success',
  'required_groups': [['اسلوب النفي'],
                      ['التحدي'],
                      ['الصمود'],
                      ['الطباق'],
                      ['ظلام'],
                      ['نور'],
                      ['هيمنه الجمل الفعليه'],
                      ['الحركيه'],
                      ['الرمز'],
                      ['السنابل'],
                      ['الجدائل']]},
 {'category': 'خطاب القصيدة',
  'endpoint': '/ask',
  'question': 'من المرسل والمرسل إليه في خطاب القصيدة؟',
  'expected_status': 'success',
  'required_groups': [['الشاعر محمود درويش'], ['العدو الصهيوني'], ['الضمائر الحيه في العالم']]},
 {'category': 'مقصدية الرسالة',
  'endpoint': '/ask',
  'question': 'ما مقصدية رسالة القصيدة، وما القيم التي تحملها؟',
  'expected_status': 'success',
  'required_groups': [['اعلان التحدي'],
                      ['الصمود'],
                      ['العدو الصهيوني'],
                      ['التضحيات'],
                      ['الحريه'],
                      ['الكرامه'],
                      ['الثقه في النفس'],
                      ['شجاعه الموقف'],
                      ['الصبر'],
                      ['التفاؤل']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص قصيدة وطني وتحليلها.',
  'expected_status': 'success',
  'required_groups': [['محمود درويش'],
                      ['وطني'],
                      ['حب الشاعر لوطنه'],
                      ['التحدي'],
                      ['الصمود'],
                      ['الحريه'],
                      ['حقل الالم'],
                      ['حقل الامل'],
                      ['العدو الصهيوني'],
                      ['اسلوب النفي'],
                      ['الطباق'],
                      ['السنابل'],
                      ['الجدائل']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما عاصمة كندا؟',
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
        "الاختبار الأولي لقصيدة وطني"
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
        "فلتر المصدر: otni-ns-shari.pdf"
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
