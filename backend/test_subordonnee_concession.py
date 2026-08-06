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
    "la-subordonnee-circonstancielle-d-opposition-"
    "ou-de-concession.pdf"
)
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-subordonnee-concession-baseline"

JSON_REPORT = Path(
    "subordonnee_concession_test_results.json"
)
CSV_REPORT = Path(
    "subordonnee_concession_test_results.csv"
)

TEST_CASES = [
    {
        "category": "Définition",
        "endpoint": "/ask",
        "question": (
            "Qu'est-ce qu'une subordonnée circonstancielle "
            "de concession ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["proposition"],
            ["complément circonstanciel de concession"],
            ["verbe principal"],
        ],
    },
    {
        "category": "Autre nom",
        "endpoint": "/ask",
        "question": (
            "Quel autre nom donne-t-on à la subordonnée "
            "de concession ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["concessive"],
        ],
    },
    {
        "category": "Fonction",
        "endpoint": "/ask",
        "question": (
            "Quelle fonction assume la subordonnée "
            "de concession ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["complément circonstanciel de concession"],
        ],
    },
    {
        "category": "Dépendance",
        "endpoint": "/ask",
        "question": (
            "De quel élément dépend la subordonnée "
            "circonstancielle de concession ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["verbe principal"],
        ],
    },
    {
        "category": "Sens",
        "endpoint": "/ask",
        "question": (
            "Quelle relation la subordonnée de concession "
            "exprime-t-elle entre deux faits ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["contradiction"],
            ["deux faits"],
            ["dépendants"],
        ],
    },
    {
        "category": "Exemple Kamel",
        "endpoint": "/ask",
        "question": (
            "Quelle phrase du cours illustre la concession "
            "avec Kamel ?"
        ),
        "expected_status": "success",
        "required_groups": [
            [
                "Bien que Kamel soit fatigué, "
                "il continue à travailler"
            ],
        ],
    },
    {
        "category": "Proposition A",
        "endpoint": "/ask",
        "question": (
            "Dans « Bien que Kamel soit fatigué, il continue "
            "à travailler », quelle est la proposition A ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["Bien que Kamel soit fatigué"],
        ],
    },
    {
        "category": "Proposition B",
        "endpoint": "/ask",
        "question": (
            "Dans « Bien que Kamel soit fatigué, il continue "
            "à travailler », quelle est la proposition B ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["il continue à travailler"],
        ],
    },
    {
        "category": "Opposition A B",
        "endpoint": "/ask",
        "question": (
            "Quelle relation existe entre les propositions A et B "
            "dans l'exemple de Kamel ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["opposés", "opposées"],
            ["contradictoires"],
        ],
    },
    {
        "category": "Logique attendue",
        "endpoint": "/ask",
        "question": (
            "Logiquement, que devrait empêcher la fatigue "
            "de Kamel selon le cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["continuer à travailler"],
            ["ne devrait pas"],
        ],
    },
    {
        "category": "Effet inattendu",
        "endpoint": "/ask",
        "question": (
            "Pourquoi l'exemple de Kamel exprime-t-il "
            "une concession ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["cause"],
            ["n'a pas l'effet attendu", "effet attendu"],
            ["fatigué", "fatigue"],
            ["continue à travailler"],
        ],
    },
    {
        "category": "Nature proposition",
        "endpoint": "/ask",
        "question": (
            "Quelle est la nature de la subordonnée "
            "circonstancielle de concession ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["proposition conjonctive"],
        ],
    },
    {
        "category": "Outils principaux",
        "endpoint": "/ask",
        "question": (
            "Quels outils subordonnants sont cités pour introduire "
            "une subordonnée de concession ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["bien que"],
            ["quoique"],
            ["même si"],
        ],
    },
    {
        "category": "Bien que mode",
        "endpoint": "/ask",
        "question": (
            "Quel mode verbal emploie-t-on après « bien que » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["subjonctif"],
        ],
    },
    {
        "category": "Quoique mode",
        "endpoint": "/ask",
        "question": (
            "Quel mode verbal emploie-t-on après « quoique » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["subjonctif"],
        ],
    },
    {
        "category": "Même si mode",
        "endpoint": "/ask",
        "question": (
            "Quel mode verbal emploie-t-on après « même si » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["indicatif"],
        ],
    },
    {
        "category": "Exemple bien que",
        "endpoint": "/ask",
        "question": (
            "Quelle phrase du cours illustre « bien que » "
            "suivi du subjonctif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["Bien qu'il pleuve, nous irons à la plage"],
            ["subjonctif"],
        ],
    },
    {
        "category": "Exemple quoique",
        "endpoint": "/ask",
        "question": (
            "Quelle phrase du cours illustre « quoique » "
            "suivi du subjonctif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["Quoiqu'il pleuve, nous irons à la plage"],
            ["subjonctif"],
        ],
    },
    {
        "category": "Verbe pleuve",
        "endpoint": "/ask",
        "question": (
            "Dans les exemples avec « bien que » et « quoique », "
            "quel verbe est employé au subjonctif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["pleuve"],
            ["subjonctif"],
        ],
    },
    {
        "category": "Exemple même si",
        "endpoint": "/ask",
        "question": (
            "Dans l'exemple avec « même si », quel verbe "
            "est employé à l'indicatif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["habite"],
            ["indicatif"],
        ],
    },
    {
        "category": "Position même si",
        "endpoint": "/ask",
        "question": (
            "La proposition introduite par « même si » peut-elle "
            "être placée avant ou après la proposition principale ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["avant"],
            ["après"],
        ],
    },
    {
        "category": "Comparaison modes",
        "endpoint": "/ask",
        "question": (
            "Quelle différence de mode existe entre « bien que » "
            "ou « quoique » et « même si » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["bien que"],
            ["quoique"],
            ["subjonctif"],
            ["même si"],
            ["indicatif"],
        ],
    },
    {
        "category": "Malgré structure",
        "endpoint": "/ask",
        "question": (
            "Quelle structure suit le mot « malgré » "
            "dans le cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["groupe nominal"],
        ],
    },
    {
        "category": "En dépit de structure",
        "endpoint": "/ask",
        "question": (
            "Quelle structure suit l'expression « en dépit de » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["groupe nominal"],
        ],
    },
    {
        "category": "Exemple malgré",
        "endpoint": "/ask",
        "question": (
            "Quelle phrase du cours utilise « malgré » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            [
                "Malgré la fatigue, l'ouvrier continue "
                "à travailler"
            ],
        ],
    },
    {
        "category": "Exemple en dépit",
        "endpoint": "/ask",
        "question": (
            "Quelle phrase du cours utilise « en dépit de » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            [
                "L'ouvrier continue à travailler "
                "en dépit de la fatigue"
            ],
        ],
    },
    {
        "category": "Groupe nominal",
        "endpoint": "/ask",
        "question": (
            "Quel groupe nominal suit « malgré » et "
            "« en dépit de » dans les exemples du cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["la fatigue"],
            ["groupe nominal"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": (
            "Comant la subordoné de concesion exprime une "
            "contradiction et quel mode on utilise avec bien que, "
            "quoique et meme si ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["contradiction"],
            ["bien que"],
            ["quoique"],
            ["subjonctif"],
            ["même si"],
            ["indicatif"],
        ],
    },
    {
        "category": "Résumé",
        "endpoint": "/summarize",
        "question": (
            "Résume le cours sur la subordonnée circonstancielle "
            "d'opposition ou de concession."
        ),
        "expected_status": "success",
        "required_groups": [
            ["concessive"],
            ["complément circonstanciel de concession"],
            ["contradiction"],
            ["bien que"],
            ["quoique"],
            ["subjonctif"],
            ["même si"],
            ["indicatif"],
            ["malgré"],
            ["en dépit de"],
            ["groupe nominal"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": (
            "Comment fonctionne un moteur à réaction ?"
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
        "Test initial du cours : Subordonnée circonstancielle "
        "d'opposition ou de concession"
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
