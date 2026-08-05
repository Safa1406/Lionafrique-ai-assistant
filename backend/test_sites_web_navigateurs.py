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
EXPECTED_SOURCE = "12-site-web-et-navigateurs.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-websites-and-browsers-baseline"

JSON_REPORT = Path("sites_web_navigateurs_test_results.json")
CSV_REPORT = Path("sites_web_navigateurs_test_results.csv")

TEST_CASES = [
    {
        "category": "Définition WWW",
        "endpoint": "/ask",
        "question": "Que signifie WWW ?",
        "expected_status": "success",
        "required_groups": [
            ["World Wide Web"],
        ],
    },
    {
        "category": "Autres noms WWW",
        "endpoint": "/ask",
        "question": "Quels autres noms sont donnés au World Wide Web dans le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["toile"],
            ["W3"],
            ["toile d'araignée mondiale"],
        ],
    },
    {
        "category": "Rôle WWW",
        "endpoint": "/ask",
        "question": "Quel est le rôle du WWW selon le document ?",
        "expected_status": "success",
        "required_groups": [
            ["ouvrir le réseau Internet", "ouvrir Internet"],
            ["grand public"],
            ["consultation des sites", "consulter les sites"],
        ],
    },
    {
        "category": "Définition adresse Web",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'une adresse Web ?",
        "expected_status": "success",
        "required_groups": [
            ["code"],
            ["mots"],
            ["signes"],
            ["accéder à un site Web", "accéder à un site"],
            ["source d'information"],
        ],
    },
    {
        "category": "Parties adresse Web",
        "endpoint": "/ask",
        "question": "Quelles sont les principales parties d'une adresse Web ?",
        "expected_status": "success",
        "required_groups": [
            ["protocole de communication"],
            ["www"],
            ["domaine"],
            ["nom du site"],
            ["suffixe"],
        ],
    },
    {
        "category": "Définition protocole",
        "endpoint": "/ask",
        "question": "Qu'est-ce que le protocole de communication dans une adresse Web ?",
        "expected_status": "success",
        "required_groups": [
            ["http"],
            ["langage", "logiciel"],
            ["relier plusieurs machines"],
            ["communiquer"],
        ],
    },
    {
        "category": "Rôle HTTP",
        "endpoint": "/ask",
        "question": "À quoi sert le protocole HTTP ?",
        "expected_status": "success",
        "required_groups": [
            ["transférer les documents"],
            ["HTML"],
            ["images"],
            ["feuilles de style"],
            ["site Web"],
        ],
    },
    {
        "category": "Signification HTTP",
        "endpoint": "/ask",
        "question": "Que signifie HTTP ?",
        "expected_status": "success",
        "required_groups": [
            ["Hyper Text Transfer Protocole", "Hypertext Transfer Protocol"],
        ],
    },
    {
        "category": "WWW dans adresse",
        "endpoint": "/ask",
        "question": "Comment le World Wide Web est-il représenté dans une adresse Web ?",
        "expected_status": "success",
        "required_groups": [
            ["www"],
        ],
    },
    {
        "category": "Définition domaine",
        "endpoint": "/ask",
        "question": "De quoi se compose le domaine d'une adresse Web ?",
        "expected_status": "success",
        "required_groups": [
            ["nom du site"],
            ["suffixe"],
        ],
    },
    {
        "category": "Exemple adresse",
        "endpoint": "/ask",
        "question": "Décompose l'adresse Web donnée en exemple dans le tableau.",
        "expected_status": "success",
        "required_groups": [
            ["http"],
            ["www"],
            ["madariss"],
            [".fr", "fr"],
        ],
    },
    {
        "category": "Définition site Web",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un site Web ?",
        "expected_status": "success",
        "required_groups": [
            ["ressource d'informations", "ressource d'information"],
            ["disponible sur le Web"],
        ],
    },
    {
        "category": "Composition site Web",
        "endpoint": "/ask",
        "question": "De quoi est constitué un site Web ?",
        "expected_status": "success",
        "required_groups": [
            ["plusieurs pages Web"],
            ["liens hypertexte"],
        ],
    },
    {
        "category": "Définition page Web",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'une page Web et que peut-elle contenir ?",
        "expected_status": "success",
        "required_groups": [
            ["document informatique"],
            ["texte"],
            ["images"],
            ["formulaires"],
        ],
    },
    {
        "category": "Définition navigateur",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un navigateur Web ?",
        "expected_status": "success",
        "required_groups": [
            ["logiciel"],
            ["système d'exploitation"],
            ["consulter"],
            ["sites Web"],
            ["World Wide Web"],
        ],
    },
    {
        "category": "Installation navigateur",
        "endpoint": "/ask",
        "question": "Où installe-t-on un navigateur et à quoi sert-il ?",
        "expected_status": "success",
        "required_groups": [
            ["système d'exploitation"],
            ["consulter"],
            ["ensemble des sites Web", "sites Web"],
        ],
    },
    {
        "category": "Interface navigateur",
        "endpoint": "/ask",
        "question": "Quels sont les éléments de l'interface graphique d'un navigateur ?",
        "expected_status": "success",
        "required_groups": [
            ["boutons de navigation"],
            ["barre d'adresse"],
            ["espace d'affichage"],
            ["barre d'état"],
        ],
    },
    {
        "category": "Boutons navigation",
        "endpoint": "/ask",
        "question": "Quel élément de l'interface permet la navigation dans un navigateur ?",
        "expected_status": "success",
        "required_groups": [
            ["boutons de navigation"],
        ],
    },
    {
        "category": "Barre adresse",
        "endpoint": "/ask",
        "question": "Dans quel élément de l'interface saisit-on une adresse Web ?",
        "expected_status": "success",
        "required_groups": [
            ["barre d'adresse"],
        ],
    },
    {
        "category": "Espace affichage",
        "endpoint": "/ask",
        "question": "Quel élément du navigateur sert à afficher les pages Web ?",
        "expected_status": "success",
        "required_groups": [
            ["espace d'affichage"],
        ],
    },
    {
        "category": "Barre état",
        "endpoint": "/ask",
        "question": "Quelle barre de l'interface du navigateur est citée avec la barre d'adresse ?",
        "expected_status": "success",
        "required_groups": [
            ["barre d'état"],
        ],
    },
    {
        "category": "Exemples navigateurs",
        "endpoint": "/ask",
        "question": "Quels navigateurs sont cités comme exemples dans le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["Internet Explorer"],
            ["IE"],
            ["Mozilla Firefox", "Mozilla FireFox"],
        ],
    },
    {
        "category": "Internet Explorer",
        "endpoint": "/ask",
        "question": "Que dit le cours à propos d'Internet Explorer ?",
        "expected_status": "success",
        "required_groups": [
            ["Internet Explorer"],
            ["IE"],
            ["installé automatiquement"],
            ["système d'exploitation"],
        ],
    },
    {
        "category": "Mozilla Firefox",
        "endpoint": "/ask",
        "question": "Que dit le cours à propos de Mozilla Firefox ?",
        "expected_status": "success",
        "required_groups": [
            ["Mozilla Firefox", "Mozilla FireFox"],
            ["navigateur Web libre"],
            ["plusieurs pages Web"],
            ["même fenêtre"],
        ],
    },
    {
        "category": "Comparaison site page",
        "endpoint": "/ask",
        "question": "Quelle est la différence entre un site Web et une page Web ?",
        "expected_status": "success",
        "required_groups": [
            ["site Web"],
            ["plusieurs pages Web"],
            ["liens hypertexte"],
            ["page Web"],
            ["document informatique"],
        ],
    },
    {
        "category": "Comparaison adresse domaine",
        "endpoint": "/ask",
        "question": "Quelle est la différence entre une adresse Web et un domaine ?",
        "expected_status": "success",
        "required_groups": [
            ["adresse Web"],
            ["code"],
            ["accéder à un site"],
            ["domaine"],
            ["nom du site"],
            ["suffixe"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": "C'est quoi un sit web, une adrese web et un navigatteur ?",
        "expected_status": "success",
        "required_groups": [
            ["site Web"],
            ["ressource d'informations", "ressource d'information"],
            ["adresse Web"],
            ["code"],
            ["navigateur"],
            ["logiciel"],
        ],
    },
    {
        "category": "Résumé sites Web",
        "endpoint": "/summarize",
        "question": "Résume la partie du cours sur le WWW, les adresses Web et les sites Web.",
        "expected_status": "success",
        "required_groups": [
            ["World Wide Web"],
            ["toile"],
            ["adresse Web"],
            ["HTTP"],
            ["Hyper Text Transfer Protocole", "Hypertext Transfer Protocol"],
            ["domaine"],
            ["nom du site"],
            ["suffixe"],
            ["site Web"],
            ["pages Web"],
            ["liens hypertexte"],
        ],
    },
    {
        "category": "Résumé navigateurs",
        "endpoint": "/summarize",
        "question": "Résume la partie du cours consacrée aux navigateurs Web.",
        "expected_status": "success",
        "required_groups": [
            ["navigateur"],
            ["système d'exploitation"],
            ["boutons de navigation"],
            ["barre d'adresse"],
            ["espace d'affichage"],
            ["barre d'état"],
            ["Internet Explorer"],
            ["Mozilla Firefox", "Mozilla FireFox"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": "Quelle est la capitale du Canada ?",
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
        r"[^\w\s./:-]",
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
        alternatives = [
            normalize_text(term)
            for term in group
        ]

        if not any(
            alternative
            and alternative in normalized_response
            for alternative in alternatives
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
    print("Test initial du cours : Sites Web et navigateurs")
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
