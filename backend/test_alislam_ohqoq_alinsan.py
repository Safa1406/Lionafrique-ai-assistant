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
EXPECTED_SOURCE = "alislam-ohqoq-alinsan.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-islam-human-rights-baseline"

JSON_REPORT = Path("alislam_ohqoq_alinsan_test_results.json")
CSV_REPORT = Path("alislam_ohqoq_alinsan_test_results.csv")

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

TEST_CASES = [{'category': 'التعريف بالكاتب',
  'endpoint': '/ask',
  'question': 'من هو كاتب نص الإسلام وحقوق الإنسان، وما أبرز مراحل حياته؟',
  'expected_status': 'success',
  'required_groups': [['عبد الهادي بوطالب'],
                      ['مفكر وكاتب وسياسي وديبلوماسي'],
                      ['ولد بفاس'],
                      ['1923'],
                      ['توفي'],
                      ['2009']]},
 {'category': 'مؤلفات الكاتب',
  'endpoint': '/ask',
  'question': 'اذكر بعض مؤلفات عبد الهادي بوطالب الواردة في الوثيقة.',
  'expected_status': 'success',
  'required_groups': [['وزير غرناطه'],
                      ['الصحوه الاسلاميه'],
                      ['حقيقه الاسلام'],
                      ['المرجع في القانون الدستوري'],
                      ['الشريعه والفقه والقانون']]},
 {'category': 'مجال النص ونوعه',
  'endpoint': '/ask',
  'question': 'إلى أي مجال ينتمي النص، وما نوعيته؟',
  'expected_status': 'success',
  'required_groups': [['مجال القيم الاسلاميه'], ['مقاله تفسيريه'], ['بعد اسلامي']]},
 {'category': 'تحليل العنوان',
  'endpoint': '/ask',
  'question': 'كيف حللت الوثيقة عنوان الإسلام وحقوق الإنسان تركيبيا ودلاليا؟',
  'expected_status': 'success',
  'required_groups': [['مركب عطفي'],
                      ['الاسلام وحقوق'],
                      ['مركب اضافي'],
                      ['حقوق الانسان'],
                      ['علاقه الدين الاسلامي بحقوق الانسان']]},
 {'category': 'فرضية القراءة',
  'endpoint': '/ask',
  'question': 'ما فرضية قراءة النص المبنية على العنوان والبداية والنهاية؟',
  'expected_status': 'success',
  'required_groups': [['موضوعه'], ['حقوق الانسان'], ['في ظل الاسلام']]},
 {'category': 'تكريم الإنسان',
  'endpoint': '/ask',
  'question': 'كيف يبين النص أن جميع بني آدم مكرمون دون تمييز؟',
  'expected_status': 'success',
  'required_groups': [['كل بني ادم'],
                      ['مكرمون'],
                      ['من امن'],
                      ['من لم يومن'],
                      ['من احسن'],
                      ['من اساء']]},
 {'category': 'العطاء الإلهي',
  'endpoint': '/ask',
  'question': 'من الذين لا يحرمون من العطاء المادي حسب النص؟',
  'expected_status': 'success',
  'required_groups': [['كافرا'], ['ملحدا'], ['مذنبا'], ['عطاء ربك'], ['غير محظور']]},
 {'category': 'منظور الإسلام للحقوق',
  'endpoint': '/ask',
  'question': 'ما منظور الإسلام الخاص تجاه حقوق الإنسان؟',
  'expected_status': 'success',
  'required_groups': [['حقوقا للبشريه'],
                      ['حقوق الله'],
                      ['تخويلها لعباده كافه'],
                      ['بدون تمييز'],
                      ['لا تفريق']]},
 {'category': 'حقوق الجنين',
  'endpoint': '/ask',
  'question': 'متى يبدأ الإسلام في كفالة حقوق الإنسان؟',
  'expected_status': 'success',
  'required_groups': [['منذ تصوره جنينا'], ['بجسد وروح'], ['في بطن امه'], ['منذ التكوين']]},
 {'category': 'الحق في الحياة',
  'endpoint': '/ask',
  'question': 'كيف حمى الإسلام حق الجنين في الحياة؟',
  'expected_status': 'success',
  'required_groups': [['اجهاضه حرام'], ['واد البنات'], ['حقه في الحياه']]},
 {'category': 'تحريم الانتحار',
  'endpoint': '/ask',
  'question': 'ما موقف الإسلام من الانتحار، وبم وصف النص المنتحر؟',
  'expected_status': 'success',
  'required_groups': [['منع الاسلام الانتحار'],
                      ['احتراما لحق الانسان في الحياه'],
                      ['المدبر'],
                      ['خسر دينه ودنياه']]},
 {'category': 'حرية العقيدة',
  'endpoint': '/ask',
  'question': 'كيف ضمن الإسلام حرية العقيدة حسب النص؟',
  'expected_status': 'success',
  'required_groups': [['حق الحريات'],
                      ['حريه العقيده'],
                      ['لا اكراه في الدين'],
                      ['قد تبين الرشد من الغي']]},
 {'category': 'الديانات السماوية',
  'endpoint': '/ask',
  'question': 'كيف تعامل الإسلام مع أتباع الديانات السماوية؟',
  'expected_status': 'success',
  'required_groups': [['يبقي علي دينه'],
                      ['يعترف بالديانات السماويه'],
                      ['لا نفرق بين احد من رسله'],
                      ['تعايش']]},
 {'category': 'صحيفة المدينة',
  'endpoint': '/ask',
  'question': 'ما الصحيفة التي أعلنها الرسول في المدينة، وما مكانتها حسب النص؟',
  'expected_status': 'success',
  'required_groups': [['الصحيفه'],
                      ['الدستور'],
                      ['المدينه'],
                      ['اول دستور مدون'],
                      ['في العالم']]},
 {'category': 'الحرب ورد العدوان',
  'endpoint': '/ask',
  'question': 'متى تشرع الحرب في الإسلام حسب النص؟',
  'expected_status': 'success',
  'required_groups': [['لا تشن'],
                      ['الا لرد عدوان'],
                      ['قاتلوا'],
                      ['الذين يقاتلونكم'],
                      ['لا تعتدوا']]},
 {'category': 'خيار السلام',
  'endpoint': '/ask',
  'question': 'ما موقف الإسلام عندما يظهر العدو جنوحا إلى السلام؟',
  'expected_status': 'success',
  'required_groups': [['ان جنحوا للسلم'],
                      ['فاجنح لها'],
                      ['خيار السلام'],
                      ['الحرب'],
                      ['الضروره القصوي']]},
 {'category': 'مساواة المرأة',
  'endpoint': '/ask',
  'question': 'كيف أنصف الإسلام المرأة وساواها بالرجل؟',
  'expected_status': 'success',
  'required_groups': [['انصف الاسلام المراه'],
                      ['كرمها'],
                      ['حق المساواه'],
                      ['الاحكام'],
                      ['النساء شقائق الرجال']]},
 {'category': 'أدوار المرأة',
  'endpoint': '/ask',
  'question': 'ما الحقوق والأدوار التي مارستها المرأة في الإسلام حسب النص؟',
  'expected_status': 'success',
  'required_groups': [['حقوقها الدينيه'],
                      ['السياسيه'],
                      ['الاجتماعيه'],
                      ['مفتيه'],
                      ['مفسره للقران'],
                      ['راويه للحديث'],
                      ['شؤون السوق'],
                      ['عائشه']]},
 {'category': 'مناهضة العنصرية',
  'endpoint': '/ask',
  'question': 'كيف ناهض الإسلام العنصرية والتمييز العنصري؟',
  'expected_status': 'success',
  'required_groups': [['ناهض الاسلام العنصريه'],
                      ['ابطل التمييز العنصري'],
                      ['لا فضل لعربي علي اعجمي'],
                      ['لا لابيض علي اسود']]},
 {'category': 'نماذج التنوع العرقي',
  'endpoint': '/ask',
  'question': 'ما النماذج التي قدمها النص للتنوع العرقي بين المسلمين؟',
  'expected_status': 'success',
  'required_groups': [['بلال بن رباح'],
                      ['حبشيا'],
                      ['صهيب الرومي'],
                      ['سلمان الفارسي'],
                      ['زواج المسلم'],
                      ['نساء اهل الكتاب']]},
 {'category': 'المضمون العام',
  'endpoint': '/ask',
  'question': 'ما المضمون العام لنص الإسلام وحقوق الإنسان؟',
  'expected_status': 'success',
  'required_groups': [['مكانه الانسان في الاسلام'], ['حقوقه الاساسيه']]},
 {'category': 'الإيضاح اللغوي',
  'endpoint': '/ask',
  'question': 'ما معاني محظور وتخويل وتكفل وجنحوا وأعجمي وندد في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['محظور ممنوع'],
                      ['تخويل تمكين'],
                      ['تكفل تضمن'],
                      ['جنحوا مالوا'],
                      ['اعجمي ليس عربيا'],
                      ['ندد شجب']]},
 {'category': 'الحقول الدلالية',
  'endpoint': '/ask',
  'question': 'ما الحقلان الدلاليان البارزان في النص، وما العلاقة بينهما؟',
  'expected_status': 'success',
  'required_groups': [['تكريم الاسلام للانسان'],
                      ['حقوق الانسان في الاسلام'],
                      ['تقاطع'],
                      ['الغايه واحده'],
                      ['تكريم الانسان']]},
 {'category': 'المضامين الأساسية',
  'endpoint': '/ask',
  'question': 'ما المضامين الأساسية للنص حسب القراءة التحليلية؟',
  'expected_status': 'success',
  'required_groups': [['تكريم الله الانسان'],
                      ['دون تمييز'],
                      ['منظور الاسلام'],
                      ['الحفاظ عليها'],
                      ['الحقوق الاساسيه'],
                      ['سبل الحفاظ عليها']]},
 {'category': 'الأسلوب الاستنباطي',
  'endpoint': '/ask',
  'question': 'كيف وظف الكاتب الأسلوب الاستنباطي حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['اسلوبا استنباطيا'],
                      ['من الخاص الي العام'],
                      ['امثله لحقوق الانسان'],
                      ['منظومه متكامله'],
                      ['شريعه حقوق الانسان']]},
 {'category': 'أسلوب الحجاج',
  'endpoint': '/ask',
  'question': 'ما وسائل الحجاج التي اعتمدها الكاتب؟',
  'expected_status': 'success',
  'required_groups': [['الاستشهاد بالنصوص الدينيه'],
                      ['القران'],
                      ['الحديث'],
                      ['سيره الرسول'],
                      ['التوكيد بالتكرار'],
                      ['الاسلام'],
                      ['حقوق'],
                      ['الانسان'],
                      ['ان']]},
 {'category': 'الطباق',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة الطباق الواردة في النص.',
  'expected_status': 'success',
  'required_groups': [['احسن'],
                      ['اساء'],
                      ['السلام'],
                      ['الحرب'],
                      ['عربي'],
                      ['اعجمي'],
                      ['ابيض'],
                      ['اسود'],
                      ['الرجل'],
                      ['المراه']]},
 {'category': 'المقصدية والقيم',
  'endpoint': '/ask',
  'question': 'ما مقصدية رسالة النص، وما القيم التي يتضمنها؟',
  'expected_status': 'success',
  'required_groups': [['ابراز دور الاسلام'],
                      ['المشروعيه لحقوق الانسان'],
                      ['تنظيمها'],
                      ['ضمان حمايه ممارستها'],
                      ['قيمه اسلاميه'],
                      ['قيمه انسانيه'],
                      ['قيمه اجتماعيه'],
                      ['المساواه'],
                      ['رفض التمييز العنصري']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص نص الإسلام وحقوق الإنسان مع أهم الحقوق والحجج والقيم.',
  'expected_status': 'success',
  'required_groups': [['الاسلام'],
                      ['حقوق الانسان'],
                      ['تكريم الانسان'],
                      ['الحق في الحياه'],
                      ['حريه العقيده'],
                      ['السلام'],
                      ['الحرب'],
                      ['المراه'],
                      ['المساواه'],
                      ['العنصريه'],
                      ['الصحيفه'],
                      ['القران'],
                      ['الحديث'],
                      ['قيمه اسلاميه'],
                      ['قيمه انسانيه'],
                      ['قيمه اجتماعيه']]},
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
        "الاختبار الأولي لنص الإسلام وحقوق الإنسان"
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
        "فلتر المصدر: alislam-ohqoq-alinsan.pdf"
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
