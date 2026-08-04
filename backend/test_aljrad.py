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
EXPECTED_SOURCE = "aljrad.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-locust-text-baseline"

JSON_REPORT = Path("aljrad_test_results.json")
CSV_REPORT = Path("aljrad_test_results.csv")

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

TEST_CASES = [{'category': 'مجال النص ومصدره ونوعه',
  'endpoint': '/ask',
  'question': 'ما مجال نص الجراد ومصدره ونوعيته حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['المجال الانساني'],
                      ['البحر لا ماء فيه'],
                      ['30'],
                      ['35'],
                      ['نص سردي'],
                      ['بعد انساني']]},
 {'category': 'تحليل العنوان',
  'endpoint': '/ask',
  'question': 'كيف حللت الوثيقة عنوان الجراد من حيث تركيبه؟',
  'expected_status': 'success',
  'required_groups': [['كلمه واحده'], ['عنوان مفرد']]},
 {'category': 'بداية النص',
  'endpoint': '/ask',
  'question': 'ما المؤشرات السردية التي تظهر في بداية نص الجراد؟',
  'expected_status': 'success',
  'required_groups': [['الشخصيات'], ['الزمان'], ['المكان'], ['نص سردي']]},
 {'category': 'نهاية النص',
  'endpoint': '/ask',
  'question': 'كيف تنسجم نهاية نص الجراد مع عنوانه؟',
  'expected_status': 'success',
  'required_groups': [['تكرر'], ['اكثر من مره'], ['الحل المقترح'], ['القضاء علي الجراد']]},
 {'category': 'فرضية القراءة',
  'endpoint': '/ask',
  'question': 'ما فرضية قراءة نص الجراد حسب المؤشرات الأولية؟',
  'expected_status': 'success',
  'required_groups': [['الجراد'], ['الاضرار'], ['يتسبب فيها'], ['للانسان']]},
 {'category': 'الإيضاح اللغوي',
  'endpoint': '/ask',
  'question': 'ما معاني يشمر ومشحونا والصخب ومشروخ في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['يشمر يستعد ويتهيا'],
                      ['مشحونا مملوءا'],
                      ['الصخب الصوت المرتفع'],
                      ['مشروخ متقطع']]},
 {'category': 'الفكرة المحورية',
  'endpoint': '/ask',
  'question': 'ما الفكرة المحورية لنص الجراد؟',
  'expected_status': 'success',
  'required_groups': [['نجاح اهل القريه'], ['التخلص من الجراد'], ['تعاونهم'], ['تضامنهم']]},
 {'category': 'حالة البداية',
  'endpoint': '/ask',
  'question': 'ما حالة البداية في أحداث نص الجراد؟',
  'expected_status': 'success',
  'required_groups': [['هدوء القريه'], ['اعمالهم اليوميه'], ['السكينه'], ['الطمأنينه']]},
 {'category': 'الحدث المحرك',
  'endpoint': '/ask',
  'question': 'ما الحدث المحرك في نص الجراد؟',
  'expected_status': 'success',
  'required_groups': [['خبر'], ['قدوم الجراد'], ['القريه']]},
 {'category': 'العقدة',
  'endpoint': '/ask',
  'question': 'ما عقدة نص الجراد؟',
  'expected_status': 'success',
  'required_groups': [['توتر اهل القريه'],
                      ['خوفهم'],
                      ['حيرتهم'],
                      ['حل'],
                      ['التخلص من الجراد']]},
 {'category': 'الحل الأول',
  'endpoint': '/ask',
  'question': 'ما الحل الأول المقترح لمطاردة الجراد؟',
  'expected_status': 'success',
  'required_groups': [['صخب'],
                      ['ضجه'],
                      ['طرق الحديد'],
                      ['ضرب الدفوف'],
                      ['دق النواقيس'],
                      ['رن الزجاجات الفارغه']]},
 {'category': 'الحل الثاني',
  'endpoint': '/ask',
  'question': 'ما الحل الثاني الذي اقترحه المبروك لمواجهة الجراد؟',
  'expected_status': 'success',
  'required_groups': [['ناكل نحن الجراد'],
                      ['بدلا من ان ياكلنا'],
                      ['شوالات'],
                      ['الجراد النائم'],
                      ['اكياس'],
                      ['يسلقوه']]},
 {'category': 'حالة النهاية',
  'endpoint': '/ask',
  'question': 'هل ظهرت حالة النهاية في القصة، وما النهاية المتوقعة؟',
  'expected_status': 'success',
  'required_groups': [['تغيب حاله النهايه'],
                      ['انتهت'],
                      ['اقتراح الحل الثاني'],
                      ['تعود السكينه'],
                      ['الطمأنينه']]},
 {'category': 'هدوء القرية',
  'endpoint': '/ask',
  'question': 'كيف وصف النص حياة القرية قبل وصول خبر الجراد؟',
  'expected_status': 'success',
  'required_groups': [['هادئا'], ['طبيعيا'], ['اعمالهم اليوميه'], ['يتفرقون هنا وهناك']]},
 {'category': 'عمل عمران',
  'endpoint': '/ask',
  'question': 'ما العمل الذي كان عمران يقوم به في بداية النص؟',
  'expected_status': 'success',
  'required_groups': [['رفع الماء من البئر'],
                      ['بالدلو'],
                      ['البقره'],
                      ['مزروعاته'],
                      ['الحبل'],
                      ['البكره']]},
 {'category': 'وصف المبروك',
  'endpoint': '/ask',
  'question': 'كيف وصف النص شخصية المبروك وحياته؟',
  'expected_status': 'success',
  'required_groups': [['الخامسه والعشرين'],
                      ['جبهته عريضه'],
                      ['وجهه'],
                      ['السمره'],
                      ['والده مات'],
                      ['اسره كبيره'],
                      ['بستانا صغيرا'],
                      ['لقمه العيش']]},
 {'category': 'عمل الحاج سالم',
  'endpoint': '/ask',
  'question': 'ماذا كان الحاج سالم يفعل قبل سماع خبر الجراد؟',
  'expected_status': 'success',
  'required_groups': [['يحرس حقله'],
                      ['سنابل القمح'],
                      ['الشعير'],
                      ['يطرد حمارا'],
                      ['قطيع اغنام'],
                      ['يرمي بالحجاره'],
                      ['العصافير']]},
 {'category': 'وصول الخبر',
  'endpoint': '/ask',
  'question': 'كيف وصل خبر الجراد إلى أهل القرية؟',
  'expected_status': 'success',
  'required_groups': [['احد الرجال'],
                      ['مهرولا'],
                      ['صيحاته'],
                      ['النذير'],
                      ['الحرقة'],
                      ['اللوعة'],
                      ['الخوف']]},
 {'category': 'مكان الجراد',
  'endpoint': '/ask',
  'question': 'أين كان الجراد ليلة وصول الخبر، وكم كان يبعد عن القرية؟',
  'expected_status': 'success',
  'required_groups': [['البطاح القريبه'], ['خمس كيلومترات'], ['تنام هذه الليله']]},
 {'category': 'رد فعل السكان',
  'endpoint': '/ask',
  'question': 'كيف كان رد فعل أهل القرية بعد سماع خبر الجراد؟',
  'expected_status': 'success',
  'required_groups': [['مجموعه من المجانين'],
                      ['يجرون هنا وهناك'],
                      ['ذعر'],
                      ['خوف'],
                      ['حنين'],
                      ['لهفه']]},
 {'category': 'رد فعل الحاج سالم',
  'endpoint': '/ask',
  'question': 'كيف تأثر الحاج سالم بخبر الجراد؟',
  'expected_status': 'success',
  'required_groups': [['حسره'],
                      ['لوعه'],
                      ['الدمعه'],
                      ['لا يرميها بالحجاره'],
                      ['لا يصيح'],
                      ['يشل كل شيء']]},
 {'category': 'خطر الجراد على العيش',
  'endpoint': '/ask',
  'question': 'لماذا كان الجراد خطرا على لقمة عيش أهل القرية؟',
  'expected_status': 'success',
  'required_groups': [['لقمتهم'],
                      ['اشجارهم'],
                      ['زراعتهم'],
                      ['اثرا بعد عين'],
                      ['كل شبر اخضر'],
                      ['جذب'],
                      ['خراب']]},
 {'category': 'اجتماع أهل القرية',
  'endpoint': '/ask',
  'question': 'كيف كان اجتماع أهل القرية أمام المسجد بعد انتشار الخبر؟',
  'expected_status': 'success',
  'required_groups': [['امام المسجد'],
                      ['حزمه واحده'],
                      ['اصواتهم غاضبه'],
                      ['حزن عميق'],
                      ['ما العمل'],
                      ['حيره']]},
 {'category': 'اقتراح الحاج سالم',
  'endpoint': '/ask',
  'question': 'ماذا اقترح الحاج سالم على أهل القرية لمواجهة الجراد؟',
  'expected_status': 'success',
  'required_groups': [['مطاردة الجراد'],
                      ['صخب'],
                      ['ضجه'],
                      ['طرق الحديد'],
                      ['الدفوف'],
                      ['النواقيس'],
                      ['الزجاجات الفارغه']]},
 {'category': 'موقف المبروك',
  'endpoint': '/ask',
  'question': 'ما موقف المبروك من فكرة الحاج سالم، وما فكرته البديلة؟',
  'expected_status': 'success',
  'required_groups': [['لا تنفع'], ['فكره اخري'], ['ناكل نحن الجراد'], ['بدلا من ان ياكلنا']]},
 {'category': 'تنفيذ خطة المبروك',
  'endpoint': '/ask',
  'question': 'كيف شرح المبروك طريقة تنفيذ خطته بالتفصيل؟',
  'expected_status': 'success',
  'required_groups': [['الساعات الاولي من السحر'],
                      ['الطرف الجنوبي'],
                      ['شوالا فارغا'],
                      ['ينام الجراد'],
                      ['اشعه الشمس'],
                      ['يعبئون الجراد'],
                      ['اكياسهم'],
                      ['يسلقوه'],
                      ['مراجل سوداء']]},
 {'category': 'الشخصيات والزمان والمكان',
  'endpoint': '/ask',
  'question': 'ما شخصيات النص وأزمنته وأمكنته حسب القراءة التحليلية؟',
  'expected_status': 'success',
  'required_groups': [['المبروك'],
                      ['الحاج سالم'],
                      ['عمران'],
                      ['مساء'],
                      ['اول امس'],
                      ['عام'],
                      ['الساعات الاولي من الفجر'],
                      ['القريه'],
                      ['الحقل'],
                      ['امام المسجد'],
                      ['الطرف الجنوبي']]},
 {'category': 'مقصدية النص',
  'endpoint': '/ask',
  'question': 'ما مقصدية نص الجراد؟',
  'expected_status': 'success',
  'required_groups': [['دور الاتحاد'], ['التضامن'], ['حل المشاكل'], ['مستعصيه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص نص الجراد مع الأحداث والشخصيات والحلول والمقصدية.',
  'expected_status': 'success',
  'required_groups': [['القريه'],
                      ['عمران'],
                      ['المبروك'],
                      ['الحاج سالم'],
                      ['الجراد'],
                      ['الحدث المحرك'],
                      ['الخوف'],
                      ['الصخب'],
                      ['الدفوف'],
                      ['الشوالات'],
                      ['الجراد النائم'],
                      ['يسلقوه'],
                      ['الاتحاد'],
                      ['التضامن']]},
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
        "الاختبار الأولي لنص الجراد"
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
        "فلتر المصدر: aljrad.pdf"
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
