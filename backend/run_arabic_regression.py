from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ARABIC_SOURCES = [
    "aslob-almdh-oalthm.pdf",
    "aslob-alastfham.pdf",
    "aslob-alakhtsas.pdf",
    "aslob-alndaa.pdf",
    "aslob-altajb.pdf",
    "aslob-alththir-oalighraa.pdf",
    "asm-alaala.pdf",
    "asm-alfaal-osigh-almbalgha-oamlhma.pdf",
    "asm-almfaol-oamlh.pdf",
    "asm-altfdhil-siaghth.pdf",
    "asmaa-alzman-oalmkan.pdf",
    "hoar-ajib.pdf",
    "khsal-almslm.pdf",
    "klim-allh.pdf",
    "mdrsa-alhiaa.pdf",
    "mhara-alsrd-ktaba-aliomiat.pdf",
    "mhara-altaqib-oaltaliq.pdf",
    "mhara-osf-alshkhos-oalamkna.pdf",
    "mhara-osf-rhla.pdf",
    "otni-ns-shari.pdf",
    "alaghnia-alabdia.pdf",
    "alialal.pdf",
    "alibdal.pdf",
    "alidhafa.pdf",
    "alislam-ohqoq-alinsan.pdf",
    "aljrad.pdf",
    "almmnoa-mn-alsrf.pdf",
    "almnfa.pdf",
    "alnsba (1).pdf",
    "alsfa-almshbha.pdf",
    "altdrb-ala-ktaba-sira-thatia-ao-ghiria.pdf",
    "altdrb-ala-tkhil-hkaia-ajiba-ao-mn-alkhial-alalmi.pdf",
    "altsghir.pdf",
]

EXPECTED_TOTAL = len(ARABIC_SOURCES)
SERVER_URL = "http://127.0.0.1:8000/openapi.json"

# بعض الدروس عندها اختبارات قديمة ونسخ نهائية مرقمة.
# نستعمل النسخة النهائية التي سبق أن اجتازت 30/30.
PREFERRED_TEST_FILES = {
    "aslob-almdh-oalthm.pdf": "test_all_arabic_questions.py",
    "aslob-altajb.pdf": "test_altajb_v4.py",
    "aslob-alththir-oalighraa.pdf": "test_alththir_oalighraa_v2.py",
    "asm-almfaol-oamlh.pdf": "test_asm_almfaol_oamlh_v2.py",
    "asm-altfdhil-siaghth.pdf": "test_asm_altfdhil_siaghth_v3.py",
}

JSON_REPORT = Path("arabic_regression_results.json")
CSV_REPORT = Path("arabic_regression_results.csv")
TEXT_REPORT = Path("arabic_regression_output.txt")


@dataclass
class Candidate:
    path: Path
    source: str
    test_version: str
    case_count: int
    modified_at: float


def normalize_source(value: str) -> str:
    return value.strip().replace("\\", "/").split("/")[-1].lower()


SOURCE_LOOKUP = {
    normalize_source(source): source
    for source in ARABIC_SOURCES
}


def literal_assignment(tree: ast.AST, name: str):
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.Assign):
            continue

        if not any(
            isinstance(target, ast.Name)
            and target.id == name
            for target in node.targets
        ):
            continue

        try:
            return ast.literal_eval(node.value)
        except Exception:
            return None

    return None


def inspect_test_file(path: Path) -> Candidate | None:
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None

    source = literal_assignment(tree, "EXPECTED_SOURCE")
    version = literal_assignment(tree, "TEST_VERSION")
    cases = literal_assignment(tree, "TEST_CASES")

    if not isinstance(cases, list):
        cases = literal_assignment(tree, "TESTS")

    # الاختبار القديم لدرس المدح والذم لا يعرّف EXPECTED_SOURCE.
    if (
        path.name == "test_all_arabic_questions.py"
        and not isinstance(source, str)
    ):
        source = "aslob-almdh-oalthm.pdf"

    if not isinstance(source, str):
        match = re.search(
            r'EXPECTED_SOURCE\s*=\s*["\']([^"\']+\.pdf)["\']',
            text,
        )
        source = match.group(1) if match else None

    if not isinstance(source, str):
        return None

    canonical_source = SOURCE_LOOKUP.get(
        normalize_source(source)
    )

    if canonical_source is None:
        return None

    case_count = len(cases) if isinstance(cases, list) else 0

    if (
        path.name == "test_all_arabic_questions.py"
        and case_count == 0
    ):
        case_count = 38

    version_text = version if isinstance(version, str) else ""

    return Candidate(
        path=path,
        source=canonical_source,
        test_version=version_text,
        case_count=case_count,
        modified_at=path.stat().st_mtime,
    )


