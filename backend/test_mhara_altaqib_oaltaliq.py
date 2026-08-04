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
EXPECTED_SOURCE = "mhara-altaqib-oaltaliq.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-commentary-rebuttal-baseline"

JSON_REPORT = Path("mhara_altaqib_oaltaliq_test_results.json")
CSV_REPORT = Path("mhara_altaqib_oaltaliq_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الحجاج',
  'endpoint': '/ask',
  'question': 'ما تعريف الحجاج حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['اسلوب استدلالي'],
                      ['الدفاع عن وجهه نظر'],
                      ['اقناع'],
                      ['اساليب الحجاج'],
                      ['دلائل'],
                      ['براهين']]},
 {'category': 'خطاب الحجاج',
  'endpoint': '/ask',
  'question': 'ما تعريف خطاب الحجاج؟',
  'expected_status': 'success',
  'required_groups': [['عمل عقلي'],
                      ['التواصل الانساني'],
                      ['تبادل الخطاب الفكري والثقافي'],
                      ['وجهات نظر متعارضه'],
                      ['عمليات عقليه استدلاليه'],
                      ['التاثير'],
                      ['الاقناع']]},
 {'category': 'تعريف التعقيب',
  'endpoint': '/ask',
  'question': 'ما تعريف التعقيب؟',
  'expected_status': 'success',
  'required_groups': [['الرد علي فكره الاخر'],
                      ['بتاييدها'],
                      ['بمعارضتها'],
                      ['الحجج'],
                      ['البراهين'],
                      ['الادله']]},
 {'category': 'تعريف التعليق',
  'endpoint': '/ask',
  'question': 'ما تعريف التعليق؟',
  'expected_status': 'success',
  'required_groups': [['عرض فكره الاخر'], ['باسلوب اخر'], ['شرحها'], ['توضيحها'], ['تفسيرها']]},
 {'category': 'عناصر التعقيب',
  'endpoint': '/ask',
  'question': 'ما عناصر التعقيب حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الاطروحه'],
                      ['الموقف'],
                      ['الراي'],
                      ['الحجه'],
                      ['الحجج الداعمه'],
                      ['الاطروحه البديله'],
                      ['الحجج الداعمه للاطروحه البديله']]},
 {'category': 'عناصر التعليق',
  'endpoint': '/ask',
  'question': 'ما عناصر التعليق حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الاطروحه الضمنيه'],
                      ['الصريحه'],
                      ['القراءه الشخصيه'],
                      ['التاويل الشخصي'],
                      ['الحجج الداعمه'],
                      ['الاطروحه البديله']]},
 {'category': 'أطروحة الفقهاء',
  'endpoint': '/ask',
  'question': 'ما أطروحة الفقهاء في نص قاسم أمين؟',
  'expected_status': 'success',
  'required_groups': [['الزواج عقد'], ['امتلاك الرجل'], ['المراه'], ['المتعه']]},
 {'category': 'موقف قاسم أمين',
  'endpoint': '/ask',
  'question': 'ما موقف قاسم أمين من أطروحة الفقهاء، وما سبب معارضته؟',
  'expected_status': 'success',
  'required_groups': [['يعارض'], ['راي الفقهاء'], ['تركيزه علي المتعه'], ['الزواج']]},
 {'category': 'حجة قاسم أمين',
  'endpoint': '/ask',
  'question': 'ما الحجة التي اعتمدها قاسم أمين في موقفه من الزواج؟',
  'expected_status': 'success',
  'required_groups': [['ومن اياته'],
                      ['خلق لكم من انفسكم ازواجا'],
                      ['لتسكنوا اليها'],
                      ['موده'],
                      ['رحمه']]},
 {'category': 'الأطروحة البديلة',
  'endpoint': '/ask',
  'question': 'ما الأطروحة البديلة التي اقترحها قاسم أمين، وما حجته على صحتها؟',
  'expected_status': 'success',
  'required_groups': [['اعتبار الزواج'],
                      ['الصيغه التي جاء بها القران'],
                      ['راي الفقهاء'],
                      ['يحط من شان المراه'],
                      ['النص القراني'],
                      ['يكرمها'],
                      ['يرفع من شانها']]},
 {'category': 'الجدار العازل',
  'endpoint': '/ask',
  'question': 'ما الأطروحة الضمنية في النص المتعلق بالجدار العازل؟',
  'expected_status': 'success',
  'required_groups': [['اسراييل'], ['اقامه الجدار العازل'], ['وسيله'], ['ضمان امنها']]},
 {'category': 'تعليق الجدار العازل',
  'endpoint': '/ask',
  'question': 'ما تعليق الكاتب على فكرة الجدار العازل، وما حجته؟',
  'expected_status': 'success',
  'required_groups': [['محاصره الشعب الفلسطيني'],
                      ['سجن كبير'],
                      ['الجدار العازل'],
                      ['لن يضمن'],
                      ['امن اسراييل']]},
 {'category': 'الأطروحة البديلة للجدار',
  'endpoint': '/ask',
  'question': 'ما الأطروحة البديلة في قضية الجدار العازل، وما الحجة الداعمة لها؟',
  'expected_status': 'success',
  'required_groups': [['ارجاع الحقوق'],
                      ['الشعب الفلسطيني'],
                      ['ضمان امن اسراييل'],
                      ['اختراق الجدار'],
                      ['تهديد امن الصهاينه'],
                      ['خرافه التفوق العسكري']]},
 {'category': 'عرض فكرة الآخر',
  'endpoint': '/ask',
  'question': 'ما طريقتا عرض فكرة الآخر في مهارة التعقيب والتعليق؟',
  'expected_status': 'success',
  'required_groups': [['الطريقه المباشره'], ['الطريقه غير المباشره'], ['الضمنيه']]},
 {'category': 'الطريقة المباشرة',
  'endpoint': '/ask',
  'question': 'كيف تعرض فكرة الآخر بالطريقة المباشرة؟',
  'expected_status': 'success',
  'required_groups': [['حرفيا'],
                      ['باسلوبه الخاص'],
                      ['بين مزدوجتين'],
                      ['يعتقد'],
                      ['يزعم'],
                      ['يري'],
                      ['يظن']]},
 {'category': 'الطريقة غير المباشرة',
  'endpoint': '/ask',
  'question': 'كيف تعرض فكرة الآخر بالطريقة غير المباشرة؟',
  'expected_status': 'success',
  'required_groups': [['باسلوبنا الشخصي'], ['نحتفظ بالمضمون'], ['نغير الشكل'], ['الاسلوب']]},
 {'category': 'أنواع الحجج',
  'endpoint': '/ask',
  'question': 'ما أنواع الحجج والبراهين التي يمكن تقديمها؟',
  'expected_status': 'success',
  'required_groups': [['حجج مويده'],
                      ['نوافقه الراي'],
                      ['حجج معارضه'],
                      ['نخالفه الراي'],
                      ['مويده ومعارضه'],
                      ['جزء من رايه']]},
 {'category': 'عرض الرأي الخاص',
  'endpoint': '/ask',
  'question': 'أين يعرض الكاتب رأيه الخاص، وما الوظيفة التي يؤديها؟',
  'expected_status': 'success',
  'required_groups': [['خاتمه الموضوع'],
                      ['وجهه نظرنا'],
                      ['استنتاج عام'],
                      ['استنتاج خاص'],
                      ['خلاصه']]},
 {'category': 'الحضارة الإسلامية',
  'endpoint': '/ask',
  'question': 'ما الرأي الذي يرد عليه النموذج الأول حول الحضارة الإسلامية؟',
  'expected_status': 'success',
  'required_groups': [['اتهمت حضارتنا بالانغلاق'],
                      ['عدم الانفتاح علي العالم'],
                      ['حبيسه حدودها الجغرافيه'],
                      ['رافضه الاتصال']]},
 {'category': 'حجج النموذج الأول',
  'endpoint': '/ask',
  'question': 'ما الحجج التي قدمها النموذج الأول لإثبات انفتاح الحضارة الإسلامية؟',
  'expected_status': 'success',
  'required_groups': [['الامر بالمعروف'],
                      ['النهي عن المنكر'],
                      ['التعاون'],
                      ['التعايش'],
                      ['الديانات السماويه'],
                      ['تقدم الاوربيين'],
                      ['الحضاره الاسلاميه'],
                      ['العلوم'],
                      ['المعارف']]},
 {'category': 'خلاصة النموذج الأول',
  'endpoint': '/ask',
  'question': 'ما الخلاصة التي انتهى إليها النموذج الأول حول الحضارة الإسلامية؟',
  'expected_status': 'success',
  'required_groups': [['اتهام الحضاره الاسلاميه بالانغلاق'],
                      ['مردود'],
                      ['لا اساس له من الصحه'],
                      ['منفتحه'],
                      ['علي مر العصور']]},
 {'category': 'تفاعل الحضارات',
  'endpoint': '/ask',
  'question': 'كيف يثبت النموذج الثاني أن الحضارة الإسلامية تفاعلت مع الحضارات السابقة؟',
  'expected_status': 'success',
  'required_groups': [['الخليفه المامون'],
                      ['الترجمه'],
                      ['بيت الحكمه'],
                      ['الفرس'],
                      ['الاداره'],
                      ['السياسه'],
                      ['اليونان'],
                      ['الفكر'],
                      ['الفلسفه']]},
 {'category': 'إسهام العلماء المسلمين',
  'endpoint': '/ask',
  'question': 'ما أمثلة إسهام العلماء المسلمين في تقدم أوروبا حسب النموذج الثاني؟',
  'expected_status': 'success',
  'required_groups': [['الخوارزمي'],
                      ['الرياضيات'],
                      ['ابن سينا'],
                      ['الطب'],
                      ['ابن خلدون'],
                      ['علم الاجتماع']]},
 {'category': 'تشبيه الحضارة',
  'endpoint': '/ask',
  'question': 'بم شبه الكاتب الحضارة في النموذج الثاني، وما مراحلها؟',
  'expected_status': 'success',
  'required_groups': [['كالانسان'],
                      ['تولد'],
                      ['تكبر'],
                      ['تعطي'],
                      ['تسود'],
                      ['تشيخ'],
                      ['تموت'],
                      ['اثرها'],
                      ['خالده']]},
 {'category': 'أطروحة التلفاز',
  'endpoint': '/ask',
  'question': 'ما الأطروحة التي يعقب عليها النموذج الثالث بخصوص التلفاز والطفل؟',
  'expected_status': 'success',
  'required_groups': [['التلفاز يشجع علي السلبيه'],
                      ['الطفل'],
                      ['الافكار الجاهزه'],
                      ['الكسل'],
                      ['يعطل طاقات الخيال']]},
 {'category': 'مزايا التلفاز',
  'endpoint': '/ask',
  'question': 'ما المزايا الإيجابية للتلفاز التي ذكرها الكاتب؟',
  'expected_status': 'success',
  'required_groups': [['البرامج الوثايقيه'],
                      ['ثقافات الشعوب'],
                      ['اسرار الطبيعه'],
                      ['البرامج الثقافيه'],
                      ['توسيع دايره معارفه'],
                      ['البرامج الاجتماعيه'],
                      ['البرامج الدينيه'],
                      ['الرسوم المتحركه'],
                      ['تغني خياله']]},
 {'category': 'خلاصة التلفاز',
  'endpoint': '/ask',
  'question': 'ما الخلاصة التي انتهى إليها الكاتب بشأن التلفاز؟',
  'expected_status': 'success',
  'required_groups': [['سلاح ذو حدين'],
                      ['مفيد للطفل'],
                      ['غير مفيد'],
                      ['دور الاسره'],
                      ['توجيه الطفل'],
                      ['اختيار'],
                      ['برامج مفيده'],
                      ['هادفه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس مهارة التعقيب والتعليق.',
  'expected_status': 'success',
  'required_groups': [['الحجاج'],
                      ['التعقيب'],
                      ['التعليق'],
                      ['الاطروحه'],
                      ['الحجج'],
                      ['الاطروحه البديله'],
                      ['الطريقه المباشره'],
                      ['الطريقه غير المباشره'],
                      ['الراي الخاص']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص نماذج مهارة التعقيب والتعليق المتعلقة بالزواج والجدار العازل والحضارة '
              'الإسلامية والتلفاز.',
  'expected_status': 'success',
  'required_groups': [['قاسم امين'],
                      ['الزواج'],
                      ['الموده'],
                      ['الرحمه'],
                      ['الجدار العازل'],
                      ['حقوق الشعب الفلسطيني'],
                      ['الحضاره الاسلاميه'],
                      ['الانفتاح'],
                      ['الخوارزمي'],
                      ['ابن سينا'],
                      ['ابن خلدون'],
                      ['التلفاز'],
                      ['سلاح ذو حدين'],
                      ['دور الاسره']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما أعلى جبل في قارة أوروبا؟',
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
        "الاختبار الأولي لمهارة التعقيب والتعليق"
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
        "فلتر المصدر: mhara-altaqib-oaltaliq.pdf"
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
