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
EXPECTED_SOURCE = "altdrb-ala-tkhil-hkaia-ajiba-ao-mn-alkhial-alalmi.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-wonder-scifi-story-baseline"

JSON_REPORT = Path("altdrb_hkaia_ajiba_test_results.json")
CSV_REPORT = Path("altdrb_hkaia_ajiba_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الحكاية العجيبة',
  'endpoint': '/ask',
  'question': 'ما تعريف الحكاية العجيبة حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['مجموعه من الاحداث'],
                      ['المركبه'],
                      ['المتسلسله'],
                      ['منطق'],
                      ['العجيب'],
                      ['الغريب'],
                      ['الشخصيات'],
                      ['الازمنه'],
                      ['الامكنه']]},
 {'category': 'أقسام الحكاية العجيبة',
  'endpoint': '/ask',
  'question': 'إلى كم قسم تنقسم الحكاية العجيبة، وما هما؟',
  'expected_status': 'success',
  'required_groups': [['قسمين'], ['الحكايه الخرافيه'], ['الاسطوريه'], ['قصص الخيال العلمي']]},
 {'category': 'أمثلة الحكاية الخرافية',
  'endpoint': '/ask',
  'question': 'ما الأمثلة المذكورة على الحكاية الخرافية أو الأسطورية؟',
  'expected_status': 'success',
  'required_groups': [['الف ليله وليله'], ['كليله ودمنه']]},
 {'category': 'نوع نص الصياد والعفريت',
  'endpoint': '/ask',
  'question': 'إلى أي نوع تنتمي حكاية الصياد والعفريت؟',
  'expected_status': 'success',
  'required_groups': [['حكايه'], ['عجيبه'], ['خرافيه'], ['اسطوريه']]},
 {'category': 'مصدر نص الانطلاق',
  'endpoint': '/ask',
  'question': 'ما مصدر نص الصياد والعفريت؟',
  'expected_status': 'success',
  'required_groups': [['كتاب الف ليله وليله'],
                      ['الجزء الاول'],
                      ['1999'],
                      ['دار صادر'],
                      ['الطباعه'],
                      ['النشر']]},
 {'category': 'بداية الحكاية',
  'endpoint': '/ask',
  'question': 'كيف بدأت حكاية الصياد والعفريت؟',
  'expected_status': 'success',
  'required_groups': [['رفع راسه الي السماء'],
                      ['اللهم ارزقني'],
                      ['رمي الشبكه'],
                      ['استقرت'],
                      ['جذبها'],
                      ['ثقيله']]},
 {'category': 'العثور على القمقم',
  'endpoint': '/ask',
  'question': 'ماذا وجد الصياد داخل الشبكة؟',
  'expected_status': 'success',
  'required_groups': [['قمقم'], ['نحاس اصفر'], ['مختوم برصاص'], ['خاتم سليمان بن داوود']]},
 {'category': 'خروج العفريت',
  'endpoint': '/ask',
  'question': 'كيف خرج العفريت من القمقم؟',
  'expected_status': 'success',
  'required_groups': [['دخان'],
                      ['يتصاعد'],
                      ['عنان السماء'],
                      ['يزحف علي الارض'],
                      ['يتحول الي عفريت'],
                      ['راسه في السحاب'],
                      ['رجلاه في التراب']]},
 {'category': 'خوف الصياد',
  'endpoint': '/ask',
  'question': 'كيف كان رد فعل الصياد عند رؤية العفريت؟',
  'expected_status': 'success',
  'required_groups': [['ارتعدت فرايصه'], ['جف ريقه'], ['عمي عن طريقه']]},
 {'category': 'تهديد العفريت',
  'endpoint': '/ask',
  'question': 'بماذا هدد العفريت الصياد؟',
  'expected_status': 'success',
  'required_groups': [['بقتلك'], ['هذه الساعه'], ['شر قتله']]},
 {'category': 'اعتراض الصياد',
  'endpoint': '/ask',
  'question': 'كيف اعترض الصياد على قرار العفريت بقتله؟',
  'expected_status': 'success',
  'required_groups': [['هل اصنع منك مليحا'], ['فتعاملني بالقبيح'], ['هل صممت علي قتلي']]},
 {'category': 'حيلة الصياد',
  'endpoint': '/ask',
  'question': 'ما الحيلة التي استعملها الصياد للتخلص من العفريت؟',
  'expected_status': 'success',
  'required_groups': [['لا اصدق'],
                      ['كنت في هذا القمقم'],
                      ['لا يسع يدك'],
                      ['ولا رجلك'],
                      ['حتى انظرك فيه'],
                      ['دخل القمقم'],
                      ['قطعه الرصاص'],
                      ['طبعها علي فم القمقم']]},
 {'category': 'نهاية الحكاية',
  'endpoint': '/ask',
  'question': 'كيف انتهت حكاية الصياد والعفريت؟',
  'expected_status': 'success',
  'required_groups': [['صار دخانا'],
                      ['دخل القمقم'],
                      ['قليلا قليلا'],
                      ['اغلق'],
                      ['فم القمقم'],
                      ['انتصار الصياد'],
                      ['الحيله']]},
 {'category': 'شرح المفردات',
  'endpoint': '/ask',
  'question': 'ما معاني الفرائص وتضرع ومليحا والقمقم؟',
  'expected_status': 'success',
  'required_groups': [['الفرايص عضلات الصدر'],
                      ['تضرع توسل'],
                      ['خضع'],
                      ['استسلم'],
                      ['مليحا معروفا'],
                      ['احسانا'],
                      ['القمقم الوعاء من النحاس']]},
 {'category': 'أحداث الحكاية',
  'endpoint': '/ask',
  'question': 'رتب أحداث حكاية الصياد والعفريت حسب مراحلها.',
  'expected_status': 'success',
  'required_groups': [['حاله البدايه'],
                      ['القاء الصياد شبكته'],
                      ['الحدث المحرك'],
                      ['فتح القمقم'],
                      ['خروج العفريت'],
                      ['العقده'],
                      ['قتل الصياد'],
                      ['الحل'],
                      ['تخلص الصياد'],
                      ['الحيله']]},
 {'category': 'تعريف حالة البداية',
  'endpoint': '/ask',
  'question': 'كيف ينبغي أن تكون حالة البداية في الحكاية؟',
  'expected_status': 'success',
  'required_groups': [['بدايه هاديه'],
                      ['لا تبدا باحداث متوتره'],
                      ['وصف المكان'],
                      ['تحديد الزمان'],
                      ['تقديم الشخصيات']]},
 {'category': 'حالة بداية النص',
  'endpoint': '/ask',
  'question': 'ما حالة البداية في حكاية الصياد والعفريت؟',
  'expected_status': 'success',
  'required_groups': [['القاء الصياد شبكته في البحر']]},
 {'category': 'تعريف الحدث المحرك',
  'endpoint': '/ask',
  'question': 'ما المقصود بالحدث المحرك؟',
  'expected_status': 'success',
  'required_groups': [['سبب'], ['يؤدي الي حدوث العقده'], ['التوتر'], ['المشكله']]},
 {'category': 'الحدث المحرك في النص',
  'endpoint': '/ask',
  'question': 'ما الحدث المحرك في حكاية الصياد والعفريت؟',
  'expected_status': 'success',
  'required_groups': [['فتح القمقم'], ['خروج العفريت']]},
 {'category': 'تعريف العقدة',
  'endpoint': '/ask',
  'question': 'ما المقصود بالعقدة في الحكاية؟',
  'expected_status': 'success',
  'required_groups': [['الورطه'], ['المشكله'], ['شخصيه'], ['شخصيات الحكاية']]},
 {'category': 'العقدة في النص',
  'endpoint': '/ask',
  'question': 'ما العقدة في حكاية الصياد والعفريت؟',
  'expected_status': 'success',
  'required_groups': [['استعداد العفريت'], ['لقتل الصياد']]},
 {'category': 'تعريف الحل',
  'endpoint': '/ask',
  'question': 'كيف ينبغي أن يكون حل الحكاية؟',
  'expected_status': 'success',
  'required_groups': [['تتوصل الشخصيات'], ['حل'], ['ذكيا'], ['مجديا']]},
 {'category': 'الحل في النص',
  'endpoint': '/ask',
  'question': 'ما الحل في حكاية الصياد والعفريت؟',
  'expected_status': 'success',
  'required_groups': [['تخلص الصياد'], ['العفريت'], ['انتصاره عليه'], ['الحيله']]},
 {'category': 'حالة النهاية',
  'endpoint': '/ask',
  'question': 'كيف ينبغي أن تكون حالة النهاية في الحكاية؟',
  'expected_status': 'success',
  'required_groups': [['نهايه هاديه'],
                      ['بعد التوصل الي الحل'],
                      ['تعود الاحداث'],
                      ['ما كانت عليه سابقا']]},
 {'category': 'خلخلة الترتيب',
  'endpoint': '/ask',
  'question': 'كيف يمكن خلخلة ترتيب الأحداث في قصص الخيال العلمي؟',
  'expected_status': 'success',
  'required_groups': [['البدء باحداث متوتره'],
                      ['استرجع احداث البدايه'],
                      ['البدء من النهايه'],
                      ['استرجاع الاحداث السابقه']]},
 {'category': 'تحديد الشخصيات',
  'endpoint': '/ask',
  'question': 'كيف تختار شخصيات الحكاية العجيبة أو الخيال العلمي؟',
  'expected_status': 'success',
  'required_groups': [['شخصيات خياليه'],
                      ['اسطوريه'],
                      ['خارقه'],
                      ['تتصارع'],
                      ['شخصيات عاديه'],
                      ['الواقع']]},
 {'category': 'تحديد الزمان والمكان',
  'endpoint': '/ask',
  'question': 'كيف يحدد الزمان والمكان في الحكاية العجيبة؟',
  'expected_status': 'success',
  'required_groups': [['زمن'], ['مكان'], ['عجيبين'], ['غريبين'], ['صف'], ['العجايبيه']]},
 {'category': 'صياغة الحكاية',
  'endpoint': '/ask',
  'question': 'ماذا تتطلب خطوة صياغة الحكاية؟',
  'expected_status': 'success',
  'required_groups': [['صغ'],
                      ['كل ما سبق'],
                      ['شكل حكايه'],
                      ['قصه'],
                      ['مستوفيه'],
                      ['الخطوات السابقه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص مهارة تخيل حكاية عجيبة أو من الخيال العلمي مع تعريفها وأقسامها ومراحل '
              'بنائها.',
  'expected_status': 'success',
  'required_groups': [['الحكايه العجيبه'],
                      ['الاحداث'],
                      ['العجيب'],
                      ['الغريب'],
                      ['الحكايه الخرافيه'],
                      ['الخيال العلمي'],
                      ['حاله البدايه'],
                      ['الحدث المحرك'],
                      ['العقده'],
                      ['الحل'],
                      ['حاله النهايه'],
                      ['الشخصيات'],
                      ['الزمان'],
                      ['المكان'],
                      ['صياغه الحكاية']]},
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
        "الاختبار الأولي لمهارة تخيل حكاية عجيبة أو من الخيال العلمي"
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
        "فلتر المصدر: altdrb-ala-tkhil-hkaia-ajiba-ao-mn-alkhial-alalmi.pdf"
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
