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
EXPECTED_SOURCE = "khsal-almslm.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-muslim-qualities-baseline"

JSON_REPORT = Path("khsal_almslm_test_results.json")
CSV_REPORT = Path("khsal_almslm_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الحديث النبوي',
  'endpoint': '/ask',
  'question': 'ما تعريف الحديث النبوي الشريف؟',
  'expected_status': 'success',
  'required_groups': [['ما صدر عن الرسول', 'ما صدر عن النبي'],
                      ['قول'],
                      ['فعل'],
                      ['تقرير'],
                      ['صفه']]},
 {'category': 'أنواع الحديث النبوي',
  'endpoint': '/ask',
  'question': 'ما الأنواع التي يشملها الحديث النبوي حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['قول'], ['فعل'], ['تقرير'], ['صفه']]},
 {'category': 'مثال القول',
  'endpoint': '/ask',
  'question': 'ما المثال الوارد في الوثيقة على الحديث القولي؟',
  'expected_status': 'success',
  'required_groups': [['انما الاعمال بالنيات'], ['لكل امري ما نوي']]},
 {'category': 'مثال الفعل',
  'endpoint': '/ask',
  'question': 'ما المثال الوارد على الحديث الفعلي؟',
  'expected_status': 'success',
  'required_groups': [['تعليمه'],
                      ['كيفيه الصلاه', 'كيفية الصلاة'],
                      ['كيفيه الحج', 'كيفية الحج'],
                      ['صلوا كما رايتموني اصلي', 'خذوا عني مناسككم']]},
 {'category': 'مثال التقرير',
  'endpoint': '/ask',
  'question': 'ما المثال الوارد على تقرير الرسول صلى الله عليه وسلم؟',
  'expected_status': 'success',
  'required_groups': [['اكل ضبا', 'اكل بعض الصحابه ضبا'], ['لم يعترض']]},
 {'category': 'تعريف الحديث القدسي',
  'endpoint': '/ask',
  'question': 'ما تعريف الحديث القدسي؟',
  'expected_status': 'success',
  'required_groups': [['معناه من الله'], ['لفظه من الرسول']]},
 {'category': 'مجال النص',
  'endpoint': '/ask',
  'question': 'إلى أي مجال ينتمي نص خصال المسلم؟',
  'expected_status': 'success',
  'required_groups': [['القيم الاسلاميه']]},
 {'category': 'نوعية النص',
  'endpoint': '/ask',
  'question': 'ما نوع نص خصال المسلم، وما المؤشرات الدالة على ذلك؟',
  'expected_status': 'success',
  'required_groups': [['احاديث قدسيه'],
                      ['نبويه شريفه'],
                      ['قال رسول الله'],
                      ['السند'],
                      ['الراوي'],
                      ['الاخراج']]},
 {'category': 'العنوان',
  'endpoint': '/ask',
  'question': 'مم يتكون عنوان خصال المسلم تركيبيا؟',
  'expected_status': 'success',
  'required_groups': [['مركب اضافي'], ['خصال'], ['مضاف'], ['المسلم'], ['مضاف اليه']]},
 {'category': 'العنوان',
  'endpoint': '/ask',
  'question': 'ما الدلالة التي يحملها عنوان خصال المسلم؟',
  'expected_status': 'success',
  'required_groups': [['خصال'], ['صيغه الجمع', 'بصيغه الجمع'], ['المسلم'], ['خصال عديده']]},
 {'category': 'بداية ونهاية النص',
  'endpoint': '/ask',
  'question': 'بم تبدأ فقرات النص وبم تنتهي؟',
  'expected_status': 'success',
  'required_groups': [['قال رسول الله'], ['نصوص حديثيه'], ['الراوي'], ['اخرجه', 'الاخراج']]},
 {'category': 'فرضية القراءة',
  'endpoint': '/ask',
  'question': 'ما فرضية القراءة المقترحة لنص خصال المسلم؟',
  'expected_status': 'success',
  'required_groups': [['الخصال'],
                      ['المسلم'],
                      ['القيم الاسلاميه النبيله'],
                      ['يدعو اليها الاسلام']]},
 {'category': 'الإيضاح اللغوي',
  'endpoint': '/ask',
  'question': 'ما معنى الكلمات الآتية حسب الوثيقة: أتقى، المحارم، عبرة؟',
  'expected_status': 'success',
  'required_groups': [['اشد خشيه'], ['كل ما حرم الله', 'ما حرم الله'], ['عظه', 'موعظه']]},
 {'category': 'المضمون العام',
  'endpoint': '/ask',
  'question': 'ما المضمون العام لنص خصال المسلم؟',
  'expected_status': 'success',
  'required_groups': [['تقوي الله'],
                      ['غني النفس'],
                      ['الامر بالمعروف'],
                      ['النهي عن المنكر'],
                      ['طلب العلم'],
                      ['صفات المسلم الحقيقي']]},
 {'category': 'خصال الحديث الأول',
  'endpoint': '/ask',
  'question': 'ما الخصال الواردة في الحديث الأول؟',
  'expected_status': 'success',
  'required_groups': [['التقوي'],
                      ['الهدي'],
                      ['العدل'],
                      ['العلم'],
                      ['العز'],
                      ['القناعه'],
                      ['غني النفس']]},
 {'category': 'نصرة الأخ',
  'endpoint': '/ask',
  'question': 'كيف تكون نصرة الأخ إذا كان مظلوما أو ظالما؟',
  'expected_status': 'success',
  'required_groups': [['مساندته', 'نصره'], ['مظلوما'], ['منعه'], ['الظلم'], ['ظالما']]},
 {'category': 'الخصال الخمس',
  'endpoint': '/ask',
  'question': 'ما الخصال الخمس التي أوصى بها الرسول صلى الله عليه وسلم؟',
  'expected_status': 'success',
  'required_groups': [['اتقاء المحارم'],
                      ['الرضي بما قسم الله'],
                      ['الاحسان الي الجار'],
                      ['حب الخير للناس'],
                      ['عدم الاكثار من الضحك', 'لا تكثر الضحك']]},
 {'category': 'الخصال التسع',
  'endpoint': '/ask',
  'question': 'اذكر ست خصال على الأقل من الخصال التسع الواردة في الحديث الرابع.',
  'expected_status': 'success',
  'required_groups': [['خشيه الله'],
                      ['العدل'],
                      ['القصد'],
                      ['اصل من قطعني', 'صله الرحم'],
                      ['اعطي من حرمني', 'الجود'],
                      ['اعفو عمن ظلمني', 'العفو']]},
 {'category': 'علاقة الإنسان بربه',
  'endpoint': '/ask',
  'question': 'ما الخصال التي تنظم علاقة الإنسان بربه؟',
  'expected_status': 'success',
  'required_groups': [['خشيه الله'], ['التقوي'], ['الهدي']]},
 {'category': 'علاقة الإنسان بالمجتمع',
  'endpoint': '/ask',
  'question': 'اذكر خصالا تنظم علاقة الإنسان بأخيه الإنسان.',
  'expected_status': 'success',
  'required_groups': [['صله الرحم'], ['العدل'], ['الاحسان الي الجار'], ['العفو']]},
 {'category': 'مضامين الحديث الأول',
  'endpoint': '/ask',
  'question': 'ما الخصال التي كان موسى عليه السلام يحبها، وما الخصلة التي كان يكرهها؟',
  'expected_status': 'success',
  'required_groups': [['التقوي'],
                      ['الهدي'],
                      ['العدل'],
                      ['العلم'],
                      ['العز'],
                      ['القناعه'],
                      ['الطمع']]},
 {'category': 'أساليب النص',
  'endpoint': '/ask',
  'question': 'ما الأساليب الموظفة في النصوص الحديثية مع مثال لكل أسلوب؟',
  'expected_status': 'success',
  'required_groups': [['النداء'],
                      ['يا رب', 'يا رسول الله'],
                      ['الاستفهام'],
                      ['اي عبادك', 'افرأيت'],
                      ['الامر'],
                      ['انصر اخاك', 'اتق المحارم', 'ارض بما قسم الله لك', 'احسن الي جارك'],
                      ['النهي'],
                      ['لا تكثر الضحك']]},
 {'category': 'الخصائص الفنية',
  'endpoint': '/ask',
  'question': 'ما المقصود بالإيجاز في النص، وما مثال عليه؟',
  'expected_status': 'success',
  'required_groups': [['الايجاز'],
                      ['اذا قدر غفر', 'انصر اخاك ظالما او مظلوما', 'صمتي فكرا']]},
 {'category': 'الخصائص الفنية',
  'endpoint': '/ask',
  'question': 'اذكر أربعة أمثلة للطباق الوارد في النصوص الحديثية.',
  'expected_status': 'success',
  'required_groups': [['يذكر', 'ينسي'],
                      ['اغني', 'افقر'],
                      ['الغني', 'الفقر'],
                      ['ظالما', 'مظلوما']]},
 {'category': 'ثنائية المقدمة والخاتمة',
  'endpoint': '/ask',
  'question': 'ما نتيجة اتقاء المحارم والرضى بالقسمة والإحسان إلى الجار وحب الخير للناس؟',
  'expected_status': 'success',
  'required_groups': [['اتق المحارم'],
                      ['اعبد الناس'],
                      ['ارض بما قسم الله'],
                      ['اغني الناس'],
                      ['احسن الي جارك'],
                      ['مؤمنا'],
                      ['احب للناس ما تحب لنفسك'],
                      ['مسلما']]},
 {'category': 'القيم الإسلامية',
  'endpoint': '/ask',
  'question': 'ما أهمية القيم الإسلامية الواردة في النص؟',
  'expected_status': 'success',
  'required_groups': [['المكانه الايجابيه'],
                      ['الانسان المسلم'],
                      ['سعادته في الدنيا والآخره', 'السعاده في الدنيا والآخره']]},
 {'category': 'قيمة العدل',
  'endpoint': '/ask',
  'question': 'ما معنى العدل وما أهميته حسب الجدول؟',
  'expected_status': 'success',
  'required_groups': [['تحقيق التوازن'],
                      ['تجنب الظلم'],
                      ['المساواه'],
                      ['الامن'],
                      ['الطمأنينه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص نص خصال المسلم.',
  'expected_status': 'success',
  'required_groups': [['التقوي'],
                      ['العدل'],
                      ['طلب العلم', 'العلم'],
                      ['القناعه'],
                      ['الاحسان الي الجار'],
                      ['حب الخير للناس'],
                      ['العفو'],
                      ['الامر بالمعروف']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص تحليل نص خصال المسلم من حيث المجال والنوع والعنوان والمضمون والخصال '
              'والأساليب والخصائص الفنية والقيم.',
  'expected_status': 'success',
  'required_groups': [['القيم الاسلاميه'],
                      ['احاديث قدسيه'],
                      ['احاديث نبويه'],
                      ['مركب اضافي'],
                      ['تقوي الله'],
                      ['علاقه الانسان بربه'],
                      ['علاقه الانسان', 'بالمجتمع'],
                      ['النداء'],
                      ['الاستفهام'],
                      ['الامر'],
                      ['النهي'],
                      ['الايجاز'],
                      ['الطباق'],
                      ['سعاده', 'الدنيا والآخره']]},
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
        "الاختبار الأولي لنص خصال المسلم"
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
