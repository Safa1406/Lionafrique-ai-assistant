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
EXPECTED_SOURCE = "asm-alfaal-osigh-almbalgha-oamlhma.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-active-participle-intensive-baseline"

JSON_REPORT = Path("asm_alfaal_osigh_almbalgha_oamlhma_test_results.json")
CSV_REPORT = Path("asm_alfaal_osigh_almbalgha_oamlhma_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف اسم الفاعل',
  'endpoint': '/ask',
  'question': 'ما تعريف اسم الفاعل؟',
  'expected_status': 'success',
  'required_groups': [['اسم مشتق'], ['من قام بالفعل', 'القائم بالفعل']]},
 {'category': 'صياغة اسم الفاعل',
  'endpoint': '/ask',
  'question': 'كيف يصاغ اسم الفاعل من الفعل الثلاثي؟',
  'expected_status': 'success',
  'required_groups': [['الفعل الثلاثي', 'الثلاثي'], ['فاعل']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الفاعل من الفعل وقف؟',
  'expected_status': 'success',
  'required_groups': [['وقف'], ['واقف']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الفاعل من الفعل كتب؟',
  'expected_status': 'success',
  'required_groups': [['كتب'], ['كاتب']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الفاعل من الفعل عمل؟',
  'expected_status': 'success',
  'required_groups': [['عمل'], ['عامل']]},
 {'category': 'صياغة غير الثلاثي',
  'endpoint': '/ask',
  'question': 'كيف يصاغ اسم الفاعل من الفعل غير الثلاثي؟',
  'expected_status': 'success',
  'required_groups': [['مضارعه'],
                      ['حرف المضارعه'],
                      ['ميما مضمومه', 'ميم مضمومه'],
                      ['كسر ما قبل الاخر']]},
 {'category': 'مثال غير ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الفاعل من الفعل استنتج؟',
  'expected_status': 'success',
  'required_groups': [['استنتج'], ['مستنتج']]},
 {'category': 'مثال غير ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الفاعل من الفعل أسلم؟',
  'expected_status': 'success',
  'required_groups': [['اسلم'], ['مسلم']]},
 {'category': 'مثال غير ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الفاعل من الفعل انفتح؟',
  'expected_status': 'success',
  'required_groups': [['انفتح'], ['منفتح']]},
 {'category': 'عمل اسم الفاعل',
  'endpoint': '/ask',
  'question': 'ما عمل اسم الفاعل عندما يعمل عمل فعله؟',
  'expected_status': 'success',
  'required_groups': [['عمل فعله'],
                      ['المبني للمعلوم'],
                      ['رفع', 'يرفع'],
                      ['الفاعل'],
                      ['نصب', 'ينصب'],
                      ['المفعول به']]},
 {'category': 'حالات العمل',
  'endpoint': '/ask',
  'question': 'في كم حالة يعمل اسم الفاعل، وما هما؟',
  'expected_status': 'success',
  'required_groups': [['حالتين', 'حالين'],
                      ['مقترن ب ال', 'مقترن بال'],
                      ['مجرد من ال', 'خلا من ال']]},
 {'category': 'المقترن بأل',
  'endpoint': '/ask',
  'question': 'متى يعمل اسم الفاعل دون شروط؟',
  'expected_status': 'success',
  'required_groups': [['مقترن ب ال', 'تحلى ب ال', 'المقترن بال'],
                      ['دون شرط', 'بدون شروط', 'لا شروط']]},
 {'category': 'المجرد من أل',
  'endpoint': '/ask',
  'question': 'ما شروط عمل اسم الفاعل المجرد من أل؟',
  'expected_status': 'success',
  'required_groups': [['الحاضر', 'الحال'], ['المستقبل', 'الاستقبال'], ['مسبوق']]},
 {'category': 'مسبوقات اسم الفاعل',
  'endpoint': '/ask',
  'question': 'بماذا يسبق اسم الفاعل المجرد من أل حتى يعمل؟',
  'expected_status': 'success',
  'required_groups': [['مبتدا'],
                      ['نفي'],
                      ['نداء'],
                      ['استفهام'],
                      ['موصوف', 'صفه'],
                      ['ناسخ']]},
 {'category': 'تطبيق شروط العمل',
  'endpoint': '/ask',
  'question': 'لماذا يعمل اسم الفاعل منظم في جملة: هل القائد منظم صفوفه؟',
  'expected_status': 'success',
  'required_groups': [['مجرد من ال'], ['الحاضر', 'المستقبل'], ['استفهام']]},
 {'category': 'تعريف صيغة المبالغة',
  'endpoint': '/ask',
  'question': 'ما تعريف صيغة المبالغة؟',
  'expected_status': 'success',
  'required_groups': [['صيغه مشتقه', 'مشتق'],
                      ['يقوم بالفعل بكثره', 'الاكثار في الفعل'],
                      ['اتصافا شديدا', 'المبالغه']]},
 {'category': 'أوزان المبالغة',
  'endpoint': '/ask',
  'question': 'ما الأوزان الخمسة لصيغ المبالغة؟',
  'expected_status': 'success',
  'required_groups': [['فعال'], ['فعول'], ['مفعال'], ['فعيل'], ['فعل']]},
 {'category': 'وزن صيغة المبالغة',
  'endpoint': '/ask',
  'question': 'ما وزن صيغة المبالغة سماع؟',
  'expected_status': 'success',
  'required_groups': [['سماع'], ['فعال']]},
 {'category': 'وزن صيغة المبالغة',
  'endpoint': '/ask',
  'question': 'ما وزن صيغة المبالغة شكور؟',
  'expected_status': 'success',
  'required_groups': [['شكور'], ['فعول']]},
 {'category': 'وزن صيغة المبالغة',
  'endpoint': '/ask',
  'question': 'ما وزن صيغة المبالغة معوان؟',
  'expected_status': 'success',
  'required_groups': [['معوان'], ['مفعال']]},
 {'category': 'وزن صيغة المبالغة',
  'endpoint': '/ask',
  'question': 'ما وزن صيغة المبالغة حليم؟',
  'expected_status': 'success',
  'required_groups': [['حليم'], ['فعيل']]},
 {'category': 'وزن صيغة المبالغة',
  'endpoint': '/ask',
  'question': 'ما وزن صيغة المبالغة فهم؟',
  'expected_status': 'success',
  'required_groups': [['فهم'], ['فعل']]},
 {'category': 'عمل صيغة المبالغة',
  'endpoint': '/ask',
  'question': 'كيف تعمل صيغة المبالغة؟',
  'expected_status': 'success',
  'required_groups': [['عمل فعلها المتعدي', 'تعمل عمل'],
                      ['اسم الفاعل'],
                      ['نفس الحالات', 'نفس الشروط']]},
 {'category': 'مثال صيغة المبالغة',
  'endpoint': '/ask',
  'question': 'ما وزن صيغة المبالغة غفور؟',
  'expected_status': 'success',
  'required_groups': [['غفور'], ['فعول']]},
 {'category': 'مصدر صيغ المبالغة',
  'endpoint': '/ask',
  'question': 'من أي نوع من الأفعال تصاغ صيغ المبالغة غالبا؟',
  'expected_status': 'success',
  'required_groups': [['متعديه', 'الفعل المتعدي'],
                      ['قل', 'نادرا'],
                      ['الفعل اللازم', 'اللازم']]},
 {'category': 'المذكر والمؤنث',
  'endpoint': '/ask',
  'question': 'ما صيغ المبالغة التي يستوي فيها المذكر والمؤنث، وما الأمثلة الواردة؟',
  'expected_status': 'success',
  'required_groups': [['فعول'],
                      ['مفعال'],
                      ['مفعل'],
                      ['مفعيل'],
                      ['رجل معطير'],
                      ['امراه معطير'],
                      ['رجل رووم'],
                      ['ام رووم']]},
 {'category': 'خطأ إملائي',
  'endpoint': '/ask',
  'question': 'ما تعريف اسم الفاعل وصيغ المبالغه وكيف يصاغان ويعملان؟',
  'expected_status': 'success',
  'required_groups': [['اسم مشتق'],
                      ['فاعل'],
                      ['مضارعه'],
                      ['صيغه المبالغه', 'صيغ المبالغه'],
                      ['فعال'],
                      ['فعول'],
                      ['عمل']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس اسم الفاعل وصيغ المبالغة وعملهما.',
  'expected_status': 'success',
  'required_groups': [['اسم الفاعل'],
                      ['اسم مشتق'],
                      ['فاعل'],
                      ['غير الثلاثي'],
                      ['صيغه المبالغه', 'صيغ المبالغه'],
                      ['فعال'],
                      ['فعول'],
                      ['عمل']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص صياغة اسم الفاعل وصيغ المبالغة وشروط عملهما.',
  'expected_status': 'success',
  'required_groups': [['الثلاثي'],
                      ['فاعل'],
                      ['مضارعه'],
                      ['ميم مضمومه', 'ميما مضمومه'],
                      ['فعال'],
                      ['فعول'],
                      ['الحاضر', 'الحال'],
                      ['المستقبل', 'الاستقبال'],
                      ['ال']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما أكبر كوكب في المجموعة الشمسية؟',
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
        "الاختبار الأولي لدرس اسم الفاعل وصيغ المبالغة وعملهما"
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
