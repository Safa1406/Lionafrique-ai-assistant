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
EXPECTED_SOURCE = "caracteriser-un-nom.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-characterize-a-noun-baseline"

JSON_REPORT = Path("caracteriser_un_nom_test_results.json")
CSV_REPORT = Path("caracteriser_un_nom_test_results.csv")

TEST_CASES = [
    {
        "category": "Définition générale",
        "endpoint": "/ask",
        "question": "Que signifie caractériser un nom ?",
        "expected_status": "success",
        "required_groups": [
            ["attribuer"],
            ["une ou plusieurs caractéristiques précises"],
            ["rendre plus clair"],
            ["procédés grammaticaux"],
        ],
    },
    {
        "category": "Objectif",
        "endpoint": "/ask",
        "question": "Pourquoi caractérise-t-on un nom ?",
        "expected_status": "success",
        "required_groups": [
            ["rendre plus clair"],
            ["caractéristiques précises"],
        ],
    },
    {
        "category": "Procédés",
        "endpoint": "/ask",
        "question": "Quels procédés grammaticaux peut-on utiliser pour caractériser un nom ?",
        "expected_status": "success",
        "required_groups": [
            ["adjectif qualificatif épithète"],
            ["adjectif qualificatif attribut"],
            ["complément de nom"],
            ["subordonnée relative"],
            ["complément d'antécédent", "complément de l'antécédent"],
        ],
    },
    {
        "category": "Définition épithète",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un adjectif qualificatif épithète ?",
        "expected_status": "success",
        "required_groups": [
            ["adjectif qualificatif épithète"],
            ["directement placé"],
            ["avant", "après"],
            ["nom"],
        ],
    },
    {
        "category": "Position épithète",
        "endpoint": "/ask",
        "question": "Où peut être placé l'adjectif qualificatif épithète par rapport au nom ?",
        "expected_status": "success",
        "required_groups": [
            ["avant"],
            ["après"],
            ["nom"],
        ],
    },
    {
        "category": "Exemple petit",
        "endpoint": "/ask",
        "question": "Dans « un petit garçon », quel est l'adjectif qualificatif épithète ?",
        "expected_status": "success",
        "required_groups": [
            ["petit"],
            ["adjectif qualificatif épithète"],
        ],
    },
    {
        "category": "Nom garçon",
        "endpoint": "/ask",
        "question": "Dans « un petit garçon », quel nom est caractérisé ?",
        "expected_status": "success",
        "required_groups": [
            ["garçon"],
        ],
    },
    {
        "category": "Exemple drôle",
        "endpoint": "/ask",
        "question": "Dans « Une histoire drôle », quel est l'adjectif qualificatif épithète ?",
        "expected_status": "success",
        "required_groups": [
            ["drôle"],
            ["adjectif qualificatif épithète"],
        ],
    },
    {
        "category": "Nom histoire",
        "endpoint": "/ask",
        "question": "Dans « Une histoire drôle », quel nom est caractérisé ?",
        "expected_status": "success",
        "required_groups": [
            ["histoire"],
        ],
    },
    {
        "category": "Définition attribut",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un adjectif qualificatif attribut ?",
        "expected_status": "success",
        "required_groups": [
            ["adjectif qualificatif attribut"],
            ["séparé du nom"],
            ["verbe d'état"],
        ],
    },
    {
        "category": "Lien attribut",
        "endpoint": "/ask",
        "question": "Par quel type de verbe l'adjectif qualificatif attribut est-il séparé du nom ?",
        "expected_status": "success",
        "required_groups": [
            ["verbe d'état"],
        ],
    },
    {
        "category": "Exemple magnifique",
        "endpoint": "/ask",
        "question": "Dans « Ce tableau est magnifique », quel est l'adjectif qualificatif attribut ?",
        "expected_status": "success",
        "required_groups": [
            ["magnifique"],
            ["adjectif qualificatif attribut"],
        ],
    },
    {
        "category": "Verbe est",
        "endpoint": "/ask",
        "question": "Dans « Ce tableau est magnifique », quel est le verbe d'état ?",
        "expected_status": "success",
        "required_groups": [
            ["est"],
        ],
    },
    {
        "category": "Exemple calme",
        "endpoint": "/ask",
        "question": "Dans « La mer paraît calme », quel est l'adjectif qualificatif attribut ?",
        "expected_status": "success",
        "required_groups": [
            ["calme"],
            ["attribut"],
        ],
    },
    {
        "category": "Verbe paraît",
        "endpoint": "/ask",
        "question": "Dans « La mer paraît calme », quel est le verbe d'état ?",
        "expected_status": "success",
        "required_groups": [
            ["paraît", "parait"],
        ],
    },
    {
        "category": "Comparaison adjectifs",
        "endpoint": "/ask",
        "question": "Quelle est la différence entre un adjectif épithète et un adjectif attribut ?",
        "expected_status": "success",
        "required_groups": [
            ["épithète"],
            ["directement placé", "placé directement"],
            ["nom"],
            ["attribut"],
            ["verbe d'état"],
        ],
    },
    {
        "category": "Définition complément",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un complément de nom selon le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["complément de nom"],
            ["préposition"],
            ["nom"],
        ],
    },
    {
        "category": "Prépositions",
        "endpoint": "/ask",
        "question": "Quelles prépositions sont citées pour introduire un complément de nom ?",
        "expected_status": "success",
        "required_groups": [
            ["à"],
            ["de"],
            ["des"],
            ["en"],
        ],
    },
    {
        "category": "Exemple immeuble",
        "endpoint": "/ask",
        "question": "Dans « Les habitants de l'immeuble s'entendent bien », quel est le complément de nom ?",
        "expected_status": "success",
        "required_groups": [
            ["de l'immeuble"],
            ["complément de nom"],
        ],
    },
    {
        "category": "Préposition exemple",
        "endpoint": "/ask",
        "question": "Quelle préposition introduit le complément de nom dans « de l'immeuble » ?",
        "expected_status": "success",
        "required_groups": [
            ["de"],
        ],
    },
    {
        "category": "Nom complété",
        "endpoint": "/ask",
        "question": "Dans la phrase « Les habitants de l'immeuble s'entendent bien », quel nom est complété par « de l'immeuble » ?",
        "expected_status": "success",
        "required_groups": [
            ["habitants"],
        ],
    },
    {
        "category": "Définition relative",
        "endpoint": "/ask",
        "question": "Quel type de proposition peut caractériser un nom dans le dernier procédé du cours ?",
        "expected_status": "success",
        "required_groups": [
            ["subordonnée relative"],
            ["complément d'antécédent", "complément de l'antécédent"],
        ],
    },
    {
        "category": "Relative exemple",
        "endpoint": "/ask",
        "question": "Dans « Il arrose l'arbre qu'il a planté il y a dix ans », quelle est la subordonnée relative ?",
        "expected_status": "success",
        "required_groups": [
            ["qu'il a planté il y a dix ans"],
            ["subordonnée relative"],
        ],
    },
    {
        "category": "Antécédent",
        "endpoint": "/ask",
        "question": "Quel est l'antécédent de « qu'il a planté il y a dix ans » ?",
        "expected_status": "success",
        "required_groups": [
            ["l'arbre", "arbre"],
            ["antécédent"],
        ],
    },
    {
        "category": "Rôle relative",
        "endpoint": "/ask",
        "question": "Quel nom est caractérisé par la subordonnée relative « qu'il a planté il y a dix ans » ?",
        "expected_status": "success",
        "required_groups": [
            ["l'arbre", "arbre"],
        ],
    },
    {
        "category": "Identification procédé",
        "endpoint": "/ask",
        "question": "Quel procédé grammatical est utilisé dans « l'arbre qu'il a planté il y a dix ans » ?",
        "expected_status": "success",
        "required_groups": [
            ["subordonnée relative"],
            ["complément d'antécédent", "complément de l'antécédent"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": "Comant peut-on caracteriser un non avec un adjectife, un complement et une proposition relative ?",
        "expected_status": "success",
        "required_groups": [
            ["adjectif qualificatif épithète"],
            ["adjectif qualificatif attribut"],
            ["complément de nom"],
            ["subordonnée relative"],
        ],
    },
    {
        "category": "Résumé général",
        "endpoint": "/summarize",
        "question": "Résume le cours sur les procédés permettant de caractériser un nom.",
        "expected_status": "success",
        "required_groups": [
            ["caractériser un nom"],
            ["caractéristiques précises"],
            ["adjectif qualificatif épithète"],
            ["adjectif qualificatif attribut"],
            ["complément de nom"],
            ["subordonnée relative"],
            ["antécédent"],
        ],
    },
    {
        "category": "Résumé exemples",
        "endpoint": "/summarize",
        "question": "Résume les exemples donnés dans le cours pour caractériser un nom.",
        "expected_status": "success",
        "required_groups": [
            ["petit garçon"],
            ["histoire drôle"],
            ["tableau est magnifique", "Ce tableau est magnifique"],
            ["mer paraît calme", "La mer paraît calme"],
            ["de l'immeuble"],
            ["l'arbre"],
            ["qu'il a planté il y a dix ans"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": "Que signifie le protocole HTTP ?",
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


def extract_response_text(endpoint: str, response_data: dict) -> str:
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
    print("Test initial du cours : Caractériser un nom")
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

    for index, test_case in enumerate(TEST_CASES, start=1):
        category = test_case["category"]
        endpoint = test_case["endpoint"]
        question = test_case["question"]
        expected_status = test_case["expected_status"]

        category_totals[category] = (
            category_totals.get(category, 0) + 1
        )

        print()
        print("-" * 100)
        print(f"[{index}/{len(TEST_CASES)}] [{category}]")
        print("Question:", question)

        started_at = time.perf_counter()
        actual_status = ""
        response_text = ""
        sources = []
        error_text = ""

        try:
            response_data = make_request(endpoint, question)
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
            error_text = f"Erreur inattendue : {error}"

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
            print("Concepts manquants:", missing_groups)

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
                "test_passed": "oui" if test_passed else "non",
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
