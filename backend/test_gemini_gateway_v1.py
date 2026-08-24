from __future__ import annotations

import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEP = "=" * 120


def main() -> int:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
        sys.stderr.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    print(SEP)
    print("GEMINI V1 - QALQUL GATEWAY SMOKE TEST")
    print(SEP)

    service = ROOT / "services" / "gemini_service.py"

    py_compile.compile(
        str(service),
        doraise=True,
    )

    print("PY_COMPILE => PASS")

    try:
        import google.genai
    except Exception as exc:
        print("GOOGLE-GENAI IMPORT => FAIL")
        print(repr(exc))
        print()
        print(
            "RUN: .\\.venv\\Scripts\\python.exe -m pip install google-genai"
        )
        return 2

    print("GOOGLE-GENAI IMPORT => PASS")

    from services.gemini_service import (
        GEMINI_BASE_URL,
        GEMINI_MODEL,
        gemini_healthcheck,
    )

    print("MODEL:", GEMINI_MODEL)
    print("BASE URL:", GEMINI_BASE_URL)

    try:
        output = gemini_healthcheck()
    except Exception as exc:
        print("GEMINI REQUEST => FAIL")
        print(type(exc).__name__ + ":", str(exc))
        return 3

    response = str(
        output.get("response", "")
        or ""
    ).strip()

    print("GEMINI REQUEST => PASS")
    print("RESPONSE:", response)

    if "LIONAFRIQUE_GEMINI_OK" not in response:
        print("EXPECTED TOKEN => FAIL")
        return 4

    print("EXPECTED TOKEN => PASS")
    print()
    print("FINAL => PASS")
    print(SEP)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