def candidate_rank(candidate: Candidate) -> tuple:
    stem = candidate.path.stem.lower()

    undesirable = any(
        token in stem
        for token in (
            "backup",
            "before",
            "old",
            "copy",
            "debug",
            "diagnose",
            "problematic",
            "remaining",
            "pipeline",
        )
    )

    version_suffix = bool(
        re.search(r"(?:_v|-v)\d+$", stem)
    )

    exact_30 = candidate.case_count == 30
    baseline = "baseline" in candidate.test_version.lower()

    return (
        not undesirable,
        not version_suffix,
        exact_30,
        baseline,
        candidate.case_count,
        candidate.modified_at,
    )


def discover_tests(
    backend_dir: Path,
) -> tuple[dict[str, Candidate], dict[str, list[Candidate]]]:
    grouped: dict[str, list[Candidate]] = {
        source: []
        for source in ARABIC_SOURCES
    }

    for path in backend_dir.glob("test_*.py"):
        if path.name == Path(__file__).name:
            continue

        candidate = inspect_test_file(path)

        if candidate is not None:
            grouped[candidate.source].append(candidate)

    selected: dict[str, Candidate] = {}

    for source, candidates in grouped.items():
        if not candidates:
            continue

        preferred_name = PREFERRED_TEST_FILES.get(source)

        if preferred_name:
            preferred = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.path.name == preferred_name
                ),
                None,
            )

            if preferred is not None:
                selected[source] = preferred
                continue

        candidates.sort(
            key=candidate_rank,
            reverse=True,
        )
        selected[source] = candidates[0]

    return selected, grouped


def show_manifest(
    selected: dict[str, Candidate],
    grouped: dict[str, list[Candidate]],
) -> bool:
    print("=" * 100)
    print("لائحة اختبارات Regression العربية")
    print("=" * 100)

    missing = [
        source
        for source in ARABIC_SOURCES
        if source not in selected
    ]

    for index, source in enumerate(
        ARABIC_SOURCES,
        start=1,
    ):
        candidate = selected.get(source)

        if candidate is None:
            print(
                f"[{index:02d}/{EXPECTED_TOTAL}] "
                f"مفقود ❌ | {source}"
            )
            continue

        print(
            f"[{index:02d}/{EXPECTED_TOTAL}] "
            f"{candidate.path.name} | "
            f"{candidate.case_count} اختبار | "
            f"{candidate.test_version or 'بدون إصدار'}"
        )

        alternatives = [
            item
            for item in grouped[source]
            if item.path != candidate.path
        ]

        if alternatives:
            names = ", ".join(
                item.path.name
                for item in alternatives
            )
            print(f"             بدائل متجاهلة: {names}")

    print("-" * 100)
    print(
        f"الموجود: {len(selected)}/{EXPECTED_TOTAL}"
    )

    if missing:
        print("\nالاختبارات المفقودة:")
        for source in missing:
            print(f"- {source}")
        return False

    print("اللائحة كاملة ✅")
    return True


def check_fastapi() -> None:
    try:
        with urllib.request.urlopen(
            SERVER_URL,
            timeout=10,
        ) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"FastAPI أعاد HTTP {response.status}"
                )
    except (
        urllib.error.URLError,
        TimeoutError,
        RuntimeError,
    ) as error:
        raise RuntimeError(
            "FastAPI غير جاهز على 127.0.0.1:8000. "
            "شغله أولاً ثم أعد الأمر."
        ) from error


def parse_counts(output: str) -> tuple[int | None, int | None, int | None]:
    success_match = re.search(
        r"(?:الناجحة|الاختبارات الناجحة):\s*(\d+)",
        output,
    )
    failed_match = re.search(
        r"(?:الفاشلة|الاختبارات الفاشلة):\s*(\d+)",
        output,
    )
    total_match = re.search(
        r"(?:المجموع|مجموع الاختبارات):\s*(\d+)",
        output,
    )

    successful = (
        int(success_match.group(1))
        if success_match
        else None
    )
    failed = (
        int(failed_match.group(1))
        if failed_match
        else None
    )
    total = (
        int(total_match.group(1))
        if total_match
        else None
    )

    return successful, failed, total


def run_test_process(
    backend_dir: Path,
    candidate: Candidate,
) -> tuple[subprocess.CompletedProcess[str], int]:
    """تشغيل الاختبار مع إعادة واحدة عند خطأ اتصال مؤقت."""

    attempts = 2
    last_process = None

    for attempt in range(1, attempts + 1):
        process = subprocess.run(
            [sys.executable, candidate.path.name],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )
        last_process = process

        combined_output = (
            process.stdout
            + (
                "\n[STDERR]\n" + process.stderr
                if process.stderr
                else ""
            )
        )

        transient_error = (
            "HTTP Error 503" in combined_output
            or "Service Unavailable" in combined_output
            or "تعذر الاتصال بـFastAPI" in combined_output
        )

        if not transient_error or attempt == attempts:
            return process, attempt

        print(
            "503 مؤقت، إعادة الاختبار مرة واحدة ...",
            end=" ",
            flush=True,
        )
        time.sleep(3)

    assert last_process is not None
    return last_process, attempts


