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
EXPECTED_SOURCE = "mhara-osf-rhla.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-describing-a-journey-baseline"

JSON_REPORT = Path("mhara_osf_rhla_test_results.json")
CSV_REPORT = Path("mhara_osf_rhla_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الرحلة',
  'endpoint': '/ask',
  'question': 'ما تعريف الرحلة حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الانتقال من مكان الي اخر']]},
 {'category': 'تعريف وصف الرحلة',
  'endpoint': '/ask',
  'question': 'ما المقصود بوصف الرحلة؟',
  'expected_status': 'success',
  'required_groups': [['تصوير الامكنه'],
                      ['الاشخاص'],
                      ['نقل المشاهدات'],
                      ['الوقايع'],
                      ['موضوع انشايي'],
                      ['الوصف'],
                      ['السرد']]},
 {'category': 'الفكرة المحورية',
  'endpoint': '/ask',
  'question': 'ما الفكرة المحورية لنص الانطلاق؟',
  'expected_status': 'success',
  'required_groups': [['وصف رحله ابن بطوطه'], ['طنجه'], ['مكه المكرمه']]},
 {'category': 'صاحب النص',
  'endpoint': '/ask',
  'question': 'من صاحب نص الانطلاق، وما مصدره؟',
  'expected_status': 'success',
  'required_groups': [['ابن بطوطه'], ['تحفه النظار في غرايب الامصار وعجايب الاسفار']]},
 {'category': 'مكان الانطلاق',
  'endpoint': '/ask',
  'question': 'من أين انطلقت رحلة ابن بطوطة؟',
  'expected_status': 'success',
  'required_groups': [['مدينه طنجه'], ['مسقط راسه']]},
 {'category': 'زمان الانطلاق',
  'endpoint': '/ask',
  'question': 'متى انطلقت رحلة ابن بطوطة؟',
  'expected_status': 'success',
  'required_groups': [['يوم الخميس'], ['الثاني من شهر رجب'], ['725 هجريه']]},
 {'category': 'وجهة الرحلة',
  'endpoint': '/ask',
  'question': 'ما وجهة رحلة ابن بطوطة؟',
  'expected_status': 'success',
  'required_groups': [['مكه المكرمه']]},
 {'category': 'غاية الرحلة',
  'endpoint': '/ask',
  'question': 'ما الغاية من رحلة ابن بطوطة إلى مكة؟',
  'expected_status': 'success',
  'required_groups': [['حج بيت الله الحرام'], ['زياره قبر الرسول']]},
 {'category': 'حال ابن بطوطة',
  'endpoint': '/ask',
  'question': 'كيف خرج ابن بطوطة من طنجة في بداية رحلته؟',
  'expected_status': 'success',
  'required_groups': [['منفردا'], ['رفيق'], ['انس بصحبته'], ['راكب']]},
 {'category': 'شرح المصطلحات',
  'endpoint': '/ask',
  'question': 'ما معنى الكلمات الآتية: مسقط رأسي، عوائد، أهل، أفذاذا؟',
  'expected_status': 'success',
  'required_groups': [['مكان ولادتي'], ['عادات'], ['طلع'], ['بزغ'], ['افرادا']]},
 {'category': 'رمضان في مكة',
  'endpoint': '/ask',
  'question': 'كيف كان أهل مكة يحتفلون بقدوم رمضان؟',
  'expected_status': 'success',
  'required_groups': [['ضرب الطبول'],
                      ['الدبادب'],
                      ['امير مكه'],
                      ['المسجد الحرام'],
                      ['تجديد الحصر'],
                      ['تكثير الشمع'],
                      ['المشاعل']]},
 {'category': 'ليلة السابع والعشرين',
  'endpoint': '/ask',
  'question': 'ما مكانة ليلة السابع والعشرين عند أهل مكة؟',
  'expected_status': 'success',
  'required_groups': [['اعظم الليالي'], ['الليالي المعظمه'], ['اهل مكه']]},
 {'category': 'أعمال البر',
  'endpoint': '/ask',
  'question': 'ما أعمال البر التي كان أهل مكة يقومون بها ليلة السابع والعشرين؟',
  'expected_status': 'success',
  'required_groups': [['الطواف'], ['الصلاه'], ['جماعات'], ['افرادا'], ['الاعتمار']]},
 {'category': 'الصلاة في المسجد الحرام',
  'endpoint': '/ask',
  'question': 'كيف كان أهل مكة يصلون ليلة السابع والعشرين؟',
  'expected_status': 'success',
  'required_groups': [['مايه ركعه'], ['ام القران'], ['سوره الاخلاص'], ['يكررونها عشرا']]},
 {'category': 'أماكن العبادة',
  'endpoint': '/ask',
  'question': 'أين كان الناس يتعبدون ليلة السابع والعشرين؟',
  'expected_status': 'success',
  'required_groups': [['في الحجر'], ['يطوفون بالبيت الشريف'], ['خرجوا للاعتمار']]},
 {'category': 'عناصر الرحلة',
  'endpoint': '/ask',
  'question': 'ما عناصر مهارة وصف الرحلة المستخرجة من نص ابن بطوطة؟',
  'expected_status': 'success',
  'required_groups': [['مكان الانطلاق'],
                      ['زمان الانطلاق'],
                      ['وجهه الرحله'],
                      ['غايه الرحله'],
                      ['الجوانب الموصوفه']]},
 {'category': 'الجوانب الموصوفة',
  'endpoint': '/ask',
  'question': 'ما الجوانب الموصوفة في رحلة ابن بطوطة إلى مكة؟',
  'expected_status': 'success',
  'required_groups': [['عادات اهل مكه'],
                      ['الاحتفال بقدوم رمضان'],
                      ['العبادات'],
                      ['الصلاه'],
                      ['الصيام'],
                      ['الطواف'],
                      ['الاعتمار'],
                      ['قراءه القران']]},
 {'category': 'مرحلة الاستعداد',
  'endpoint': '/ask',
  'question': 'ما العناصر التي تتضمنها مقدمة وصف الرحلة؟',
  'expected_status': 'success',
  'required_groups': [['نقطه الانطلاق'], ['زمنه'], ['وجهه الرحله'], ['غايه الرحله']]},
 {'category': 'عرض الرحلة',
  'endpoint': '/ask',
  'question': 'ما العناصر التي نركز عليها في عرض موضوع الرحلة؟',
  'expected_status': 'success',
  'required_groups': [['سرد الاحداث'], ['المرتبطه بالرحله'], ['وصف الامكنه'], ['الشخوص']]},
 {'category': 'الوصف والسرد',
  'endpoint': '/ask',
  'question': 'لماذا نعطي الأهمية للوصف أكثر من السرد في نص الرحلة؟',
  'expected_status': 'success',
  'required_groups': [['الرحله نص وصفي'],
                      ['تكثر فيه الاوصاف'],
                      ['تهيمن فيه الاسماء'],
                      ['علي الافعال']]},
 {'category': 'خاتمة الرحلة',
  'endpoint': '/ask',
  'question': 'ماذا نكتب في خاتمة وصف الرحلة؟',
  'expected_status': 'success',
  'required_groups': [['شعورنا'], ['ازاء الرحله'], ['اهميه الرحله'], ['فايدتها']]},
 {'category': 'مالقة',
  'endpoint': '/ask',
  'question': 'كيف وصف ابن بطوطة مدينة مالقة وخيراتها؟',
  'expected_status': 'success',
  'required_groups': [['احدي قواعد الاندلس'],
                      ['مرافق البر والبحر'],
                      ['كثيره الخيرات'],
                      ['الفواكه'],
                      ['العنب'],
                      ['الرمان'],
                      ['التين'],
                      ['اللوز']]},
 {'category': 'صناعة ومسجد مالقة',
  'endpoint': '/ask',
  'question': 'بم اشتهرت مالقة صناعيا، وكيف وصف ابن بطوطة مسجدها؟',
  'expected_status': 'success',
  'required_groups': [['الفخار المذهب'],
                      ['العجيب'],
                      ['مسجدها كبير الساحه'],
                      ['شهير البركه'],
                      ['صحنه'],
                      ['الحسن']]},
 {'category': 'غرناطة',
  'endpoint': '/ask',
  'question': 'كيف وصف ابن بطوطة مدينة غرناطة وخارجها؟',
  'expected_status': 'success',
  'required_groups': [['قاعده بلاد الاندلس'],
                      ['عروس مدنها'],
                      ['الانهار الكثيره'],
                      ['البساتين'],
                      ['الجنان'],
                      ['الرياض'],
                      ['القصور']]},
 {'category': 'ملك غرناطة',
  'endpoint': '/ask',
  'question': 'من كان ملك غرناطة، ولماذا لم يلتق به ابن بطوطة؟',
  'expected_status': 'success',
  'required_groups': [['السلطان ابا الحجاج يوسف'], ['ابي الوليد'], ['مرض']]},
 {'category': 'علماء غرناطة',
  'endpoint': '/ask',
  'question': 'من أبرز من لقيهم ابن بطوطة من علماء غرناطة؟',
  'expected_status': 'success',
  'required_groups': [['ابو القاسم الحسيني السبتي'],
                      ['ابو عبد الله البياني'],
                      ['ابو سعيد فرج بن قاسم']]},
 {'category': 'مسار العودة',
  'endpoint': '/ask',
  'question': 'ما المدن والأماكن التي مر بها ابن بطوطة قبل عودته إلى المغرب؟',
  'expected_status': 'success',
  'required_groups': [['رنده'],
                      ['قريه بني رياح'],
                      ['جبل الفتح'],
                      ['ركبت البحر'],
                      ['عدت الي المغرب']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس مهارة وصف رحلة.',
  'expected_status': 'success',
  'required_groups': [['الرحله'],
                      ['الانتقال من مكان الي اخر'],
                      ['وصف الرحله'],
                      ['تصوير الامكنه'],
                      ['نقل المشاهدات'],
                      ['نقطه الانطلاق'],
                      ['وجهه الرحله'],
                      ['غايه الرحله'],
                      ['سرد الاحداث'],
                      ['وصف الامكنه'],
                      ['شعورنا'],
                      ['اهميه الرحله']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص رحلتي ابن بطوطة إلى مكة والأندلس، مع إبراز مكان الانطلاق والوجهة والغاية '
              'والعادات والمدن والشخصيات والعودة.',
  'expected_status': 'success',
  'required_groups': [['ابن بطوطه'],
                      ['طنجه'],
                      ['مكه المكرمه'],
                      ['حج بيت الله الحرام'],
                      ['رمضان'],
                      ['ليله سبع وعشرين'],
                      ['مالقه'],
                      ['غرناطه'],
                      ['ابو الحجاج يوسف'],
                      ['رنده'],
                      ['بني رياح'],
                      ['جبل الفتح'],
                      ['المغرب']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'من اخترع الهاتف؟',
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
        "الاختبار الأولي لمهارة وصف رحلة"
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
        "فلتر المصدر: mhara-osf-rhla.pdf"
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
