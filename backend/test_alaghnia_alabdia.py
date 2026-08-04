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
EXPECTED_SOURCE = "alaghnia-alabdia.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-eternal-song-baseline"

JSON_REPORT = Path("alaghnia_alabdia_test_results.json")
CSV_REPORT = Path("alaghnia_alabdia_test_results.csv")

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

TEST_CASES = [{'category': 'مصدر النص',
  'endpoint': '/ask',
  'question': 'ما مصدر نص الأغنية الأبدية، ومن ترجمته؟',
  'expected_status': 'success',
  'required_groups': [['اساطير الهنود الحمر'], ['راويه صادق'], ['مجله الكرمل']]},
 {'category': 'مجال النص',
  'endpoint': '/ask',
  'question': 'إلى أي مجال ينتمي نص الأغنية الأبدية؟',
  'expected_status': 'success',
  'required_groups': [['القيم الانسانيه']]},
 {'category': 'نوعية النص',
  'endpoint': '/ask',
  'question': 'ما نوع نص الأغنية الأبدية؟',
  'expected_status': 'success',
  'required_groups': [['نص حكايي اسطوري'], ['بعد وطني'], ['انساني']]},
 {'category': 'تركيب العنوان',
  'endpoint': '/ask',
  'question': 'ما تركيب عنوان الأغنية الأبدية؟',
  'expected_status': 'success',
  'required_groups': [['مركب وصفي'], ['الاغنيه'], ['موصوف'], ['الابديه'], ['صفه']]},
 {'category': 'دلالة العنوان',
  'endpoint': '/ask',
  'question': 'ما الدلالة المعجمية والدلالية لعنوان الأغنية الأبدية؟',
  'expected_status': 'success',
  'required_groups': [['ابداع انساني'],
                      ['الافراح'],
                      ['الاحزان'],
                      ['الخلود'],
                      ['الاستمرار'],
                      ['صفه الاسطوريه'],
                      ['المجال الانساني']]},
 {'category': 'بداية النص',
  'endpoint': '/ask',
  'question': 'ما المؤشرات التي تظهر في بداية النص، وعم تتحدث؟',
  'expected_status': 'success',
  'required_groups': [['المكان'],
                      ['الزمان'],
                      ['الشخصيات'],
                      ['سرديه النص'],
                      ['مؤشرات اسطوريه'],
                      ['استعداد الهنود الحمر للحرب']]},
 {'category': 'نهاية النص',
  'endpoint': '/ask',
  'question': 'إلى ماذا تشير نهاية النص؟',
  'expected_status': 'success',
  'required_groups': [['الاغنيه'], ['العنوان'], ['مصدرها']]},
 {'category': 'فرضية القراءة',
  'endpoint': '/ask',
  'question': 'ما فرضية القراءة المقترحة للنص؟',
  'expected_status': 'success',
  'required_groups': [['اسطوره الهنود الحمر'],
                      ['حربهم علي الغزاه'],
                      ['رمزيه التضحيه'],
                      ['حريتهم']]},
 {'category': 'الإيضاح اللغوي',
  'endpoint': '/ask',
  'question': 'ما معنى الكلمات: حالك، الأحراج، الأيكة، كلل؟',
  'expected_status': 'success',
  'required_groups': [['شديد السواد'],
                      ['المكان الكثيف الشجر'],
                      ['الشجره العظيمه'],
                      ['اغصان كثيفه'],
                      ['تعب'],
                      ['عياء']]},
 {'category': 'المضمون العام',
  'endpoint': '/ask',
  'question': 'ما المضمون العام لنص الأغنية الأبدية؟',
  'expected_status': 'success',
  'required_groups': [['حكايه المحارب الهندي'],
                      ['ضحي بنفسه'],
                      ['وطنه'],
                      ['عبره'],
                      ['عاشق للحريه'],
                      ['رافض للمحتل']]},
 {'category': 'بداية الرحلة الحربية',
  'endpoint': '/ask',
  'question': 'كيف كان المحاربون يتقدمون ليلا، وما غايتهم؟',
  'expected_status': 'success',
  'required_groups': [['خطوه الذيب'],
                      ['يتجنبون وطء الاغصان'],
                      ['دون ان يهمسوا'],
                      ['مفاجاه العدو'],
                      ['قبيل حلول الصباح']]},
 {'category': 'تنظيم المحاربين',
  'endpoint': '/ask',
  'question': 'كيف نظم المحاربون تقدمهم لحماية المجموعة؟',
  'expected_status': 'success',
  'required_groups': [['قوه استطلاع'], ['الموخره'], ['تحميهم'], ['ايه مفاجاه']]},
 {'category': 'الاستراحة',
  'endpoint': '/ask',
  'question': 'ماذا فعل المحاربون عندما استراحوا حول النار؟',
  'expected_status': 'success',
  'required_groups': [['يصلح حذاءه'],
                      ['الاقواس'],
                      ['السهام'],
                      ['يعدون وجبه'],
                      ['يحكون حكايات'],
                      ['معارك'],
                      ['مغامرات']]},
 {'category': 'الحكايات الأسطورية',
  'endpoint': '/ask',
  'question': 'ما الحكايات الأسطورية التي كان المحاربون يروونها؟',
  'expected_status': 'success',
  'required_groups': [['طلسم'],
                      ['قوه خارقه'],
                      ['حافظ علي حياه'],
                      ['جعبه سحريه'],
                      ['تحول سهام الاعداء'],
                      ['يرتد الي قلب']]},
 {'category': 'النار والصلاة',
  'endpoint': '/ask',
  'question': 'كيف تغير سلوك النار عندما قام العجوز الأشيب للصلاة؟',
  'expected_status': 'success',
  'required_groups': [['عجوز اشيب'],
                      ['الصلاه الرسميه'],
                      ['النار ترتفع'],
                      ['تصطك'],
                      ['الشرر'],
                      ['كل الاتجاهات']]},
 {'category': 'ظهور الغناء',
  'endpoint': '/ask',
  'question': 'كيف ظهر الغناء الغريب بين الأشجار؟',
  'expected_status': 'success',
  'required_groups': [['ارتفع غناء'],
                      ['الاشجار المجاوره'],
                      ['ملا الايكه'],
                      ['ترنيمه'],
                      ['رق'],
                      ['تنهيدات الريح']]},
 {'category': 'البحث عن مصدر الغناء',
  'endpoint': '/ask',
  'question': 'ماذا فعل الزعيم والمحاربون للبحث عن مصدر الغناء؟',
  'expected_status': 'success',
  'required_groups': [['اطفيوا النار'],
                      ['ابتعد في الظلام'],
                      ['القمر'],
                      ['تقدم المحاربون'],
                      ['في حذر'],
                      ['شجره دردار']]},
 {'category': 'الشجرة الغامضة',
  'endpoint': '/ask',
  'question': 'كيف اقترب المحاربون من شجرة الدردار، وماذا حدث للغناء؟',
  'expected_status': 'success',
  'required_groups': [['دائره واسعه'],
                      ['يتقدمون ببطء'],
                      ['خطوه خطوه'],
                      ['تضيق'],
                      ['الغناء يتصاعد'],
                      ['ذروه النغمه'],
                      ['انطفا']]},
 {'category': 'اكتشاف الهيكل',
  'endpoint': '/ask',
  'question': 'ماذا اكتشف المحاربون بين جذور شجرة الدردار؟',
  'expected_status': 'success',
  'required_groups': [['عظام هيكل عظمي'], ['محارب مجهول'], ['قوسه المحطم'], ['سهام مبعثره']]},
 {'category': 'تفسير الزعيم',
  'endpoint': '/ask',
  'question': 'كيف فسر الزعيم الغناء والهيكل العظمي؟',
  'expected_status': 'success',
  'required_groups': [['بطل'],
                      ['ضحي بحياته'],
                      ['من اجل الاخرين'],
                      ['الموت'],
                      ['لا يمكن ان يخرس صوته'],
                      ['غناءه يستمر'],
                      ['رسالته']]},
 {'category': 'واجب التضحية',
  'endpoint': '/ask',
  'question': 'ما الواجب الإنساني الذي تحمله الأغنية الأبدية؟',
  'expected_status': 'success',
  'required_groups': [['قداسه واجب التضحيه بالنفس'],
                      ['فداء للاخرين'],
                      ['لسان حال هذه الاغنيه'],
                      ['نصون هذه الترنيمه'],
                      ['ذاكرتنا']]},
 {'category': 'بلد الظل',
  'endpoint': '/ask',
  'question': 'ماذا قال الزعيم عن الوصول إلى بلد الظل ومصير أغنيتهم؟',
  'expected_status': 'success',
  'required_groups': [['بلد الظل'], ['لن تموت اغنيتنا'], ['الترنيمه'], ['صداها ابديا']]},
 {'category': 'الحقل الأسطوري',
  'endpoint': '/ask',
  'question': 'ما أبرز ألفاظ الحقل الأسطوري في النص؟',
  'expected_status': 'success',
  'required_groups': [['خليج الثعابين'],
                      ['الداكوتاش'],
                      ['جعبه سحريه'],
                      ['طلسم'],
                      ['قوه خارقه'],
                      ['ظاهره اشد غرابه'],
                      ['اوامر سريه'],
                      ['بلد الظل']]},
 {'category': 'الحقل الحربي',
  'endpoint': '/ask',
  'question': 'ما أبرز ألفاظ الحقل الحربي في النص؟',
  'expected_status': 'success',
  'required_groups': [['ساحه الحرب'],
                      ['المحاربين'],
                      ['العدو'],
                      ['قوي استطلاع'],
                      ['الاقواس'],
                      ['معارك'],
                      ['سهام'],
                      ['سلاح'],
                      ['التضحيه'],
                      ['فداء']]},
 {'category': 'دلالة المعجم',
  'endpoint': '/ask',
  'question': 'ما دلالة الجمع بين المعجم الأسطوري والمعجم الحربي؟',
  'expected_status': 'success',
  'required_groups': [['الهنود الحمر'],
                      ['حروبهم'],
                      ['تضحياتهم'],
                      ['اسطوره ابديه'],
                      ['المعجم الاسطوري'],
                      ['يعزز المعجم الحربي'],
                      ['صفه الابديه']]},
 {'category': 'مضامين النص',
  'endpoint': '/ask',
  'question': 'ما المضامين الأساسية التي يتدرج عبرها النص؟',
  'expected_status': 'success',
  'required_groups': [['استعداد الهنود الحمر'],
                      ['مواجهه العدو'],
                      ['استراحه المحاربين'],
                      ['سرد بطولاتهم الاسطوريه'],
                      ['انبعاث صوت غريب'],
                      ['البحث عن مصدره'],
                      ['اكتشاف مصدر الصوت'],
                      ['سر الاغنيه الابديه']]},
 {'category': 'الأسلوب والرموز',
  'endpoint': '/ask',
  'question': 'ما أسلوب النص، وما دلالة رموز الأغنية وخليج الثعابين وبلد الظل؟',
  'expected_status': 'success',
  'required_groups': [['اسلوبا سرديا'],
                      ['قالب اسطوري'],
                      ['الرمزيه'],
                      ['الخيال'],
                      ['الاغنيه'],
                      ['الحريه'],
                      ['التضحيه'],
                      ['خليج الثعابين'],
                      ['السم'],
                      ['الخطوره'],
                      ['بلد الظل'],
                      ['الراحه'],
                      ['الاستقرار'],
                      ['الطمأنينه']]},
 {'category': 'الرموز والمقصدية',
  'endpoint': '/ask',
  'question': 'إلى ماذا يرمز المحارب المجهول والطلسم، وما مقصدية النص وقيمه؟',
  'expected_status': 'success',
  'required_groups': [['المحارب المجهول'],
                      ['كل انسان مضح'],
                      ['مناضل'],
                      ['الطلسم'],
                      ['الغموض'],
                      ['السحر'],
                      ['السر الخفي'],
                      ['الشجاعه'],
                      ['التضحيه'],
                      ['التحدي'],
                      ['الحريه'],
                      ['الكرامه'],
                      ['قيمه وطنيه'],
                      ['قيمه انسانيه'],
                      ['قيمه فنيه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص نص الأغنية الأبدية وتحليله.',
  'expected_status': 'success',
  'required_groups': [['الهنود الحمر'],
                      ['المحاربين'],
                      ['الغناء'],
                      ['شجره الدردار'],
                      ['محارب مجهول'],
                      ['ضحي بنفسه'],
                      ['الاغنيه الابديه'],
                      ['الحريه'],
                      ['التضحيه'],
                      ['الحقل الاسطوري'],
                      ['الحقل الحربي'],
                      ['اسلوب سردي'],
                      ['الرموز'],
                      ['الشجاعه'],
                      ['الكرامه']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما أكبر محيط في العالم؟',
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
        "الاختبار الأولي لنص الأغنية الأبدية"
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
        "فلتر المصدر: alaghnia-alabdia.pdf"
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
