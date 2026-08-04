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
EXPECTED_SOURCE = "mhara-alsrd-ktaba-aliomiat.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-diary-writing-baseline"

JSON_REPORT = Path("mhara_alsrd_ktaba_aliomiat_test_results.json")
CSV_REPORT = Path("mhara_alsrd_ktaba_aliomiat_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف السرد',
  'endpoint': '/ask',
  'question': 'ما تعريف السرد حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الطريقه التي تحكي بها احداث قصه'],
                      ['السارد'],
                      ['متلق معين'],
                      ['اساليب لغويه']]},
 {'category': 'تعريف الوصف',
  'endpoint': '/ask',
  'question': 'ما تعريف الوصف حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['تمثل الاشخاص'], ['الاشياء'], ['الحالات'], ['المشاعر'], ['الانفعالات']]},
 {'category': 'تعريف اليوميات',
  'endpoint': '/ask',
  'question': 'ما تعريف اليوميات؟',
  'expected_status': 'success',
  'required_groups': [['سجل شخصي'],
                      ['يدون فيه صاحبه'],
                      ['بشكل منتظم'],
                      ['وقائع مرتبطه بحياته اليوميه']]},
 {'category': 'الفكرة المحورية',
  'endpoint': '/ask',
  'question': 'ما الفكرة المحورية لنص الانطلاق؟',
  'expected_status': 'success',
  'required_groups': [['اعتناق جيفري لانغ'], ['الاسلام']]},
 {'category': 'كاتب اليومية والحدث',
  'endpoint': '/ask',
  'question': 'من كاتب اليومية في نص الانطلاق، وما الحدث الذي يسرده؟',
  'expected_status': 'success',
  'required_groups': [['الدكتور جيفري لانغ'], ['اعتناق الاسلام'], ['اول يوم']]},
 {'category': 'الزمان والمكان',
  'endpoint': '/ask',
  'question': 'ما الزمان والمكان في يومية جيفري لانغ؟',
  'expected_status': 'success',
  'required_groups': [['اليوم الاول من اعتناق الاسلام'],
                      ['ليله اليوم الاول'],
                      ['المسجد'],
                      ['الغرفه']]},
 {'category': 'أحداث اليوم الأول',
  'endpoint': '/ask',
  'question': 'ماذا حدث لجيفري لانغ في اليوم الأول من اعتناقه الإسلام؟',
  'expected_status': 'success',
  'required_groups': [['امام المسجد'],
                      ['كتيبا'],
                      ['كيفيه الصلاه'],
                      ['قلق الطلاب المسلمين'],
                      ['قرر'],
                      ['الصلوات الخمس'],
                      ['اوقاتها']]},
 {'category': 'ليلة اليوم الأول',
  'endpoint': '/ask',
  'question': 'كيف استعد جيفري لانغ لأداء صلاته الأولى ليلة اليوم الأول؟',
  'expected_status': 'success',
  'required_groups': [['حركات الصلاه'],
                      ['الايات القرانيه'],
                      ['الادعيه'],
                      ['باللغه العربيه'],
                      ['معانيها باللغه الانجليزيه'],
                      ['تفحص الكتيب'],
                      ['صلاه العشاء']]},
 {'category': 'شرح المصطلحات',
  'endpoint': '/ask',
  'question': 'ما معنى الكلمات الآتية: اعتنقت، فورا، تفحصت؟',
  'expected_status': 'success',
  'required_groups': [['اختاره عقيده دينيه'], ['حالا'], ['بحث']]},
 {'category': 'خطوات المهارة',
  'endpoint': '/ask',
  'question': 'ما المقصود بتحديد الزمن العام لليومية؟',
  'expected_status': 'success',
  'required_groups': [['الزمن العام'],
                      ['يوم الاثنين'],
                      ['12 شتنبر 2015'],
                      ['اليوم الاول'],
                      ['يوم نجاحي في امتحان']]},
 {'category': 'خطوات المهارة',
  'endpoint': '/ask',
  'question': 'ما الأزمنة الخاصة أو الجزئية التي يمكن استعمالها في اليومية؟',
  'expected_status': 'success',
  'required_groups': [['صباحا'], ['مساء'], ['قبل'], ['بعد'], ['علي الساعه']]},
 {'category': 'خطوات المهارة',
  'endpoint': '/ask',
  'question': 'كيف ترتب الأحداث عند كتابة اليومية، وما الذي يجب إبرازه؟',
  'expected_status': 'success',
  'required_groups': [['كل زمن جزيي'], ['تسلسلها الزمني'], ['اهميه اليوم'], ['حياتك']]},
 {'category': 'ضوابط السرد',
  'endpoint': '/ask',
  'question': 'ما الأمور التي ينبغي مراعاتها أثناء سرد أحداث اليومية؟',
  'expected_status': 'success',
  'required_groups': [['صف الاشخاص'],
                      ['الامكنه'],
                      ['الازمنه'],
                      ['الحوار الداخلي'],
                      ['ضمير المتكلم'],
                      ['الوضوح'],
                      ['الشفافيه']]},
 {'category': 'الحوار الداخلي',
  'endpoint': '/ask',
  'question': 'ما الحوار الداخلي، وما الأمثلة الواردة عليه في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['قلت في نفسي'], ['تساءلت'], ['حدثتني نفسي']]},
 {'category': 'عناصر المهارة',
  'endpoint': '/ask',
  'question': 'استخرج عناصر مهارة كتابة اليوميات من نص جيفري لانغ.',
  'expected_status': 'success',
  'required_groups': [['كاتب اليوميه'],
                      ['الدكتور جيفري لانغ'],
                      ['الحدث'],
                      ['اعتناق الاسلام'],
                      ['الزمان'],
                      ['اليوم الاول'],
                      ['المكان'],
                      ['المسجد'],
                      ['الغرفه']]},
 {'category': 'السرد والوصف',
  'endpoint': '/ask',
  'question': 'ما وظيفة السرد والوصف في نص الانطلاق؟',
  'expected_status': 'success',
  'required_groups': [['السرد'],
                      ['وقائع'],
                      ['اعتناق الاسلام'],
                      ['الوصف'],
                      ['مجريات الاحداث'],
                      ['المشاعر'],
                      ['الانفعالات']]},
 {'category': 'تنظيم اليومية',
  'endpoint': '/ask',
  'question': 'كيف ينظم كاتب اليومية الوقائع والأحداث؟',
  'expected_status': 'success',
  'required_groups': [['تسلسل الوقائع'], ['الاحداث'], ['تقطيع الحدث'], ['الزمن الذي وقع فيه']]},
 {'category': 'موضوع التطبيق',
  'endpoint': '/ask',
  'question': 'ما موضوع التطبيق المقترح في درس كتابة اليوميات؟',
  'expected_status': 'success',
  'required_groups': [['كتابه يوميه'], ['وقائع صيامك'], ['اول يوم'], ['شهر رمضان']]},
 {'category': 'بيانات يومية رمضان',
  'endpoint': '/ask',
  'question': 'ما التاريخ الوارد في نموذج يومية أول يوم من رمضان؟',
  'expected_status': 'success',
  'required_groups': [['1431'], ['11 غشت 2010']]},
 {'category': 'ليلة رمضان',
  'endpoint': '/ask',
  'question': 'ماذا حدث في الساعة الثانية عشرة ليلا في نموذج يومية رمضان؟',
  'expected_status': 'success',
  'required_groups': [['نشره الاخبار'],
                      ['ثبوت رويه هلال رمضان'],
                      ['فرحت'],
                      ['التبريكات'],
                      ['الاتصال بالاهل والاقارب'],
                      ['تهنيتهم']]},
 {'category': 'السحور',
  'endpoint': '/ask',
  'question': 'ماذا حدث في الساعة الثالثة صباحا في نموذج يومية رمضان؟',
  'expected_status': 'success',
  'required_groups': [['ايقظتني والدتي'],
                      ['وجبه السحور'],
                      ['ساعدها'],
                      ['تمر'],
                      ['عصير'],
                      ['والدي واخي'],
                      ['صلاه الفجر']]},
 {'category': 'صباح رمضان',
  'endpoint': '/ask',
  'question': 'ماذا فعلت صاحبة اليومية في الساعة الحادية عشرة صباحا؟',
  'expected_status': 'success',
  'required_groups': [['استيقظت متاخره'],
                      ['تنظيف المنزل'],
                      ['رفقه امي'],
                      ['السوق'],
                      ['لوازم'],
                      ['وجبه الافطار']]},
 {'category': 'معاناة الصيام',
  'endpoint': '/ask',
  'question': 'ماذا شعرت صاحبة اليومية أثناء النهار، وكيف حاولت تمضية الوقت؟',
  'expected_status': 'success',
  'required_groups': [['الجوع'], ['العطش'], ['مشاهده التلفاز'], ['قراءه الجرايد']]},
 {'category': 'وقت الإفطار',
  'endpoint': '/ask',
  'question': 'ماذا فعلت صاحبة اليومية في الساعة السادسة والنصف مساء؟',
  'expected_status': 'success',
  'required_groups': [['مائده الافطار'],
                      ['توضات'],
                      ['سطح المنزل'],
                      ['اذان المغرب'],
                      ['التمر'],
                      ['الحليب'],
                      ['صلاه المغرب'],
                      ['انتظار عوده ابي واخي']]},
 {'category': 'مشاعر الإفطار',
  'endpoint': '/ask',
  'question': 'ما المشاعر التي أحست بها صاحبة اليومية عند لحظة الإفطار؟',
  'expected_status': 'success',
  'required_groups': [['زال العناء', 'لم يعد للعناء اثر'],
                      ['فخر'],
                      ['ارتياح'],
                      ['رجاء'],
                      ['تقبل الله لصيامنا'],
                      ['نيل مرضاته']]},
 {'category': 'خصائص اليومية',
  'endpoint': '/ask',
  'question': 'ما أهم خصائص كتابة اليومية المستخلصة من الدرس؟',
  'expected_status': 'success',
  'required_groups': [['سجل شخصي'],
                      ['الزمن العام'],
                      ['الازمنه الجزييه'],
                      ['التسلسل الزمني'],
                      ['ضمير المتكلم'],
                      ['الحوار الداخلي'],
                      ['الوصف'],
                      ['الوضوح']]},
 {'category': 'خطة الكتابة',
  'endpoint': '/ask',
  'question': 'قدم خطة مختصرة لكتابة يومية ناجحة حسب خطوات المهارة.',
  'expected_status': 'success',
  'required_groups': [['تحديد الزمن العام'],
                      ['الازمنه الخاصه'],
                      ['سرد الاحداث'],
                      ['التسلسل الزمني'],
                      ['وصف الاشخاص'],
                      ['الامكنه'],
                      ['الحوار الداخلي'],
                      ['ضمير المتكلم'],
                      ['اهميه اليوم']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس مهارة السرد: كتابة اليوميات.',
  'expected_status': 'success',
  'required_groups': [['السرد'],
                      ['الوصف'],
                      ['اليوميات'],
                      ['سجل شخصي'],
                      ['الزمن العام'],
                      ['الازمنه الجزييه'],
                      ['التسلسل الزمني'],
                      ['ضمير المتكلم'],
                      ['الحوار الداخلي'],
                      ['الوضوح']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص نص الانطلاق ونموذج يومية أول يوم من رمضان مع إبراز الكاتب والحدث والزمان '
              'والمكان وتسلسل الوقائع والمشاعر.',
  'expected_status': 'success',
  'required_groups': [['جيفري لانغ'],
                      ['اعتناق الاسلام'],
                      ['اليوم الاول'],
                      ['المسجد'],
                      ['الغرفه'],
                      ['الصلاه'],
                      ['رمضان'],
                      ['12 ليلا'],
                      ['3 صباحا'],
                      ['11 صباحا'],
                      ['6:30 مساء'],
                      ['الجوع'],
                      ['العطش'],
                      ['الفخر'],
                      ['الارتياح']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما عاصمة الأرجنتين؟',
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
        "الاختبار الأولي لمهارة السرد: كتابة اليوميات"
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
        "فلتر المصدر: mhara-alsrd-ktaba-aliomiat.pdf"
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
