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
SUBJECT = "Informatique"
SEMESTER = None
EXPECTED_SOURCE = "7-notion-de-la-programmation.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-programming-notions-baseline"

JSON_REPORT = Path("notions_programmation_test_results.json")
CSV_REPORT = Path("notions_programmation_test_results.csv")

TEST_CASES = [
    {
        "category": "Définition programme",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un programme selon le document ?",
        "expected_status": "success",
        "required_groups": [
            ["ensemble d'instructions", "ensemble des instructions"],
            ["ordres"],
            ["machine"],
            ["comprend", "comprenne"],
            ["exécute"],
        ],
    },
    {
        "category": "Définition programmation",
        "endpoint": "/ask",
        "question": "Qu'est-ce que la programmation ?",
        "expected_status": "success",
        "required_groups": [
            ["domaine d'informatique", "domaine de l'informatique"],
            ["écrire un programme"],
            ["compréhensible par la machine"],
        ],
    },
    {
        "category": "Définition langage",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un langage de programmation ?",
        "expected_status": "success",
        "required_groups": [
            ["ensemble de signes"],
            ["codes"],
            ["règles précises"],
            ["rédiger un programme"],
        ],
    },
    {
        "category": "Définition logiciel",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un logiciel de programmation ?",
        "expected_status": "success",
        "required_groups": [
            ["logiciel d'application"],
            ["utilisateur"],
            ["écrire"],
            ["corriger"],
            ["programme"],
        ],
    },
    {
        "category": "Définition algorithme",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un algorithme ?",
        "expected_status": "success",
        "required_groups": [
            ["suite finie"],
            ["actions précises"],
            ["ordonnées"],
            ["résolution d'un problème"],
        ],
    },
    {
        "category": "Comparaison notions",
        "endpoint": "/ask",
        "question": "Quelle est la différence entre un programme, la programmation et un langage de programmation ?",
        "expected_status": "success",
        "required_groups": [
            ["programme"],
            ["ensemble d'instructions", "instructions"],
            ["programmation"],
            ["écrire un programme"],
            ["langage de programmation"],
            ["signes", "codes"],
        ],
    },
    {
        "category": "Rôle logiciel",
        "endpoint": "/ask",
        "question": "À quoi sert un logiciel de programmation ?",
        "expected_status": "success",
        "required_groups": [
            ["écrire"],
            ["corriger"],
            ["programme"],
        ],
    },
    {
        "category": "Caractéristiques algorithme",
        "endpoint": "/ask",
        "question": "Quelles sont les caractéristiques d'un algorithme ?",
        "expected_status": "success",
        "required_groups": [
            ["suite finie"],
            ["précises"],
            ["ordonnées"],
            ["résolution"],
            ["problème"],
        ],
    },
    {
        "category": "Définition LOGO",
        "endpoint": "/ask",
        "question": "Qu'est-ce que le langage LOGO ?",
        "expected_status": "success",
        "required_groups": [
            ["langage de programmation"],
            ["débutants"],
            ["apprendre à programmer"],
        ],
    },
    {
        "category": "Public LOGO",
        "endpoint": "/ask",
        "question": "À quel public le langage LOGO est-il destiné ?",
        "expected_status": "success",
        "required_groups": [
            ["débutants"],
        ],
    },
    {
        "category": "Objectif LOGO",
        "endpoint": "/ask",
        "question": "Quel est l'objectif principal du langage LOGO ?",
        "expected_status": "success",
        "required_groups": [
            ["apprendre à programmer"],
            ["débutants"],
        ],
    },
    {
        "category": "Versions LOGO",
        "endpoint": "/ask",
        "question": "Quelles versions du logiciel LOGO sont citées dans le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["LOGO.NET"],
            ["XLOGO"],
        ],
    },
    {
        "category": "Description LOGO",
        "endpoint": "/ask",
        "question": "Comment le logiciel LOGO est-il décrit dans le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["comme un jeu"],
            ["utilisateur"],
            ["ordres"],
            ["tortue"],
            ["tâche bien définie"],
        ],
    },
    {
        "category": "Tortue LOGO",
        "endpoint": "/ask",
        "question": "Quel est le rôle de la tortue dans le logiciel LOGO ?",
        "expected_status": "success",
        "required_groups": [
            ["tortue"],
            ["ordres"],
            ["réalise une tâche", "réaliser une tâche"],
        ],
    },
    {
        "category": "Installation LOGO.NET",
        "endpoint": "/ask",
        "question": "Le logiciel LOGO.NET est-il gratuit ?",
        "expected_status": "success",
        "required_groups": [
            ["oui"],
            ["LOGO.NET"],
            ["gratuit"],
        ],
    },
    {
        "category": "Installation XLOGO",
        "endpoint": "/ask",
        "question": "Le logiciel XLOGO est-il gratuit ?",
        "expected_status": "success",
        "required_groups": [
            ["oui"],
            ["XLOGO"],
            ["gratuit"],
        ],
    },
    {
        "category": "Téléchargement",
        "endpoint": "/ask",
        "question": "Que dit le document à propos du téléchargement de LOGO.NET et XLOGO ?",
        "expected_status": "success",
        "required_groups": [
            ["LOGO.NET"],
            ["gratuit"],
            ["XLOGO"],
            ["téléchargé", "télécharger"],
            ["URL"],
        ],
    },
    {
        "category": "Interface LOGO",
        "endpoint": "/ask",
        "question": "De combien de parties principales se compose l'interface LOGO ?",
        "expected_status": "success",
        "required_groups": [
            ["deux parties"],
            ["partie graphique"],
            ["partie de commande"],
        ],
    },
    {
        "category": "Partie graphique",
        "endpoint": "/ask",
        "question": "Qu'est-ce que la partie graphique de l'interface LOGO ?",
        "expected_status": "success",
        "required_groups": [
            ["espace"],
            ["tortue"],
        ],
    },
    {
        "category": "Partie commande",
        "endpoint": "/ask",
        "question": "Qu'est-ce que la partie de commande dans LOGO ?",
        "expected_status": "success",
        "required_groups": [
            ["endroit"],
            ["utilisateur"],
            ["rédiger les ordres", "écrire les ordres"],
            ["tortue"],
        ],
    },
    {
        "category": "Comparaison interface",
        "endpoint": "/ask",
        "question": "Quelle est la différence entre la partie graphique et la partie de commande de LOGO ?",
        "expected_status": "success",
        "required_groups": [
            ["partie graphique"],
            ["tortue"],
            ["partie de commande"],
            ["ordres"],
        ],
    },
    {
        "category": "Avantage raisonnement",
        "endpoint": "/ask",
        "question": "Comment la programmation développe-t-elle le raisonnement et la créativité ?",
        "expected_status": "success",
        "required_groups": [
            ["raisonnement"],
            ["créativité"],
        ],
    },
    {
        "category": "Qualités développées",
        "endpoint": "/ask",
        "question": "Quelles qualités la programmation permet-elle de développer selon le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["clair"],
            ["précis"],
            ["bien organisé"],
            ["rigoureux"],
        ],
    },
    {
        "category": "Avantages complets",
        "endpoint": "/ask",
        "question": "Quels sont les avantages de la programmation mentionnés dans le document ?",
        "expected_status": "success",
        "required_groups": [
            ["raisonnement"],
            ["créativité"],
            ["clair"],
            ["précis"],
            ["organisé"],
            ["rigoureux"],
        ],
    },
    {
        "category": "Identification notion",
        "endpoint": "/ask",
        "question": "Quelle notion désigne une suite finie d'actions précises et ordonnées ?",
        "expected_status": "success",
        "required_groups": [
            ["algorithme"],
        ],
    },
    {
        "category": "Identification interface",
        "endpoint": "/ask",
        "question": "Dans quelle partie de LOGO l'utilisateur écrit-il les ordres destinés à la tortue ?",
        "expected_status": "success",
        "required_groups": [
            ["partie de commande"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": "C'est quoi un algoriteme et un langaje de programation ?",
        "expected_status": "success",
        "required_groups": [
            ["algorithme"],
            ["suite finie"],
            ["langage de programmation"],
            ["signes"],
            ["codes"],
            ["règles précises"],
        ],
    },
    {
        "category": "Résumé général",
        "endpoint": "/summarize",
        "question": "Résume le cours sur les notions de programmation et le langage LOGO.",
        "expected_status": "success",
        "required_groups": [
            ["programme"],
            ["programmation"],
            ["langage de programmation"],
            ["logiciel de programmation"],
            ["algorithme"],
            ["LOGO"],
            ["débutants"],
            ["tortue"],
            ["partie graphique"],
            ["partie de commande"],
        ],
    },
    {
        "category": "Résumé avantages",
        "endpoint": "/summarize",
        "question": "Résume les avantages de la programmation et le fonctionnement de l'interface LOGO.",
        "expected_status": "success",
        "required_groups": [
            ["raisonnement"],
            ["créativité"],
            ["clair"],
            ["précis"],
            ["organisé"],
            ["rigoureux"],
            ["partie graphique"],
            ["partie de commande"],
            ["tortue"],
            ["ordres"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": "Quelle est la capitale du Japon ?",
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
        r"[^\w\s.-]",
        " ",
        normalized,
        flags=re.UNICODE,
    )
    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


def make_request(endpoint: str, question: str) -> dict:
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
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT_SECONDS,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


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
            f" | page "
            f"{source.get('page', '?')}"
        )
        for source in sources
    )


def main() -> None:
    configure_console()

    print("=" * 100)
    print("Test initial du cours : Notion de la programmation")
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
            response_data = make_request(
                endpoint=endpoint,
                question=question,
            )
            actual_status = response_data.get("status", "")
            response_text = extract_response_text(
                endpoint=endpoint,
                response_data=response_data,
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
            response_text=response_text,
            required_groups=test_case["required_groups"],
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
                "correct_source": "oui" if correct_source else "non",
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
        "generated_at": datetime.now().isoformat(timespec="seconds"),
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
        fieldnames = list(results[0].keys())
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
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
