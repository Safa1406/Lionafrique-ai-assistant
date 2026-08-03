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
EXPECTED_SOURCE = "asm-altfdhil-siaghth.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v3-comparative-superlative-fair-morphology"

JSON_REPORT = Path("asm_altfdhil_siaghth_test_results_v3.json")
CSV_REPORT = Path("asm_altfdhil_siaghth_test_results_v3.csv")

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

TEST_CASES = [{'category': 'تعريف اسم التفضيل', 'endpoint': '/ask', 'question': 'ما تعريف اسم التفضيل؟', 'expected_status': 'success', 'required_groups': [['اسم مشتق'], ['شييين', 'شيئان', 'شيئين'], ['اشتركا', 'المشاركه'], ['صفه واحده'], ['زاد احدهما', 'يزيد احدهما']]}, {'category': 'وزن اسم التفضيل', 'endpoint': '/ask', 'question': 'ما وزن اسم التفضيل، وما صيغة مؤنثه؟', 'expected_status': 'success', 'required_groups': [['افعل'], ['فعلي']]}, {'category': 'مثال اسم التفضيل', 'endpoint': '/ask', 'question': 'ما اسم التفضيل الوارد في الآية: ليوسف وأخوه أحب إلى أبينا منا؟', 'expected_status': 'success', 'required_groups': [['احب'], ['افعل'], ['الحب']]}, {'category': 'الصياغة المباشرة', 'endpoint': '/ask', 'question': 'ما شروط صياغة اسم التفضيل مباشرة من الفعل؟', 'expected_status': 'success', 'required_groups': [['ثلاثيا'], ['متصرفا'], ['مثبتا'], ['تاما'], ['مبنيا للمعلوم'], ['قابلا للتفاضل', 'قابلا للتفاوت'], ['لون'], ['عيب'], ['حليه']]}, {'category': 'الأفعال الجامدة', 'endpoint': '/ask', 'question': 'ما الأفعال الجامدة التي لا يصاغ منها اسم التفضيل حسب الدرس؟', 'expected_status': 'success', 'required_groups': [['نعم'], ['بيس'], ['عسي'], ['ليس']]}, {'category': 'عدم قابلية التفاضل', 'endpoint': '/ask', 'question': 'اذكر الفعلين غير القابلين للتفاضل الواردين في الدرس.', 'expected_status': 'success', 'required_groups': [['مات'], ['فني']]}, {'category': 'الصياغة غير المباشرة', 'endpoint': '/ask', 'question': 'كيف يصاغ اسم التفضيل بطريقة غير مباشرة من فعل غير مستوف للشروط؟', 'expected_status': 'success', 'required_groups': [['مصدر الفعل', 'مصدره'], ['منصوبا'], ['التمييز'], ['فعل مساعد', 'اسم تفضيل مساعد'], ['افعل']]}, {'category': 'تطبيق الصياغة غير المباشرة', 'endpoint': '/ask', 'question': 'لماذا قيل: الشمس أشد حمرة في المساء، وكيف صيغ التفضيل؟', 'expected_status': 'success', 'required_groups': [['حمر'], ['لون'], ['اشد'], ['حمره'], ['تمييز']]}, {'category': 'الأفعال المساعدة', 'endpoint': '/ask', 'question': 'اذكر ثلاثة أفعال مساعدة على وزن أفعل تستعمل في الصياغة غير المباشرة.', 'expected_status': 'success', 'required_groups': [['اكثر'], ['اشد'], ['اقوي']]}, {'category': 'المبني للمجهول والمنفي', 'endpoint': '/ask', 'question': 'كيف يصاغ اسم التفضيل من الفعل المبني للمجهول أو المنفي؟', 'expected_status': 'success', 'required_groups': [['المصدر المول', 'المصدر الموول'], ['فعل مساعد', 'اسم التفضيل المساعد'], ['افعل']]}, {'category': 'تطبيق المبني للمجهول', 'endpoint': '/ask', 'question': 'اشرح صياغة التفضيل في جملة: الشرف أحق أن يصان.', 'expected_status': 'success', 'required_groups': [['يصان'], ['مبني للمجهول'], ['احق'], ['ان يصان'], ['مصدر مول', 'مصدر موول', 'المصدر المول', 'المصدر الموول']]}, {'category': 'تطبيق المنفي', 'endpoint': '/ask', 'question': 'اشرح صياغة التفضيل في جملة: الأجدر ألا ينسى المرء وطنه.', 'expected_status': 'success', 'required_groups': [['ينسي'], ['منفي'], ['الاجدر'], ['الا ينسي'], ['مصدر مول', 'مصدر موول', 'المصدر المول', 'المصدر الموول']]}, {'category': 'عمل اسم التفضيل', 'endpoint': '/ask', 'question': 'ما عمل اسم التفضيل؟', 'expected_status': 'success', 'required_groups': [['يرفع'], ['فاعلا'], ['ضميرا مستترا']]}, {'category': 'الفاعل المستتر', 'endpoint': '/ask', 'question': 'ما نوع الفاعل الذي رفعه اسم التفضيل أحب في الآية: ليوسف وأخوه أحب إلى أبينا منا؟', 'expected_status': 'success', 'required_groups': [['احب'], ['فاعل'], ['ضمير مستتر', 'ضميرا مستترا']]}, {'category': 'الفاعل الظاهر', 'endpoint': '/ask', 'question': 'ما الفاعل الظاهر الذي رفعه اسم التفضيل أجمل في جملة: ما شاهدت فتاة أجمل في عينها الكحل من فاطمة؟', 'expected_status': 'success', 'required_groups': [['اجمل'], ['الكحل'], ['فاعل'], ['ظاهر']]}, {'category': 'الفاعل الظاهر', 'endpoint': '/ask', 'question': 'ما الفاعل الظاهر الذي رفعه اسم التفضيل أحب في قول الدرس: وأحب أوطان البلاد إلى الفتى أرض ينال بها كريم المطلب؟', 'expected_status': 'success', 'required_groups': [['احب'], ['ارض'], ['فاعل'], ['ظاهر']]}, {'category': 'تصنيف الصياغة', 'endpoint': '/ask', 'question': 'هل صيغ اسم التفضيل في: الشمس أشد حمرة في المساء، بطريقة مباشرة أم غير مباشرة؟ علل جوابك.', 'expected_status': 'success', 'required_groups': [['غير مباشره'], ['لون'], ['اشد'], ['حمره']]}, {'category': 'معنى اسم الفاعل', 'endpoint': '/ask', 'question': 'هل يقصد التفضيل في قول الدرس: الله أعلم حيث يجعل رسالته؟', 'expected_status': 'success', 'required_groups': [['لا'], ['اسم الفاعل'], ['لا يقصد منه تفضيل', 'لا يقصد التفضيل']]}, {'category': 'أمثلة المصدر', 'endpoint': '/ask', 'question': 'ما اسما التفضيل والمصدران في المثالين: أنت أكثر إنفاقا وأسرع استجابة؟', 'expected_status': 'success', 'required_groups': [['اكثر'], ['انفاقا'], ['اسرع'], ['استجابه']]}, {'category': 'إعراب', 'endpoint': '/ask', 'question': 'ما إعراب العليا في جملة: المرتبة العليا من نصيب المجتهد؟', 'expected_status': 'success', 'required_groups': [['نعت'], ['مرفوع'], ['الضمه المقدره'], ['الالف'], ['التعذر']]}, {'category': 'إعراب', 'endpoint': '/ask', 'question': 'ما إعراب أشد وكرما في جملة: خليل أشد كرما من سعد؟', 'expected_status': 'success', 'required_groups': [['اشد'], ['خبر'], ['مرفوع'], ['كرما'], ['تمييز'], ['منصوب']]}, {'category': 'إعراب', 'endpoint': '/ask', 'question': 'ما إعراب أطول ومن الأيائل في جملة: الزرافات أطول من الأيائل؟', 'expected_status': 'success', 'required_groups': [['اطول'], ['خبر'], ['مرفوع'], ['من الايايل'], ['جار ومجرور'], ['متعلقان', 'متعلق']]}, {'category': 'إعراب', 'endpoint': '/ask', 'question': 'ما إعراب أكبر في جملة: أخواك أكبر من عمر؟', 'expected_status': 'success', 'required_groups': [['اكبر'], ['خبر'], ['مرفوع'], ['الضمه']]}, {'category': 'إعراب', 'endpoint': '/ask', 'question': 'لماذا جر عمر بالفتحة في جملة: أخواك أكبر من عمر؟', 'expected_status': 'success', 'required_groups': [['اسم مجرور'], ['الفتحه'], ['ممنوع من الصرف'], ['علم معدول'], ['عامر'], ['فعل']]}, {'category': 'إعراب', 'endpoint': '/ask', 'question': 'ما إعراب فضليا والنساء في جملة: خديجة وسعاد فضليا النساء؟', 'expected_status': 'success', 'required_groups': [['فضليا'], ['خبر'], ['مرفوع'], ['الالف'], ['مثني'], ['مضاف'], ['النساء'], ['مضاف اليه'], ['مجرور']]}, {'category': 'سؤال مركب', 'endpoint': '/ask', 'question': 'ما تعريف اسم التفضيل وكيف يصاغ بالطريقه المباشره وغير المباشره وكيف يعمل؟', 'expected_status': 'success', 'required_groups': [['اسم مشتق'], ['افعل'], ['ثلاثي', 'ثلاثيا'], ['متصرف', 'متصرفا'], ['فعل مساعد', 'اسم تفضيل مساعد'], ['مصدر'], ['تمييز'], ['يرفع'], ['فاعلا']]}, {'category': 'قاعدة إعرابية', 'endpoint': '/ask', 'question': 'كيف يعرب اسم التفضيل المعرف بأل إذا جاء بعد المفضل عليه؟', 'expected_status': 'success', 'required_groups': [['المعرف ب ال', 'المعرف بال'], ['بعد المفضل عليه'], ['نعتا', 'نعت']]}, {'category': 'تلخيص', 'endpoint': '/summarize', 'question': 'لخص درس اسم التفضيل وصياغته وعمله.', 'expected_status': 'success', 'required_groups': [['اسم التفضيل'], ['اسم مشتق'], ['افعل'], ['فعلي'], ['الصياغه المباشره', 'مباشره'], ['الصياغه غير المباشره', 'غير مباشره'], ['فاعل']]}, {'category': 'تلخيص', 'endpoint': '/summarize', 'question': 'لخص شروط صياغة اسم التفضيل مباشرة وغير مباشرة، وصياغته من المبني للمجهول والمنفي، وعمله.', 'expected_status': 'success', 'required_groups': [['ثلاثيا'], ['متصرفا'], ['مثبتا'], ['تاما'], ['مبنيا للمعلوم'], ['قابلا للتفاضل', 'التفاضل'], ['مصدر'], ['تمييز'], ['المصدر المول', 'المصدر الموول'], ['المبني للمجهول'], ['المنفي'], ['يرفع'], ['فاعلا']]}, {'category': 'رفض صحيح', 'endpoint': '/ask', 'question': 'ما أسرع حيوان في العالم؟', 'expected_status': 'insufficient_context', 'required_groups': []}]


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
        "الاختبار الأولي لدرس اسم التفضيل وصياغته"
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
