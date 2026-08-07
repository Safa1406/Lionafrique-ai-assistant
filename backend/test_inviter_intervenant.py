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
    "ecrit-2-2-rediger-une-lettre-pour-inviter-un-intervenant.pdf"
)
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-inviter-intervenant-baseline"

JSON_REPORT = Path("inviter_intervenant_test_results.json")
CSV_REPORT = Path("inviter_intervenant_test_results.csv")

TEST_CASES = [
    {
        "category": "Type de production",
        "endpoint": "/ask",
        "question": "Quel type de lettre faut-il rédiger dans ce cours ?",
        "expected_status": "success",
        "required_groups": [
            ["lettre d'invitation"],
            ["intervenant", "représentant"],
        ],
    },
    {
        "category": "Projet de classe",
        "endpoint": "/ask",
        "question": "Quel est le projet de classe mentionné dans le sujet ?",
        "expected_status": "success",
        "required_groups": [
            ["débat"],
            ["environnement"],
        ],
    },
    {
        "category": "Destinataire",
        "endpoint": "/ask",
        "question": "À qui la lettre d'invitation du sujet est-elle adressée ?",
        "expected_status": "success",
        "required_groups": [
            ["représentant"],
            ["GIEC"],
        ],
    },
    {
        "category": "But invitation",
        "endpoint": "/ask",
        "question": "Pourquoi invite-t-on le représentant du GIEC ?",
        "expected_status": "success",
        "required_groups": [
            ["participer"],
            ["débat"],
        ],
    },
    {
        "category": "Période événement",
        "endpoint": "/ask",
        "question": "Pendant quelle période le débat sera-t-il organisé ?",
        "expected_status": "success",
        "required_groups": [
            ["semaine de l'environnement"],
        ],
    },
    {
        "category": "Lieu événement",
        "endpoint": "/ask",
        "question": "Où le débat sera-t-il organisé ?",
        "expected_status": "success",
        "required_groups": [
            ["collège"],
        ],
    },
    {
        "category": "Canevas",
        "endpoint": "/ask",
        "question": "Que doivent élaborer les élèves avec leurs camarades avant la rédaction ?",
        "expected_status": "success",
        "required_groups": [
            ["canevas"],
            ["lettre d'invitation"],
            ["GIEC"],
        ],
    },
    {
        "category": "Cadre formel",
        "endpoint": "/ask",
        "question": "Dans quel cadre faut-il rappeler la structure de la lettre d'invitation ?",
        "expected_status": "success",
        "required_groups": [
            ["cadre formel"],
        ],
    },
    {
        "category": "Rappels",
        "endpoint": "/ask",
        "question": "Quels éléments faut-il rappeler avant de produire la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["structure"],
            ["expressions"],
            ["formules de politesse"],
            ["trois phases", "3 phases"],
        ],
    },
    {
        "category": "Formule d'appel",
        "endpoint": "/ask",
        "question": "Quel élément doit apparaître avant le corps de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["formule d'appel"],
        ],
    },
    {
        "category": "Trois paragraphes",
        "endpoint": "/ask",
        "question": "Combien de paragraphes doit contenir le corps de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["trois paragraphes", "3 paragraphes"],
        ],
    },
    {
        "category": "Premier paragraphe",
        "endpoint": "/ask",
        "question": "Quelles informations doit contenir le premier paragraphe du corps de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["organisation de l'événement", "organisation de l’événement"],
            ["date"],
            ["objet"],
            ["invitation"],
            ["lieu"],
        ],
    },
    {
        "category": "Deuxième paragraphe",
        "endpoint": "/ask",
        "question": "Que doit contenir le deuxième paragraphe de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["insistance"],
            ["nature de l'intervention", "nature de l’intervention"],
        ],
    },
    {
        "category": "Troisième paragraphe",
        "endpoint": "/ask",
        "question": "Que doit contenir le troisième paragraphe de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["demande de confirmation"],
            ["coordonnées"],
            ["mail"],
        ],
    },
    {
        "category": "Formule de politesse",
        "endpoint": "/ask",
        "question": "Quel élément de politesse doit apparaître après le corps de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["formule de politesse"],
        ],
    },
    {
        "category": "Signature",
        "endpoint": "/ask",
        "question": "Quel élément doit accompagner la fin de la lettre après la formule de politesse ?",
        "expected_status": "success",
        "required_groups": [
            ["signature"],
        ],
    },
    {
        "category": "Expression invitation 1",
        "endpoint": "/ask",
        "question": "Quelle expression formelle commence par « Nous avons le plaisir » ?",
        "expected_status": "success",
        "required_groups": [
            ["nous avons le plaisir de vous inviter"],
        ],
    },
    {
        "category": "Expression invitation 2",
        "endpoint": "/ask",
        "question": "Quelle expression formelle contient le mot « ravis » ?",
        "expected_status": "success",
        "required_groups": [
            ["nous sommes ravis de vous inviter"],
        ],
    },
    {
        "category": "Expression invitation 3",
        "endpoint": "/ask",
        "question": "Quelle expression indique que l'acceptation de l'invitation ferait plaisir ?",
        "expected_status": "success",
        "required_groups": [
            ["vous nous ferez tellement plaisir"],
            ["acceptez notre invitation"],
        ],
    },
    {
        "category": "Date événement",
        "endpoint": "/ask",
        "question": "Quelles deux informations faut-il explicitement indiquer avant la formule finale ?",
        "expected_status": "success",
        "required_groups": [
            ["date"],
            ["événement"],
        ],
    },
    {
        "category": "Formule finale",
        "endpoint": "/ask",
        "question": "Que faut-il insérer à la fin de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["formule finale de politesse"],
        ],
    },
    {
        "category": "Grille canevas",
        "endpoint": "/ask",
        "question": "Quel critère de la grille concerne le canevas de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["respecté"],
            ["canevas"],
            ["lettre formelle"],
        ],
    },
    {
        "category": "Grille structure",
        "endpoint": "/ask",
        "question": "Que vérifie la grille concernant le corps de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["structuré"],
            ["3 paragraphes", "trois paragraphes"],
        ],
    },
    {
        "category": "Grille expressions",
        "endpoint": "/ask",
        "question": "Quelles expressions la grille demande-t-elle d'utiliser convenablement ?",
        "expected_status": "success",
        "required_groups": [
            ["présenter l'évènement", "présenter l'événement"],
            ["objet"],
            ["date"],
            ["lieu"],
            ["inviter"],
            ["confirmation"],
        ],
    },
    {
        "category": "Colonnes grille",
        "endpoint": "/ask",
        "question": "Quelles réponses peut-on cocher dans la grille d'évaluation ?",
        "expected_status": "success",
        "required_groups": [
            ["oui"],
            ["non"],
        ],
    },
    {
        "category": "Évaluation finale",
        "endpoint": "/ask",
        "question": "Quelles sont les trois rubriques proposées à la fin des activités ?",
        "expected_status": "success",
        "required_groups": [
            ["je maîtrise bien"],
            ["je maîtrise peu"],
            ["je ne maîtrise pas"],
        ],
    },
    {
        "category": "Projet groupe",
        "endpoint": "/ask",
        "question": "Quel spécialiste faut-il inviter dans le projet de groupe de la page 3 ?",
        "expected_status": "success",
        "required_groups": [
            ["spécialiste"],
            ["écologie"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": "Coman redijé une letre pour invité un intervanan du GIEC au déba denvironeman ?",
        "expected_status": "success",
        "required_groups": [
            ["lettre d'invitation"],
            ["GIEC"],
            ["trois paragraphes", "3 paragraphes"],
            ["confirmation"],
            ["mail"],
            ["formule de politesse"],
            ["signature"],
        ],
    },
    {
        "category": "Résumé",
        "endpoint": "/summarize",
        "question": "Résume le cours sur la rédaction d'une lettre pour inviter un intervenant.",
        "expected_status": "success",
        "required_groups": [
            ["lettre d'invitation"],
            ["représentant"],
            ["GIEC"],
            ["débat"],
            ["environnement"],
            ["semaine de l'environnement"],
            ["collège"],
            ["canevas"],
            ["formule d'appel"],
            ["trois paragraphes", "3 paragraphes"],
            ["date"],
            ["objet"],
            ["lieu"],
            ["nature de l'intervention", "nature de l’intervention"],
            ["confirmation"],
            ["coordonnées"],
            ["mail"],
            ["formule de politesse"],
            ["signature"],
            ["spécialiste de l'écologie", "spécialiste de l’écologie"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": "Comment calcule-t-on la masse molaire du dioxyde de carbone ?",
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
        "Test initial du cours : Rédiger une lettre "
        "pour inviter un intervenant"
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
