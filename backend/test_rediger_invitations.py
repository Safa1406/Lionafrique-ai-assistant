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
EXPECTED_SOURCE = "ecrit-2-1-rediger-des-invitations.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-rediger-invitations-baseline"

JSON_REPORT = Path("rediger_invitations_test_results.json")
CSV_REPORT = Path("rediger_invitations_test_results.csv")

TEST_CASES = [
    {
        "category": "Type de production",
        "endpoint": "/ask",
        "question": "Quel type de lettre faut-il rédiger dans ce cours ?",
        "expected_status": "success",
        "required_groups": [
            ["lettre d'invitation"],
        ],
    },
    {
        "category": "Cadre du projet",
        "endpoint": "/ask",
        "question": "Dans quel cadre la lettre d'invitation est-elle rédigée ?",
        "expected_status": "success",
        "required_groups": [
            ["club artistique et culturel"],
            ["établissement"],
        ],
    },
    {
        "category": "Destinataire",
        "endpoint": "/ask",
        "question": "À qui la lettre d'invitation doit-elle être adressée ?",
        "expected_status": "success",
        "required_groups": [
            ["directeur provincial"],
        ],
    },
    {
        "category": "Objet de l'invitation",
        "endpoint": "/ask",
        "question": "À quoi le directeur provincial est-il invité ?",
        "expected_status": "success",
        "required_groups": [
            ["assister"],
            ["manifestation culturelle"],
        ],
    },
    {
        "category": "Organisateur",
        "endpoint": "/ask",
        "question": "Qui organise la manifestation culturelle ?",
        "expected_status": "success",
        "required_groups": [
            ["club"],
        ],
    },
    {
        "category": "Travail préparatoire",
        "endpoint": "/ask",
        "question": "Que doivent élaborer les élèves avec leurs camarades avant de rédiger la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["canevas"],
            ["lettre d'invitation"],
        ],
    },
    {
        "category": "Cadre formel",
        "endpoint": "/ask",
        "question": "Dans quel cadre la structure de la lettre d'invitation doit-elle être rappelée ?",
        "expected_status": "success",
        "required_groups": [
            ["cadre formel"],
        ],
    },
    {
        "category": "Expressions à rappeler",
        "endpoint": "/ask",
        "question": "Quel type d'expressions faut-il rappeler avant de rédiger la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["expressions"],
            ["inviter"],
        ],
    },
    {
        "category": "Politesse",
        "endpoint": "/ask",
        "question": "Quel type de formules faut-il utiliser dans une lettre d'invitation formelle ?",
        "expected_status": "success",
        "required_groups": [
            ["formules de politesse"],
        ],
    },
    {
        "category": "Corps de lettre",
        "endpoint": "/ask",
        "question": "Combien de grandes parties du corps de la lettre d'invitation sont indiquées dans le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["trois"],
        ],
    },
    {
        "category": "Premier paragraphe",
        "endpoint": "/ask",
        "question": "Que doit-on annoncer dans la première partie du corps de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["événement"],
            ["objet de l'invitation", "objet"],
            ["lieu"],
            ["date"],
        ],
    },
    {
        "category": "Qui invite",
        "endpoint": "/ask",
        "question": "Parmi les informations sur l'événement, doit-on préciser qui invite ?",
        "expected_status": "success",
        "required_groups": [
            ["qui invite"],
        ],
    },
    {
        "category": "Attente envers invité",
        "endpoint": "/ask",
        "question": "Que faut-il dire concernant la personne invitée dans la deuxième partie du corps de la lettre ?",
        "expected_status": "success",
        "required_groups": [
            ["ce que l'on attend", "ce qu'on attend"],
            ["personne invitée"],
        ],
    },
    {
        "category": "Confirmation",
        "endpoint": "/ask",
        "question": "Quelle confirmation doit-on demander à la personne invitée ?",
        "expected_status": "success",
        "required_groups": [
            ["confirmation"],
            ["participation"],
        ],
    },
    {
        "category": "Expression invitation 1",
        "endpoint": "/ask",
        "question": "Quelle expression formelle du cours commence par « Nous avons le plaisir » ?",
        "expected_status": "success",
        "required_groups": [
            ["nous avons le plaisir de vous inviter"],
        ],
    },
    {
        "category": "Expression invitation 2",
        "endpoint": "/ask",
        "question": "Quelle expression formelle du cours utilise le mot « ravis » ?",
        "expected_status": "success",
        "required_groups": [
            ["nous sommes ravis de vous inviter"],
        ],
    },
    {
        "category": "Expression invitation 3",
        "endpoint": "/ask",
        "question": "Quelle expression du cours indique que l'acceptation de l'invitation ferait plaisir ?",
        "expected_status": "success",
        "required_groups": [
            ["vous nous ferez tellement plaisir"],
            ["acceptez notre invitation"],
        ],
    },
    {
        "category": "Formule finale",
        "endpoint": "/ask",
        "question": "Que faut-il insérer à la fin de la lettre d'invitation ?",
        "expected_status": "success",
        "required_groups": [
            ["formule finale de politesse"],
        ],
    },
    {
        "category": "Canevas",
        "endpoint": "/ask",
        "question": "Sur quel élément les élèves doivent-ils s'appuyer pour rédiger la lettre formelle ?",
        "expected_status": "success",
        "required_groups": [
            ["canevas"],
            ["lettre"],
        ],
    },
    {
        "category": "Grille amélioration",
        "endpoint": "/ask",
        "question": "À quoi sert la grille de critères après la rédaction ?",
        "expected_status": "success",
        "required_groups": [
            ["améliore", "améliorer"],
            ["texte"],
            ["grille"],
        ],
    },
    {
        "category": "Critère canevas",
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
        "category": "Critère expressions",
        "endpoint": "/ask",
        "question": "Quel critère vérifie l'emploi des expressions d'invitation ?",
        "expected_status": "success",
        "required_groups": [
            ["utilisé"],
            ["expressions pour inviter"],
        ],
    },
    {
        "category": "Trois paragraphes",
        "endpoint": "/ask",
        "question": "Sous quelle forme la lettre doit-elle être structurée selon la grille ?",
        "expected_status": "success",
        "required_groups": [
            ["trois paragraphes"],
        ],
    },
    {
        "category": "Critère politesse",
        "endpoint": "/ask",
        "question": "Que demande la grille au sujet des formules de politesse ?",
        "expected_status": "success",
        "required_groups": [
            ["formules de politesse"],
            ["convenables"],
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
        "category": "Structure globale",
        "endpoint": "/ask",
        "question": "Quels éléments essentiels doivent apparaître dans une lettre d'invitation formelle selon le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["événement"],
            ["personne invitée"],
            ["confirmation"],
            ["formule finale"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": "Coman redijé une letre dinvitasion formel pour invité le directeur provinsial ?",
        "expected_status": "success",
        "required_groups": [
            ["lettre d'invitation"],
            ["directeur provincial"],
            ["manifestation culturelle"],
            ["trois paragraphes"],
            ["confirmation"],
            ["formule finale"],
        ],
    },
    {
        "category": "Résumé",
        "endpoint": "/summarize",
        "question": "Résume le cours sur la rédaction des invitations.",
        "expected_status": "success",
        "required_groups": [
            ["lettre d'invitation"],
            ["directeur provincial"],
            ["club artistique et culturel"],
            ["manifestation culturelle"],
            ["canevas"],
            ["événement"],
            ["lieu"],
            ["date"],
            ["personne invitée"],
            ["confirmation"],
            ["participation"],
            ["nous avons le plaisir de vous inviter"],
            ["nous sommes ravis de vous inviter"],
            ["trois paragraphes"],
            ["formules de politesse"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": "Comment calcule-t-on l'énergie cinétique d'une voiture ?",
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
    print("Test initial du cours : Rédiger des invitations")
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
        print(f"[{index}/{len(TEST_CASES)}] [{category}]")
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
