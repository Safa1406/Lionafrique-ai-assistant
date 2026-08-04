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
EXPECTED_SOURCE = "alibdal.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-ibdal-baseline"

JSON_REPORT = Path("alibdal_test_results.json")
CSV_REPORT = Path("alibdal_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الإبدال',
  'endpoint': '/ask',
  'question': 'ما تعريف الإبدال حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['تغيير حرف بحرف'], ['يزال المبدل منه'], ['يوضع المبدل مكانه']]},
 {'category': 'السماعي والقياسي',
  'endpoint': '/ask',
  'question': 'ما الفرق بين الإبدال السماعي والإبدال القياسي؟',
  'expected_status': 'success',
  'required_groups': [['سماعي'], ['مرجعه متون اللغه'], ['قياسي']]},
 {'category': 'حروف الإبدال',
  'endpoint': '/ask',
  'question': 'كم عدد الحروف التي يقاس وضعها مكان غيرها، وفي أي كلمتين جمعت؟',
  'expected_status': 'success',
  'required_groups': [['عشره'], ['هدات'], ['موطيا']]},
 {'category': 'علاقة الإبدال بالإعلال',
  'endpoint': '/ask',
  'question': 'ما علاقة حروف العلة الثلاثة بالإبدال والإعلال؟',
  'expected_status': 'success',
  'required_groups': [['ثلاثه حروف عله'], ['ابدالها اعلالا'], ['بحث خاص'], ['سبق']]},
 {'category': 'تنوين المنصوب',
  'endpoint': '/ask',
  'question': 'ماذا يحدث لنون تنوين الاسم المنصوب عند الوقف؟',
  'expected_status': 'success',
  'required_groups': [['تقلب نون تنوينه الفا'], ['حين الوقف']]},
 {'category': 'مثال تنوين المنصوب',
  'endpoint': '/ask',
  'question': 'كيف نقف على كلمة قلم في جملة اشتريت قلما من أخيك؟',
  'expected_status': 'success',
  'required_groups': [['اشتريت قلما'], ['الوقف'], ['قلم']]},
 {'category': 'الواو المتطرفة',
  'endpoint': '/ask',
  'question': 'متى تقلب الواو المتطرفة همزة؟ اذكر مثال سماء.',
  'expected_status': 'success',
  'required_groups': [['اذا تطرفت الواو'],
                      ['بعد الف ساكنه'],
                      ['تقلب همزه'],
                      ['سماء'],
                      ['سماو'],
                      ['سموت']]},
 {'category': 'الياء المتطرفة',
  'endpoint': '/ask',
  'question': 'متى تقلب الياء المتطرفة همزة؟ اذكر مثال قضاء.',
  'expected_status': 'success',
  'required_groups': [['اذا تطرفت الياء'],
                      ['بعد الف ساكنه'],
                      ['تقلب همزه'],
                      ['قضاء'],
                      ['قضاي'],
                      ['قضيت']]},
 {'category': 'الألف المتطرفة',
  'endpoint': '/ask',
  'question': 'ماذا يحدث للألف إذا تطرفت بعد ألف؟',
  'expected_status': 'success',
  'required_groups': [['تقلب همزه'], ['صحراء'], ['خضراء']]},
 {'category': 'فاعل الأجوف',
  'endpoint': '/ask',
  'question': 'كيف يقع الإبدال في ألف صيغة فاعل من الفعل الأجوف؟',
  'expected_status': 'success',
  'required_groups': [['صيغه فاعل'], ['الاجوف'], ['قائل'], ['بائع'], ['قاول'], ['بايع']]},
 {'category': 'جمع فعائل',
  'endpoint': '/ask',
  'question': 'ماذا يحدث لحرف العلة الزائد ثالثا عند تكسير الاسم الصحيح على فعائل؟',
  'expected_status': 'success',
  'required_groups': [['حرف العله الزائد ثالثا'], ['المفرد الصحيح'], ['يقلب همزه'], ['فعائل']]},
 {'category': 'أمثلة فعائل',
  'endpoint': '/ask',
  'question': 'ما جموع سحابة وصحيفة وعجوز على وزن فعائل؟',
  'expected_status': 'success',
  'required_groups': [['سحائب'], ['صحائف'], ['عجائز']]},
 {'category': 'اجتماع واوين',
  'endpoint': '/ask',
  'question': 'ما القاعدة إذا اجتمعت في أول الكلمة واوان وكانت الثانية أصلية؟',
  'expected_status': 'success',
  'required_groups': [['اجتمع في اولها واوان'], ['الثانيه اصليه'], ['قلب اولاهما همزه']]},
 {'category': 'جمع الواقية والواصلة',
  'endpoint': '/ask',
  'question': 'كيف تجمع الواقية والواصلة جمع تكسير بعد اجتماع الواوين؟',
  'expected_status': 'success',
  'required_groups': [['الاواقي'], ['الاواصل'], ['الوواقي'], ['الوواصل']]},
 {'category': 'تصغير ويصل',
  'endpoint': '/ask',
  'question': 'كيف يقع الإبدال في تصغير كلمة ويصل؟',
  'expected_status': 'success',
  'required_groups': [['اويصل'], ['وويصل'], ['قلب اولاهما همزه']]},
 {'category': 'إبدال فاء المثال تاء',
  'endpoint': '/ask',
  'question': 'ما قاعدة إبدال فاء المثال في وزن افتعل؟',
  'expected_status': 'success',
  'required_groups': [['تقلب فاء المثال تاء'], ['وزن افتعل']]},
 {'category': 'أمثلة فاء المثال',
  'endpoint': '/ask',
  'question': 'كيف صارت أوتصل وأوتقى وايتسر إلى اتصل واتقى واتسر؟',
  'expected_status': 'success',
  'required_groups': [['اتصل'],
                      ['اتقي'],
                      ['اتسر'],
                      ['اوتصل'],
                      ['اوتقي'],
                      ['ايتسر'],
                      ['الوصل'],
                      ['الوقايه'],
                      ['اليسر']]},
 {'category': 'إبدال تاء افتعل دالا',
  'endpoint': '/ask',
  'question': 'متى تقلب تاء افتعل دالا؟',
  'expected_status': 'success',
  'required_groups': [['تاء افتعل'], ['بعد دال'], ['ذال'], ['زاي'], ['تقلب دالا']]},
 {'category': 'أمثلة الدال',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة قلب تاء افتعل دالا مع أصولها.',
  'expected_status': 'success',
  'required_groups': [['ادان'], ['اتدان'], ['اذكر'], ['اتذكر'], ['ازدهر'], ['ازتهر']]},
 {'category': 'إبدال تاء افتعل طاء',
  'endpoint': '/ask',
  'question': 'متى تقلب تاء افتعل طاء؟',
  'expected_status': 'success',
  'required_groups': [['بعد صاد'], ['ضاد'], ['طاء'], ['ظاء'], ['قلبت طاء']]},
 {'category': 'سبب قلب التاء طاء',
  'endpoint': '/ask',
  'question': 'لماذا تقلب تاء افتعل طاء بعد الصاد والضاد والطاء والظاء؟',
  'expected_status': 'success',
  'required_groups': [['صعوبه الانتقال'], ['حرف شديد'], ['حرف خفيف']]},
 {'category': 'أمثلة الطاء',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة قلب تاء افتعل طاء مع أصولها.',
  'expected_status': 'success',
  'required_groups': [['اصطبر'],
                      ['اصتبر'],
                      ['اضطرب'],
                      ['اضترب'],
                      ['اطرد'],
                      ['اطترد'],
                      ['اظطلم'],
                      ['اظتلم']]},
 {'category': 'الإدغام الجائز',
  'endpoint': '/ask',
  'question': 'ما الحكم إذا كانت فاء الكلمة تاء أو دالا أو ذالا أو زايا أو صادا أو ضادا أو طاء '
              'أو ظاء في أوزان تفعل وتفاعل وتفعلل؟',
  'expected_status': 'success',
  'required_groups': [['جاز'],
                      ['اتباع القاعده العامه'],
                      ['ادغام التاء'],
                      ['الحرف الذي بعدها'],
                      ['جلب الف الوصل'],
                      ['لا يبدا بساكن']]},
 {'category': 'أمثلة الإدغام',
  'endpoint': '/ask',
  'question': 'ما أمثلة الصيغ قبل الإدغام وبعده في الملاحظة؟',
  'expected_status': 'success',
  'required_groups': [['تثاقل'],
                      ['اثاقل'],
                      ['تذاكر'],
                      ['اذاكر'],
                      ['تزين'],
                      ['ازين'],
                      ['تضرع'],
                      ['اضرع'],
                      ['تطرب'],
                      ['اطرب'],
                      ['تدحرج'],
                      ['ادحرج']]},
 {'category': 'قلب النون ميما',
  'endpoint': '/ask',
  'question': 'متى تقلب النون الساكنة أو التنوين ميما؟',
  'expected_status': 'success',
  'required_groups': [['النون الساكنه'],
                      ['التنوين'],
                      ['قبل باء'],
                      ['تقلب ميما'],
                      ['في اللفظ'],
                      ['تبقي علي حالها خطا']]},
 {'category': 'أمثلة الميم',
  'endpoint': '/ask',
  'question': 'كيف تلفظ من بغى وخطأ بينا عند قلب النون أو التنوين ميما؟',
  'expected_status': 'success',
  'required_groups': [['من بغي'], ['ممبغي'], ['خطا بينا'], ['خطامبينا']]},
 {'category': 'تاء التأنيث',
  'endpoint': '/ask',
  'question': 'كيف يوقف على تاء التأنيث في الأسماء المفردة؟',
  'expected_status': 'success',
  'required_groups': [['تاء التانيث'], ['الاسماء المفرده'], ['يوقف عليها هاء']]},
 {'category': 'أمثلة الهاء',
  'endpoint': '/ask',
  'question': 'كيف تلفظ فتاة وفاضلة عند الوقف؟',
  'expected_status': 'success',
  'required_groups': [['فتاه'], ['فاضله']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس الإبدال مع أهم القواعد والأمثلة.',
  'expected_status': 'success',
  'required_groups': [['الابدال'],
                      ['السماعي'],
                      ['القياسي'],
                      ['الالف'],
                      ['الهمزه'],
                      ['التاء'],
                      ['الدال'],
                      ['الطاء'],
                      ['الميم'],
                      ['الهاء'],
                      ['قلما'],
                      ['سماء'],
                      ['قضاء'],
                      ['قائل'],
                      ['سحائب'],
                      ['اتصل'],
                      ['ازدهر'],
                      ['اصطبر'],
                      ['ممبغي'],
                      ['فتاه']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما أسرع حيوان في العالم؟',
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
        "الاختبار الأولي لدرس الإبدال"
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
        "فلتر المصدر: alibdal.pdf"
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
