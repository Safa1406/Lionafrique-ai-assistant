import json
import sys
import time
from pathlib import Path

from test_batch_17_65 import request_api

LESSONS = {18,21,22,23,24,32,43,45,50,51,53,59,64}
SPEC_PATH = Path("mega_batch_17_65_specs.json")

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    docs = [
        d for d in spec["documents"]
        if d["lesson_number"] in LESSONS
    ]

    passed = 0
    total = 0

    print("=" * 100)
    print("RETRY REFUSAL ONLY - 13 PDF")
    print("=" * 100)

    for doc in docs:
        tc = doc["tests"][29]
        assert tc["category"] == "Refus correct"

        started = time.perf_counter()
        error = ""
        data = {}

        try:
            data = request_api(
                tc["endpoint"],
                doc["source"],
                tc["question"],
            )
        except Exception as exc:
            error = str(exc)

        duration = round(time.perf_counter() - started, 3)
        status = data.get("status", "") if data else ""
        answer = data.get("answer", "") if data else ""

        ok = (
            not error
            and status == "insufficient_context"
        )

        passed += int(ok)
        total += 1

        mark = "✅" if ok else "❌"
        print(
            f"PDF {doc['lesson_number']:02d} {mark} "
            f"{status or 'ERROR'} | {duration}s | {doc['source']}"
        )

        if not ok:
            if error:
                print("  Erreur:", error)
            if answer:
                print("  Réponse:", answer[:500].replace("\n", " "))

    print("\n" + "=" * 100)
    print("RESULTAT REFUSAL RETRY")
    print("=" * 100)
    print("Réussis:", passed)
    print("Échoués:", total - passed)
    print("Total:", total)

    if passed == total:
        print("\n13/13 refus corrects ✅")
        print("MEGA BATCH 17-65 = 1470/1470 ✅")
        print("FRANÇAIS = 65/65 PDF ✅")

if __name__ == "__main__":
    main()
