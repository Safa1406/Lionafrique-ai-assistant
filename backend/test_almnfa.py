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
EXPECTED_SOURCE = "almnfa.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-exile-text-baseline"

JSON_REPORT = Path("almnfa_test_results.json")
CSV_REPORT = Path("almnfa_test_results.csv")

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
  'question': 'من صاحب نص المنفى، وما أهم مراحل حياته وصفته وتخصصه؟',
  'expected_status': 'success',
  'required_groups': [['روم لاندو'],
                      ['1899'],
                      ['انجلترا'],
                      ['كاتب'],
                      ['مولف'],
                      ['نحات'],
                      ['مربي انجليزي'],
                      ['الثقافه العربيه الاسلاميه'],
                      ['المغرب العربي'],
                      ['1974']]},
 {'category': 'مؤلفات الكاتب',
  'endpoint': '/ask',
  'question': 'ما أهم أعمال روم لاندو ومؤلفاته الواردة في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['دعوه الي المغرب'],
                      ['فرنسا والعرب'],
                      ['الاسلام والعرب'],
                      ['سلم الرسل'],
                      ['الفن العربي']]},
 {'category': 'مجال النص ونوعه',
  'endpoint': '/ask',
  'question': 'ما مجال نص المنفى ونوعيته؟',
  'expected_status': 'success',
  'required_groups': [['القيم الوطنيه والانسانيه'], ['سيره غيريه'], ['بعد وطني']]},
 {'category': 'تحليل العنوان',
  'endpoint': '/ask',
  'question': 'حلل عنوان المنفى تركيبيا ودلاليا حسب الوثيقة.',
  'expected_status': 'success',
  'required_groups': [['مفرد'],
                      ['كلمه المنفي'],
                      ['اسم المكان'],
                      ['الفعل نفي'],
                      ['مكان ابعاد شخص'],
                      ['سبب محدد'],
                      ['فتره'],
                      ['عقابا']]},
 {'category': 'بداية النص ونهايته',
  'endpoint': '/ask',
  'question': 'ماذا تكشف بداية نص المنفى ونهايته؟',
  'expected_status': 'success',
  'required_groups': [['الشخصيات'],
                      ['الزمان'],
                      ['المكان'],
                      ['نفي الملك محمد الخامس'],
                      ['بدايه محنته'],
                      ['انسان'],
                      ['مسلم'],
                      ['مناضل']]},
 {'category': 'فرضية القراءة',
  'endpoint': '/ask',
  'question': 'ما فرضية قراءة نص المنفى؟',
  'expected_status': 'success',
  'required_groups': [['نفي الاسره الملكيه'],
                      ['معاناتهم'],
                      ['المنفي'],
                      ['صمودهم'],
                      ['سبيل الوطن']]},
 {'category': 'أعلام الأمكنة',
  'endpoint': '/ask',
  'question': 'عرّف كورسيكا ومدغشقر وتاهيتي وانتسرابي حسب الوثيقة.',
  'expected_status': 'success',
  'required_groups': [['كورسيكا'],
                      ['جزيره فرنسيه'],
                      ['البحر المتوسط'],
                      ['غربي ايطاليا'],
                      ['مدغشقر'],
                      ['المحيط الهندي'],
                      ['الساحل الجنوبي الشرقي لافريقيا'],
                      ['تاهيتي'],
                      ['بولينيسيا الفرنسيه'],
                      ['المحيط الهادي'],
                      ['انتسرابي'],
                      ['مدينه جبليه']]},
 {'category': 'شرح المصطلحات',
  'endpoint': '/ask',
  'question': 'ما معاني الغرض ومغري والولاء ولم يأل جهدا ودعاية مغرضة وسهد؟',
  'expected_status': 'success',
  'required_groups': [['الغرض الهدف'],
                      ['مغري جذاب'],
                      ['الولاء الطاعه'],
                      ['لم يال جهدا لم يدخر جهدا'],
                      ['دعايه مغرضه خبر كاذب'],
                      ['هدف مقصود'],
                      ['سهد ارق']]},
 {'category': 'المضمون العام',
  'endpoint': '/ask',
  'question': 'ما المضمون العام لنص المنفى؟',
  'expected_status': 'success',
  'required_groups': [['ظروف'],
                      ['مراحل نفي محمد الخامس'],
                      ['اسرته'],
                      ['معاناتهم الماديه'],
                      ['النفسيه'],
                      ['المنفي']]},
 {'category': 'بداية رحلة النفي',
  'endpoint': '/ask',
  'question': 'كيف بدأت رحلة نفي السلطان محمد الخامس وولديه؟',
  'expected_status': 'success',
  'required_groups': [['اقلعت الطائره'],
                      ['السلطان وولداه'],
                      ['الثانيه بعد الزوال'],
                      ['اتجاه مجهول'],
                      ['تدريب المظليين'],
                      ['لم تكن بها مقاعد']]},
 {'category': 'معاناة السفر',
  'endpoint': '/ask',
  'question': 'ما مظاهر معاناة السلطان وولديه أثناء السفر بالطائرة؟',
  'expected_status': 'success',
  'required_groups': [['يجلسوا علي الارض'],
                      ['البيجامات'],
                      ['الجلابيب الخفيفه'],
                      ['يرتعشون من البرد'],
                      ['ثمان ساعات'],
                      ['لم يتناولوا طعاما'],
                      ['ليس فيها طعام']]},
 {'category': 'موقف السلطان من الخمر',
  'endpoint': '/ask',
  'question': 'ماذا حدث عندما طلب سيدي محمد الماء في الطائرة؟',
  'expected_status': 'success',
  'required_groups': [['زجاجه من الجعه'],
                      ['مسلم'],
                      ['لا يشرب الخمر'],
                      ['الشراب الوحيد'],
                      ['العسكريين'],
                      ['يفضلون الجعه علي الماء']]},
 {'category': 'الوصول إلى كورسيكا',
  'endpoint': '/ask',
  'question': 'متى وصلت الأسرة إلى كورسيكا، وكيف استقبلها الموظفون الفرنسيون؟',
  'expected_status': 'success',
  'required_groups': [['العاشره ليلا'],
                      ['جزيره كورسيكا'],
                      ['الموظفون الفرنسيون'],
                      ['يجهلون كل شيء'],
                      ['وضعيتهم'],
                      ['الغرض من زيارتهم'],
                      ['قضاء الاجازه']]},
 {'category': 'الإقامة في كورسيكا',
  'endpoint': '/ask',
  'question': 'ما ظروف إقامة الأسرة الملكية في كورسيكا؟',
  'expected_status': 'success',
  'required_groups': [['دار الوالي'],
                      ['لم يحملوا متاعا'],
                      ['فرشاه اسنان'],
                      ['البيجامات والجلابيب'],
                      ['خال من كل تسليه'],
                      ['يمنعون من الاتصال'],
                      ['الخروج الي السوق'],
                      ['لا يملكون نقودا']]},
 {'category': 'المندوب السامي',
  'endpoint': '/ask',
  'question': 'كيف كان موقف المندوب السامي في مدغشقر من الأسرة الملكية؟',
  'expected_status': 'success',
  'required_groups': [['رجلا'], ['مزايا الانسان'], ['ليس بالسجان']]},
 {'category': 'العقيد تويا',
  'endpoint': '/ask',
  'question': 'كيف تغير موقف العقيد تويا من محمد الخامس والأسرة الملكية؟',
  'expected_status': 'success',
  'required_groups': [['رئيس رجال الدرك'],
                      ['العقيد تويا'],
                      ['لا يعرف'],
                      ['المشكل المغربي'],
                      ['الصحف الفرنسيه'],
                      ['ضحيه دعايه مغرضه'],
                      ['الموده'],
                      ['الولاء'],
                      ['الاخلاص'],
                      ['صديقا للاسره الملكيه']]},
 {'category': 'رفض الانتقال إلى تاهيتي',
  'endpoint': '/ask',
  'question': 'لماذا لم يرتح سيدي محمد لمشروع نقله إلى تاهيتي؟',
  'expected_status': 'success',
  'required_groups': [['يكره الابتعاد عن المغرب'],
                      ['يواصل ابناوه تعليمهم'],
                      ['مدغشقر'],
                      ['طلب من العقيد تويا'],
                      ['التدخل لدي فرنسا'],
                      ['ابقايه في مدغشقر']]},
 {'category': 'الإقامة في أنتسيرابي',
  'endpoint': '/ask',
  'question': 'أين تقرر أن تقيم الأسرة الملكية بعد قبول رغبة سيدي محمد؟',
  'expected_status': 'success',
  'required_groups': [['قبلت رغبته'], ['الاسره الملكيه'], ['انتسيرابي']]},
 {'category': 'اهتمام الملك بالمغرب',
  'endpoint': '/ask',
  'question': 'كيف كان محمد الخامس يتابع أخبار المغرب من المنفى؟',
  'expected_status': 'success',
  'required_groups': [['المغرب'],
                      ['اهم ما يشغل باله'],
                      ['طوال النهار'],
                      ['الاذاعه'],
                      ['الصحف'],
                      ['الاخبار سييه'],
                      ['سهد'],
                      ['يصلي حتي الفجر']]},
 {'category': 'أبعاد شخصية الملك',
  'endpoint': '/ask',
  'question': 'كيف وصف النص محمد الخامس بوصفه إنسانا ومسلما ومناضلا؟',
  'expected_status': 'success',
  'required_groups': [['انسانا'],
                      ['يتالم'],
                      ['مسلما'],
                      ['يقبل قدره'],
                      ['مناضلا'],
                      ['يصمد'],
                      ['حقوق بلاده']]},
 {'category': 'معجم المعاناة',
  'endpoint': '/ask',
  'question': 'اذكر مظاهر معاناة الملك وأسرته الواردة في المعجم الدالي.',
  'expected_status': 'success',
  'required_groups': [['يجلسوا علي الارض'],
                      ['البيجامات'],
                      ['يرتعشون من البرد'],
                      ['لم يتناولوا طعاما'],
                      ['لم يحملوا متاعا'],
                      ['فرشاه اسنان'],
                      ['خال من كل تسليه'],
                      ['يمنعون من الاتصال'],
                      ['لا يملكون نقودا']]},
 {'category': 'معجم الوطنية',
  'endpoint': '/ask',
  'question': 'ما الألفاظ والمواقف الدالة على وطنية الملك محمد الخامس؟',
  'expected_status': 'success',
  'required_groups': [['المغرب'],
                      ['اهم ما يشغل باله'],
                      ['اخباره'],
                      ['الاذاعه والصحف'],
                      ['يصلي حتي الفجر'],
                      ['مناضلا'],
                      ['حقوق بلاده']]},
 {'category': 'أحداث النص',
  'endpoint': '/ask',
  'question': 'رتب أحداث نص المنفى بوصفه سيرة غيرية.',
  'expected_status': 'success',
  'required_groups': [['نفي الملك محمد الخامس'],
                      ['مكان مجهول'],
                      ['ظروف مفاجيه وقاسيه'],
                      ['كورسيكا'],
                      ['استمرار معاناتهم'],
                      ['مدغشقر'],
                      ['العقيد تويا'],
                      ['صديقا'],
                      ['انشغال الملك باخبار بلاده']]},
 {'category': 'الشخصيات',
  'endpoint': '/ask',
  'question': 'ما الشخصيات الواردة في نص المنفى؟',
  'expected_status': 'success',
  'required_groups': [['محمد الخامس'],
                      ['ولداه'],
                      ['العقيد تويا'],
                      ['الموظفون الفرنسيون'],
                      ['المندوب السامي'],
                      ['الوالي'],
                      ['العسكريون']]},
 {'category': 'الزمان',
  'endpoint': '/ask',
  'question': 'ما المؤشرات الزمنية الواردة في نص المنفى؟',
  'expected_status': 'success',
  'required_groups': [['الثانيه بعد الزوال'],
                      ['العاشره ليلا'],
                      ['عده ايام'],
                      ['طوال النهار'],
                      ['الفجر']]},
 {'category': 'المكان',
  'endpoint': '/ask',
  'question': 'ما الأمكنة الواردة في نص المنفى؟',
  'expected_status': 'success',
  'required_groups': [['كورسيكا'], ['مدغشقر'], ['المغرب'], ['انتسرابي'], ['تاهيتي']]},
 {'category': 'مقصدية النص',
  'endpoint': '/ask',
  'question': 'ما مقصدية رسالة نص المنفى؟',
  'expected_status': 'success',
  'required_groups': [['تاريخ حدث منفي الملك محمد الخامس'],
                      ['معاناه البعد عن الوطن'],
                      ['الحريه'],
                      ['الاستقلال'],
                      ['صدق وطنيته'],
                      ['مناهضه الاحتلال'],
                      ['الصمود'],
                      ['نكران الذات'],
                      ['مصلحه الوطن والشعب']]},
 {'category': 'قيم النص',
  'endpoint': '/ask',
  'question': 'ما القيم الوطنية والإنسانية في نص المنفى؟',
  'expected_status': 'success',
  'required_groups': [['قيمه وطنيه'],
                      ['وطنيه الملك محمد الخامس'],
                      ['تشبثه بوطنه'],
                      ['الحريه والاستقلال'],
                      ['قيمه انسانيه'],
                      ['اخلاق الملك'],
                      ['تقدير الاجانب'],
                      ['احترامهم']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص نص المنفى مع مراحل النفي والمعاناة والشخصيات والقيم والمقصدية.',
  'expected_status': 'success',
  'required_groups': [['محمد الخامس'],
                      ['الاسره الملكيه'],
                      ['كورسيكا'],
                      ['مدغشقر'],
                      ['العقيد تويا'],
                      ['المعاناه'],
                      ['الوطن'],
                      ['المغرب'],
                      ['الحريه'],
                      ['الاستقلال'],
                      ['القيمه الوطنيه'],
                      ['القيمه الانسانيه']]},
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
        "الاختبار الأولي لنص المنفى"
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
        "فلتر المصدر: almnfa.pdf"
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
