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
EXPECTED_SOURCE = "mdrsa-alhiaa.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-school-of-life-baseline"

JSON_REPORT = Path("mdrsa_alhiaa_test_results.json")
CSV_REPORT = Path("mdrsa_alhiaa_test_results.csv")

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

TEST_CASES = [{'category': 'الكاتب',
  'endpoint': '/ask',
  'question': 'من هو كاتب نص مدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['عبد السلام العجيلي']]},
 {'category': 'حياة الكاتب',
  'endpoint': '/ask',
  'question': 'متى وأين ولد عبد السلام العجيلي، ومتى توفي؟',
  'expected_status': 'success',
  'required_groups': [['1918'], ['الرقه'], ['05 ابريل 2006', '5 ابريل 2006']]},
 {'category': 'دراسة الكاتب',
  'endpoint': '/ask',
  'question': 'أين درس عبد السلام العجيلي، ومتى تخرج طبيبا؟',
  'expected_status': 'success',
  'required_groups': [['الرقه'], ['حلب'], ['جامعه دمشق'], ['1945'], ['طبيبا']]},
 {'category': 'مناصب الكاتب',
  'endpoint': '/ask',
  'question': 'ما أهم المناصب التي تولاها عبد السلام العجيلي؟',
  'expected_status': 'success',
  'required_groups': [['نايبا عن الرقه', 'نائبا عن الرقه'],
                      ['1947'],
                      ['وزاره الثقافه', 'وزارات الثقافه'],
                      ['الخارجيه'],
                      ['الاعلام'],
                      ['1962']]},
 {'category': 'أعمال الكاتب',
  'endpoint': '/ask',
  'question': 'اذكر ثلاثة من أعمال عبد السلام العجيلي الواردة في الوثيقة.',
  'expected_status': 'success',
  'required_groups': [['الليالي والنجوم'], ['باسمه بين الدموع'], ['فارس مدينه القنطره']]},
 {'category': 'مصدر النص',
  'endpoint': '/ask',
  'question': 'من أي موضوع اقتطف نص مدرسة الحياة، وما دلالة عنوان المصدر؟',
  'expected_status': 'success',
  'required_groups': [['ابحرت في كل المواني'],
                      ['جرب'],
                      ['عاش مواقف عديده', 'مواقف عديده'],
                      ['متناقضه']]},
 {'category': 'الصورة',
  'endpoint': '/ask',
  'question': 'ماذا تمثل الصورة المصاحبة للنص، وما علاقتها بمدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['مطحنه الحبوب'], ['فصل من فصول مدرسه الحياه']]},
 {'category': 'مجال النص',
  'endpoint': '/ask',
  'question': 'إلى أي مجال ينتمي نص مدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['المجال الاجتماعي'], ['الاقتصادي']]},
 {'category': 'العنوان',
  'endpoint': '/ask',
  'question': 'مم يتكون عنوان مدرسة الحياة تركيبيا؟',
  'expected_status': 'success',
  'required_groups': [['مركب اضافي'],
                      ['مدرسه'],
                      ['مضاف'],
                      ['الحياه'],
                      ['مضاف اليه'],
                      ['الاضافه المعنويه'],
                      ['التعريف']]},
 {'category': 'العنوان',
  'endpoint': '/ask',
  'question': 'ما الدلالة التي يحملها عنوان مدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['لا يقصد بها الفضاء التربوي النظامي', 'ليست المدرسه النظاميه'],
                      ['الحياه فضاء'],
                      ['نتعلم فيه'],
                      ['النجاح'],
                      ['الفشل']]},
 {'category': 'نوعية النص',
  'endpoint': '/ask',
  'question': 'ما نوع نص مدرسة الحياة، وما المؤشرات الدالة على ذلك؟',
  'expected_status': 'success',
  'required_groups': [['مقطع من سيره ذاتيه'],
                      ['بعد اجتماعي'],
                      ['الجمل الفعليه'],
                      ['الزمان'],
                      ['المكان'],
                      ['الشخصيات'],
                      ['ضمير المتكلم']]},
 {'category': 'فرضية القراءة',
  'endpoint': '/ask',
  'question': 'ما فرضية القراءة المقترحة لنص مدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['سيره السارد'], ['مدرسه الحياه']]},
 {'category': 'الإيضاح اللغوي',
  'endpoint': '/ask',
  'question': 'ما معنى الكلمات الآتية: الدولاب، القنباز، منعطف؟',
  'expected_status': 'success',
  'required_groups': [['اداه مستديره'],
                      ['تدور حول مركزها'],
                      ['لباس للرجل'],
                      ['واسع في اسفله'],
                      ['نقطه التحول', 'منعرج']]},
 {'category': 'الإيضاح اللغوي',
  'endpoint': '/ask',
  'question': 'ما معنى: جابيا على غلتها، الحنطة، الأرمني، المضافة؟',
  'expected_status': 'success',
  'required_groups': [['جامعا لمحصولها وارباحها'],
                      ['الحنطه', 'القمح', 'الجعه'],
                      ['نسبه الي ارمينيا'],
                      ['غرفه خاصه لاستقبال الضيوف']]},
 {'category': 'المضمون العام',
  'endpoint': '/ask',
  'question': 'ما المضمون العام لنص مدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['احداثا من طفولته'],
                      ['انقطع عن الدراسه'],
                      ['مطحنه والده'],
                      ['تعلم الكثير من مدرسه الحياه'],
                      ['الرجوع الي المدرسه'],
                      ['اثبات جدارته']]},
 {'category': 'أحداث السيرة',
  'endpoint': '/ask',
  'question': 'ما حالة البداية في نص مدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['تذكر السارد'], ['المزاوجه بين الدراسه'], ['التردد علي مطحنه والده']]},
 {'category': 'أحداث السيرة',
  'endpoint': '/ask',
  'question': 'ما الحدث المحرك في نص مدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['مرض السارد'], ['انتقاله الي حلب'], ['العلاج']]},
 {'category': 'أحداث السيرة',
  'endpoint': '/ask',
  'question': 'ما العقدة في نص مدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['انقطاعه عن الدراسه'], ['بقاؤه في القريه'], ['مساعده والده']]},
 {'category': 'أحداث السيرة',
  'endpoint': '/ask',
  'question': 'ما الحل في نص مدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['الاستفاده'],
                      ['التعلم من مدرسه الحياه'],
                      ['ابراز موهلاته', 'ابراز مؤهلاته'],
                      ['مواهبه الابداعيه']]},
 {'category': 'أحداث السيرة',
  'endpoint': '/ask',
  'question': 'ما حالة النهاية في نص مدرسة الحياة؟',
  'expected_status': 'success',
  'required_groups': [['الرجوع الي المدرسه'], ['من جديد']]},
 {'category': 'صفات السارد',
  'endpoint': '/ask',
  'question': 'اذكر أربعة تعابير تدل على اجتهاد السارد وشغفه بالاطلاع والتعلم.',
  'expected_status': 'success',
  'required_groups': [['فتحت افاق تفكيره'],
                      ['الهبت خياله'],
                      ['اتلقي المعرفه'],
                      ['التعرف علي اصناف الناس']]},
 {'category': 'دلالة المعجم',
  'endpoint': '/ask',
  'question': 'ماذا يدل معجم الاجتهاد والتعلم في النص؟',
  'expected_status': 'success',
  'required_groups': [['منضبطا', 'منظبطا'],
                      ['مجدا'],
                      ['شغوفا بالاطلاع'],
                      ['الاستكشاف'],
                      ['التعلم']]},
 {'category': 'الوقائع البارزة',
  'endpoint': '/ask',
  'question': 'لخص أهم الأحداث والوقائع البارزة في نص مدرسة الحياة.',
  'expected_status': 'success',
  'required_groups': [['حادث المطحنه', 'الحدث المولم'],
                      ['نهايه المرحله الابتداييه'],
                      ['مرض السارد'],
                      ['انقطاعه عن الدراسه'],
                      ['عمله بمطحنه ابيه'],
                      ['مسرحيه وفاء السموأل', 'وفاء السموأل'],
                      ['قصيده'],
                      ['عودته الي الدراسه']]},
 {'category': 'عناصر السيرة الذاتية',
  'endpoint': '/ask',
  'question': 'ما عناصر السيرة الذاتية الموجودة في النص؟',
  'expected_status': 'success',
  'required_groups': [['ضمير المتكلم'],
                      ['زمن الماضي'],
                      ['السارد هو نفسه البطل'],
                      ['السرد'],
                      ['الوصف']]},
 {'category': 'العلاقة بين السارد والبطل',
  'endpoint': '/ask',
  'question': 'ما العلاقة بين السارد والشخصية الرئيسية؟',
  'expected_status': 'success',
  'required_groups': [['تطابق'], ['السارد'], ['الشخصيه الرييسيه']]},
 {'category': 'الاسترجاع والاستباق',
  'endpoint': '/ask',
  'question': 'كيف وظف النص تقنيتي الاسترجاع والاستباق؟',
  'expected_status': 'success',
  'required_groups': [['الاسترجاع'],
                      ['حدث في احدي مرات'],
                      ['الذي اذكره'],
                      ['كنت احضر معهم'],
                      ['الاستباق'],
                      ['انا الطبيب'],
                      ['مسيره دراسيه ناجحه']]},
 {'category': 'الرسالة والقيم',
  'endpoint': '/ask',
  'question': 'ما رسالة نص مدرسة الحياة، وما مقصديتها وقيمه؟',
  'expected_status': 'success',
  'required_groups': [['الحياه مدرسه'],
                      ['لا تقل اهميه عن المدرسه النظاميه'],
                      ['انخراط الفرد'],
                      ['واقعه'],
                      ['محيطه المجتمعي'],
                      ['التعلم'],
                      ['حب الاطلاع'],
                      ['الطاعه'],
                      ['الاجتهاد'],
                      ['الصبر'],
                      ['التفاني']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص نص مدرسة الحياة.',
  'expected_status': 'success',
  'required_groups': [['السارد'],
                      ['المدرسه'],
                      ['مطحنه والده'],
                      ['المرض'],
                      ['انقطاعه عن الدراسه'],
                      ['مدرسه الحياه'],
                      ['القصيده'],
                      ['العوده الي الدراسه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص تحليل نص مدرسة الحياة من حيث الكاتب والمجال والعنوان والنوع والمضمون '
              'والأحداث وعناصر السيرة والتقنيات والرسالة والقيم.',
  'expected_status': 'success',
  'required_groups': [['عبد السلام العجيلي'],
                      ['المجال الاجتماعي والاقتصادي'],
                      ['مركب اضافي'],
                      ['سيره ذاتيه'],
                      ['مدرسه الحياه'],
                      ['حاله البدايه'],
                      ['العقده'],
                      ['الحل'],
                      ['ضمير المتكلم'],
                      ['زمن الماضي'],
                      ['الاسترجاع'],
                      ['الاستباق'],
                      ['الحياه مدرسه'],
                      ['حب الاطلاع'],
                      ['الصبر']]},
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
        "الاختبار الأولي لنص مدرسة الحياة"
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
        "فلتر المصدر: mdrsa-alhiaa.pdf"
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
