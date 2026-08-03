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
EXPECTED_SOURCE = "aslob-alththir-oalighraa.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v2-fair-arabic-equivalence"

JSON_REPORT = Path("alththir_oalighraa_test_results.json")
CSV_REPORT = Path("alththir_oalighraa_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الإغراء',
  'endpoint': '/ask',
  'question': 'ما تعريف أسلوب الإغراء؟',
  'expected_status': 'success',
  'required_groups': [['تنبيه'],
                      ['المخاطب'],
                      ['امر محمود'],
                      ['يفعله', 'يلزمه'],
                      ['مفعول به'],
                      ['الزم', 'التزم']]},
 {'category': 'تركيب الإغراء',
  'endpoint': '/ask',
  'question': 'مم تتكون جملة الإغراء؟',
  'expected_status': 'success',
  'required_groups': [['جمله فعليه'],
                      ['حذف'],
                      ['الفعل'],
                      ['فاعله', 'الفاعل'],
                      ['المفعول به']]},
 {'category': 'صور الإغراء',
  'endpoint': '/ask',
  'question': 'ما صور الاسم المغرى به؟',
  'expected_status': 'success',
  'required_groups': [['مفرد'], ['مكرر'], ['معطوف']]},
 {'category': 'الإغراء المفرد',
  'endpoint': '/ask',
  'question': 'اذكر مثالا على الإغراء بالمفرد.',
  'expected_status': 'success',
  'required_groups': [['الاجتهاد'], ['جماعه']]},
 {'category': 'الإغراء المكرر',
  'endpoint': '/ask',
  'question': 'اذكر مثالا على الإغراء بالتكرار.',
  'expected_status': 'success',
  'required_groups': [['الاجتهاد'], ['مكرر', 'الاجتهاد الاجتهاد']]},
 {'category': 'الإغراء المعطوف',
  'endpoint': '/ask',
  'question': 'اذكر مثالا على الإغراء بالعطف.',
  'expected_status': 'success',
  'required_groups': [['الاجتهاد'], ['الانضباط'], ['عطف', 'معطوف']]},
 {'category': 'تعريف التحذير',
  'endpoint': '/ask',
  'question': 'ما تعريف أسلوب التحذير؟',
  'expected_status': 'success',
  'required_groups': [['تنبيه'],
                      ['المخاطب'],
                      ['امر غير محمود'],
                      ['يجتنبه'],
                      ['مفعول به'],
                      ['احذر']]},
 {'category': 'تركيب التحذير',
  'endpoint': '/ask',
  'question': 'مم تتكون جملة التحذير؟',
  'expected_status': 'success',
  'required_groups': [['جمله فعليه'],
                      ['حذف'],
                      ['الفعل'],
                      ['فاعله', 'الفاعل'],
                      ['المفعول به']]},
 {'category': 'صور التحذير',
  'endpoint': '/ask',
  'question': 'ما صور الاسم المحذر منه؟',
  'expected_status': 'success',
  'required_groups': [['مفرد'], ['مكرر'], ['معطوف'], ['اياك', 'ضمير نصب']]},
 {'category': 'التحذير المفرد',
  'endpoint': '/ask',
  'question': 'اذكر مثالا على التحذير بالمفرد.',
  'expected_status': 'success',
  'required_groups': [['الضجيج'], ['اطفال']]},
 {'category': 'التحذير المكرر',
  'endpoint': '/ask',
  'question': 'اذكر مثالا على التحذير بالتكرار.',
  'expected_status': 'success',
  'required_groups': [['الضجيج', 'الغش'], ['مكرر', 'توكيد لفظي']]},
 {'category': 'التحذير المعطوف',
  'endpoint': '/ask',
  'question': 'اذكر مثالا على التحذير بالعطف.',
  'expected_status': 'success',
  'required_groups': [['الكذب'], ['الخيانه'], ['عطف', 'معطوف']]},
 {'category': 'صيغ إياك',
  'endpoint': '/ask',
  'question': 'ما الصور الواردة للتحذير باستعمال إياك؟',
  'expected_status': 'success',
  'required_groups': [['اياك الغش'], ['اياك اياك'], ['اياك والغش']]},
 {'category': 'حذف الفعل',
  'endpoint': '/ask',
  'question': 'متى يحذف الفعل وجوبا في الإغراء والتحذير؟',
  'expected_status': 'success',
  'required_groups': [['وجوبا'], ['مكرر'], ['معطوف']]},
 {'category': 'حذف الفعل',
  'endpoint': '/ask',
  'question': 'متى يجوز حذف الفعل في الإغراء والتحذير؟',
  'expected_status': 'success',
  'required_groups': [['جوازا', 'يجوز'], ['مفرد']]},
 {'category': 'الفرق',
  'endpoint': '/ask',
  'question': 'ما الفرق بين الإغراء والتحذير؟',
  'expected_status': 'success',
  'required_groups': [['الاغراء'],
                      ['امر محمود'],
                      ['التحذير'],
                      ['امر غير محمود'],
                      ['الزم', 'التزم'],
                      ['احذر']]},
 {'category': 'إعراب',
  'endpoint': '/ask',
  'question': 'أعرب الصبر في جملة: الصبر يا رجل.',
  'expected_status': 'success',
  'required_groups': [['الصبر'],
                      ['مفعول به'],
                      ['منصوب'],
                      ['الاغراء'],
                      ['الزم'],
                      ['جوازا']]},
 {'category': 'إعراب',
  'endpoint': '/ask',
  'question': 'أعرب رجل في جملة: الصبر يا رجل.',
  'expected_status': 'success',
  'required_groups': [['رجل'], ['منادى'], ['مبني'], ['الضم'], ['محل نصب']]},
 {'category': 'إعراب',
  'endpoint': '/ask',
  'question': 'أعرب كلمتي الغش في جملة: الغش الغش يا أولاد.',
  'expected_status': 'success',
  'required_groups': [['الغش'], ['مفعول به'], ['التحذير'], ['توكيد لفظي'], ['منصوب']]},
 {'category': 'إعراب',
  'endpoint': '/ask',
  'question': 'أعرب الاجتهاد والانضباط في جملة: الاجتهاد والانضباط يا تلاميذ.',
  'expected_status': 'success',
  'required_groups': [['الاجتهاد'],
                      ['مفعول به'],
                      ['منصوب'],
                      ['الانضباط'],
                      ['معطوف'],
                      ['الفتحه'],
                      ['الزم']]},
 {'category': 'إعراب إياك',
  'endpoint': '/ask',
  'question': 'أعرب إيا في جملة: إياك الكذب.',
  'expected_status': 'success',
  'required_groups': [['ضمير منفصل'],
                      ['مبني'],
                      ['السكون'],
                      ['محل نصب'],
                      ['مفعول به'],
                      ['التحذير'],
                      ['احذر']]},
 {'category': 'إعراب إياك',
  'endpoint': '/ask',
  'question': 'ما إعراب الكاف في إياك؟',
  'expected_status': 'success',
  'required_groups': [['الكاف'], ['حرف خطاب'], ['مبني'], ['الفتح'], ['لا محل']]},
 {'category': 'إعراب إياك',
  'endpoint': '/ask',
  'question': 'أعرب الكذب في جملة: إياك الكذب.',
  'expected_status': 'success',
  'required_groups': [['الكذب'],
                      ['مفعول به'],
                      ['فعل محذوف'],
                      ['احذر', 'اجتنب'],
                      ['منصوب']]},
 {'category': 'إعراب إياك',
  'endpoint': '/ask',
  'question': 'ما إعراب إيا الثانية في جملة: إياك إياك الكذب؟',
  'expected_status': 'success',
  'required_groups': [['ايا'], ['ضمير منفصل'], ['محل نصب'], ['توكيد لفظي']]},
 {'category': 'إعراب إياك',
  'endpoint': '/ask',
  'question': 'أعرب الواو والكذب في جملة: إياك والكذب.',
  'expected_status': 'success',
  'required_groups': [['الواو', 'و'],
                      ['زائده'],
                      ['لا محل'],
                      ['الكذب'],
                      ['مفعول به'],
                      ['احذر', 'اجتنب'],
                      ['منصوب']]},
 {'category': 'صياغة مختلفة',
  'endpoint': '/ask',
  'question': 'اشرح قاعدة الإغراء والتحذير باختصار.',
  'expected_status': 'success',
  'required_groups': [['الاغراء'],
                      ['امر محمود'],
                      ['التحذير'],
                      ['امر غير محمود'],
                      ['مفرد'],
                      ['مكرر'],
                      ['معطوف'],
                      ['وجوبا', 'جوازا']]},
 {'category': 'خطأ إملائي',
  'endpoint': '/ask',
  'question': 'ما تعريف اسلوب التحذير والاغرا؟',
  'expected_status': 'success',
  'required_groups': [['الاغراء'], ['محمود'], ['التحذير'], ['غير محمود']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس أسلوب التحذير والإغراء.',
  'expected_status': 'success',
  'required_groups': [['الاغراء'],
                      ['التحذير'],
                      ['مفعول به'],
                      ['مفرد'],
                      ['مكرر'],
                      ['معطوف']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص صور الإغراء والتحذير وحكم حذف الفعل.',
  'expected_status': 'success',
  'required_groups': [['مفرد'], ['مكرر'], ['معطوف'], ['وجوبا'], ['جوازا', 'يجوز'], ['اياك']]},
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
        "الاختبار النهائي لدرس أسلوب التحذير والإغراء"
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
