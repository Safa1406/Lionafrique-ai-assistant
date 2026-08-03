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
EXPECTED_SOURCE = "asm-almfaol-oamlh.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v2-passive-participle-fair-inflection"

JSON_REPORT = Path("asm_almfaol_oamlh_test_results_v2.json")
CSV_REPORT = Path("asm_almfaol_oamlh_test_results_v2.csv")

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

TEST_CASES = [{'category': 'تعريف اسم المفعول',
  'endpoint': '/ask',
  'question': 'ما تعريف اسم المفعول؟',
  'expected_status': 'success',
  'required_groups': [['اسم مشتق'],
                      ['الحدث'],
                      ['من وقع عليه الفعل', 'وقع عليه فعل الفاعل']]},
 {'category': 'صياغة الثلاثي',
  'endpoint': '/ask',
  'question': 'كيف يصاغ اسم المفعول من الفعل الثلاثي؟',
  'expected_status': 'success',
  'required_groups': [['الفعل الثلاثي', 'الثلاثي'], ['مفعول']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم المفعول من الفعل وجد؟',
  'expected_status': 'success',
  'required_groups': [['وجد'], ['موجود']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم المفعول من الفعل حكم؟',
  'expected_status': 'success',
  'required_groups': [['حكم'], ['محكوم']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم المفعول من الفعل مد؟',
  'expected_status': 'success',
  'required_groups': [['مد'], ['ممدود']]},
 {'category': 'صياغة غير الثلاثي',
  'endpoint': '/ask',
  'question': 'كيف يصاغ اسم المفعول من الفعل غير الثلاثي؟',
  'expected_status': 'success',
  'required_groups': [['مضارعه'],
                      ['حرف المضارعه'],
                      ['ميما مضمومه', 'ميم مضمومه'],
                      ['فتح ما قبل الاخر']]},
 {'category': 'مثال غير ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم المفعول من الفعل كرم؟',
  'expected_status': 'success',
  'required_groups': [['كرم'], ['مكرم']]},
 {'category': 'مثال غير ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم المفعول من الفعل امتحن؟',
  'expected_status': 'success',
  'required_groups': [['امتحن'], ['ممتحن']]},
 {'category': 'مثال غير ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم المفعول من الفعل أعطى؟',
  'expected_status': 'success',
  'required_groups': [['اعطي'], ['معطي']]},
 {'category': 'عمل اسم المفعول',
  'endpoint': '/ask',
  'question': 'ما عمل اسم المفعول عندما يعمل عمل فعله؟',
  'expected_status': 'success',
  'required_groups': [['عمل فعله'], ['المبني للمجهول'], ['يرفع', 'رفع'], ['نايب الفاعل']]},
 {'category': 'نوع الفعل',
  'endpoint': '/ask',
  'question': 'هل يعمل اسم المفعول المشتق من الفعل المتعدي واللازم؟',
  'expected_status': 'success',
  'required_groups': [['نعم', 'يعمل'], ['المتعدي'], ['اللازم']]},
 {'category': 'المعرف بأل',
  'endpoint': '/ask',
  'question': 'متى يعمل اسم المفعول دون شرط؟',
  'expected_status': 'success',
  'required_groups': [['المعرف ب ال', 'مقترن ب ال', 'المقترن بال'],
                      ['دون شرط', 'بدون شرط']]},
 {'category': 'المجرد من أل',
  'endpoint': '/ask',
  'question': 'ما شروط عمل اسم المفعول المجرد من أل؟',
  'expected_status': 'success',
  'required_groups': [['الحاضر', 'الحال'], ['المستقبل', 'الاستقبال'], ['مسبوق']]},
 {'category': 'مسبوقات اسم المفعول',
  'endpoint': '/ask',
  'question': 'بماذا يسبق اسم المفعول المجرد من أل حتى يعمل؟',
  'expected_status': 'success',
  'required_groups': [['مبتدا'],
                      ['نفي'],
                      ['نداء'],
                      ['استفهام'],
                      ['موصوف', 'صفه'],
                      ['ناسخ']]},
 {'category': 'تطبيق شروط العمل',
  'endpoint': '/ask',
  'question': 'لماذا يعمل اسم المفعول محمود في جملة: المؤمن محمود فعله؟',
  'expected_status': 'success',
  'required_groups': [['مجرد من ال'],
                      ['الحاضر', 'المستقبل'],
                      ['مبتدا'],
                      ['فعل'],
                      ['نايب فاعل']]},
 {'category': 'صور نائب الفاعل',
  'endpoint': '/ask',
  'question': 'ماذا يكون نائب الفاعل إذا كان الفعل المشتق منه اسم المفعول متعديا؟',
  'expected_status': 'success',
  'required_groups': [['مفعولا به', 'مفعول به'], ['متعديا', 'الفعل المتعدي']]},
 {'category': 'صور نائب الفاعل',
  'endpoint': '/ask',
  'question': 'ماذا يكون نائب الفاعل إذا كان الفعل المشتق منه اسم المفعول لازما؟',
  'expected_status': 'success',
  'required_groups': [['جارا ومجرورا', 'جار ومجرور'],
                      ['ظرفا', 'ظرف'],
                      ['لازما', 'الفعل اللازم']]},
 {'category': 'صور نائب الفاعل',
  'endpoint': '/ask',
  'question': 'ماذا يكون نائب الفاعل إذا كان الفعل متعديا لأكثر من مفعول؟',
  'expected_status': 'success',
  'required_groups': [['مفعولا اولا', 'المفعول الاول'], ['اكثر من مفعول']]},
 {'category': 'شروط العمل',
  'endpoint': '/ask',
  'question': 'هل يعمل اسم المفعول بنفس شروط عمل اسم الفاعل؟',
  'expected_status': 'success',
  'required_groups': [['نعم', 'بنفس'], ['شروط'], ['اسم الفاعل']]},
 {'category': 'الفعل اللازم',
  'endpoint': '/ask',
  'question': 'كيف يصاغ اسم المفعول من الفعل اللازم؟',
  'expected_status': 'success',
  'required_groups': [['فعل لازم', 'الفعل اللازم'], ['ظرف'], ['مصدر'], ['جار ومجرور']]},
 {'category': 'أمثلة الفعل اللازم',
  'endpoint': '/ask',
  'question': 'اذكر مثالين من الدرس على صياغة اسم المفعول من فعل لازم.',
  'expected_status': 'success',
  'required_groups': [['السرير منوم فوقه', 'منوم فوقه'],
                      ['الارض متسابق عليها', 'متسابق عليها']]},
 {'category': 'صيغ سماعية',
  'endpoint': '/ask',
  'question': 'اذكر صيغتين سماعيتين تأتيان بمعنى اسم المفعول مع أمثلة.',
  'expected_status': 'success',
  'required_groups': [['فعيل'], ['جريح', 'قتيل'], ['فعله'], ['اكله', 'مضغه', 'طعمه']]},
 {'category': 'تشابه الصيغتين',
  'endpoint': '/ask',
  'question': 'متى يجتمع اسم الفاعل واسم المفعول على صيغة واحدة، وكيف نفرق بينهما؟',
  'expected_status': 'success',
  'required_groups': [['غير الثلاثي'], ['المضعف'], ['الاجوف'], ['بالقرينه', 'القرينه']]},
 {'category': 'مثال التشابه',
  'endpoint': '/ask',
  'question': 'اشرح دلالة كلمة مختار في قول الدرس: أختارك رئيسك فأنت مختار ورئيسك مختار.',
  'expected_status': 'success',
  'required_groups': [['انت مختار'],
                      ['رئيسك مختار'],
                      ['اسم فاعل'],
                      ['اسم مفعول'],
                      ['القرينه']]},
 {'category': 'إعراب',
  'endpoint': '/ask',
  'question': 'ما إعراب محبوبة في جملة: المجتهد محبوبة أعماله؟',
  'expected_status': 'success',
  'required_groups': [['خبر'], ['مرفوع'], ['اسم مفعول'], ['يعمل فعله المبني للمجهول']]},
 {'category': 'إعراب',
  'endpoint': '/ask',
  'question': 'ما إعراب أعماله في جملة: المجتهد محبوبة أعماله؟',
  'expected_status': 'success',
  'required_groups': [['اعمال'],
                      ['نايب فاعل'],
                      ['مرفوع'],
                      ['مضاف'],
                      ['الهاء', 'ضمير'],
                      ['مضاف اليه']]},
 {'category': 'خطأ إملائي',
  'endpoint': '/ask',
  'question': 'ما تعريف اسم المفعول وكيف يصاغ من الثلاثي وغير الثلاثي وكيف يعمل؟',
  'expected_status': 'success',
  'required_groups': [['اسم مشتق'],
                      ['مفعول'],
                      ['مضارعه'],
                      ['ميم مضمومه', 'ميما مضمومه'],
                      ['فتح ما قبل الاخر'],
                      ['المبني للمجهول'],
                      ['نايب الفاعل']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس اسم المفعول وعمله.',
  'expected_status': 'success',
  'required_groups': [['اسم المفعول'],
                      ['اسم مشتق'],
                      ['مفعول'],
                      ['غير الثلاثي'],
                      ['المبني للمجهول'],
                      ['نايب الفاعل'],
                      ['الحاضر', 'الحال'],
                      ['المستقبل', 'الاستقبال']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص صياغة اسم المفعول وشروط عمله وصور نائب الفاعل.',
  'expected_status': 'success',
  'required_groups': [['الثلاثي'],
                      ['مفعول'],
                      ['مضارعه'],
                      ['ميم مضمومه', 'ميما مضمومه'],
                      ['فتح ما قبل الاخر'],
                      ['المعرف ب ال', 'مقترن ب ال'],
                      ['المجرد من ال'],
                      ['مفعول به', 'مفعولا به'],
                      ['جار ومجرور', 'جارا ومجرورا'],
                      ['ظرف', 'ظرفا']]},
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
        "الاختبار الأولي لدرس اسم المفعول وعمله"
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
        "فلتر المصدر: مفعل"
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
