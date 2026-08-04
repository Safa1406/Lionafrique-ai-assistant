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
EXPECTED_SOURCE = "klim-allh.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-kalim-allah-baseline"

JSON_REPORT = Path("klim_allh_test_results.json")
CSV_REPORT = Path("klim_allh_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف القرآن',
  'endpoint': '/ask',
  'question': 'ما تعريف القرآن لغة واصطلاحا حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['قرأ', 'تلاه'],
                      ['كلام الله'],
                      ['المنزل'],
                      ['محمد'],
                      ['بلسان عربي فصيح'],
                      ['جبريل'],
                      ['الفاتحه'],
                      ['الناس'],
                      ['بالتواتر'],
                      ['محفوظا', 'محفوظ']]},
 {'category': 'سورة الشعراء',
  'endpoint': '/ask',
  'question': 'هل سورة الشعراء مكية أم مدنية، وما الآيات المستثناة؟',
  'expected_status': 'success',
  'required_groups': [['مكيه'], ['197'], ['224'], ['اخر السوره'], ['مدنيه']]},
 {'category': 'سورة الشعراء',
  'endpoint': '/ask',
  'question': 'كم عدد آيات سورة الشعراء وما ترتيبها في المصحف؟',
  'expected_status': 'success',
  'required_groups': [['227'], ['26']]},
 {'category': 'سورة الشعراء',
  'endpoint': '/ask',
  'question': 'بعد أي سورة نزلت سورة الشعراء، وبأي حروف بدأت؟',
  'expected_status': 'success',
  'required_groups': [['سوره الواقعه'], ['طسم']]},
 {'category': 'تسمية السورة',
  'endpoint': '/ask',
  'question': 'لماذا سميت سورة الشعراء بهذا الاسم؟',
  'expected_status': 'success',
  'required_groups': [['اخبار الشعراء'],
                      ['الرد علي المشركين'],
                      ['محمد'],
                      ['شاعرا'],
                      ['الشعر']]},
 {'category': 'مجال النص',
  'endpoint': '/ask',
  'question': 'إلى أي مجال ينتمي نص كليم الله؟',
  'expected_status': 'success',
  'required_groups': [['القيم الاسلاميه']]},
 {'category': 'نوعية النص',
  'endpoint': '/ask',
  'question': 'ما نوع نص كليم الله، وما المؤشرات الدالة على ذلك؟',
  'expected_status': 'success',
  'required_groups': [['نص قراني'],
                      ['ايات قرانيه'],
                      ['قال الله'],
                      ['سوره الشعراء'],
                      ['الرسم العثماني']]},
 {'category': 'العنوان',
  'endpoint': '/ask',
  'question': 'مم يتكون عنوان كليم الله تركيبيا؟',
  'expected_status': 'success',
  'required_groups': [['مركب اضافي'], ['كليم'], ['مضاف'], ['الله'], ['مضاف اليه']]},
 {'category': 'العنوان',
  'endpoint': '/ask',
  'question': 'ما دلالة عنوان كليم الله؟',
  'expected_status': 'success',
  'required_groups': [['لقب'], ['موسي'], ['الله كلمه', 'كلمه الله']]},
 {'category': 'بداية النص',
  'endpoint': '/ask',
  'question': 'ما المكونات الثلاثة التي تشير إليها بداية النص؟',
  'expected_status': 'success',
  'required_groups': [['المرسل'],
                      ['الله'],
                      ['المخاطب'],
                      ['محمد'],
                      ['موضوع الرساله'],
                      ['بعثه موسي'],
                      ['فرعون']]},
 {'category': 'نهاية النص',
  'endpoint': '/ask',
  'question': 'إلى ماذا تشير نهاية نص كليم الله؟',
  'expected_status': 'success',
  'required_groups': [['انتصار موسي'], ['سحره فرعون'], ['ايمانهم'], ['الله']]},
 {'category': 'فرضية القراءة',
  'endpoint': '/ask',
  'question': 'ما فرضية القراءة المقترحة لنص كليم الله؟',
  'expected_status': 'success',
  'required_groups': [['قصه موسي'], ['فرعون'], ['قومه']]},
 {'category': 'الإيضاح اللغوي',
  'endpoint': '/ask',
  'question': 'ما معنى الكلمات الآتية: لبثت، وهب، تمن، الملأ؟',
  'expected_status': 'success',
  'required_groups': [['اقمت', 'بيننا'], ['اعطي'], ['تعدد ما فعلت من الخير'], ['اكابر القوم']]},
 {'category': 'الإيضاح اللغوي',
  'endpoint': '/ask',
  'question': 'ما معنى الكلمات الآتية: أرجه، حاشرين، ميقاتا، يأفكون؟',
  'expected_status': 'success',
  'required_groups': [['اخر امره'], ['جامعين'], ['وقت معلوم'], ['يكذبون']]},
 {'category': 'المضمون العام',
  'endpoint': '/ask',
  'question': 'ما المضمون العام لنص كليم الله؟',
  'expected_status': 'success',
  'required_groups': [['قصه موسي'],
                      ['ارساله الي فرعون'],
                      ['استكبر', 'تجبر'],
                      ['السحره'],
                      ['انتصاره'],
                      ['ايمان السحره']]},
 {'category': 'بعثة موسى',
  'endpoint': '/ask',
  'question': 'بم أمر الله موسى عليه السلام في الآيتين 10 و11؟',
  'expected_status': 'success',
  'required_groups': [['تبليغ رسالته'], ['فرعون'], ['انقاذ بني اسراييل'], ['بطشه', 'جبروته']]},
 {'category': 'طلب موسى',
  'endpoint': '/ask',
  'question': 'لماذا طلب موسى من ربه أن يرسل معه هارون؟',
  'expected_status': 'success',
  'required_groups': [['اخاف ان يكذبون', 'خوفه من التكذيب'],
                      ['يضيق صدري'],
                      ['لا ينطلق لساني'],
                      ['هارون']]},
 {'category': 'مواجهة فرعون',
  'endpoint': '/ask',
  'question': 'بم واجه موسى فرعون، وكيف كان رد فرعون؟',
  'expected_status': 'success',
  'required_groups': [['الحجج البينه'],
                      ['تجبر فرعون'],
                      ['اتهمه بالسحر', 'اتهامه موسي بالسحر']]},
 {'category': 'رب العالمين',
  'endpoint': '/ask',
  'question': 'كيف عرف موسى رب العالمين لفرعون؟',
  'expected_status': 'success',
  'required_groups': [['رب السماوات والارض'],
                      ['ما بينهما'],
                      ['ربكم'],
                      ['رب ابايكم الاولين'],
                      ['رب المشرق والمغرب']]},
 {'category': 'معجزات موسى',
  'endpoint': '/ask',
  'question': 'ما المعجزتان اللتان أظهرهما موسى أمام فرعون؟',
  'expected_status': 'success',
  'required_groups': [['القي عصاه'], ['ثعبان مبين'], ['نزع يده'], ['بيضاء للناظرين']]},
 {'category': 'تعنت فرعون',
  'endpoint': '/ask',
  'question': 'اذكر ثلاثة مظاهر من تعنت فرعون وجبروته.',
  'expected_status': 'success',
  'required_groups': [['لمجنون', 'مجنون'], ['المسجونين'], ['ساحر عليم']]},
 {'category': 'مواجهة السحرة',
  'endpoint': '/ask',
  'question': 'ماذا حدث عندما ألقى موسى عصاه أمام السحرة؟',
  'expected_status': 'success',
  'required_groups': [['تلقف ما يافكون'],
                      ['القي السحره ساجدين', 'فالقي السحره ساجدين'],
                      ['امنا برب العالمين'],
                      ['رب موسي وهارون']]},
 {'category': 'ثبات السحرة',
  'endpoint': '/ask',
  'question': 'كيف هدد فرعون السحرة بعد إيمانهم، وكيف أجابوه؟',
  'expected_status': 'success',
  'required_groups': [['لاقطعن ايديكم وارجلكم'],
                      ['لاصلبنكم'],
                      ['لا ضير'],
                      ['الي ربنا منقلبون'],
                      ['يغفر لنا ربنا خطايانا']]},
 {'category': 'أسلوب النص',
  'endpoint': '/ask',
  'question': 'ما الأسلوبان المعتمدان في النص، وما وظيفة كل واحد منهما؟',
  'expected_status': 'success',
  'required_groups': [['السرد'], ['قصه موسي'], ['الحوار'], ['قال']]},
 {'category': 'الشخصيات',
  'endpoint': '/ask',
  'question': 'ما أوصاف موسى وهارون وفرعون والسحرة حسب الجدول؟',
  'expected_status': 'success',
  'required_groups': [['موسي'],
                      ['رسول رب العالمين'],
                      ['صاحب معجزه'],
                      ['هارون'],
                      ['اخ موسي'],
                      ['مسانده'],
                      ['فصيح'],
                      ['فرعون'],
                      ['متكبر'],
                      ['متجبر'],
                      ['السحره'],
                      ['مومنين في النهايه', 'تابين ومومنين']]},
 {'category': 'مراحل الأحداث',
  'endpoint': '/ask',
  'question': 'لخص مراحل أحداث قصة موسى من الآية 10 إلى الآية 51.',
  'expected_status': 'success',
  'required_groups': [['10'],
                      ['11'],
                      ['تبليغ رسالته'],
                      ['12'],
                      ['17'],
                      ['هارون'],
                      ['18'],
                      ['37'],
                      ['الحجج البينه'],
                      ['38'],
                      ['51'],
                      ['انتصاره'],
                      ['ايمانهم']]},
 {'category': 'المقصدية والقيم',
  'endpoint': '/ask',
  'question': 'ما مقصدية نص كليم الله، وما القيم التي يتضمنها؟',
  'expected_status': 'success',
  'required_groups': [['اخذ العبره'],
                      ['موسي'],
                      ['فرعون'],
                      ['التوحيد'],
                      ['الامتثال لامر الله'],
                      ['الايمان'],
                      ['الثبات علي الايمان'],
                      ['طلب المغفره']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص قصة كليم الله.',
  'expected_status': 'success',
  'required_groups': [['موسي'],
                      ['فرعون'],
                      ['هارون'],
                      ['بني اسراييل'],
                      ['العصا'],
                      ['السحره'],
                      ['انتصار'],
                      ['ايمان السحره'],
                      ['تهديد فرعون']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص تحليل نص كليم الله من حيث المجال والنوع والعنوان والمضمون والشخصيات '
              'والأحداث والأسلوب والمقصدية والقيم.',
  'expected_status': 'success',
  'required_groups': [['القيم الاسلاميه'],
                      ['نص قراني'],
                      ['مركب اضافي'],
                      ['موسي'],
                      ['فرعون'],
                      ['هارون'],
                      ['السحره'],
                      ['السرد'],
                      ['الحوار'],
                      ['اخذ العبره'],
                      ['التوحيد'],
                      ['الثبات علي الايمان']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما أسرع حيوان بري في العالم؟',
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
        "الاختبار الأولي لنص كليم الله"
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
        "فلتر المصدر: klim-allh.pdf"
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
