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
EXPECTED_SOURCE = "ecrit-4-1-rediger-une-lettre-ouverte-2.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-lettre-ouverte-baseline"

JSON_REPORT = Path("lettre_ouverte_test_results.json")
CSV_REPORT = Path("lettre_ouverte_test_results.csv")

TEST_CASES = [
    {
        "category": "Type de production",
        "endpoint": "/ask",
        "question": "Quel type de texte faut-il rédiger dans ce cours ?",
        "expected_status": "success",
        "required_groups": [
            ["lettre ouverte"],
        ],
    },
    {
        "category": "Cadre du projet",
        "endpoint": "/ask",
        "question": "Dans quel cadre la lettre ouverte est-elle rédigée ?",
        "expected_status": "success",
        "required_groups": [
            ["club de l'environnement"],
        ],
    },
    {
        "category": "Destinataire",
        "endpoint": "/ask",
        "question": "À qui la lettre ouverte doit-elle être adressée ?",
        "expected_status": "success",
        "required_groups": [
            ["opinion publique"],
        ],
    },
    {
        "category": "Phénomène",
        "endpoint": "/ask",
        "question": "Quel phénomène doit être expliqué dans la lettre ouverte ?",
        "expected_status": "success",
        "required_groups": [
            ["réchauffement climatique"],
        ],
    },
    {
        "category": "Premier objectif",
        "endpoint": "/ask",
        "question": "Quel est le premier objectif de la lettre concernant le réchauffement climatique ?",
        "expected_status": "success",
        "required_groups": [
            ["expliquer"],
            ["phénomène"],
        ],
    },
    {
        "category": "Deuxième objectif",
        "endpoint": "/ask",
        "question": "Que faut-il montrer à propos du réchauffement climatique ?",
        "expected_status": "success",
        "required_groups": [
            ["effets"],
            ["monde"],
        ],
    },
    {
        "category": "Troisième objectif",
        "endpoint": "/ask",
        "question": "Que faut-il proposer dans la lettre pour faire face au problème ?",
        "expected_status": "success",
        "required_groups": [
            ["solutions"],
            ["résoudre"],
            ["fléau"],
        ],
    },
    {
        "category": "Objectifs complets",
        "endpoint": "/ask",
        "question": "Quels sont les trois objectifs principaux de la lettre ouverte ?",
        "expected_status": "success",
        "required_groups": [
            ["expliquer"],
            ["effets"],
            ["solutions"],
        ],
    },
    {
        "category": "Projet environnement",
        "endpoint": "/ask",
        "question": "À quel domaine général appartient le projet de cette lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["environnement"],
        ],
    },
    {
        "category": "Rappel caractéristiques",
        "endpoint": "/ask",
        "question": "Quelles caractéristiques faut-il rappeler avant de rédiger ?",
        "expected_status": "success",
        "required_groups": [
            ["caractéristiques"],
            ["lettre conventionnelle"],
        ],
    },
    {
        "category": "Rappel structure corps",
        "endpoint": "/ask",
        "question": "Que faut-il rappeler concernant le corps de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["structure"],
            ["corps"],
            ["trois phases"],
        ],
    },
    {
        "category": "Nombre phases",
        "endpoint": "/ask",
        "question": "En combien de phases le corps de la lettre doit-il être structuré ?",
        "expected_status": "success",
        "required_groups": [
            ["trois phases"],
        ],
    },
    {
        "category": "Production structure conventionnelle",
        "endpoint": "/ask",
        "question": "Quelle structure générale faut-il respecter pendant la production ?",
        "expected_status": "success",
        "required_groups": [
            ["structure"],
            ["lettre conventionnelle"],
        ],
    },
    {
        "category": "Production thème",
        "endpoint": "/ask",
        "question": "Quel élément thématique faut-il respecter pendant la rédaction ?",
        "expected_status": "success",
        "required_groups": [
            ["thème"],
            ["lettre"],
        ],
    },
    {
        "category": "Production corps",
        "endpoint": "/ask",
        "question": "Quelle structure particulière faut-il respecter dans le corps de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["structure"],
            ["corps"],
            ["lettre"],
        ],
    },
    {
        "category": "Critères production",
        "endpoint": "/ask",
        "question": "Quels sont les trois éléments à respecter pour rédiger la lettre ouverte ?",
        "expected_status": "success",
        "required_groups": [
            ["structure de la lettre conventionnelle"],
            ["thème"],
            ["structure du corps"],
        ],
    },
    {
        "category": "Grille amélioration",
        "endpoint": "/ask",
        "question": "À quoi sert la grille d'évaluation après la rédaction ?",
        "expected_status": "success",
        "required_groups": [
            ["améliore", "améliorer"],
            ["texte"],
            ["grille"],
        ],
    },
    {
        "category": "Critère lettre",
        "endpoint": "/ask",
        "question": "Quel critère vérifie le type de lettre écrite ?",
        "expected_status": "success",
        "required_groups": [
            ["j'ai écrit une lettre conventionnelle"],
        ],
    },
    {
        "category": "Critère caractéristiques",
        "endpoint": "/ask",
        "question": "Quel critère vérifie le respect des caractéristiques de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["respecté"],
            ["caractéristiques"],
            ["formules"],
        ],
    },
    {
        "category": "Critère expressions",
        "endpoint": "/ask",
        "question": "Que demande la grille au sujet des expressions employées ?",
        "expected_status": "success",
        "required_groups": [
            ["expressions convenables"],
        ],
    },
    {
        "category": "Critère thème",
        "endpoint": "/ask",
        "question": "Quel thème la grille demande-t-elle d'employer ?",
        "expected_status": "success",
        "required_groups": [
            ["thème"],
            ["environnement"],
        ],
    },
    {
        "category": "Critère trois phases",
        "endpoint": "/ask",
        "question": "Quel critère vérifie l'organisation du corps de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["structure"],
            ["corps"],
            ["trois phases"],
        ],
    },
    {
        "category": "Colonnes grille",
        "endpoint": "/ask",
        "question": "Quelles réponses peut-on cocher dans la grille de critères ?",
        "expected_status": "success",
        "required_groups": [
            ["oui"],
            ["non"],
        ],
    },
    {
        "category": "Lien thème projet",
        "endpoint": "/ask",
        "question": "Quel lien existe entre le thème de la lettre et le projet du club ?",
        "expected_status": "success",
        "required_groups": [
            ["environnement"],
            ["réchauffement climatique"],
        ],
    },
    {
        "category": "Public large",
        "endpoint": "/ask",
        "question": "La lettre est-elle destinée à une seule personne ou à un public plus large ?",
        "expected_status": "success",
        "required_groups": [
            ["opinion publique"],
        ],
    },
    {
        "category": "Fléau",
        "endpoint": "/ask",
        "question": "Quel problème est qualifié de fléau dans le sujet ?",
        "expected_status": "success",
        "required_groups": [
            ["réchauffement climatique"],
            ["fléau"],
        ],
    },
    {
        "category": "Séquence logique",
        "endpoint": "/ask",
        "question": "Quelle progression d'idées le sujet demande-t-il de suivre dans la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["expliquer"],
            ["effets"],
            ["solutions"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": "Coman redijé une letr ouver sur le rechofman klimatik pour lopinion publik, expliké lé zefé é proposé dé solusion ?",
        "expected_status": "success",
        "required_groups": [
            ["lettre ouverte"],
            ["opinion publique"],
            ["réchauffement climatique"],
            ["effets"],
            ["solutions"],
            ["lettre conventionnelle"],
            ["trois phases"],
        ],
    },
    {
        "category": "Résumé",
        "endpoint": "/summarize",
        "question": "Résume le cours sur la rédaction d'une lettre ouverte.",
        "expected_status": "success",
        "required_groups": [
            ["lettre ouverte"],
            ["club de l'environnement"],
            ["opinion publique"],
            ["réchauffement climatique"],
            ["expliquer"],
            ["effets"],
            ["monde"],
            ["solutions"],
            ["lettre conventionnelle"],
            ["trois phases"],
            ["expressions convenables"],
            ["environnement"],
            ["oui"],
            ["non"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": "Comment calcule-t-on la dérivée de la fonction x au carré ?",
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
    print("Test initial du cours : Rédiger une lettre ouverte")
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
