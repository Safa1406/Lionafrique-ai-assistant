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
EXPECTED_SOURCE = "hoar-ajib.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-wonderful-dialogue-baseline"

JSON_REPORT = Path("hoar_ajib_test_results.json")
CSV_REPORT = Path("hoar_ajib_test_results.csv")

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

TEST_CASES = [{'category': 'الكاتبة',
  'endpoint': '/ask',
  'question': 'من هي كاتبة نص حوار عجيب؟',
  'expected_status': 'success',
  'required_groups': [['زينب حبش']]},
 {'category': 'حياة الكاتبة',
  'endpoint': '/ask',
  'question': 'متى وأين ولدت زينب حبش حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['1943'], ['بيت دجن'], ['يافا'], ['فلسطين']]},
 {'category': 'دراسة الكاتبة',
  'endpoint': '/ask',
  'question': 'متى بدأت زينب حبش دراستها الجامعية، وأين درست، وما الشهادة التي حصلت عليها '
              'سنة 1965؟',
  'expected_status': 'success',
  'required_groups': [['1961'],
                      ['جامعه دمشق'],
                      ['سوريا'],
                      ['1965'],
                      ['ليسانس'],
                      ['اللغه الانجليزيه'],
                      ['ادابها']]},
 {'category': 'أعمال الكاتبة',
  'endpoint': '/ask',
  'question': 'اذكر ثلاثة من أعمال زينب حبش الواردة في الوثيقة.',
  'expected_status': 'success',
  'required_groups': [['قولي للرمل'],
                      ['الجرح الفلسطيني وبراعم الدم',
                       'لا تقولي مات يا امي',
                       'حفروا مذكراتي علي جسدي',
                       'لانه وطني'],
                      ['لا تقولي مات يا امي', 'حفروا مذكراتي علي جسدي', 'لانه وطني']]},
 {'category': 'العنوان',
  'endpoint': '/ask',
  'question': 'مم يتكون عنوان حوار عجيب تركيبيا؟',
  'expected_status': 'success',
  'required_groups': [['مركب وصفي'], ['حوار'], ['موصوف'], ['عجيب'], ['صفه']]},
 {'category': 'العنوان',
  'endpoint': '/ask',
  'question': 'ما الدلالة التي يحملها عنوان حوار عجيب؟',
  'expected_status': 'success',
  'required_groups': [['حوار'],
                      ['نوعيه النص', 'نوع النص'],
                      ['عجيب'],
                      ['الغرائبيه', 'العجائبيه'],
                      ['التشويق']]},
 {'category': 'بداية النص',
  'endpoint': '/ask',
  'question': 'ما المؤشرات التي تتضمنها بداية نص حوار عجيب، وعلام تدل؟',
  'expected_status': 'success',
  'required_groups': [['المكان'],
                      ['الزمان'],
                      ['الشخصيات'],
                      ['الراوي'],
                      ['الحوار'],
                      ['مسرحيه']]},
 {'category': 'نهاية النص',
  'endpoint': '/ask',
  'question': 'كيف تنسجم نهاية نص حوار عجيب مع عنوانه؟',
  'expected_status': 'success',
  'required_groups': [['حوار داخلي'], ['الاستغراب', 'التعجب'], ['قتل ابنه', 'يقتل ابنه']]},
 {'category': 'نوعية النص',
  'endpoint': '/ask',
  'question': 'ما نوع نص حوار عجيب وما بعده؟',
  'expected_status': 'success',
  'required_groups': [['نص حواري'], ['مسرحيه'], ['بعد وطني']]},
 {'category': 'فرضية القراءة',
  'endpoint': '/ask',
  'question': 'ما فرضية القراءة التي بنيت انطلاقا من العنوان وبداية النص ونهايته؟',
  'expected_status': 'success',
  'required_groups': [['وحشيه الصهاينه'],
                      ['الاطفال الفلسطينيين'],
                      ['الضمير الانساني'],
                      ['موشي']]},
 {'category': 'الإيضاح اللغوي',
  'endpoint': '/ask',
  'question': 'ما معاني الكلمات الآتية حسب الوثيقة: فرح غامر، مذعورا، امتقع، ممتعضا؟',
  'expected_status': 'success',
  'required_groups': [['فرح كبير'],
                      ['خايفا', 'فزعا'],
                      ['تغير لونه', 'شاحبا'],
                      ['متذمرا', 'منزعجا']]},
 {'category': 'المضمون العام',
  'endpoint': '/ask',
  'question': 'ما المضمون العام لنص حوار عجيب؟',
  'expected_status': 'success',
  'required_groups': [['وحشيه'],
                      ['حاييم'],
                      ['الاطفال الفلسطينيين'],
                      ['موشي'],
                      ['استنكار'],
                      ['تعاطف']]},
 {'category': 'حقل الوحشية',
  'endpoint': '/ask',
  'question': 'اذكر ثلاثة تعابير من حقل الوحشية والقسوة في النص.',
  'expected_status': 'success',
  'required_groups': [['اطلقت النار علي المتظاهرين',
                       'اصبت طفلا',
                       'الطفل قد مات',
                       'اصوب بندقيتي الي قلبه',
                       'تقتل الاطفال الصغار'],
                      ['اصبت طفلا',
                       'الطفل قد مات',
                       'اصوب بندقيتي الي قلبه',
                       'تقتل الاطفال الصغار',
                       'يطلقوا عليهم الرصاص'],
                      ['الطفل قد مات',
                       'اصوب بندقيتي الي قلبه',
                       'تقتل الاطفال الصغار',
                       'يطلقوا عليهم الرصاص',
                       'رصاص بندقيتي الي راس ابني']]},
 {'category': 'حقل الاستنكار',
  'endpoint': '/ask',
  'question': 'اذكر ثلاثة تعابير من حقل الاستنكار والتعاطف.',
  'expected_status': 'success',
  'required_groups': [['انا طفل مثلهم',
                       'لا يحملون سوي الحجاره الصغيره',
                       'هل تخاف من الاطفال',
                       'انت قاس يا ابي'],
                      ['لا يحملون سوي الحجاره الصغيره',
                       'هل تخاف من الاطفال',
                       'انت قاس يا ابي',
                       'لماذا لا تتركهم يلعبون ويضحكون'],
                      ['هل تخاف من الاطفال',
                       'انت قاس يا ابي',
                       'لماذا لا تتركهم يلعبون ويضحكون']]},
 {'category': 'دلالة المعجم',
  'endpoint': '/ask',
  'question': 'بمن يرتبط حقل الوحشية والقسوة، وبمن يرتبط حقل الاستنكار والتعاطف؟',
  'expected_status': 'success',
  'required_groups': [['حاييم'], ['اسرته'], ['موشي']]},
 {'category': 'أحداث المسرحية',
  'endpoint': '/ask',
  'question': 'ما وضعية البداية في مسرحية حوار عجيب؟',
  'expected_status': 'success',
  'required_groups': [['سعاده الاسره'],
                      ['عوده حاييم'],
                      ['رام الله', 'رام'],
                      ['محاربه الفلسطينيين']]},
 {'category': 'أحداث المسرحية',
  'endpoint': '/ask',
  'question': 'ما الحدث الرئيسي في مسرحية حوار عجيب؟',
  'expected_status': 'success',
  'required_groups': [['تباهي حاييم', 'افتخار حاييم'], ['قتل طفل فلسطيني']]},
 {'category': 'أحداث المسرحية',
  'endpoint': '/ask',
  'question': 'ما العقدة في مسرحية حوار عجيب؟',
  'expected_status': 'success',
  'required_groups': [['اصرار موشي'], ['معرفه حقيقه'], ['والده'], ['الاطفال الفلسطينيين']]},
 {'category': 'أحداث المسرحية',
  'endpoint': '/ask',
  'question': 'ما الحل في مسرحية حوار عجيب؟',
  'expected_status': 'success',
  'required_groups': [['محاوله الاسره'],
                      ['تبرير قتل الاطفال الفلسطينيين'],
                      ['اقناع موشي'],
                      ['دون جدوي']]},
 {'category': 'أحداث المسرحية',
  'endpoint': '/ask',
  'question': 'ما وضعية النهاية في مسرحية حوار عجيب؟',
  'expected_status': 'success',
  'required_groups': [['تفكير الاب', 'تفكير حاييم'],
                      ['قتل ابنه موشي'],
                      ['عجز'],
                      ['اقناعه']]},
 {'category': 'الشخصيات',
  'endpoint': '/ask',
  'question': 'ماذا يمثل حاييم وأسرته في المسرحية؟',
  'expected_status': 'success',
  'required_groups': [['الشخصيه الاسرائيليه'],
                      ['المحتله'],
                      ['ارض فلسطين'],
                      ['العاجزه عن تبرير اعتدايها', 'عاجزه عن تبرير اعتدايها'],
                      ['كراهيتها للفلسطينيين']]},
 {'category': 'الشخصيات',
  'endpoint': '/ask',
  'question': 'ماذا يمثل موشي في النص؟',
  'expected_status': 'success',
  'required_groups': [['الضمير الانساني الحي'], ['قتل الاطفال'], ['المستنكر']]},
 {'category': 'الشخصيات',
  'endpoint': '/ask',
  'question': 'ماذا يمثل علي في النص؟',
  'expected_status': 'success',
  'required_groups': [['القضيه الفلسطينيه'],
                      ['الانسان الفلسطيني'],
                      ['التضحيه بنفسه'],
                      ['وطنه']]},
 {'category': 'الفضاء الزماني',
  'endpoint': '/ask',
  'question': 'ما الزمن الخاص والزمن العام في النص؟',
  'expected_status': 'success',
  'required_groups': [['الاجازه الاسبوعيه'], ['زمن الاحتلال']]},
 {'category': 'الفضاء المكاني',
  'endpoint': '/ask',
  'question': 'ما المكان الخاص والمكان العام في النص؟',
  'expected_status': 'success',
  'required_groups': [['رام الله', 'رام'],
                      ['تل ابيب'],
                      ['ارض فلسطين المحتله'],
                      ['اسراييل']]},
 {'category': 'أساليب النص',
  'endpoint': '/ask',
  'question': 'ما الأساليب المسرحية الموظفة في النص، وما وظيفة كل واحد منها؟',
  'expected_status': 'success',
  'required_groups': [['الاستفهام'],
                      ['التساولات'],
                      ['الوصف'],
                      ['الانفعالات', 'الحالات الشخصيه'],
                      ['الحوار'],
                      ['تنوع الاراء', 'اختلافها']]},
 {'category': 'مقصدية وقيم النص',
  'endpoint': '/ask',
  'question': 'ما مقصدية نص حوار عجيب، وما القيمة الإنسانية التي يتضمنها؟',
  'expected_status': 'success',
  'required_groups': [['معاناه الشعب الفلسطيني'],
                      ['الاطفال'],
                      ['الضماير الانسانيه الحيه'],
                      ['التعاطف'],
                      ['موشي'],
                      ['استنكاره'],
                      ['تصرف ابيه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص نص حوار عجيب.',
  'expected_status': 'success',
  'required_groups': [['حاييم'],
                      ['طفل فلسطيني'],
                      ['موشي'],
                      ['الاستنكار', 'استنكر'],
                      ['قتل الاطفال'],
                      ['التفكير في قتل ابنه', 'فكر في قتل ابنه']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص تحليل نص حوار عجيب من حيث النوع، المضمون، الشخصيات، الأحداث، الأساليب، '
              'المقصدية والقيمة.',
  'expected_status': 'success',
  'required_groups': [['نص حواري'],
                      ['مسرحيه'],
                      ['بعد وطني'],
                      ['وحشيه'],
                      ['موشي'],
                      ['وضعيه البدايه'],
                      ['العقده'],
                      ['النهايه'],
                      ['الاستفهام'],
                      ['الوصف'],
                      ['الحوار'],
                      ['معاناه الشعب الفلسطيني'],
                      ['قيمه انسانيه']]},
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
        "الاختبار الأولي لنص حوار عجيب"
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