def run_regression(
    backend_dir: Path,
    selected: dict[str, Candidate],
) -> int:
    check_fastapi()

    started_at = datetime.now().isoformat(timespec="seconds")
    overall_start = time.perf_counter()

    results: list[dict] = []
    full_logs: list[str] = []

    print("\n" + "=" * 100)
    print("بدء الاختبار الشامل للدروس العربية")
    print("=" * 100)

    for index, source in enumerate(
        ARABIC_SOURCES,
        start=1,
    ):
        candidate = selected[source]
        start = time.perf_counter()

        print(
            f"[{index:02d}/{EXPECTED_TOTAL}] "
            f"{candidate.path.name} ...",
            end=" ",
            flush=True,
        )

        process, attempts_used = run_test_process(
            backend_dir=backend_dir,
            candidate=candidate,
        )

        duration = round(
            time.perf_counter() - start,
            3,
        )

        combined_output = (
            process.stdout
            + (
                "\n[STDERR]\n" + process.stderr
                if process.stderr
                else ""
            )
        )

        successful, failed, total = parse_counts(
            combined_output
        )

        expected_count = (
            candidate.case_count
            if candidate.case_count > 0
            else total
        )

        passed = (
            process.returncode == 0
            and failed == 0
            and total is not None
            and successful == total
            and (
                expected_count is None
                or total == expected_count
            )
        )

        status = "PASS" if passed else "FAIL"
        print(
            f"{status} | "
            f"{successful if successful is not None else '?'}"
            f"/{total if total is not None else '?'} | "
            f"{duration}s"
        )

        results.append(
            {
                "source": source,
                "test_file": candidate.path.name,
                "test_version": candidate.test_version,
                "case_count_declared": candidate.case_count,
                "successful": successful,
                "failed": failed,
                "total": total,
                "return_code": process.returncode,
                "attempts_used": attempts_used,
                "duration_seconds": duration,
                "status": status,
            }
        )

        full_logs.append(
            "\n".join(
                [
                    "=" * 100,
                    f"SOURCE: {source}",
                    f"TEST: {candidate.path.name}",
                    f"STATUS: {status}",
                    "=" * 100,
                    combined_output,
                ]
            )
        )

        if not passed:
            tail = "\n".join(
                combined_output.splitlines()[-25:]
            )
            print("\nآخر سطور الخطأ:")
            print(tail)
            print()

    duration_total = round(
        time.perf_counter() - overall_start,
        3,
    )

    passed_count = sum(
        1
        for row in results
        if row["status"] == "PASS"
    )
    failed_count = EXPECTED_TOTAL - passed_count

    payload = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "duration_seconds": duration_total,
        "expected_lessons": EXPECTED_TOTAL,
        "passed_lessons": passed_count,
        "failed_lessons": failed_count,
        "all_passed": failed_count == 0,
        "results": results,
    }

    JSON_REPORT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with CSV_REPORT.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(results[0].keys()),
        )
        writer.writeheader()
        writer.writerows(results)

    TEXT_REPORT.write_text(
        "\n\n".join(full_logs),
        encoding="utf-8",
    )

    print("\n" + "=" * 100)
    print("النتيجة النهائية للـRegression")
    print("=" * 100)
    print(f"الدروس الناجحة: {passed_count}/{EXPECTED_TOTAL}")
    print(f"الدروس الفاشلة: {failed_count}")
    print(f"المدة الإجمالية: {duration_total} ثانية")
    print("\nالتقارير:")
    print(JSON_REPORT.resolve())
    print(CSV_REPORT.resolve())
    print(TEXT_REPORT.resolve())

    if failed_count == 0:
        print("\nجميع الدروس العربية ناجحة ✅")
        return 0

    print("\nكاين Regression فدرس واحد أو أكثر ❌")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "تشغيل Regression شامل لاختبارات "
            "الدروس العربية الـ33."
        )
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="عرض الاختبارات المختارة دون تشغيلها.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="تشغيل الاختبارات وإنشاء التقارير.",
    )
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parent
    selected, grouped = discover_tests(
        backend_dir
    )

    manifest_ok = show_manifest(
        selected,
        grouped,
    )

    if not manifest_ok:
        return 2

    if args.run:
        return run_regression(
            backend_dir,
            selected,
        )

    if not args.list:
        print(
            "\nاستعمل --run لتشغيل الاختبارات، "
            "أو --list لعرض اللائحة فقط."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
