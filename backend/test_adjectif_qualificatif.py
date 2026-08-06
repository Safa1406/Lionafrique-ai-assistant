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
SUBJECT = "Français"
SEMESTER = None
EXPECTED_SOURCE = (
    "l-adjectif-qualificatif-nature-fonction-et-accord.pdf"
)
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-adjectif-qualificatif-baseline"

JSON_REPORT = Path(
    "adjectif_qualificatif_test_results.json"
)
CSV_REPORT = Path(
    "adjectif_qualificatif_test_results.csv"
)

TEST_CASES = [
    {
        "category": "Définition",
        "endpoint": "/ask",
        "question": (
            "Qu'est-ce qu'un adjectif qualificatif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["classe grammaticale"],
            ["nature"],
            ["nom"],
            ["caractériser"],
            ["précision"],
        ],
    },
    {
        "category": "Nature",
        "endpoint": "/ask",
        "question": (
            "Quelle est la nature grammaticale de "
            "l'adjectif qualificatif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["classe grammaticale"],
            ["adjectif qualificatif"],
        ],
    },
    {
        "category": "Rôle",
        "endpoint": "/ask",
        "question": (
            "À quoi sert l'adjectif qualificatif "
            "lorsqu'il est associé à un nom ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["caractériser"],
            ["plus de précision", "précision"],
            ["nom"],
        ],
    },
    {
        "category": "Exemple jardin",
        "endpoint": "/ask",
        "question": (
            "Pourquoi « Un jardin magnifique » est-il "
            "plus précis que « un jardin » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["magnifique"],
            ["caractérise", "caractériser"],
            ["jardin"],
            ["plus précis", "précision"],
        ],
    },
    {
        "category": "Adjectif jardin",
        "endpoint": "/ask",
        "question": (
            "Dans « Un jardin magnifique », quel est "
            "l'adjectif qualificatif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["magnifique"],
            ["adjectif qualificatif"],
        ],
    },
    {
        "category": "Nom jardin",
        "endpoint": "/ask",
        "question": (
            "Dans « Un jardin magnifique », quel nom "
            "est caractérisé ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["jardin"],
        ],
    },
    {
        "category": "Fonctions",
        "endpoint": "/ask",
        "question": (
            "Quelles fonctions l'adjectif qualificatif "
            "peut-il avoir selon le cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["épithète"],
            ["attribut"],
        ],
    },
    {
        "category": "Définition épithète",
        "endpoint": "/ask",
        "question": (
            "Quand un adjectif qualificatif est-il "
            "épithète ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["épithète"],
            ["à côté du nom"],
            ["avant", "après"],
        ],
    },
    {
        "category": "Position épithète",
        "endpoint": "/ask",
        "question": (
            "Où peut se placer un adjectif qualificatif "
            "épithète par rapport au nom ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["avant"],
            ["après"],
            ["nom"],
        ],
    },
    {
        "category": "Exemple épithète",
        "endpoint": "/ask",
        "question": (
            "Dans « Un élève intelligent », quel est "
            "l'adjectif qualificatif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["intelligent"],
            ["adjectif qualificatif"],
        ],
    },
    {
        "category": "Fonction intelligent",
        "endpoint": "/ask",
        "question": (
            "Quelle est la fonction de « intelligent » "
            "dans « Un élève intelligent » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["épithète"],
        ],
    },
    {
        "category": "Nom élève épithète",
        "endpoint": "/ask",
        "question": (
            "Dans « Un élève intelligent », quel nom "
            "est qualifié par l'adjectif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["élève"],
        ],
    },
    {
        "category": "Définition attribut",
        "endpoint": "/ask",
        "question": (
            "Quand un adjectif qualificatif est-il "
            "attribut ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["attribut"],
            ["séparé du nom"],
            ["verbe d'état"],
        ],
    },
    {
        "category": "Lien attribut",
        "endpoint": "/ask",
        "question": (
            "Par quoi l'adjectif attribut est-il séparé "
            "du nom ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["verbe d'état"],
        ],
    },
    {
        "category": "Exemple attribut",
        "endpoint": "/ask",
        "question": (
            "Dans « Cet élève est intelligent », quel "
            "est l'adjectif qualificatif attribut ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["intelligent"],
            ["attribut"],
        ],
    },
    {
        "category": "Verbe état",
        "endpoint": "/ask",
        "question": (
            "Quel est le verbe d'état dans "
            "« Cet élève est intelligent » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["est"],
            ["verbe d'état"],
        ],
    },
    {
        "category": "Nom élève attribut",
        "endpoint": "/ask",
        "question": (
            "Dans « Cet élève est intelligent », quel "
            "nom est caractérisé par « intelligent » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["élève"],
        ],
    },
    {
        "category": "Comparaison fonctions",
        "endpoint": "/ask",
        "question": (
            "Quelle est la différence entre un adjectif "
            "épithète et un adjectif attribut ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["épithète"],
            ["à côté du nom", "avant ou après"],
            ["attribut"],
            ["verbe d'état"],
        ],
    },
    {
        "category": "Règle accord",
        "endpoint": "/ask",
        "question": (
            "Avec quoi l'adjectif qualificatif "
            "s'accorde-t-il ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["genre"],
            ["nombre"],
            ["nom"],
        ],
    },
    {
        "category": "Deux accords",
        "endpoint": "/ask",
        "question": (
            "Quels sont les deux éléments d'accord de "
            "l'adjectif qualificatif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["genre"],
            ["nombre"],
        ],
    },
    {
        "category": "Fille sérieuse",
        "endpoint": "/ask",
        "question": (
            "Dans « Une fille sérieuse », quel est "
            "l'adjectif qualificatif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["sérieuse"],
        ],
    },
    {
        "category": "Accord féminin singulier",
        "endpoint": "/ask",
        "question": (
            "Pourquoi écrit-on « sérieuse » dans "
            "« Une fille sérieuse » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["féminin"],
            ["singulier"],
            ["fille"],
            ["accord"],
        ],
    },
    {
        "category": "Filles sérieuses",
        "endpoint": "/ask",
        "question": (
            "Dans « Des filles sérieuses », sous quelle "
            "forme l'adjectif est-il accordé ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["sérieuses"],
            ["féminin"],
            ["pluriel"],
        ],
    },
    {
        "category": "Transformation féminin",
        "endpoint": "/ask",
        "question": (
            "Transforme « Une fille sérieuse » au pluriel "
            "selon l'exemple du cours."
        ),
        "expected_status": "success",
        "required_groups": [
            ["Des filles sérieuses"],
        ],
    },
    {
        "category": "Garçon gentil",
        "endpoint": "/ask",
        "question": (
            "Dans « Un garçon gentil », quel est "
            "l'adjectif qualificatif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["gentil"],
        ],
    },
    {
        "category": "Garçons gentils",
        "endpoint": "/ask",
        "question": (
            "Comment l'adjectif « gentil » s'accorde-t-il "
            "dans « Des garçons gentils » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["gentils"],
            ["masculin"],
            ["pluriel"],
        ],
    },
    {
        "category": "Transformation masculin",
        "endpoint": "/ask",
        "question": (
            "Transforme « Un garçon gentil » au pluriel "
            "selon l'exemple du cours."
        ),
        "expected_status": "success",
        "required_groups": [
            ["Des garçons gentils"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": (
            "Comant l'adjectife qualificatife s'acorde "
            "avec le non et quelle fonction peut il avoir ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["genre"],
            ["nombre"],
            ["nom"],
            ["épithète"],
            ["attribut"],
        ],
    },
    {
        "category": "Résumé",
        "endpoint": "/summarize",
        "question": (
            "Résume le cours sur la nature, les fonctions "
            "et l'accord de l'adjectif qualificatif."
        ),
        "expected_status": "success",
        "required_groups": [
            ["classe grammaticale"],
            ["caractériser"],
            ["épithète"],
            ["attribut"],
            ["verbe d'état"],
            ["genre"],
            ["nombre"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": (
            "Quelle est la capitale du Canada ?"
        ),
        "expected_status": "insufficient_context",
        "required_groups": [],
    },
]


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
    normalized = re.sub(
        r"[^\w\s'-]",
        " ",
        normalized,
        flags=re.UNICODE,
    )
    return re.sub(r"\s+", " ", normalized).strip()


def make_request(endpoint: str, question: str) -> dict:
    payload = {
        "question": question,
        "number_of_results": NUMBER_OF_RESULTS,
        "program": PROGRAM,
        "subject": SUBJECT,
        "semester": SEMESTER,
        "source": EXPECTED_SOURCE,
    }

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(
            f"{API_BASE_URL}{endpoint}",
            data=json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=TIMEOUT_SECONDS,
            ) as response:
                return json.loads(
                    response.read().decode("utf-8")
                )

        except urllib.error.HTTPError as error:
            last_error = error

            if error.code == 503 and attempt < MAX_ATTEMPTS:
                print(
                    "Réponse HTTP 503 : nouvelle tentative "
                    "dans 2 secondes..."
                )
                time.sleep(2)
                continue

            raise

        except urllib.error.URLError as error:
            last_error = error

            if attempt < MAX_ATTEMPTS:
                print(
                    "Connexion temporairement indisponible : "
                    "nouvelle tentative dans 2 secondes..."
                )
                time.sleep(2)
                continue

            raise

    raise last_error


def extract_response_text(
    endpoint: str,
    response_data: dict,
) -> str:
    if endpoint == "/summarize":
        return response_data.get("summary", "")

    return response_data.get("answer", "")


def source_is_correct(sources: list[dict]) -> bool:
    if not sources:
        return False

    return all(
        source.get("file", "") == EXPECTED_SOURCE
        for source in sources
    )


def find_missing_groups(
    response_text: str,
    required_groups: list[list[str]],
) -> list[list[str]]:
    normalized_response = normalize_text(response_text)
    missing_groups = []

    for group in required_groups:
        normalized_alternatives = [
            normalize_text(term)
            for term in group
        ]

        if not any(
            alternative
            and alternative in normalized_response
            for alternative in normalized_alternatives
        ):
            missing_groups.append(group)

    return missing_groups


def format_sources(sources: list[dict]) -> str:
    return " ; ".join(
        (
            f"{source.get('file', 'source inconnue')}"
            f" | page {source.get('page', '?')}"
        )
        for source in sources
    )


def main() -> None:
    configure_console()

    print("=" * 100)
    print(
        "Test initial du cours : "
        "L'adjectif qualificatif"
    )
    print("=" * 100)
    print("Version du test:", TEST_VERSION)
    print("Nombre de tests:", len(TEST_CASES))
    print("Source attendue:", EXPECTED_SOURCE)
    print("Filtre de source:", EXPECTED_SOURCE)

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
        expected_status = test_case["expected_status"]

        category_totals[category] = (
            category_totals.get(category, 0) + 1
        )

        print()
        print("-" * 100)
        print(
            f"[{index}/{len(TEST_CASES)}] "
            f"[{category}]"
        )
        print("Question:", question)

        started_at = time.perf_counter()
        actual_status = ""
        response_text = ""
        sources = []
        error_text = ""

        try:
            response_data = make_request(
                endpoint,
                question,
            )
            actual_status = response_data.get("status", "")
            response_text = extract_response_text(
                endpoint,
                response_data,
            )
            sources = response_data.get("sources") or []

        except TimeoutError:
            error_text = (
                "Le délai de la requête a dépassé "
                f"{TIMEOUT_SECONDS} secondes."
            )

        except urllib.error.URLError as error:
            error_text = (
                "Impossible de contacter FastAPI : "
                f"{error}"
            )

        except Exception as error:
            error_text = (
                f"Erreur inattendue : {error}"
            )

        duration = round(
            time.perf_counter() - started_at,
            3,
        )

        missing_groups = find_missing_groups(
            response_text,
            test_case["required_groups"],
        )

        requires_source = expected_status == "success"
        correct_source = (
            source_is_correct(sources)
            if requires_source
            else True
        )

        test_passed = (
            not error_text
            and actual_status == expected_status
            and not missing_groups
            and correct_source
        )

        if test_passed:
            passed_count += 1
            category_passed[category] = (
                category_passed.get(category, 0) + 1
            )
            result_label = "RÉUSSI ✅"
        else:
            failed_count += 1
            result_label = "ÉCHEC ❌"

        print("Statut attendu:", expected_status)
        print("Statut obtenu:", actual_status or "absent")
        print("Durée:", duration, "seconde(s)")

        if response_text:
            print()
            print("Réponse:")
            print(response_text)

        if sources:
            print()
            print("Sources:", format_sources(sources))

        if missing_groups:
            print()
            print(
                "Concepts manquants:",
                missing_groups,
            )

        if requires_source and not correct_source:
            print()
            print("La source attendue est absente.")

        if error_text:
            print()
            print(error_text)

        print()
        print("Résultat du test:", result_label)

        results.append(
            {
                "number": index,
                "category": category,
                "endpoint": endpoint,
                "question": question,
                "expected_status": expected_status,
                "actual_status": actual_status,
                "test_passed": (
                    "oui" if test_passed else "non"
                ),
                "duration_seconds": duration,
                "response": response_text,
                "missing_groups": json.dumps(
                    missing_groups,
                    ensure_ascii=False,
                ),
                "correct_source": (
                    "oui" if correct_source else "non"
                ),
                "sources": format_sources(sources),
                "error": error_text,
            }
        )

    category_summary = {}

    for category, total in category_totals.items():
        passed = category_passed.get(category, 0)
        category_summary[category] = {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        }

    report = {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "test_version": TEST_VERSION,
        "program": PROGRAM,
        "subject": SUBJECT,
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
        writer = csv.DictWriter(
            csv_file,
            fieldnames=list(results[0].keys()),
        )
        writer.writeheader()
        writer.writerows(results)

    print()
    print("=" * 100)
    print("RÉSULTAT FINAL")
    print("=" * 100)
    print("Réussis:", passed_count)
    print("Échoués:", failed_count)
    print("Total:", len(TEST_CASES))

    print()
    print("Résultats par catégorie:")

    for category, summary in category_summary.items():
        print(
            f"- {category}: "
            f"{summary['passed']}/{summary['total']}"
        )

    print()
    print("Rapports enregistrés:")
    print(JSON_REPORT.resolve())
    print(CSV_REPORT.resolve())


if __name__ == "__main__":
    main()
