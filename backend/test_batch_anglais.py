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
SUBJECT = "Anglais"
SEMESTER = None
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 90
MAX_ATTEMPTS = 2
SPEC_PATH = Path("mega_anglais_specs.json")
OVERALL_JSON = Path("mega_anglais_results.json")
OVERALL_CSV = Path("mega_anglais_results.csv")


def normalize_text(text):
    s = unicodedata.normalize(
        "NFKC",
        (text or "").lower(),
    )

    s = (
        s.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )

    # OCR / punctuation equivalence:
    # 11p.m. == 11 p m
    # am/'m  == am m
    # I'm    == i m

    s = re.sub(
        r"(?<=\d)(?=[a-z])",
        " ",
        s,
    )

    s = re.sub(
        r"(?<=[a-z])(?=\d)",
        " ",
        s,
    )

    s = s.replace(
        "'",
        " ",
    )

    s = re.sub(
        r"[^\w\s\-]",
        " ",
        s,
        flags=re.UNICODE,
    )

    return re.sub(
        r"\s+",
        " ",
        s,
    ).strip()



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

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):
        req = urllib.request.Request(
            API_BASE_URL + endpoint,
            data=json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Content-Type":
                "application/json"
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                req,
                timeout=TIMEOUT_SECONDS,
            ) as response:
                return json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
        ) as exc:
            last_error = exc

            if attempt < MAX_ATTEMPTS:
                time.sleep(1)
                continue

            raise

    raise last_error


def _token_close(expected, actual):
    if expected == actual:
        return True

    if (
        len(expected) < 4
        or len(actual) < 4
    ):
        return False

    import difflib

    return (
        difflib.SequenceMatcher(
            None,
            expected,
            actual,
        ).ratio()
        >= 0.80
    )


def missing_groups(text, groups):
    nt = normalize_text(text)
    normalized_response = (
        nt.replace("-", " ")
    )

    response_tokens = [
        token
        for token in normalized_response.split()
        if token
    ]

    missing = []

    for group in groups:
        matched = False

        for alternative in group:
            a = (
                normalize_text(alternative)
                .replace("-", " ")
            )

            if not a:
                continue

            if a in normalized_response:
                matched = True
                break

            expected_tokens = [
                token
                for token in a.split()
                if token
            ]

            if not expected_tokens:
                continue

            fuzzy_matches = 0

            for expected in expected_tokens:
                if any(
                    _token_close(
                        expected,
                        actual,
                    )
                    for actual
                    in response_tokens
                ):
                    fuzzy_matches += 1

            coverage = (
                fuzzy_matches
                / len(expected_tokens)
            )

            if coverage >= 0.90:
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
    print("MEGA BATCH ANGLAIS")
    print("PDF uniques:", spec["total_pdfs"], "| Tests:", spec["total_tests"])
    print("Duplicates ignorés:", len(spec.get("duplicates", [])))
    print("=" * 110)

    total_docs = spec["total_pdfs"]

    for dindex, doc in enumerate(spec["documents"], 1):
        source = doc["source"]
        lesson = doc["lesson_number"]
        passed = 0
        rows = []

        print("\n" + "#" * 110)
        print(f"PDF {lesson}/{total_docs} | {dindex}/{total_docs} | {source}")
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
            sources = (data.get("sources") or []) if data else []
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
                print("  Question:", tc["question"])
                if miss:
                    print("  Missing:", miss)
                if not source_ok:
                    print("  Expected source missing")
                if err:
                    print("  Error:", err)
                if text:
                    print("  Answer:", text[:700].replace("\n", " "))

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
        Path(f"anglais_{lesson:02d}_{stem}_results.json").write_text(
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
    print("RESULTAT GLOBAL MEGA BATCH ANGLAIS")
    print("=" * 110)
    print("Réussis:", grand_passed)
    print("Échoués:", grand_total - grand_passed)
    print("Total:", grand_total)

    bad = [d for d in doc_summaries if d["failed"]]
    print("\nPDF non validés:")
    if not bad:
        print(f"Aucun. {total_docs}/{total_docs} PDF validés ✅")
        print(f"ANGLAIS = {grand_total}/{grand_total} ✅")
    else:
        for d in bad:
            print(
                f"- PDF {d['lesson_number']}: "
                f"{d['passed']}/30 | {d['source']}"
            )


if __name__ == "__main__":
    main()
