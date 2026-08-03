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
EXPECTED_SOURCE = "asmaa-alzman-oalmkan.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-time-place-nouns-baseline"

JSON_REPORT = Path("asmaa_alzman_oalmkan_test_results.json")
CSV_REPORT = Path("asmaa_alzman_oalmkan_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف أسماء الزمان والمكان',
  'endpoint': '/ask',
  'question': 'ما تعريف اسمي الزمان والمكان؟',
  'expected_status': 'success',
  'required_groups': [['صيغ مشتقه', 'اسماء مشتقه'],
                      ['زمان وقوع الفعل', 'زمن وقوع الفعل'],
                      ['مكان وقوع الفعل']]},
 {'category': 'تمييز اسم الزمان',
  'endpoint': '/ask',
  'question': 'لماذا تعد كلمة منضج في جملة: منضج بعض الفواكه فصل الشتاء، اسم زمان؟',
  'expected_status': 'success',
  'required_groups': [['منضج'], ['نضج'], ['زمان وقوعه', 'زمن وقوعه'], ['اسم زمان']]},
 {'category': 'تمييز اسم المكان',
  'endpoint': '/ask',
  'question': 'لماذا تعد كلمة ملعب في جملة: جرت المباراة في ملعب جديد، اسم مكان؟',
  'expected_status': 'success',
  'required_groups': [['ملعب'], ['لعب'], ['مكان وقوعه'], ['اسم مكان']]},
 {'category': 'صياغة الثلاثي',
  'endpoint': '/ask',
  'question': 'على أي وزنين تصاغ أسماء الزمان والمكان من الفعل الثلاثي؟',
  'expected_status': 'success',
  'required_groups': [['مفعل'], ['وزنين']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الزمان أو المكان من الفعل جلس؟',
  'expected_status': 'success',
  'required_groups': [['جلس'], ['يجلس'], ['مجلس']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الزمان أو المكان من الفعل وضع؟',
  'expected_status': 'success',
  'required_groups': [['وضع'], ['يضع'], ['موضع']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الزمان أو المكان من الفعل ركب؟',
  'expected_status': 'success',
  'required_groups': [['ركب'], ['يركب'], ['مركب']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الزمان أو المكان من الفعل دخل؟',
  'expected_status': 'success',
  'required_groups': [['دخل'], ['يدخل'], ['مدخل']]},
 {'category': 'مثال ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الزمان أو المكان من الفعل سعى؟',
  'expected_status': 'success',
  'required_groups': [['سعي'], ['يسعي'], ['مسعي']]},
 {'category': 'قاعدة الثلاثي',
  'endpoint': '/ask',
  'question': 'متى يصاغ اسم الزمان أو المكان من الثلاثي على وزن مفعل في حالة كسر عين '
              'المضارع؟',
  'expected_status': 'success',
  'required_groups': [['مكسور العين', 'كسر العين'], ['المضارع'], ['صحيح الاخر'], ['مفعل']]},
 {'category': 'قاعدة الثلاثي',
  'endpoint': '/ask',
  'question': 'ما حكم صياغة اسم الزمان والمكان من المثال الواوي الصحيح الآخر؟',
  'expected_status': 'success',
  'required_groups': [['مثال واوي'], ['صحيح الاخر'], ['مفعل'], ['موضع', 'موقع']]},
 {'category': 'قاعدة الثلاثي',
  'endpoint': '/ask',
  'question': 'على أي وزن يصاغ اسم الزمان والمكان من الفعل الثلاثي الذي جاء على غير '
              'الحالات السابقة؟',
  'expected_status': 'success',
  'required_groups': [['مفعل'], ['غير ما سبق', 'غير الحالات السابقه']]},
 {'category': 'صياغة غير الثلاثي',
  'endpoint': '/ask',
  'question': 'كيف يصاغ اسما الزمان والمكان من الفعل غير الثلاثي؟',
  'expected_status': 'success',
  'required_groups': [['اسم المفعول'],
                      ['حرف المضارعه'],
                      ['ميما مضمومه', 'ميم مضمومه'],
                      ['فتح ما قبل الاخر']]},
 {'category': 'مثال غير ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الزمان أو المكان من الفعل اجتمع؟',
  'expected_status': 'success',
  'required_groups': [['اجتمع'], ['مجتمع'], ['مفتعل']]},
 {'category': 'مثال غير ثلاثي',
  'endpoint': '/ask',
  'question': 'ما اسم الزمان أو المكان من الفعل استقبل؟',
  'expected_status': 'success',
  'required_groups': [['استقبل'], ['مستقبل'], ['مستفعل']]},
 {'category': 'صيغة مفعلة',
  'endpoint': '/ask',
  'question': 'متى يصاغ اسم المكان على وزن مفعلة، وماذا يدل هذا الوزن؟',
  'expected_status': 'success',
  'required_groups': [['اسم المكان'],
                      ['مفعله'],
                      ['كثره الشيء', 'كثرة الشيء'],
                      ['في المكان']]},
 {'category': 'مثال مفعلة',
  'endpoint': '/ask',
  'question': 'ما معنى كلمة مأسدة في قول الدرس: وفي الغابة مأسدة؟',
  'expected_status': 'success',
  'required_groups': [['ماسده', 'مأسده'], ['مكان'], ['تكثر فيه الاسود']]},
 {'category': 'مثال مفعلة',
  'endpoint': '/ask',
  'question': 'ما معنى كلمة مقمحة في قول الدرس: أصبحت السهول مقمحة؟',
  'expected_status': 'success',
  'required_groups': [['مقمحه'], ['مكان'], ['يكثر فيه القمح']]},
 {'category': 'أمثلة الثلاثي',
  'endpoint': '/ask',
  'question': 'اذكر مثالين من الدرس لاسم الزمان أو المكان من فعل ثلاثي مفتوح أو مضموم عين '
              'المضارع، ومثالين من مكسور العين.',
  'expected_status': 'success',
  'required_groups': [['مكتب', 'مدخل', 'مجال', 'منظر'], ['منزل', 'مهبط', 'مطير', 'مبيع']]},
 {'category': 'الفعل الناقص',
  'endpoint': '/ask',
  'question': 'كيف تصاغ أسماء الزمان والمكان من الفعل الناقص، وما الأمثلة الواردة؟',
  'expected_status': 'success',
  'required_groups': [['الفعل الناقص', 'ناقصا'], ['مفعل'], ['مسعي'], ['موقي'], ['مرمي']]},
 {'category': 'دلالة المثال',
  'endpoint': '/ask',
  'question': 'ماذا تدل كلمة منتظر في قول الدرس: هنا منتظر الزوار؟',
  'expected_status': 'success',
  'required_groups': [['منتظر الزوار'], ['مكان'], ['انتظارهم']]},
 {'category': 'دلالة المثال',
  'endpoint': '/ask',
  'question': 'ماذا تدل كلمة مسافر في قول الدرس: غدا مسافر الوفد؟',
  'expected_status': 'success',
  'required_groups': [['مسافر الوفد'], ['زمن', 'زمان'], ['سفره']]},
 {'category': 'تشابه الصيغ',
  'endpoint': '/ask',
  'question': 'ما الصيغ التي تجتمع على صورة واحدة في الأفعال غير الثلاثية؟',
  'expected_status': 'success',
  'required_groups': [['المصدر الميمي'],
                      ['اسم المفعول'],
                      ['اسم الزمان', 'اسما الزمان'],
                      ['اسم المكان', 'المكان']]},
 {'category': 'التفريق بالقرائن',
  'endpoint': '/ask',
  'question': 'كيف نفرق بين المصدر الميمي واسم المفعول واسمي الزمان والمكان إذا اتحدت '
              'صيغتها؟',
  'expected_status': 'success',
  'required_groups': [['بالقراين', 'بالقرائن', 'القرينه']]},
 {'category': 'أسماء سماعية',
  'endpoint': '/ask',
  'question': 'اذكر الأسماء السماعية التي وردت بالكسر على خلاف قاعدة أسماء الزمان والمكان.',
  'expected_status': 'success',
  'required_groups': [['المشرق'],
                      ['المغرب'],
                      ['المسجد'],
                      ['المنبت'],
                      ['المنجر'],
                      ['المظنه']]},
 {'category': 'حكم السماع والقياس',
  'endpoint': '/ask',
  'question': 'هل فتح الأسماء السماعية السابقة على القاعدة صحيح، وأيهما أحسن؟',
  'expected_status': 'success',
  'required_groups': [['صواب', 'صحيح'], ['مراعاه السماع احسن', 'السماع احسن']]},
 {'category': 'سؤال مركب',
  'endpoint': '/ask',
  'question': 'ما تعريف اسما الزمان والمكان وكيف يصاغان من الثلاثي وغير الثلاثي وما دلالة '
              'وزن مفعله؟',
  'expected_status': 'success',
  'required_groups': [['صيغ مشتقه', 'اسمان مشتقان'],
                      ['زمان', 'زمن'],
                      ['مكان'],
                      ['الثلاثي'],
                      ['غير الثلاثي'],
                      ['اسم المفعول'],
                      ['مفعله'],
                      ['كثره الشيء', 'كثرة الشيء']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس أسماء الزمان والمكان.',
  'expected_status': 'success',
  'required_groups': [['اسم الزمان'],
                      ['اسم المكان'],
                      ['صيغ مشتقه', 'مشتقان'],
                      ['الثلاثي'],
                      ['غير الثلاثي'],
                      ['اسم المفعول'],
                      ['مفعله'],
                      ['القراين', 'القرائن']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص صياغة اسمي الزمان والمكان من الثلاثي وغير الثلاثي، مع صيغة مفعلة '
              'والأسماء السماعية.',
  'expected_status': 'success',
  'required_groups': [['مكسور العين'],
                      ['صحيح الاخر'],
                      ['مثال واوي'],
                      ['غير الثلاثي'],
                      ['ميم مضمومه', 'ميما مضمومه'],
                      ['فتح ما قبل الاخر'],
                      ['مفعله'],
                      ['المشرق'],
                      ['المغرب'],
                      ['المسجد']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما ارتفاع جبل إفرست؟',
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
        "الاختبار الأولي لدرس أسماء الزمان والمكان"
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
