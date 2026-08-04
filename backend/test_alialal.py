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
EXPECTED_SOURCE = "alialal.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-ilal-baseline"

JSON_REPORT = Path("alialal_test_results.json")
CSV_REPORT = Path("alialal_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الإعلال',
  'endpoint': '/ask',
  'question': 'ما تعريف الإعلال حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['تغير'], ['احرف العله'], ['القلب'], ['الحذف'], ['التسكين']]},
 {'category': 'أحرف العلة',
  'endpoint': '/ask',
  'question': 'ما أحرف العلة، وما الحرف الذي يلحق بها لكثرة تغيره؟',
  'expected_status': 'success',
  'required_groups': [['الواو'], ['الالف'], ['الياء'], ['الهمزه'], ['كثره تغيرها']]},
 {'category': 'معرفة الأصل',
  'endpoint': '/ask',
  'question': 'كيف نوضح الإعلال في كلمة ونعرف أصل حرف العلة؟',
  'expected_status': 'success',
  'required_groups': [['نردها الي اصلها'], ['المضارع'], ['المصدر'], ['اصل حرف العله']]},
 {'category': 'أقسام الإعلال',
  'endpoint': '/ask',
  'question': 'ما أقسام الإعلال التي عرضتها الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الاعلال بالقلب'], ['الاعلال بالحذف'], ['الاعلال بالاسكان']]},
 {'category': 'الألف الثالثة في الأفعال',
  'endpoint': '/ask',
  'question': 'كيف ترد الألف الثالثة في دعا ورمى مع ضمائر الرفع المتحركة؟',
  'expected_status': 'success',
  'required_groups': [['دعوت'], ['رميت'], ['دعونا'], ['رمينا'], ['دعون'], ['رمين']]},
 {'category': 'الألف الرابعة فصاعدا',
  'endpoint': '/ask',
  'question': 'ماذا يحدث للألف إذا كانت رابعة فصاعدا؟ اذكر مثالي أبقى ويستدعى.',
  'expected_status': 'success',
  'required_groups': [['تقلب ياء'], ['ابقيت'], ['يستدعين']]},
 {'category': 'الألف في الأسماء',
  'endpoint': '/ask',
  'question': 'متى تنقلب الألف الثالثة واوا في الأسماء عند التثنية والجمع؟',
  'expected_status': 'success',
  'required_groups': [['اذا كان اصلها واوا'], ['عصوان'], ['عصوين'], ['رضوان'], ['رضوات']]},
 {'category': 'قلب الألف ياء',
  'endpoint': '/ask',
  'question': 'متى تقلب الألف ياء في تثنية الأسماء؟ اذكر هدى ومصطفى.',
  'expected_status': 'success',
  'required_groups': [['في غير هذه الحاله'], ['تقلب الالف ياء'], ['هديان'], ['مصطفيان']]},
 {'category': 'ياء التصغير',
  'endpoint': '/ask',
  'question': 'ماذا يحدث للألف إذا وقعت بعد ياء التصغير؟',
  'expected_status': 'success',
  'required_groups': [['تقلب ياء'], ['خطاب'], ['خطيب'], ['غزال'], ['غزيل']]},
 {'category': 'الألف بعد الضم',
  'endpoint': '/ask',
  'question': 'ماذا يحدث للألف إذا وقعت بعد حرف مضموم؟',
  'expected_status': 'success',
  'required_groups': [['تقلب واوا'], ['بايع'], ['بويع']]},
 {'category': 'الألف بعد الكسر',
  'endpoint': '/ask',
  'question': 'ماذا يحدث للألف إذا وقعت بعد حرف مكسور؟',
  'expected_status': 'success',
  'required_groups': [['تقلب ياء'], ['مفتاح'], ['مفاتيح']]},
 {'category': 'سبب قلب الألف',
  'endpoint': '/ask',
  'question': 'لماذا تقلب الألف واوا بعد الضم وياء بعد الكسر؟',
  'expected_status': 'success',
  'required_groups': [['عدم امكان تحريك الالف'], ['بالضم'], ['بالكسر']]},
 {'category': 'الواو الساكنة بعد كسر',
  'endpoint': '/ask',
  'question': 'متى تقلب الواو الساكنة ياء بعد الكسرة؟ اذكر مثالي وزن ووقت.',
  'expected_status': 'success',
  'required_groups': [['اذا سكنت'],
                      ['سبقت بكسرة'],
                      ['ميزان'],
                      ['ميقات'],
                      ['موزان'],
                      ['موقات']]},
 {'category': 'الواو المتطرفة',
  'endpoint': '/ask',
  'question': 'متى تقلب الواو المتطرفة ياء بعد الكسر؟',
  'expected_status': 'success',
  'required_groups': [['اذا تطرفت بعد كسر'], ['رضي'], ['يسترضي'], ['الداعي'], ['الداعو']]},
 {'category': 'الواو بين الكسرة والألف',
  'endpoint': '/ask',
  'question': 'متى تقلب الواو ياء إذا وقعت حشوا بين كسرة وألف؟',
  'expected_status': 'success',
  'required_groups': [['حشوا بين كسرة والف'],
                      ['الاجوف المعتل العين'],
                      ['الصيام'],
                      ['القيام'],
                      ['العياده'],
                      ['الصوام'],
                      ['القوام'],
                      ['العواده']]},
 {'category': 'اجتماع الواو والياء',
  'endpoint': '/ask',
  'question': 'ما القاعدة عند اجتماع الواو والياء الأصليتين وسكون السابقة منهما؟',
  'expected_status': 'success',
  'required_groups': [['اجتمعت الواو والياء'],
                      ['سكنت السابقه'],
                      ['تقلب الواو ياء'],
                      ['مرموي'],
                      ['مرمي'],
                      ['جريو'],
                      ['جري']]},
 {'category': 'قلب الياء واوا',
  'endpoint': '/ask',
  'question': 'متى تقلب الياء واوا؟ اذكر مثال موقن.',
  'expected_status': 'success',
  'required_groups': [['اذا سكنت الياء بعد ضمه'], ['تقلب واوا'], ['موقن'], ['ميقن']]},
 {'category': 'قلب الواو والياء ألفا',
  'endpoint': '/ask',
  'question': 'متى تقلب الواو والياء ألفا؟',
  'expected_status': 'success',
  'required_groups': [['اذا تحركت الواو او الياء'],
                      ['حركه اصليه'],
                      ['بعد حرف مفتوح'],
                      ['تقلب الفا']]},
 {'category': 'أمثلة القلب ألفا',
  'endpoint': '/ask',
  'question': 'ما أصول الكلمات رمى وغزا وقال وباع قبل قلب الواو أو الياء ألفا؟',
  'expected_status': 'success',
  'required_groups': [['رمي'], ['غزو'], ['قول'], ['بيع']]},
 {'category': 'موانع القلب ألفا',
  'endpoint': '/ask',
  'question': 'اذكر بعض الحالات المستثناة من قلب الواو والياء ألفا.',
  'expected_status': 'success',
  'required_groups': [['معتل العين'],
                      ['وليه ساكن'],
                      ['طويل'],
                      ['خورنق'],
                      ['بيان'],
                      ['غيور'],
                      ['جولان'],
                      ['هيمان'],
                      ['فتيان'],
                      ['علوي']]},
 {'category': 'الحذف لالتقاء الساكنين',
  'endpoint': '/ask',
  'question': 'متى يحذف حرف العلة بسبب التقاء الساكنين؟ اذكر الأمثلة.',
  'expected_status': 'success',
  'required_groups': [['التقي ساكنان'],
                      ['احدهما عله'],
                      ['يحذف حرف العله'],
                      ['قمت'],
                      ['بعتم'],
                      ['يخفن'],
                      ['محام'],
                      ['فتي']]},
 {'category': 'عدم الحذف',
  'endpoint': '/ask',
  'question': 'متى لا يحذف حرف العلة رغم مجيء ساكن بعده؟',
  'expected_status': 'success',
  'required_groups': [['اذا كان ما بعد العله'], ['حرفا مشددا'], ['لا حذف'], ['جاد']]},
 {'category': 'المعتل الآخر',
  'endpoint': '/ask',
  'question': 'متى تحذف علة الفعل المعتل الآخر؟',
  'expected_status': 'success',
  'required_groups': [['اذا جزم مضارعه'], ['فعل الامر'], ['حذفت علته'], ['لم يقض'], ['ارم']]},
 {'category': 'المثال الواوي',
  'endpoint': '/ask',
  'question': 'ما حكم واو المثال الواوي مكسور عين المضارع؟',
  'expected_status': 'success',
  'required_groups': [['تحذف واوه'], ['في المضارع'], ['الامر'], ['وعد'], ['يعد'], ['عد']]},
 {'category': 'الإعلال بالإسكان',
  'endpoint': '/ask',
  'question': 'ما قاعدة الإعلال بالإسكان في الواو والياء المتطرفتين؟',
  'expected_status': 'success',
  'required_groups': [['يستثقلون تحريك الواو والياء'],
                      ['المتطرفتين'],
                      ['بعد حرف متحرك'],
                      ['بالضم'],
                      ['بالكسر'],
                      ['يسكنون']]},
 {'category': 'يدعون',
  'endpoint': '/ask',
  'question': 'كيف فسرت الوثيقة الإعلال في كلمة يدعون؟',
  'expected_status': 'success',
  'required_groups': [['اصل'],
                      ['يدعوون'],
                      ['واوان ساكنتان'],
                      ['تحذف لام الكلمه'],
                      ['تبقي واو الجماعه']]},
 {'category': 'مقول',
  'endpoint': '/ask',
  'question': 'كيف صارت مقوول إلى مقول؟',
  'expected_status': 'success',
  'required_groups': [['اصلها مقوول'],
                      ['نقلنا حركه الواو'],
                      ['الساكن قبلها'],
                      ['اجتمع علتان ساكنتان'],
                      ['حذفنا الاولي'],
                      ['واو صيغه مفعول']]},
 {'category': 'مواضع قلب الواو ياء',
  'endpoint': '/ask',
  'question': 'ما المواضع الأربعة التي تقلب فيها الواو ياء؟',
  'expected_status': 'success',
  'required_groups': [['اذا سكنت بعد كسر'],
                      ['اذا تطرفت بعد كسر'],
                      ['حشوا بين كسرة والف'],
                      ['اجتمعت الواو والياء'],
                      ['سكنت السابقه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس الإعلال بالقلب والحذف والإسكان مع أهم القواعد والأمثلة.',
  'expected_status': 'success',
  'required_groups': [['الاعلال'],
                      ['احرف العله'],
                      ['القلب'],
                      ['الحذف'],
                      ['الاسكان'],
                      ['الالف'],
                      ['الواو'],
                      ['الياء'],
                      ['ميزان'],
                      ['ميقات'],
                      ['مرمي'],
                      ['موقن'],
                      ['لم يقض'],
                      ['وعد'],
                      ['يعد'],
                      ['يدعون'],
                      ['مقول']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'من أول من وصل إلى القمر؟',
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
        "الاختبار الأولي لدرس الإعلال"
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
        "فلتر المصدر: alialal.pdf"
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
