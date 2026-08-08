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
SUBJECT = "?ducation islamique"
SEMESTER = None
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 90
MAX_ATTEMPTS = 2
SPEC_PATH = Path("mega_education_islamique_specs.json")
OVERALL_JSON = Path("mega_education_islamique_results.json")
OVERALL_CSV = Path("mega_education_islamique_results.csv")

ARABIC_DIACRITICS = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
)


def normalize_text(text):
    s = unicodedata.normalize("NFKC", (text or "").lower())
    s = ARABIC_DIACRITICS.sub("", s)
    s = s.translate(str.maketrans({
        "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
        "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه", "ـ": "",
    }))
    s = re.sub(r"[^\w\s-]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def request_api(endpoint, source, question):
    payload = {
        "question": question,
        "number_of_results": NUMBER_OF_RESULTS,
        "program": PROGRAM,
        "subject": SUBJECT,
        "semester": SEMESTER,
        "source": source,
    }
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(
            API_BASE_URL + endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(1)
                continue
            raise
    raise last_error


def missing_groups(text, groups):
    nt = normalize_text(text)
    response_tokens = set(nt.replace("-", " ").split())
    missing = []
    for group in groups:
        matched = False
        for alternative in group:
            a = normalize_text(alternative).replace("-", " ")
            if not a:
                continue
            if a in nt.replace("-", " "):
                matched = True
                break
            tokens = [t for t in a.split() if t]
            if tokens and all(t in response_tokens for t in tokens):
                matched = True
                break
        if not matched:
            missing.append(group)
    return missing


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    all_rows = []
    doc_summaries = []
    grand_passed = 0
    grand_total = 0

    print("=" * 110)
    print("MEGA BATCH EDUCATION ISLAMIQUE")
    print("PDF uniques:", spec["total_pdfs"], "| Tests:", spec["total_tests"])
    print("Duplicate ignoré:", len(spec.get("duplicates", [])))
    print("=" * 110)

    for dindex, doc in enumerate(spec["documents"], 1):
        source = doc["source"]
        lesson = doc["lesson_number"]
        passed = 0
        rows = []

        print("\n" + "#" * 110)
        print(f"PDF {lesson}/27 | {dindex}/27 | {source}")
        print("#" * 110)

        for i, tc in enumerate(doc["tests"], 1):
            started = time.perf_counter()
            err = ""
            data = {}
            try:
                data = request_api(tc["endpoint"], source, tc["question"])
            except Exception as exc:
                err = str(exc)

            duration = round(time.perf_counter() - started, 3)
            actual = data.get("status", "") if data else ""
            text = (
                data.get("summary", "")
                if tc["endpoint"] == "/summarize"
                else data.get("answer", "")
            )
            sources = data.get("sources") or [] if data else []
            miss = missing_groups(text, tc["required_groups"])

            source_ok = True
            if tc["expected_status"] == "success":
                source_ok = bool(sources) and all(
                    s.get("file", "") == source for s in sources
                )

            ok = (
                not err
                and actual == tc["expected_status"]
                and not miss
                and source_ok
            )

            passed += int(ok)
            grand_passed += int(ok)
            grand_total += 1
            mark = "✅" if ok else "❌"
            print(
                f"[{i:02d}/30] {mark} {tc['category']} | "
                f"{duration}s | {actual or 'ERROR'}"
            )

            if not ok:
                print("  السؤال:", tc["question"])
                if miss:
                    print("  العناصر الناقصة:", miss)
                if not source_ok:
                    print("  المصدر المتوقع غير موجود")
                if err:
                    print("  الخطأ:", err)
                if text:
                    print("  الجواب:", text[:700].replace("\n", " "))

            rows.append({
                "lesson_number": lesson,
                "source": source,
                "test_number": i,
                "category": tc["category"],
                "question": tc["question"],
                "expected_status": tc["expected_status"],
                "actual_status": actual,
                "passed": "oui" if ok else "non",
                "duration_seconds": duration,
                "missing_groups": json.dumps(miss, ensure_ascii=False),
                "source_ok": "oui" if source_ok else "non",
                "response": text,
                "error": err,
            })

        failed = 30 - passed
        print(
            f"RESULTAT PDF {lesson}: {passed}/30",
            "✅" if failed == 0 else f"| {failed} échec(s) ❌",
        )
        doc_summaries.append({
            "lesson_number": lesson,
            "source": source,
            "passed": passed,
            "failed": failed,
        })
        all_rows.extend(rows)

        stem = Path(source).stem
        Path(f"islamique_{lesson:02d}_{stem}_results.json").write_text(
            json.dumps({
                "lesson_number": lesson,
                "source": source,
                "passed": passed,
                "failed": failed,
                "results": rows,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    OVERALL_JSON.write_text(
        json.dumps({
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "passed": grand_passed,
            "failed": grand_total - grand_passed,
            "total": grand_total,
            "documents": doc_summaries,
            "results": all_rows,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with OVERALL_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    print("\n" + "=" * 110)
    print("RESULTAT GLOBAL MEGA BATCH EDUCATION ISLAMIQUE")
    print("=" * 110)
    print("Réussis:", grand_passed)
    print("Échoués:", grand_total - grand_passed)
    print("Total:", grand_total)

    bad = [d for d in doc_summaries if d["failed"]]
    print("\nPDF non validés:")
    if not bad:
        print("Aucun. 27/27 PDF validés ✅")
        print("EDUCATION ISLAMIQUE = 810/810 ✅")
    else:
        for d in bad:
            print(
                f"- PDF {d['lesson_number']}: "
                f"{d['passed']}/30 | {d['source']}"
            )


if __name__ == "__main__":
    main()
