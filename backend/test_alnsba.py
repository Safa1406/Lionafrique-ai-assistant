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
EXPECTED_SOURCE = "alnsba (1).pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-nisba-lesson-baseline"

JSON_REPORT = Path("alnsba_test_results.json")
CSV_REPORT = Path("alnsba_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف النسبة',
  'endpoint': '/ask',
  'question': 'ما تعريف النسبة حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الحاق ياء مشدده'],
                      ['مكسور ما قبلها'],
                      ['اخر الاسم'],
                      ['نسبه شيء الي شيء اخر']]},
 {'category': 'وظيفة النسبة',
  'endpoint': '/ask',
  'question': 'ما وظيفة النسبة في اللغة العربية؟',
  'expected_status': 'success',
  'required_groups': [['وصف المنسوب'], ['توضيحه']]},
 {'category': 'عناصر النسبة',
  'endpoint': '/ask',
  'question': 'ما عنصرا النسبة، وما الفرق بين المنسوب والمنسوب إليه؟',
  'expected_status': 'success',
  'required_groups': [['المنسوب اليه'],
                      ['الاسم الاصلي'],
                      ['تلحق باخره ياء النسبه'],
                      ['المنسوب'],
                      ['اضيفت الي اخره ياء النسبه']]},
 {'category': 'أمثلة العناصر',
  'endpoint': '/ask',
  'question': 'ما أمثلة المنسوب إليه والمنسوب الواردة في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['شجره'],
                      ['عصا'],
                      ['الصدي'],
                      ['انشاء'],
                      ['شجري'],
                      ['عصوي'],
                      ['الصدوي'],
                      ['انشائي']]},
 {'category': 'تاء التأنيث',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم المختوم بتاء التأنيث؟',
  'expected_status': 'success',
  'required_groups': [['تحذف تاء التانيث'],
                      ['تزاد ياء النسبه المشدده'],
                      ['كسر ما قبلها'],
                      ['شجره شجري'],
                      ['حضاره حضاري']]},
 {'category': 'الثلاثي المكسور العين',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم الثلاثي المكسور العين؟',
  'expected_status': 'success',
  'required_groups': [['فتح عينه'], ['ياء النسبه المشدده'], ['ملك ملكي'], ['نمر نمري']]},
 {'category': 'فعيلة بالحرف الصحيح',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم على وزن فعيلة إذا كان ثانيه حرفا صحيحا غير مكرر؟',
  'expected_status': 'success',
  'required_groups': [['تحذف التاء والياء'],
                      ['تفتح العين'],
                      ['ياء النسبه المشدده'],
                      ['صحيفه صحفي'],
                      ['طبيعه طبعي'],
                      ['جهينه جهني']]},
 {'category': 'فعيلة بحرف علة أو مكرر',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم على وزن فعيلة إذا كان ثانيه حرف علة أو مكررا؟',
  'expected_status': 'success',
  'required_groups': [['تبقي الياء'], ['تحذف التاء'], ['ياء النسبه المشدده'], ['حقيقه حقيقي']]},
 {'category': 'تعريف المقصور',
  'endpoint': '/ask',
  'question': 'ما تعريف الاسم المقصور حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['اسم'], ['مختوما بالالف المقصوره'], ['الممدوده']]},
 {'category': 'المقصور ألفه ثالثة',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم المقصور إذا كانت ألفه ثالثة؟',
  'expected_status': 'success',
  'required_groups': [['تقلب الالف واوا'], ['عصا'], ['عصوي'], ['ياء النسبه']]},
 {'category': 'المقصور ألفه رابعة متحرك الثاني',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم المقصور إذا كانت ألفه رابعة وثانيه متحرك؟',
  'expected_status': 'success',
  'required_groups': [['تحذف الالف'], ['كندا'], ['كندي'], ['الحرف الثاني متحرك']]},
 {'category': 'المقصور ألفه رابعة ساكن الثاني',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم المقصور إذا كانت ألفه رابعة وثانيه ساكن؟',
  'expected_status': 'success',
  'required_groups': [['تحذف الالف'], ['او تقلب واوا'], ['معني'], ['معنوي'], ['ثانيه ساكن']]},
 {'category': 'المقصور ألفه خامسة أو سادسة',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم المقصور إذا كانت ألفه خامسة أو سادسة؟',
  'expected_status': 'success',
  'required_groups': [['تحذف الالف'], ['مرتضي'], ['مستبقي'], ['ياء النسبه']]},
 {'category': 'تعريف المنقوص',
  'endpoint': '/ask',
  'question': 'ما تعريف الاسم المنقوص حسب درس النسبة؟',
  'expected_status': 'success',
  'required_groups': [['الاسم المختوم بالياء']]},
 {'category': 'المنقوص ياؤه ثالثة',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم المنقوص إذا كانت ياؤه ثالثة؟',
  'expected_status': 'success',
  'required_groups': [['تقلب الياء واوا'],
                      ['تكسر الواو'],
                      ['يفتح ما قبلها'],
                      ['الصدي'],
                      ['الصدوي']]},
 {'category': 'المنقوص ياؤه رابعة',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم المنقوص إذا كانت ياؤه رابعة؟',
  'expected_status': 'success',
  'required_groups': [['تحذف الياء'],
                      ['او تقلب الياء واوا'],
                      ['الداعي'],
                      ['الداعوي'],
                      ['ياء النسبه']]},
 {'category': 'المنقوص ياؤه خامسة أو سادسة',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم المنقوص إذا كانت ياؤه خامسة أو سادسة؟',
  'expected_status': 'success',
  'required_groups': [['تحذف ياوه'], ['المقتدي'], ['المستجدي'], ['ياء النسبه المشدده']]},
 {'category': 'تعريف الممدود',
  'endpoint': '/ask',
  'question': 'ما تعريف الاسم الممدود حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['اسم ختم بهمزه'], ['قبلها الف ممدوده']]},
 {'category': 'الممدود همزته أصلية',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم الممدود إذا كانت همزته أصلية؟',
  'expected_status': 'success',
  'required_groups': [['تبقي الهمزه'], ['انشاء'], ['انشائي'], ['ياء النسبه']]},
 {'category': 'الممدود همزته للتأنيث',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم الممدود إذا كانت همزته زائدة للتأنيث؟',
  'expected_status': 'success',
  'required_groups': [['تقلب الهمزه واوا'], ['صفراء'], ['صفراوي']]},
 {'category': 'الممدود همزته منقلبة عن واو',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم الممدود إذا كانت همزته منقلبة عن واو؟',
  'expected_status': 'success',
  'required_groups': [['تبقي الهمزه'],
                      ['او تقلب الهمزه واوا'],
                      ['رجاء'],
                      ['رجائي'],
                      ['رجاوي']]},
 {'category': 'الممدود همزته منقلبة عن ياء',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم الممدود إذا كانت همزته منقلبة عن ياء؟',
  'expected_status': 'success',
  'required_groups': [['تبقي الهمزه'],
                      ['او تقلب الهمزه واوا'],
                      ['اجراء'],
                      ['اجرائي'],
                      ['اجراوي']]},
 {'category': 'المثنى والجمع',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى المثنى والجمع، وما أمثلة ذلك؟',
  'expected_status': 'success',
  'required_groups': [['يردان الي المفرد'],
                      ['ياء مشدده'],
                      ['قمران قمري'],
                      ['نجوم نجمي'],
                      ['موحدون موحدي']]},
 {'category': 'المركب الإضافي غير الكنية',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى المركب الإضافي إذا لم يكن كنية؟',
  'expected_status': 'success',
  'required_groups': [['ينسب الي صدره'],
                      ['الجزء الاول'],
                      ['نور الدين نوري'],
                      ['بدر الدين بدري']]},
 {'category': 'المركب الإضافي الكنية',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى المركب الإضافي إذا كان كنية مسبوقة بأب أو أم أو ابن؟',
  'expected_status': 'success',
  'required_groups': [['ينسب الي عجزه'],
                      ['الجزء الثاني'],
                      ['ابو بكر بكري'],
                      ['ابن طالب طالبي']]},
 {'category': 'المركب المزجي والإسنادي',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى المركب المزجي والإسنادي؟',
  'expected_status': 'success',
  'required_groups': [['الجزء الاول'], ['بعلبك بعلي'], ['جاد الحق جادي']]},
 {'category': 'انتقال الإعراب',
  'endpoint': '/ask',
  'question': 'إلى أين ينتقل الإعراب عند صياغة الاسم المنسوب؟',
  'expected_status': 'success',
  'required_groups': [['ينتقل الاعراب'], ['الي الياء المشدده']]},
 {'category': 'الثلاثي المحذوف اللام',
  'endpoint': '/ask',
  'question': 'كيف ينسب إلى الاسم الثلاثي المحذوف اللام، وما أمثلته؟',
  'expected_status': 'success',
  'required_groups': [['ترد عليه لامه'],
                      ['ابوي'],
                      ['بنوي'],
                      ['اخوي'],
                      ['دموي'],
                      ['سنوي'],
                      ['يدوي']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس النسبة مع تعريفها وعناصرها وأهم قواعد النسب إلى الأسماء المختلفة.',
  'expected_status': 'success',
  'required_groups': [['النسبه'],
                      ['ياء مشدده'],
                      ['المنسوب'],
                      ['المنسوب اليه'],
                      ['تاء التانيث'],
                      ['الثلاثي المكسور العين'],
                      ['فعيل'],
                      ['المقصور'],
                      ['المنقوص'],
                      ['الممدود'],
                      ['المثني'],
                      ['الجمع'],
                      ['المركب الاضافي'],
                      ['المركب المزجي'],
                      ['المركب الاسنادي']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما سرعة الضوء؟',
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
        "الاختبار الأولي لدرس النسبة"
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
        "فلتر المصدر: alnsba (1).pdf"
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
