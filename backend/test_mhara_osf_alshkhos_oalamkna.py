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
EXPECTED_SOURCE = "mhara-osf-alshkhos-oalamkna.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-describing-people-places-baseline"

JSON_REPORT = Path("mhara_osf_alshkhos_oalamkna_test_results.json")
CSV_REPORT = Path("mhara_osf_alshkhos_oalamkna_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الوصف',
  'endpoint': '/ask',
  'question': 'ما تعريف الوصف حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['تقنيه للتعبير'],
                      ['ينقل'],
                      ['بصريا'],
                      ['خطاب مكتوب'],
                      ['رسم بالكلمات'],
                      ['تصوير للمشاهد'],
                      ['الانفعالات'],
                      ['الاحاسيس']]},
 {'category': 'عناصر النص الوصفي',
  'endpoint': '/ask',
  'question': 'ما العنصران الرئيسيان في كل نص وصفي؟',
  'expected_status': 'success',
  'required_groups': [['الموصوف'], ['اوصافه']]},
 {'category': 'خطوات المهارة',
  'endpoint': '/ask',
  'question': 'ما العناصر التي نحددها عند كتابة نص وصفي؟',
  'expected_status': 'success',
  'required_groups': [['الموصوف الرييسي'], ['الموصوفات الفرعيه'], ['الامتدادات الوصفيه']]},
 {'category': 'الموصوف الرئيسي',
  'endpoint': '/ask',
  'question': 'ماذا يمكن أن يكون الموصوف الرئيسي؟',
  'expected_status': 'success',
  'required_groups': [['شخصا'], ['مكانا'], ['حيوانا'], ['غير ذلك']]},
 {'category': 'وصف الشخوص',
  'endpoint': '/ask',
  'question': 'ما الجوانب التي نركز عليها عند وصف شخص؟',
  'expected_status': 'success',
  'required_groups': [['الاوصاف الجسميه'],
                      ['الاوصاف النفسيه'],
                      ['الاوصاف الاجتماعيه'],
                      ['الافعال'],
                      ['الحركات']]},
 {'category': 'الأوصاف الجسمية',
  'endpoint': '/ask',
  'question': 'ما العناصر التي تدخل ضمن الأوصاف الجسمية للشخص؟',
  'expected_status': 'success',
  'required_groups': [['الملامح'], ['الهييه'], ['اللباس']]},
 {'category': 'الأوصاف النفسية',
  'endpoint': '/ask',
  'question': 'ما العناصر التي تدخل ضمن الأوصاف النفسية للشخص؟',
  'expected_status': 'success',
  'required_groups': [['المزاج'], ['التصرفات'], ['المشاعر'], ['المواقف'], ['الافكار']]},
 {'category': 'الأوصاف الاجتماعية',
  'endpoint': '/ask',
  'question': 'ما العناصر التي تدخل ضمن الأوصاف الاجتماعية للشخص؟',
  'expected_status': 'success',
  'required_groups': [['الاسم'], ['السن'], ['الجنس'], ['الوضعيه الاجتماعيه']]},
 {'category': 'وصف الأمكنة',
  'endpoint': '/ask',
  'question': 'ما الجوانب التي نركز عليها عند وصف مكان؟',
  'expected_status': 'success',
  'required_groups': [['موقع المكان'], ['هندسه المكان'], ['الاثاث'], ['الديكور']]},
 {'category': 'نموذج وصف الشخص',
  'endpoint': '/ask',
  'question': 'من الشخصية الموصوفة في النموذج الأول، وما مصدر النص؟',
  'expected_status': 'success',
  'required_groups': [['مدرس اللغه الفرنسيه'], ['في الطفوله'], ['عبد المجيد بن جلون']]},
 {'category': 'ملامح المدرس',
  'endpoint': '/ask',
  'question': 'كيف وصف الكاتب جسم مدرس اللغة الفرنسية ووجهه؟',
  'expected_status': 'success',
  'required_groups': [['رجل نحيل'], ['وجهه'], ['العرض'], ['الطول'], ['قصير القامه']]},
 {'category': 'لباس المدرس',
  'endpoint': '/ask',
  'question': 'كيف وصف الكاتب لباس مدرس اللغة الفرنسية؟',
  'expected_status': 'success',
  'required_groups': [['طربوشا'], ['شديد القصر'], ['برنسا'], ['دون جلباب']]},
 {'category': 'حركات المدرس',
  'endpoint': '/ask',
  'question': 'ما الحركات التي كان يقوم بها مدرس اللغة الفرنسية؟',
  'expected_status': 'success',
  'required_groups': [['يرمي بجناحيه'], ['الي الوراء'], ['يعقد عليهما يديه'], ['يذرع الفصل']]},
 {'category': 'ملامح الوجه',
  'endpoint': '/ask',
  'question': 'كيف وصف الكاتب ذقن المدرس وحاجبيه وعينيه وأنفه؟',
  'expected_status': 'success',
  'required_groups': [['شعر ذقنه'],
                      ['كثيفا'],
                      ['شديد سواد شعر الحاجبين'],
                      ['عينان حادتان'],
                      ['قلقتان'],
                      ['انف افطس']]},
 {'category': 'صوت المدرس وتأثيره',
  'endpoint': '/ask',
  'question': 'كيف وصف الكاتب صوت المدرس، وما أثر مظهره في السارد؟',
  'expected_status': 'success',
  'required_groups': [['صوته قويا'], ['حادا'], ['الضحك'], ['الا انظر اليه']]},
 {'category': 'نموذج وصف المكان',
  'endpoint': '/ask',
  'question': 'مم يتألف المنزل في نموذج وصف المكان؟',
  'expected_status': 'success',
  'required_groups': [['دورين'], ['الدور الاول'], ['الدور الثاني']]},
 {'category': 'غرفة الاستقبال',
  'endpoint': '/ask',
  'question': 'كيف وصفت غرفة الاستقبال في المنزل؟',
  'expected_status': 'success',
  'required_groups': [['المقاعد الوثيره'],
                      ['الصور'],
                      ['تمثال صغير'],
                      ['باقه من الزهور'],
                      ['تحفه صغيره'],
                      ['حاك'],
                      ['الاسطوانات']]},
 {'category': 'غرفة الجلوس',
  'endpoint': '/ask',
  'question': 'ما محتويات غرفة الجلوس العادية؟',
  'expected_status': 'success',
  'required_groups': [['المقاعد'], ['الكراسي'], ['منضده'], ['الصحف'], ['رفوف'], ['كتب']]},
 {'category': 'غرفة المائدة',
  'endpoint': '/ask',
  'question': 'كيف وصفت غرفة المائدة؟',
  'expected_status': 'success',
  'required_groups': [['مائده كبيره مربعه'],
                      ['الكراسي'],
                      ['رفوف طويله'],
                      ['مستلزمات المائده'],
                      ['قفص كبير'],
                      ['ببغاء']]},
 {'category': 'الدور الثاني',
  'endpoint': '/ask',
  'question': 'كيف وزعت غرف الدور الثاني في المنزل؟',
  'expected_status': 'success',
  'required_groups': [['ثلاث غرف'], ['لكل من الشابين غرفه'], ['الاخوات الثلاث']]},
 {'category': 'نموذج وصف الطبيعة',
  'endpoint': '/ask',
  'question': 'كيف وصف الكاتب الصباح في بداية نموذج وصف الطبيعة؟',
  'expected_status': 'success',
  'required_groups': [['الصباح مشرقا'], ['ساحرا'], ['يغري بالتنزه'], ['الطبيعه']]},
 {'category': 'مكونات المتنزه',
  'endpoint': '/ask',
  'question': 'ما أبرز مكونات المتنزه التي ذكرها الكاتب؟',
  'expected_status': 'success',
  'required_groups': [['بحيره'], ['روضه غناء'], ['المروج الخضراء'], ['السهول'], ['سنديانه']]},
 {'category': 'وصف البحيرة',
  'endpoint': '/ask',
  'question': 'بم شبه الكاتب البحيرة وصفحة الماء؟',
  'expected_status': 'success',
  'required_groups': [['لوحه فنيه'], ['صفحه الماء'], ['المراه المصقوله'], ['الفضه البراقه']]},
 {'category': 'وصف المروج والسهول',
  'endpoint': '/ask',
  'question': 'كيف وصف الكاتب المروج والسهول، وما أثرهما في النفس؟',
  'expected_status': 'success',
  'required_groups': [['المروج الخضراء'],
                      ['الاعشاب الناضره'],
                      ['الورود اليانعه'],
                      ['السهول المنبسطه'],
                      ['السرور'],
                      ['تبهج العين'],
                      ['تروح الصدر']]},
 {'category': 'وصف السنديانة',
  'endpoint': '/ask',
  'question': 'كيف وصف الكاتب السنديانة وأغصانها؟',
  'expected_status': 'success',
  'required_groups': [['سنديانه ظليله'],
                      ['اغصانها متشابكه'],
                      ['النسيم'],
                      ['تميس'],
                      ['حفيف اوراقها'],
                      ['تغريد بلابلها']]},
 {'category': 'وصف الغروب',
  'endpoint': '/ask',
  'question': 'كيف وصف الكاتب الشمس والبحيرة عند الغروب؟',
  'expected_status': 'success',
  'required_groups': [['الشمس عند الافق'],
                      ['وقفه الوداع'],
                      ['لونها الاحمر المتوهج'],
                      ['منعكس علي البحيره'],
                      ['سبيكه كبيره من الذهب']]},
 {'category': 'أثر الطبيعة',
  'endpoint': '/ask',
  'question': 'ما المشاعر التي أحس بها الكاتب في نهاية رحلته بالطبيعة؟',
  'expected_status': 'success',
  'required_groups': [['سرور'],
                      ['ارتياح'],
                      ['نشوه'],
                      ['طمأنينه'],
                      ['سكينه'],
                      ['ابتهاجا'],
                      ['املا']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس مهارة وصف الشخوص والأمكنة.',
  'expected_status': 'success',
  'required_groups': [['الوصف'],
                      ['رسم بالكلمات'],
                      ['الموصوف الرييسي'],
                      ['الموصوفات الفرعيه'],
                      ['الامتدادات الوصفيه'],
                      ['الاوصاف الجسميه'],
                      ['الاوصاف النفسيه'],
                      ['الاوصاف الاجتماعيه'],
                      ['موقع المكان'],
                      ['هندسه المكان'],
                      ['الاثاث'],
                      ['الديكور']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص نماذج وصف الشخص والمكان والطبيعة الواردة في الدرس، مع إبراز أهم الصفات '
              'والتفاصيل والمشاعر.',
  'expected_status': 'success',
  'required_groups': [['مدرس اللغه الفرنسيه'],
                      ['نحيل'],
                      ['قصير القامه'],
                      ['المنزل'],
                      ['دورين'],
                      ['غرفه الاستقبال'],
                      ['غرفه الجلوس'],
                      ['غرفه المائده'],
                      ['البحيره'],
                      ['المروج الخضراء'],
                      ['السنديانه'],
                      ['الغروب'],
                      ['السرور'],
                      ['الارتياح']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما عدد كواكب المجموعة الشمسية؟',
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
        "الاختبار الأولي لمهارة وصف الشخوص والأمكنة"
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
        "فلتر المصدر: mhara-osf-alshkhos-oalamkna.pdf"
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
