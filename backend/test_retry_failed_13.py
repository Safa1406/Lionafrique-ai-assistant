import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from test_batch_17_65 import request_api, missing_groups

SPEC_PATH = Path("mega_batch_17_65_specs.json")
LESSONS = {18,21,22,23,24,32,43,45,50,51,53,59,64}
OUT_JSON = Path("mega_retry_failed_13_results.json")
OUT_CSV = Path("mega_retry_failed_13_results.csv")

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    docs = [d for d in spec["documents"] if d["lesson_number"] in LESSONS]

    all_rows = []
    summaries = []
    total_passed = 0
    total = 0

    print("=" * 110)
    print("RETRY FINAL - 13 PDF NON VALIDÉS")
    print("PDF:", len(docs), "| Tests:", len(docs) * 30)
    print("=" * 110)

    for doc in docs:
        source = doc["source"]
        lesson = doc["lesson_number"]
        passed = 0

        print("\n" + "#" * 110)
        print(f"PDF {lesson}/65 | {source}")
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
            total_passed += int(ok)
            total += 1

            mark = "✅" if ok else "❌"
            print(
                f"[{i:02d}/30] {mark} "
                f"{tc['category']} | {duration}s | {actual or 'ERROR'}"
            )
            if not ok:
                print("  Q:", tc["question"])
                if miss:
                    print("  Manquants:", miss)
                if not source_ok:
                    print("  Source attendue absente")
                if err:
                    print("  Erreur:", err)
                if text:
                    print("  Réponse:", text[:700].replace("\n", " "))

            all_rows.append({
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
        summaries.append({
            "lesson_number": lesson,
            "source": source,
            "passed": passed,
            "failed": failed,
        })
        print(
            f"RESULTAT PDF {lesson}: {passed}/30",
            "✅" if failed == 0 else f"| {failed} échec(s) ❌",
        )

    OUT_JSON.write_text(
        json.dumps({
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "passed": total_passed,
            "failed": total - total_passed,
            "total": total,
            "documents": summaries,
            "results": all_rows,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    print("\n" + "=" * 110)
    print("RESULTAT RETRY FINAL")
    print("=" * 110)
    print("Réussis:", total_passed)
    print("Échoués:", total - total_passed)
    print("Total:", total)

    bad = [d for d in summaries if d["failed"]]
    if not bad:
        print("\n13/13 PDF validés ✅")
        print("MEGA BATCH 17-65 = 1470/1470 ✅")
        print("FRANÇAIS = 65/65 PDF ✅")
    else:
        print("\nPDF encore non validés:")
        for d in bad:
            print(
                f"- PDF {d['lesson_number']}: "
                f"{d['passed']}/30 | {d['source']}"
            )

if __name__ == "__main__":
    main()
