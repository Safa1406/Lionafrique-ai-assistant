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
EXPECTED_SOURCE = "2-la-presentation-assistee-par-ordinateur.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-computer-assisted-presentation-baseline"

JSON_REPORT = Path("presentation_assistee_test_results.json")
CSV_REPORT = Path("presentation_assistee_test_results.csv")

TEST_CASES = [
    {
        "category": "Définition Pré AO",
        "endpoint": "/ask",
        "question": "Qu'est-ce que la présentation assistée par ordinateur ?",
        "expected_status": "success",
        "required_groups": [
            ["succession de diapositives"],
            ["visionné sur écran", "visionnée sur écran", "écran de l'ordinateur"],
            ["vidéo-projecteur", "vidéoprojecteur"],
        ],
    },
    {
        "category": "Notation Pré AO",
        "endpoint": "/ask",
        "question": "Comment note-t-on la présentation assistée par ordinateur dans le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["Pré AO", "Pre AO"],
        ],
    },
    {
        "category": "Définition diapositive",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'une diapositive ?",
        "expected_status": "success",
        "required_groups": [
            ["page écran", "page-écran"],
        ],
    },
    {
        "category": "Contenu diapositive",
        "endpoint": "/ask",
        "question": "Quels types de contenus une diapositive peut-elle contenir ?",
        "expected_status": "success",
        "required_groups": [
            ["texte"],
            ["images"],
            ["tableaux"],
            ["graphiques"],
            ["organigrammes"],
            ["animations"],
            ["sons"],
            ["vidéos"],
        ],
    },
    {
        "category": "Définition logiciel Pré AO",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un logiciel de Pré AO ?",
        "expected_status": "success",
        "required_groups": [
            ["logiciel"],
            ["créer des diapositives"],
            ["défiler à l'écran", "défiler sur l'écran"],
            ["manuellement"],
            ["automatiquement"],
        ],
    },
    {
        "category": "Logiciels de Pré AO",
        "endpoint": "/ask",
        "question": "Quels logiciels de présentation assistée par ordinateur sont cités dans le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["Microsoft PowerPoint", "Microsoft power point"],
            ["Corel Présentation", "corel présentation"],
            ["OpenOffice.org Impress", "Open Office.org Impress", "Impress"],
        ],
    },
    {
        "category": "Définition diaporama",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un diaporama ?",
        "expected_status": "success",
        "required_groups": [
            ["ensemble de pages-écran", "ensemble de pages écran"],
            ["les unes à la suite des autres"],
            ["plein écran"],
        ],
    },
    {
        "category": "Mode diaporama",
        "endpoint": "/ask",
        "question": "À quoi sert le mode diaporama ?",
        "expected_status": "success",
        "required_groups": [
            ["visualiser une présentation"],
            ["plein écran"],
        ],
    },
    {
        "category": "Définition PowerPoint",
        "endpoint": "/ask",
        "question": "Qu'est-ce que Microsoft PowerPoint selon le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["logiciel"],
            ["création"],
            ["présentations multimédia"],
        ],
    },
    {
        "category": "Démarrage PowerPoint",
        "endpoint": "/ask",
        "question": "Quelles sont les étapes pour démarrer PowerPoint ?",
        "expected_status": "success",
        "required_groups": [
            ["Démarrer"],
            ["Tous les programmes"],
            ["Microsoft Office"],
            ["Microsoft Office PowerPoint", "PowerPoint"],
        ],
    },
    {
        "category": "Première étape",
        "endpoint": "/ask",
        "question": "Quelle est la première étape pour démarrer PowerPoint ?",
        "expected_status": "success",
        "required_groups": [
            ["cliquer sur Démarrer", "cliquez sur Démarrer"],
        ],
    },
    {
        "category": "Deuxième étape",
        "endpoint": "/ask",
        "question": "Quelle est la deuxième étape pour démarrer PowerPoint ?",
        "expected_status": "success",
        "required_groups": [
            ["Tous les programmes"],
        ],
    },
    {
        "category": "Troisième étape",
        "endpoint": "/ask",
        "question": "Quelle est la troisième étape pour démarrer PowerPoint ?",
        "expected_status": "success",
        "required_groups": [
            ["Microsoft Office"],
            ["Microsoft Office PowerPoint", "PowerPoint"],
        ],
    },
    {
        "category": "Défilement",
        "endpoint": "/ask",
        "question": "Comment les diapositives peuvent-elles défiler à l'écran ?",
        "expected_status": "success",
        "required_groups": [
            ["manuellement"],
            ["automatiquement"],
        ],
    },
    {
        "category": "Support de visualisation",
        "endpoint": "/ask",
        "question": "Sur quels supports peut-on visionner ou projeter une présentation assistée par ordinateur ?",
        "expected_status": "success",
        "required_groups": [
            ["écran de l'ordinateur", "écran d'ordinateur"],
            ["vidéo-projecteur", "vidéoprojecteur"],
        ],
    },
    {
        "category": "Interface PowerPoint",
        "endpoint": "/ask",
        "question": "Quels éléments de la fenêtre de Microsoft PowerPoint 2007 sont indiqués dans l'image ?",
        "expected_status": "success",
        "required_groups": [
            ["barre d'accès outils rapide", "barre d'accès rapide"],
            ["ruban"],
            ["diapositives"],
            ["diapositive"],
            ["gestion du contenu multimédia", "contenu multimédia"],
            ["barre d'état"],
        ],
    },
    {
        "category": "Barre d'accès rapide",
        "endpoint": "/ask",
        "question": "Quel élément se trouve en haut à gauche de la fenêtre PowerPoint dans l'image ?",
        "expected_status": "success",
        "required_groups": [
            ["barre d'accès outils rapide", "barre d'accès rapide"],
        ],
    },
    {
        "category": "Ruban",
        "endpoint": "/ask",
        "question": "Comment s'appelle la grande zone de commandes située en haut de PowerPoint ?",
        "expected_status": "success",
        "required_groups": [
            ["ruban"],
        ],
    },
    {
        "category": "Volet diapositives",
        "endpoint": "/ask",
        "question": "Quelle zone de l'interface affiche les miniatures des diapositives ?",
        "expected_status": "success",
        "required_groups": [
            ["diapositives"],
        ],
    },
    {
        "category": "Zone centrale",
        "endpoint": "/ask",
        "question": "Quelle partie de l'interface permet de travailler sur la diapositive courante ?",
        "expected_status": "success",
        "required_groups": [
            ["diapositive"],
        ],
    },
    {
        "category": "Contenu multimédia",
        "endpoint": "/ask",
        "question": "Quelle zone de PowerPoint est associée à la gestion du contenu multimédia ?",
        "expected_status": "success",
        "required_groups": [
            ["gestion du contenu multimédia", "contenu multimédia"],
        ],
    },
    {
        "category": "Barre d'état",
        "endpoint": "/ask",
        "question": "Comment s'appelle la barre située en bas de la fenêtre PowerPoint ?",
        "expected_status": "success",
        "required_groups": [
            ["barre d'état"],
        ],
    },
    {
        "category": "Comparaison",
        "endpoint": "/ask",
        "question": "Quelle est la différence entre une diapositive et un diaporama ?",
        "expected_status": "success",
        "required_groups": [
            ["diapositive"],
            ["page écran", "page-écran"],
            ["diaporama"],
            ["ensemble de pages-écran", "ensemble de pages écran"],
            ["plein écran"],
        ],
    },
    {
        "category": "Identification logiciel",
        "endpoint": "/ask",
        "question": "Quel logiciel du cours permet de créer des présentations multimédia ?",
        "expected_status": "success",
        "required_groups": [
            ["PowerPoint"],
        ],
    },
    {
        "category": "Identification contenu",
        "endpoint": "/ask",
        "question": "Peut-on insérer des sons, des vidéos et des animations dans une diapositive ?",
        "expected_status": "success",
        "required_groups": [
            ["oui"],
            ["sons"],
            ["vidéos"],
            ["animations"],
        ],
    },
    {
        "category": "Explication courte",
        "endpoint": "/ask",
        "question": "Explique brièvement la présentation assistée par ordinateur.",
        "expected_status": "success",
        "required_groups": [
            ["succession de diapositives"],
            ["écran"],
            ["vidéo-projecteur", "vidéoprojecteur"],
            ["logiciel"],
            ["diaporama"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": "C'est quoi une presentasion assiste par ordinatteur et un diaporrama ?",
        "expected_status": "success",
        "required_groups": [
            ["succession de diapositives"],
            ["diaporama"],
            ["ensemble de pages-écran", "ensemble de pages écran"],
            ["plein écran"],
        ],
    },
    {
        "category": "Résumé général",
        "endpoint": "/summarize",
        "question": "Résume le cours sur la présentation assistée par ordinateur.",
        "expected_status": "success",
        "required_groups": [
            ["présentation assistée par ordinateur"],
            ["Pré AO", "Pre AO"],
            ["diapositive"],
            ["texte"],
            ["images"],
            ["Microsoft PowerPoint", "PowerPoint"],
            ["diaporama"],
            ["plein écran"],
        ],
    },
    {
        "category": "Résumé PowerPoint",
        "endpoint": "/summarize",
        "question": "Résume la partie du cours consacrée à Microsoft PowerPoint et à son environnement.",
        "expected_status": "success",
        "required_groups": [
            ["présentations multimédia"],
            ["Démarrer"],
            ["Tous les programmes"],
            ["Microsoft Office"],
            ["PowerPoint"],
            ["ruban"],
            ["barre d'état"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": "Quelle est la capitale de l'Australie ?",
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
        r"[^\w\s-]",
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
    print("Test initial du cours : La présentation assistée par ordinateur")
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

        category_totals[category] = category_totals.get(category, 0) + 1

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
