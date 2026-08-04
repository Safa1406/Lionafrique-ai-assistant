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
EXPECTED_SOURCE = "almmnoa-mn-alsrf.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-mamnu-min-al-sarf-baseline"

JSON_REPORT = Path("almmnoa_mn_alsrf_test_results.json")
CSV_REPORT = Path("almmnoa_mn_alsrf_test_results.csv")

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

TEST_CASES = [{'category': 'تعريف الممنوع من الصرف',
  'endpoint': '/ask',
  'question': 'ما تعريف الممنوع من الصرف حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['الاسم الممنوع من التنوين'],
                      ['يرفع بالضمه'],
                      ['ينصب بالفتحه'],
                      ['يجر بالفتحه'],
                      ['نائبه عن الكسره']]},
 {'category': 'خصائص عواقب',
  'endpoint': '/ask',
  'question': 'لماذا تعد كلمة عواقب ممنوعة من الصرف، وكيف تعرب في حالتي النصب والجر؟',
  'expected_status': 'success',
  'required_groups': [['لا تقبل التنوين'],
                      ['صيغه منتهي الجموع'],
                      ['منصوبه بالفتحه'],
                      ['مجروره بالفتحه'],
                      ['نائبه عن الكسره']]},
 {'category': 'المنع لسبب واحد',
  'endpoint': '/ask',
  'question': 'ما الحالات التي يمنع فيها الاسم من الصرف لسبب واحد؟',
  'expected_status': 'success',
  'required_groups': [['الف تانيث مقصوره'], ['الف تانيث ممدوده'], ['صيغه منتهي الجموع']]},
 {'category': 'ألف التأنيث المقصورة',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة الأسماء المختومة بألف التأنيث المقصورة الواردة في الوثيقة.',
  'expected_status': 'success',
  'required_groups': [['ذكري'], ['حبلي'], ['جرحي']]},
 {'category': 'ألف التأنيث الممدودة',
  'endpoint': '/ask',
  'question': 'اذكر أمثلة الأسماء المختومة بألف التأنيث الممدودة الواردة في الوثيقة.',
  'expected_status': 'success',
  'required_groups': [['صحراء'], ['حسناء'], ['عذراء']]},
 {'category': 'صيغة منتهى الجموع',
  'endpoint': '/ask',
  'question': 'ما تعريف صيغة منتهى الجموع، وما أمثلتها في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['جمع تكسير'],
                      ['في وسطه الف ساكنه'],
                      ['بعدها حرفان'],
                      ['ثلاثه احرف'],
                      ['عواقب'],
                      ['عصافير'],
                      ['مساجد']]},
 {'category': 'العلمية والتأنيث',
  'endpoint': '/ask',
  'question': 'متى يمنع العلم من الصرف للعلمية والتأنيث، وما أمثلته؟',
  'expected_status': 'success',
  'required_groups': [['العلميه'], ['التانيث'], ['فاطمه'], ['سعاد'], ['حمزه']]},
 {'category': 'العلمية وزيادة الألف والنون',
  'endpoint': '/ask',
  'question': 'ما حكم العلم المختوم بألف ونون زائدتين، وما أمثلته؟',
  'expected_status': 'success',
  'required_groups': [['العلميه'], ['زياده الالف والنون'], ['مروان'], ['رمضان'], ['عثمان']]},
 {'category': 'العلمية والعجمة',
  'endpoint': '/ask',
  'question': 'متى يمنع العلم الأعجمي من الصرف، وما أمثلته؟',
  'expected_status': 'success',
  'required_groups': [['علم اعجمي'], ['زائد علي ثلاثه احرف'], ['ابراهيم'], ['اسماعيل']]},
 {'category': 'العلمية ووزن الفعل',
  'endpoint': '/ask',
  'question': 'ما المقصود بالعلمية ووزن الفعل، وما أمثلتهما؟',
  'expected_status': 'success',
  'required_groups': [['العلميه'], ['وزن الفعل'], ['احمد'], ['يزيد']]},
 {'category': 'العلمية والتركيب المزجي',
  'endpoint': '/ask',
  'question': 'ما العلم المركب تركيبا مزجيا، وما أمثلته في الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['التركيب المزجي'], ['كلمتان'], ['كلمه واحده'], ['بعلبك'], ['حضرموت']]},
 {'category': 'العلمية والعدل',
  'endpoint': '/ask',
  'question': 'ما المقصود بالعلمية والعدل على وزن فعل، وما أمثلته؟',
  'expected_status': 'success',
  'required_groups': [['العلميه'], ['العدل'], ['وزن فعل'], ['عمر'], ['زحل']]},
 {'category': 'صفة أفعل فعلاء',
  'endpoint': '/ask',
  'question': 'متى تمنع الصفة على وزن أفعل من الصرف؟',
  'expected_status': 'success',
  'required_groups': [['صفه لمذكر'],
                      ['وزن افعل'],
                      ['مونثه فعلاء'],
                      ['افضل'],
                      ['اخضر'],
                      ['اعرج']]},
 {'category': 'صفة فعلان فعلى',
  'endpoint': '/ask',
  'question': 'متى تمنع الصفة على وزن فعلان من الصرف؟',
  'expected_status': 'success',
  'required_groups': [['وزن فعلان'], ['مونثه فعلي'], ['حيران'], ['عطشان'], ['غضبان']]},
 {'category': 'الصفة المعدولة في الأعداد',
  'endpoint': '/ask',
  'question': 'كيف تمنع الصفات العددية المعدولة من الصرف، وما أوزانها وأمثلتها؟',
  'expected_status': 'success',
  'required_groups': [['مفعل'], ['فعال'], ['مثني'], ['خماس'], ['مربع'], ['رباع'], ['معدوله']]},
 {'category': 'صفة أخر',
  'endpoint': '/ask',
  'question': 'لماذا تمنع كلمة أخر من الصرف حسب الوثيقة؟',
  'expected_status': 'success',
  'required_groups': [['صفه'], ['وزن فعل'], ['معدوله'], ['اخر']]},
 {'category': 'الجر بالكسرة',
  'endpoint': '/ask',
  'question': 'متى يجر الممنوع من الصرف بالكسرة؟',
  'expected_status': 'success',
  'required_groups': [['معرفا بال'], ['مضافا'], ['يجر بالكسره']]},
 {'category': 'العواقب وعواقب الاستلاب',
  'endpoint': '/ask',
  'question': 'لماذا جرت كلمتا العواقب وعواقب الاستلاب بالكسرة؟',
  'expected_status': 'success',
  'required_groups': [['العواقب'], ['معرفه بال'], ['عواقب الاستلاب'], ['مضافه'], ['الكسره']]},
 {'category': 'العلم الأعجمي الثلاثي',
  'endpoint': '/ask',
  'question': 'ما حكم العلم الأعجمي الثلاثي ساكن الوسط، وما الأمثلة الواردة؟',
  'expected_status': 'success',
  'required_groups': [['ثلاثيا'], ['ساكن الوسط'], ['ينون'], ['جاك'], ['جرج']]},
 {'category': 'الاسم المنقوص',
  'endpoint': '/ask',
  'question': 'ما حكم الاسم المنقوص إذا جاء على أوزان صيغة منتهى الجموع؟',
  'expected_status': 'success',
  'required_groups': [['تحذف ياوه'],
                      ['رفعا'],
                      ['جرا'],
                      ['تقدر عليها علامه الاعراب'],
                      ['تنوين عوض'],
                      ['الياء المحذوفه']]},
 {'category': 'إعراب عمر وعثمان',
  'endpoint': '/ask',
  'question': 'ما إعراب عمر وعثمان في جملة رضي الله عن عمر وعثمان؟',
  'expected_status': 'success',
  'required_groups': [['عمر'],
                      ['اسم مجرور'],
                      ['الفتحه نيابه عن الكسره'],
                      ['العلميه والعدل'],
                      ['عثمان'],
                      ['معطوف'],
                      ['العلميه وزياده الالف والنون']]},
 {'category': 'إعراب مساجد',
  'endpoint': '/ask',
  'question': 'ما إعراب مساجد في جملة صليت بمساجد؟',
  'expected_status': 'success',
  'required_groups': [['مساجد'],
                      ['اسم مجرور'],
                      ['الفتحه نيابه عن الكسره'],
                      ['ممنوع من الصرف']]},
 {'category': 'إعراب سلوى',
  'endpoint': '/ask',
  'question': 'ما إعراب سلوى في جملة مررت بسلوى؟',
  'expected_status': 'success',
  'required_groups': [['سلوي'],
                      ['اسم مجرور'],
                      ['الفتحه المقدره'],
                      ['التعذر'],
                      ['الف التانيث المقصوره']]},
 {'category': 'إعراب أحمد',
  'endpoint': '/ask',
  'question': 'ما إعراب أحمد في جملة زرت مدرسة أحمد؟',
  'expected_status': 'success',
  'required_groups': [['احمد'], ['مضاف اليه'], ['مجرور'], ['الفتحه'], ['العلميه ووزن الفعل']]},
 {'category': 'إعراب حضرموت',
  'endpoint': '/ask',
  'question': 'ما إعراب حضرموت في جملة جاب أبناء حضرموت الأرض؟',
  'expected_status': 'success',
  'required_groups': [['حضرموت'],
                      ['مضاف اليه'],
                      ['مجرور'],
                      ['الفتحه نيابه عن الكسره'],
                      ['العلميه والتركيب المزجي']]},
 {'category': 'إعراب إبراهيم',
  'endpoint': '/ask',
  'question': 'ما إعراب إبراهيم في جملة إسماعيل بن إبراهيم؟',
  'expected_status': 'success',
  'required_groups': [['ابراهيم'],
                      ['مضاف اليه'],
                      ['مجرور'],
                      ['الفتحه نيابه عن الكسره'],
                      ['العلميه والاعجميه']]},
 {'category': 'إعراب حسان',
  'endpoint': '/ask',
  'question': 'ما إعراب حسان في جملة قرأت شعر حسان؟',
  'expected_status': 'success',
  'required_groups': [['حسان'],
                      ['مضاف اليه'],
                      ['مجرور'],
                      ['الفتحه نيابه عن الكسره'],
                      ['العلميه وزياده الالف والنون']]},
 {'category': 'إعراب عطشان وأخر',
  'endpoint': '/ask',
  'question': 'ما إعراب عطشان في حيوان عطشان، وأخر في نسوة أخر؟',
  'expected_status': 'success',
  'required_groups': [['عطشان'],
                      ['نعت'],
                      ['مجرور'],
                      ['وزن فعلان'],
                      ['اخر'],
                      ['نعت'],
                      ['الفتحه'],
                      ['ممنوع من الصرف']]},
 {'category': 'تلخيص',
  'endpoint': '/summarize',
  'question': 'لخص درس الممنوع من الصرف مع أسبابه وأحكامه وأهم الأمثلة والإعراب.',
  'expected_status': 'success',
  'required_groups': [['الممنوع من الصرف'],
                      ['التنوين'],
                      ['الفتحه'],
                      ['الكسره'],
                      ['الف التانيث المقصوره'],
                      ['الف التانيث الممدوده'],
                      ['صيغه منتهي الجموع'],
                      ['العلميه'],
                      ['التانيث'],
                      ['العجمه'],
                      ['التركيب المزجي'],
                      ['وزن الفعل'],
                      ['افعل'],
                      ['فعلان'],
                      ['مفعل'],
                      ['فعال'],
                      ['معرفا بال'],
                      ['مضافا']]},
 {'category': 'رفض صحيح',
  'endpoint': '/ask',
  'question': 'ما عاصمة البرازيل؟',
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
        "الاختبار الأولي لدرس الممنوع من الصرف"
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
        "فلتر المصدر: almmnoa-mn-alsrf.pdf"
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
