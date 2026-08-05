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
EXPECTED_SOURCE = "altdrb-ala-ktaba-sira-thatia-ao-ghiria.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-biography-writing-baseline"

JSON_REPORT = Path("altdrb_sira_test_results.json")
CSV_REPORT = Path("altdrb_sira_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف السيرة',
  'endpoint': '/ask',
  'question': 'ما تعريف السيرة حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['فن ادبي'],
                      ['تصوير حياه شخصيه'],
                      ['نقل تفاصيلها'],
                      ['محطاتها البارزه'],
                      ['القراء']]},
 {'category': 'تعريف السيرة الذاتية',
  'endpoint': '/ask',
  'question': 'ما تعريف السيرة الذاتية؟',
  'expected_status': 'success',
  'required_groups': [['فن ادبي'], ['يحكي فيه الكاتب'], ['حياته'], ['جزء منها']]},
 {'category': 'ميثاق الترجمة الذاتية',
  'endpoint': '/ask',
  'question': 'ما المقصود بميثاق الترجمة الذاتية؟',
  'expected_status': 'success',
  'required_groups': [['ميثاق'], ['يعد فيه القارئ'], ['يقول الحقيقه'], ['ما عاشه']]},
 {'category': 'ضمير السيرة الذاتية',
  'endpoint': '/ask',
  'question': 'بأي ضمير تكتب السيرة الذاتية، وما الاستثناء المذكور؟',
  'expected_status': 'success',
  'required_groups': [['ضمير المتكلم'], ['طه حسين'], ['الايام'], ['ضمير الغايب']]},
 {'category': 'عناصر السيرة الذاتية',
  'endpoint': '/ask',
  'question': 'ما العناصر التي ينبغي تحديدها في السيرة الذاتية؟',
  'expected_status': 'success',
  'required_groups': [['الحدث'],
                      ['الاحداث'],
                      ['الزمان'],
                      ['المكان'],
                      ['الكاتب'],
                      ['الشخصيه الرييسيه'],
                      ['البطل']]},
 {'category': 'مثال السيرة الذاتية',
  'endpoint': '/ask',
  'question': 'ما المثال الوارد في الوثيقة على السيرة الذاتية، ومن صاحبه؟',
  'expected_status': 'success',
  'required_groups': [['في الطفوله'], ['عبد المجيد بن جلون']]},
 {'category': 'تعريف السيرة الغيرية',
  'endpoint': '/ask',
  'question': 'ما تعريف السيرة الغيرية؟',
  'expected_status': 'success',
  'required_groups': [['يكتب المولف'],
                      ['شخصيه اخري'],
                      ['البييه'],
                      ['الزمان'],
                      ['الذاكره'],
                      ['المشاهده'],
                      ['الحياد']]},
 {'category': 'شخصية السيرة الغيرية',
  'endpoint': '/ask',
  'question': 'عن أي نوع من الشخصيات تكتب السيرة الغيرية؟',
  'expected_status': 'success',
  'required_groups': [['شخص جدير بالاهتمام'], ['مكانه في المجتمع'], ['حقق انجازات']]},
 {'category': 'ضمير السيرة الغيرية',
  'endpoint': '/ask',
  'question': 'بأي ضمير تكتب السيرة الغيرية؟',
  'expected_status': 'success',
  'required_groups': [['ضمير الغايب'], ['هو'], ['هي']]},
 {'category': 'متطلبات السيرة الغيرية',
  'endpoint': '/ask',
  'question': 'ما المتطلبات الأساسية لكتابة سيرة غيرية؟',
  'expected_status': 'success',
  'required_groups': [['تحديد وتنظيم الاحداث'],
                      ['الشخصيات الاخري'],
                      ['الزمان'],
                      ['المكان'],
                      ['السرد'],
                      ['الوصف'],
                      ['الدقه'],
                      ['الموضوعيه'],
                      ['الحياد'],
                      ['تعدد المصادر']]},
 {'category': 'عدم سبق الزمن',
  'endpoint': '/ask',
  'question': 'ماذا يعني ألا يسبق كاتب السيرة الغيرية الزمن؟',
  'expected_status': 'success',
  'required_groups': [['الا يسبق الزمن'],
                      ['ولد الشاعر الكبير'],
                      ['لم يكن شاعرا'],
                      ['لم يكن كبيرا'],
                      ['يوم ولد']]},
 {'category': 'الأعمال الأدبية والشخصية',
  'endpoint': '/ask',
  'question': 'لماذا لا ينبغي الاعتماد على الأعمال الأدبية وحدها في الدلالة على شخصية صاحبها؟',
  'expected_status': 'success',
  'required_groups': [['عباره مضلله'],
                      ['القصيده'],
                      ['حاله وجدانيه'],
                      ['لحظات معدودات'],
                      ['ربما لم يقع حقيقه'],
                      ['حلم'],
                      ['امنيه']]},
 {'category': 'المشكلات والوعظ',
  'endpoint': '/ask',
  'question': 'ما موقف الوثيقة من بناء السيرة على مشكلة أو الوعظ المباشر؟',
  'expected_status': 'success',
  'required_groups': [['الا يقيم السيره'],
                      ['مشكلات'],
                      ['المعضلات'],
                      ['الخطابه'],
                      ['الوعظ'],
                      ['اوحى بالدرس الاخلاقي'],
                      ['لم ينص عليه']]},
 {'category': 'الشخصيات الثانوية',
  'endpoint': '/ask',
  'question': 'كيف ينبغي التعامل مع الشخصيات الثانوية في السيرة الغيرية؟',
  'expected_status': 'success',
  'required_groups': [['الحيويه'],
                      ['الحركه'],
                      ['الشخصيات الثانويه'],
                      ['مراحل الحياه'],
                      ['لا يجوز الاستخفاف'],
                      ['لا يجوز جعل ادوارهم طاغيه']]},
 {'category': 'مثال السيرة الغيرية',
  'endpoint': '/ask',
  'question': 'من الشخصية التي تناولها مثال السيرة الغيرية في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الرسول محمد'], ['مكه'], ['عام الفيل']]},
 {'category': 'خلاصة الفرق',
  'endpoint': '/ask',
  'question': 'ما الفرق الأساسي بين السيرة الذاتية والسيرة الغيرية؟',
  'expected_status': 'success',
  'required_groups': [['السيره الذاتيه'],
                      ['حياته الخاصه'],
                      ['السيره الغيريه'],
                      ['حياه شخص اخر'],
                      ['الحياد'],
                      ['الموضوعيه']]},
 {'category': 'الفرق في الضمير',
  'endpoint': '/ask',
  'question': 'ما الفرق بين السيرة الذاتية والغيرية من حيث الضمير المستعمل؟',
  'expected_status': 'success',
  'required_groups': [['ضمير المتكلم'], ['ضمير الغايب']]},
 {'category': 'العلاقة بين السارد والشخصية',
  'endpoint': '/ask',
  'question': 'ما الفرق بين السيرة الذاتية والغيرية من حيث علاقة السارد بالشخصية الرئيسية؟',
  'expected_status': 'success',
  'required_groups': [['السارد'],
                      ['الشخصيه الرييسيه'],
                      ['السارد = الشخصيه الرييسيه'],
                      ['السارد ≠ الشخصيه الرييسيه']]},
 {'category': 'الرؤية السردية',
  'endpoint': '/ask',
  'question': 'ما الفرق بين السيرة الذاتية والغيرية من حيث الرؤية السردية؟',
  'expected_status': 'success',
  'required_groups': [['الرويه مع'], ['من الداخل'], ['من الخارج']]},
 {'category': 'مصادر كاتب السيرة الذاتية',
  'endpoint': '/ask',
  'question': 'على ماذا يعتمد كاتب السيرة الذاتية؟',
  'expected_status': 'success',
  'required_groups': [['ما عاشه'],
                      ['مارسه'],
                      ['تجارب'],
                      ['احداث'],
                      ['احساسه الشخصي'],
                      ['داخل نفسه']]},
 {'category': 'مصادر كاتب السيرة الغيرية',
  'endpoint': '/ask',
  'question': 'على ماذا يعتمد كاتب السيرة الغيرية؟',
  'expected_status': 'success',
  'required_groups': [['الوثايق'],
                      ['المعلومات'],
                      ['جمعها'],
                      ['الحقايق'],
                      ['دون الاحاسيس'],
                      ['المشاعر']]},
 {'category': 'استرجاع الأحداث',
  'endpoint': '/ask',
  'question': 'ما المقصود بخطوة استرجاع الأحداث في كتابة السيرة الذاتية؟',
  'expected_status': 'success',
  'required_groups': [['التذكر'],
                      ['الاحداث'],
                      ['الحياه الماضيه'],
                      ['استعادتها'],
                      ['تفاصيلها'],
                      ['بشكل سريع'],
                      ['حسب اهميتها']]},
 {'category': 'مدى الاسترجاع',
  'endpoint': '/ask',
  'question': 'ما المقصود بمدى الاسترجاع؟',
  'expected_status': 'success',
  'required_groups': [['النقطه'],
                      ['يصل اليها التذكر'],
                      ['الزمن الماضي'],
                      ['محطه'],
                      ['تقف عندها الذاكره']]},
 {'category': 'أنواع مدى الاسترجاع',
  'endpoint': '/ask',
  'question': 'ما أنواع مدى الاسترجاع الثلاثة؟',
  'expected_status': 'success',
  'required_groups': [['المدى القريب'], ['المدى البعيد'], ['المدى المتوسط']]},
 {'category': 'سعة الاسترجاع',
  'endpoint': '/ask',
  'question': 'ما المقصود بسعة الاسترجاع؟',
  'expected_status': 'success',
  'required_groups': [['مجموع الاحداث'],
                      ['مسافه معينه'],
                      ['مدى الاسترجاع'],
                      ['محطه المدى'],
                      ['لحظه التذكر'],
                      ['كبيره'],
                      ['صغيره'],
                      ['متوسطه']]},
 {'category': 'صياغة الأحداث',
  'endpoint': '/ask',
  'question': 'كيف تصاغ الأحداث بعد تجميعها في السيرة الذاتية؟',
  'expected_status': 'success',
  'required_groups': [['اسلوب حكايي'],
                      ['تسلسل الاحداث'],
                      ['التقديم'],
                      ['التاخير'],
                      ['الاستباق'],
                      ['السرد'],
                      ['الوصف'],
                      ['التعليق']]},
 {'category': 'خطوات السيرة الغيرية',
  'endpoint': '/ask',
  'question': 'ما الخطوات الأساسية لكتابة سيرة غيرية؟',
  'expected_status': 'success',
  'required_groups': [['انتقاء الشخصيه'],
                      ['جمع المعلومات'],
                      ['ترتيب المعلومات'],
                      ['صياغه الاحداث'],
                      ['الدقه'],
                      ['الموضوعيه']]},
 {'category': 'ترتيب معلومات السيرة الغيرية',
  'endpoint': '/ask',
  'question': 'كيف ترتب المعلومات عند كتابة سيرة غيرية؟',
  'expected_status': 'success',
  'required_groups': [['الولاده'],
                      ['النشاه'],
                      ['اوصاف الشخصيه'],
                      ['اعمال'],
                      ['انجازات'],
                      ['مصير الشخصيه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص مهارة كتابة سيرة ذاتية أو غيرية مع التعريف والفرق بينهما وخطوات كتابة كل '
              'نوع.',
  'expected_status': 'success',
  'required_groups': [['السيره'],
                      ['السيره الذاتيه'],
                      ['السيره الغيريه'],
                      ['ضمير المتكلم'],
                      ['ضمير الغايب'],
                      ['السارد'],
                      ['الشخصيه الرييسيه'],
                      ['الحياد'],
                      ['الموضوعيه'],
                      ['استرجاع الاحداث'],
                      ['مدى الاسترجاع'],
                      ['سعه الاسترجاع'],
                      ['صياغه الاحداث'],
                      ['انتقاء الشخصيه'],
                      ['جمع المعلومات'],
                      ['ترتيب المعلومات']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما عاصمة اليابان؟',
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
        "الاختبار الأولي لمهارة كتابة سيرة ذاتية أو غيرية"
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
        "فلتر المصدر: altdrb-ala-ktaba-sira-thatia-ao-ghiria.pdf"
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
