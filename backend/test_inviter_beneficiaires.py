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
    "ecrit-3-1-rediger-des-lettres-pour-inviter-"
    "des-beneficiaires-1.pdf"
)
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-inviter-beneficiaires-baseline"

JSON_REPORT = Path(
    "inviter_beneficiaires_test_results.json"
)
CSV_REPORT = Path(
    "inviter_beneficiaires_test_results.csv"
)

TEST_CASES = [
    {
        "category": "Objectif général",
        "endpoint": "/ask",
        "question": (
            "Que doit-on apprendre à rédiger dans ce cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["correspondances d'invitation", "lettres pour inviter"],
        ],
    },
    {
        "category": "Événement",
        "endpoint": "/ask",
        "question": (
            "À quel événement les personnes doivent-elles être invitées ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["débat"],
            ["environnement"],
        ],
    },
    {
        "category": "Personnes invitées",
        "endpoint": "/ask",
        "question": (
            "Quelles catégories de personnes sont citées comme personnes à inviter ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["participants"],
            ["bénéficiaires"],
            ["parents"],
        ],
    },
    {
        "category": "Diversité correspondances",
        "endpoint": "/ask",
        "question": (
            "Que demande le sujet de rédiger pour inviter les différentes personnes ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["divers types de correspondances"],
            ["invitations"],
        ],
    },
    {
        "category": "Lettre parents",
        "endpoint": "/ask",
        "question": (
            "Quel type de correspondance peut être adressé aux parents d'élèves ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["lettre"],
            ["parents d'élèves"],
        ],
    },
    {
        "category": "SMS ami",
        "endpoint": "/ask",
        "question": (
            "Quel moyen de correspondance est proposé pour inviter un ami ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["sms"],
            ["ami"],
        ],
    },
    {
        "category": "Mail cousin",
        "endpoint": "/ask",
        "question": (
            "Quel moyen de correspondance est proposé pour inviter un cousin ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["mail"],
            ["cousin"],
        ],
    },
    {
        "category": "Réseaux sociaux",
        "endpoint": "/ask",
        "question": (
            "Quel type de message peut être partagé sur les réseaux sociaux ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["message"],
            ["réseaux sociaux"],
        ],
    },
    {
        "category": "Lettre directeur",
        "endpoint": "/ask",
        "question": (
            "À qui peut être adressée une autre lettre d'invitation proposée dans le cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["directeur"],
            ["collège"],
        ],
    },
    {
        "category": "Choix correspondances",
        "endpoint": "/ask",
        "question": (
            "Combien de propositions de correspondances sont données dans le sujet ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["cinq", "5"],
        ],
    },
    {
        "category": "But compréhension",
        "endpoint": "/ask",
        "question": (
            "Que vont rédiger les élèves après avoir choisi parmi les propositions ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["divers types"],
            ["correspondances d'invitation"],
        ],
    },
    {
        "category": "Rappel types",
        "endpoint": "/ask",
        "question": (
            "Quel premier élément faut-il rappeler avant la production ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["différents types de correspondances"],
        ],
    },
    {
        "category": "Rappel structure",
        "endpoint": "/ask",
        "question": (
            "Que faut-il rappeler concernant la correspondance choisie ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["structure"],
            ["correspondance choisie"],
        ],
    },
    {
        "category": "Rappel expressions",
        "endpoint": "/ask",
        "question": (
            "Quel élément linguistique faut-il rappeler avant de rédiger ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["expressions"],
            ["utiliser"],
        ],
    },
    {
        "category": "Rappel formules",
        "endpoint": "/ask",
        "question": (
            "Quel autre élément linguistique faut-il rappeler avec les expressions ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["formules"],
            ["utiliser"],
        ],
    },
    {
        "category": "Production choix",
        "endpoint": "/ask",
        "question": (
            "Quel est le premier critère donné pour rédiger un document d'invitation ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["choix"],
            ["correspondance d'invitation"],
        ],
    },
    {
        "category": "Production structure",
        "endpoint": "/ask",
        "question": (
            "Que faut-il respecter après avoir choisi une correspondance d'invitation ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["structure"],
            ["correspondances"],
        ],
    },
    {
        "category": "Production expressions",
        "endpoint": "/ask",
        "question": (
            "Quel type d'expressions faut-il employer dans le document d'invitation ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["expressions convenables"],
        ],
    },
    {
        "category": "Production formules",
        "endpoint": "/ask",
        "question": (
            "Quel type de formules faut-il employer dans le document d'invitation ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["formules convenables"],
        ],
    },
    {
        "category": "Grille amélioration",
        "endpoint": "/ask",
        "question": (
            "À quoi sert la grille de critères après la rédaction ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["améliore", "améliorer"],
            ["correspondance"],
            ["grille"],
        ],
    },
    {
        "category": "Critère choix",
        "endpoint": "/ask",
        "question": (
            "Quel critère de la grille vérifie le choix d'une correspondance ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["j'ai choisi une correspondance"],
        ],
    },
    {
        "category": "Critère structure",
        "endpoint": "/ask",
        "question": (
            "Quel critère de la grille vérifie la structure de la correspondance ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["j'ai respecté la structure"],
            ["correspondance"],
        ],
    },
    {
        "category": "Critère expressions",
        "endpoint": "/ask",
        "question": (
            "Quel critère de la grille concerne les expressions ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["j'ai employé"],
            ["expressions convenables"],
        ],
    },
    {
        "category": "Critère formules",
        "endpoint": "/ask",
        "question": (
            "Quel critère de la grille concerne les formules ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["j'ai employé"],
            ["formules convenables"],
        ],
    },
    {
        "category": "Colonnes grille",
        "endpoint": "/ask",
        "question": (
            "Quelles réponses peut-on cocher dans la grille d'évaluation ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["oui"],
            ["non"],
        ],
    },
    {
        "category": "Évaluation finale",
        "endpoint": "/ask",
        "question": (
            "Quelles sont les trois rubriques de l'évaluation finale ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["je maîtrise bien"],
            ["je maîtrise peu"],
            ["je ne maîtrise pas"],
        ],
    },
    {
        "category": "Adaptation support",
        "endpoint": "/ask",
        "question": (
            "Pourquoi faut-il choisir la structure de la correspondance avant de rédiger ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["correspondance choisie"],
            ["structure"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": (
            "Coman redijé pluzieur korrespondenk dinvitasion pour invité paron ami kouzin é direktèr o déba denvironeman ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["lettre"],
            ["sms"],
            ["mail"],
            ["réseaux sociaux"],
            ["directeur"],
            ["débat"],
            ["environnement"],
            ["structure"],
            ["expressions convenables"],
            ["formules convenables"],
        ],
    },
    {
        "category": "Résumé",
        "endpoint": "/summarize",
        "question": (
            "Résume le cours sur la rédaction de correspondances pour inviter des bénéficiaires."
        ),
        "expected_status": "success",
        "required_groups": [
            ["débat"],
            ["environnement"],
            ["participants"],
            ["bénéficiaires"],
            ["parents"],
            ["lettre"],
            ["sms"],
            ["mail"],
            ["réseaux sociaux"],
            ["directeur"],
            ["collège"],
            ["structure"],
            ["expressions convenables"],
            ["formules convenables"],
            ["oui"],
            ["non"],
            ["je maîtrise bien"],
            ["je maîtrise peu"],
            ["je ne maîtrise pas"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": (
            "Comment calcule-t-on la résistance électrique d'un conducteur ?"
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
        "Test initial du cours : Rédiger des lettres "
        "pour inviter des bénéficiaires"
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
