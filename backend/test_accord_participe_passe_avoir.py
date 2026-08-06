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
    "accord-du-participe-passe-employe-avec-l-auxiliaire-avoir.pdf"
)
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-accord-participe-passe-avoir-baseline"

JSON_REPORT = Path(
    "accord_participe_passe_avoir_test_results.json"
)
CSV_REPORT = Path(
    "accord_participe_passe_avoir_test_results.csv"
)

TEST_CASES = [
    {
        "category": "Règle sujet",
        "endpoint": "/ask",
        "question": (
            "Avec l'auxiliaire « avoir », le participe passé "
            "s'accorde-t-il avec le sujet ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["ne s'accorde jamais", "jamais"],
            ["sujet"],
        ],
    },
    {
        "category": "Absence accord",
        "endpoint": "/ask",
        "question": (
            "Avec quel élément le participe passé des verbes "
            "conjugués avec « avoir » ne s'accorde-t-il jamais ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["sujet"],
            ["ne s'accorde jamais", "jamais"],
        ],
    },
    {
        "category": "Exemple travaillé",
        "endpoint": "/ask",
        "question": (
            "Dans « Les filles ont bien travaillé », "
            "quel est le participe passé ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["travaillé"],
            ["participe passé"],
        ],
    },
    {
        "category": "Sujet filles",
        "endpoint": "/ask",
        "question": (
            "Quel est le sujet dans la phrase "
            "« Les filles ont bien travaillé » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["Les filles", "filles"],
        ],
    },
    {
        "category": "Pas accord travaillé",
        "endpoint": "/ask",
        "question": (
            "Pourquoi « travaillé » ne s'accorde-t-il pas "
            "avec « Les filles » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["auxiliaire avoir", "avoir"],
            ["ne s'accorde jamais", "pas d'accord"],
            ["sujet"],
        ],
    },
    {
        "category": "Règle COD",
        "endpoint": "/ask",
        "question": (
            "Dans quel cas le participe passé employé avec "
            "l'auxiliaire « avoir » s'accorde-t-il ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["complément d'objet direct", "COD"],
            ["placé avant"],
            ["auxiliaire"],
        ],
    },
    {
        "category": "Type accord COD",
        "endpoint": "/ask",
        "question": (
            "En quoi le participe passé s'accorde-t-il avec "
            "le COD placé avant l'auxiliaire « avoir » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["genre"],
            ["nombre"],
            ["COD", "complément d'objet direct"],
        ],
    },
    {
        "category": "COD histoire après",
        "endpoint": "/ask",
        "question": (
            "Dans « J'ai lu cette histoire », quel est le COD ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["cette histoire"],
            ["COD", "complément d'objet direct"],
        ],
    },
    {
        "category": "Position COD après",
        "endpoint": "/ask",
        "question": (
            "Dans « J'ai lu cette histoire », le COD est-il "
            "placé avant ou après l'auxiliaire « avoir » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["après"],
            ["auxiliaire"],
        ],
    },
    {
        "category": "Forme lu",
        "endpoint": "/ask",
        "question": (
            "Quelle forme du participe passé est utilisée dans "
            "« J'ai lu cette histoire » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["lu"],
        ],
    },
    {
        "category": "Pourquoi lu",
        "endpoint": "/ask",
        "question": (
            "Pourquoi écrit-on « lu » sans accord dans "
            "« J'ai lu cette histoire » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["COD", "complément d'objet direct"],
            ["après"],
            ["auxiliaire"],
        ],
    },
    {
        "category": "Forme lue",
        "endpoint": "/ask",
        "question": (
            "Dans « Cette histoire, je l'ai lue », "
            "quel est le participe passé ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["lue"],
            ["participe passé"],
        ],
    },
    {
        "category": "Nature l apostrophe",
        "endpoint": "/ask",
        "question": (
            "Quelle est la nature de « l' » dans "
            "« Cette histoire, je l'ai lue » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["pronom personnel"],
        ],
    },
    {
        "category": "Référent l apostrophe",
        "endpoint": "/ask",
        "question": (
            "Que remplace le pronom personnel « l' » dans "
            "« Cette histoire, je l'ai lue » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["cette histoire"],
            ["COD", "complément d'objet direct"],
        ],
    },
    {
        "category": "Position l apostrophe",
        "endpoint": "/ask",
        "question": (
            "Où est placé le pronom « l' » par rapport "
            "à l'auxiliaire « avoir » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["avant"],
            ["auxiliaire"],
        ],
    },
    {
        "category": "Pourquoi lue",
        "endpoint": "/ask",
        "question": (
            "Pourquoi écrit-on « lue » avec un e dans "
            "« Cette histoire, je l'ai lue » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["COD", "complément d'objet direct"],
            ["placé avant", "avant"],
            ["cette histoire"],
            ["féminin"],
            ["singulier"],
        ],
    },
    {
        "category": "Comparaison lu lue",
        "endpoint": "/ask",
        "question": (
            "Quelle différence d'accord y a-t-il entre "
            "« J'ai lu cette histoire » et "
            "« Cette histoire, je l'ai lue » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["lu"],
            ["COD"],
            ["après"],
            ["lue"],
            ["avant"],
        ],
    },
    {
        "category": "Formes COD avant",
        "endpoint": "/ask",
        "question": (
            "Sous quelles formes le COD placé avant "
            "l'auxiliaire « avoir » peut-il apparaître "
            "selon la remarque du cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["pronom relatif"],
            ["pronom personnel"],
        ],
    },
    {
        "category": "Phrase pronom relatif",
        "endpoint": "/ask",
        "question": (
            "Quelle phrase du cours illustre un COD placé avant "
            "« avoir » sous la forme d'un pronom relatif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            [
                "J'ai fait quelques propositions que la direction "
                "a acceptées"
            ],
        ],
    },
    {
        "category": "Identifier que",
        "endpoint": "/ask",
        "question": (
            "Dans « J'ai fait quelques propositions que la "
            "direction a acceptées », quel est le pronom relatif ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["que"],
            ["pronom relatif"],
        ],
    },
    {
        "category": "Position que",
        "endpoint": "/ask",
        "question": (
            "Dans l'exemple des propositions acceptées, "
            "où se trouve le pronom relatif « que » par rapport "
            "à l'auxiliaire « avoir » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["précède", "avant"],
            ["auxiliaire"],
        ],
    },
    {
        "category": "Accord acceptées relatif",
        "endpoint": "/ask",
        "question": (
            "Pourquoi le participe passé « acceptées » prend-il "
            "la marque du féminin pluriel dans la phrase avec « que » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["quelques propositions", "propositions"],
            ["COD"],
            ["avant", "précède"],
            ["féminin"],
            ["pluriel"],
        ],
    },
    {
        "category": "Phrase pronom personnel",
        "endpoint": "/ask",
        "question": (
            "Quelle phrase du cours illustre un COD placé avant "
            "« avoir » sous la forme d'un pronom personnel ?"
        ),
        "expected_status": "success",
        "required_groups": [
            [
                "J'ai fait quelques propositions et la direction "
                "les a acceptées"
            ],
        ],
    },
    {
        "category": "Identifier les",
        "endpoint": "/ask",
        "question": (
            "Dans « J'ai fait quelques propositions et la "
            "direction les a acceptées », quel est le pronom personnel ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["les"],
            ["pronom personnel"],
        ],
    },
    {
        "category": "Position les",
        "endpoint": "/ask",
        "question": (
            "Où est placé le pronom personnel « les » "
            "par rapport à l'auxiliaire « avoir » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["précède", "avant"],
            ["auxiliaire"],
        ],
    },
    {
        "category": "Accord acceptées personnel",
        "endpoint": "/ask",
        "question": (
            "Avec quel COD « acceptées » s'accorde-t-il "
            "dans la phrase contenant le pronom « les » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["quelques propositions", "propositions"],
            ["COD"],
        ],
    },
    {
        "category": "Comparaison pronoms",
        "endpoint": "/ask",
        "question": (
            "Quelle différence y a-t-il entre « que » et « les » "
            "dans les deux exemples de la remarque ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["que"],
            ["pronom relatif"],
            ["les"],
            ["pronom personnel"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": (
            "Comant le participe passer avec avoir sacorde avec "
            "le sujet ou le COD placer avant lauxiliaire ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["ne s'accorde jamais", "jamais"],
            ["sujet"],
            ["COD", "complément d'objet direct"],
            ["placé avant", "avant"],
            ["genre"],
            ["nombre"],
        ],
    },
    {
        "category": "Résumé",
        "endpoint": "/summarize",
        "question": (
            "Résume le cours sur l'accord du participe passé "
            "employé avec l'auxiliaire « avoir »."
        ),
        "expected_status": "success",
        "required_groups": [
            ["ne s'accorde jamais", "jamais"],
            ["sujet"],
            ["COD", "complément d'objet direct"],
            ["placé avant", "avant"],
            ["genre"],
            ["nombre"],
            ["pronom relatif"],
            ["pronom personnel"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": (
            "Comment fonctionne un moteur électrique ?"
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
        "Test initial du cours : Accord du participe passé "
        "avec l'auxiliaire avoir"
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
