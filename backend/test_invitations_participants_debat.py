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
    "ecrit-3-2-rediger-les-invitations-a-adresser-aux-differents-"
    "participants-du-debat-projet-2.pdf"
)
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-invitations-participants-debat-baseline"

JSON_REPORT = Path(
    "invitations_participants_debat_test_results.json"
)
CSV_REPORT = Path(
    "invitations_participants_debat_test_results.csv"
)

TEST_CASES = [
    {
        "category": "Objectif général",
        "endpoint": "/ask",
        "question": (
            "Que doivent rédiger les élèves avec leurs camarades dans ce projet ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["invitations"],
            ["participants"],
            ["débat"],
        ],
    },
    {
        "category": "Travail de groupe",
        "endpoint": "/ask",
        "question": (
            "Avec qui l'élève réalise-t-il les tâches proposées ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["membres"],
            ["groupe"],
        ],
    },
    {
        "category": "Nombre de tâches",
        "endpoint": "/ask",
        "question": (
            "Combien de tâches différentes sont proposées dans le projet ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["sept", "7"],
        ],
    },
    {
        "category": "Carte invitation",
        "endpoint": "/ask",
        "question": (
            "Quel premier type de support d'invitation est proposé ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["carte d'invitation"],
        ],
    },
    {
        "category": "Destinataires carte",
        "endpoint": "/ask",
        "question": (
            "À qui la carte d'invitation doit-elle être adressée ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["différents participants"],
        ],
    },
    {
        "category": "Action carte",
        "endpoint": "/ask",
        "question": (
            "Que demande le cours de faire avec la carte d'invitation ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["remplis", "remplir"],
            ["carte"],
        ],
    },
    {
        "category": "Carte postale",
        "endpoint": "/ask",
        "question": (
            "Quel deuxième support d'invitation est proposé dans le projet ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["carte postale"],
        ],
    },
    {
        "category": "Directeur régional",
        "endpoint": "/ask",
        "question": (
            "À quel responsable régional une lettre doit-elle être adressée ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["directeur régional"],
        ],
    },
    {
        "category": "Directeur collège",
        "endpoint": "/ask",
        "question": (
            "À quel responsable de l'établissement une lettre doit-elle être adressée ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["directeur"],
            ["collège"],
        ],
    },
    {
        "category": "Parents élèves",
        "endpoint": "/ask",
        "question": (
            "Quel type de lettre doit être adressé aux parents d'élèves ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["lettre conventionnelle"],
            ["invitation"],
            ["parents d'élèves"],
        ],
    },
    {
        "category": "Association environnement",
        "endpoint": "/ask",
        "question": (
            "Quel support est proposé pour inviter les membres d'une association ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["email", "e-mail", "mail"],
        ],
    },
    {
        "category": "Association objectif",
        "endpoint": "/ask",
        "question": (
            "Quelle cause défend l'association mentionnée dans le projet ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["environnement"],
        ],
    },
    {
        "category": "Amis",
        "endpoint": "/ask",
        "question": (
            "Quel type de correspondance est proposé pour inviter des amis ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["lettre"],
            ["amis"],
        ],
    },
    {
        "category": "Supports non lettre",
        "endpoint": "/ask",
        "question": (
            "Quels supports autres qu'une lettre sont proposés dans le projet ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["carte d'invitation"],
            ["carte postale"],
            ["email", "e-mail", "mail"],
        ],
    },
    {
        "category": "Supports lettre",
        "endpoint": "/ask",
        "question": (
            "Quels destinataires reçoivent explicitement une lettre dans les tâches proposées ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["directeur régional"],
            ["directeur du collège"],
            ["parents d'élèves"],
            ["amis"],
        ],
    },
    {
        "category": "Public institutionnel",
        "endpoint": "/ask",
        "question": (
            "Quels deux directeurs sont cités comme destinataires de lettres ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["directeur régional"],
            ["directeur du collège"],
        ],
    },
    {
        "category": "Public familial",
        "endpoint": "/ask",
        "question": (
            "Quel public familial est cité comme destinataire d'une invitation ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["parents d'élèves"],
        ],
    },
    {
        "category": "Public amical",
        "endpoint": "/ask",
        "question": (
            "Quel public amical est cité comme destinataire d'une invitation ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["amis"],
        ],
    },
    {
        "category": "Public associatif",
        "endpoint": "/ask",
        "question": (
            "Quel public associatif doit recevoir un Email ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["membres"],
            ["association"],
            ["environnement"],
        ],
    },
    {
        "category": "Lien débat",
        "endpoint": "/ask",
        "question": (
            "À quelle activité commune sont liées toutes les invitations du projet ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["débat"],
        ],
    },
    {
        "category": "Projet",
        "endpoint": "/ask",
        "question": (
            "Le cours est-il présenté comme une leçon ordinaire ou comme un projet ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["projet"],
        ],
    },
    {
        "category": "Premier groupe tâches",
        "endpoint": "/ask",
        "question": (
            "Quelles sont les deux premières tâches proposées ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["carte d'invitation"],
            ["carte postale"],
        ],
    },
    {
        "category": "Deux directeurs",
        "endpoint": "/ask",
        "question": (
            "Quelles sont les deux tâches qui concernent des directeurs ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["directeur régional"],
            ["directeur du collège"],
        ],
    },
    {
        "category": "Invitation formelle parents",
        "endpoint": "/ask",
        "question": (
            "Quelle invitation est explicitement qualifiée de conventionnelle ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["lettre conventionnelle d'invitation"],
            ["parents d'élèves"],
        ],
    },
    {
        "category": "Invitation numérique",
        "endpoint": "/ask",
        "question": (
            "Quelle invitation numérique est mentionnée dans le projet ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["email", "e-mail", "mail"],
            ["association"],
        ],
    },
    {
        "category": "Variété supports",
        "endpoint": "/ask",
        "question": (
            "Le projet demande-t-il d'utiliser un seul type d'invitation ou plusieurs supports ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["plusieurs", "différents"],
            ["carte"],
            ["lettre"],
            ["email", "mail"],
        ],
    },
    {
        "category": "Organisation collective",
        "endpoint": "/ask",
        "question": (
            "Comment le travail d'invitation est-il organisé entre les élèves ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["camarades"],
            ["membres"],
            ["groupe"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": (
            "Coman preparé lé invitasion pour lé partisipan du déba: kart, postale, direktèr rejional, paron, asosiasion é ami ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["carte d'invitation"],
            ["carte postale"],
            ["directeur régional"],
            ["parents d'élèves"],
            ["association"],
            ["amis"],
        ],
    },
    {
        "category": "Résumé",
        "endpoint": "/summarize",
        "question": (
            "Résume le projet sur la rédaction des invitations aux différents participants du débat."
        ),
        "expected_status": "success",
        "required_groups": [
            ["invitations"],
            ["participants"],
            ["débat"],
            ["camarades"],
            ["groupe"],
            ["carte d'invitation"],
            ["carte postale"],
            ["directeur régional"],
            ["directeur du collège"],
            ["lettre conventionnelle"],
            ["parents d'élèves"],
            ["email", "mail"],
            ["association"],
            ["environnement"],
            ["amis"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": (
            "Comment calcule-t-on la fréquence d'une onde sonore ?"
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
        "Test initial du projet : Invitations aux différents "
        "participants du débat"
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
