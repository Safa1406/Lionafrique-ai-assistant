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
    "la-phrase-interrogative-et-la-phrase-imperative-"
    "au-discours-rapporte.pdf"
)
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = (
    "v1-discours-rapporte-interrogatif-imperatif-baseline"
)

JSON_REPORT = Path(
    "discours_rapporte_interrogatif_imperatif_test_results.json"
)
CSV_REPORT = Path(
    "discours_rapporte_interrogatif_imperatif_test_results.csv"
)

TEST_CASES = [
    {
        "category": "Ponctuation",
        "endpoint": "/ask",
        "question": (
            "Quels signes de ponctuation disparaissent lors du "
            "passage du discours direct au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["guillemets"],
            ["deux points"],
            ["point d'interrogation"],
            ["point d'exclamation"],
        ],
    },
    {
        "category": "Pronoms et possessifs",
        "endpoint": "/ask",
        "question": (
            "Que deviennent les pronoms personnels et les adjectifs "
            "possessifs au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["changent"],
            ["personne à qui ils se rapportent", "personne"],
        ],
    },
    {
        "category": "Interrogation totale",
        "endpoint": "/ask",
        "question": (
            "Quand une interrogation est-elle dite totale ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["oui"],
            ["non"],
        ],
    },
    {
        "category": "Introduction totale",
        "endpoint": "/ask",
        "question": (
            "Par quel mot introduit-on une interrogation totale "
            "au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["si"],
            ["adverbe interrogatif", "interrogative indirecte"],
        ],
    },
    {
        "category": "Transformation totale",
        "endpoint": "/ask",
        "question": (
            "Transforme au discours indirect : Mon père me demande : "
            "« Est-ce que tu as fait tes exercices ? »"
        ),
        "expected_status": "success",
        "required_groups": [
            ["Mon père me demande si j'ai fait mes exercices"],
        ],
    },
    {
        "category": "Formes question totale",
        "endpoint": "/ask",
        "question": (
            "Quelles sont les trois formulations directes données "
            "pour demander si les exercices ont été faits ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["Est-ce que tu as fait tes exercices"],
            ["As-tu fait tes exercices"],
            ["Tu as fait tes exercices"],
        ],
    },
    {
        "category": "Interrogation partielle",
        "endpoint": "/ask",
        "question": (
            "Quand une interrogation est-elle dite partielle ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["ne peut répondre", "on ne peut répondre"],
            ["oui"],
            ["non"],
        ],
    },
    {
        "category": "Introduction partielle",
        "endpoint": "/ask",
        "question": (
            "Par quoi introduit-on une interrogation partielle "
            "au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["même mot interrogatif"],
        ],
    },
    {
        "category": "Pourquoi pleures-tu",
        "endpoint": "/ask",
        "question": (
            "Transforme au discours indirect : Le père demande à "
            "sa petite fille : « Pourquoi pleures-tu ? »"
        ),
        "expected_status": "success",
        "required_groups": [
            [
                "Le père demande à sa petite fille pourquoi "
                "elle pleure"
            ],
        ],
    },
    {
        "category": "Différence interrogations",
        "endpoint": "/ask",
        "question": (
            "Quelle est la différence entre une interrogation totale "
            "et une interrogation partielle ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["totale"],
            ["oui"],
            ["non"],
            ["partielle"],
            ["même mot interrogatif"],
        ],
    },
    {
        "category": "Règle impérative",
        "endpoint": "/ask",
        "question": (
            "Que devient une phrase impérative au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["infinitif"],
            ["préposition de", "de"],
        ],
    },
    {
        "category": "Verbe impératif",
        "endpoint": "/ask",
        "question": (
            "Que devient le verbe conjugué à l'impératif lors du "
            "passage au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["infinitif"],
            ["précédé"],
            ["de"],
        ],
    },
    {
        "category": "Révise",
        "endpoint": "/ask",
        "question": (
            "Comment transforme-t-on « Révise tes leçons ! » "
            "au discours indirect après « Le père ordonne à son fils » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["de réviser ses leçons"],
        ],
    },
    {
        "category": "Ne perds pas",
        "endpoint": "/ask",
        "question": (
            "Comment transforme-t-on « Ne perds pas ton temps à jouer ! » "
            "au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["de ne pas perdre son temps à jouer"],
        ],
    },
    {
        "category": "Transformation impérative complète",
        "endpoint": "/ask",
        "question": (
            "Transforme toute la phrase : Le père ordonne à son fils : "
            "« Révise tes leçons ! Ne perds pas ton temps à jouer ! »"
        ),
        "expected_status": "success",
        "required_groups": [
            [
                "Le père ordonne à son fils de réviser ses leçons "
                "et de ne pas perdre son temps à jouer"
            ],
        ],
    },
    {
        "category": "Condition changement temps",
        "endpoint": "/ask",
        "question": (
            "Dans quel cas les temps verbaux changent-ils au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["verbe introducteur"],
            ["passé"],
        ],
    },
    {
        "category": "Présent imparfait",
        "endpoint": "/ask",
        "question": (
            "Que devient le présent au discours indirect lorsque "
            "le verbe introducteur est au passé ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["imparfait"],
        ],
    },
    {
        "category": "Travailles travaillais",
        "endpoint": "/ask",
        "question": (
            "Transforme : Il m'a demandé : "
            "« Est-ce que tu travailles bien ? »"
        ),
        "expected_status": "success",
        "required_groups": [
            ["Il m'a demandé si je travaillais bien"],
        ],
    },
    {
        "category": "Passé composé plus-que-parfait",
        "endpoint": "/ask",
        "question": (
            "Que devient le passé composé au discours indirect "
            "lorsque le verbe introducteur est au passé ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["plus-que-parfait", "plus que parfait"],
        ],
    },
    {
        "category": "Révisé avais révisé",
        "endpoint": "/ask",
        "question": (
            "Transforme : Il m'a demandé : "
            "« As-tu révisé tes leçons ? »"
        ),
        "expected_status": "success",
        "required_groups": [
            ["Il m'a demandé si j'avais révisé mes leçons"],
        ],
    },
    {
        "category": "Futur conditionnel",
        "endpoint": "/ask",
        "question": (
            "Que devient le futur simple au discours indirect "
            "lorsque le verbe introducteur est au passé ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["conditionnel présent"],
        ],
    },
    {
        "category": "Arrivera arriverait",
        "endpoint": "/ask",
        "question": (
            "Transforme : Il m'a demandé : "
            "« Quand arrivera-t-elle ? »"
        ),
        "expected_status": "success",
        "required_groups": [
            ["Il m'a demandé quand elle arriverait"],
        ],
    },
    {
        "category": "Temps inchangés",
        "endpoint": "/ask",
        "question": (
            "Quels temps ne changent pas lorsque le verbe introducteur "
            "est au passé ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["passé simple"],
            ["plus-que-parfait", "plus que parfait"],
            ["conditionnel"],
            ["imparfait"],
        ],
    },
    {
        "category": "Disparition question",
        "endpoint": "/ask",
        "question": (
            "Le point d'interrogation est-il conservé au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["disparaît", "non"],
            ["point d'interrogation"],
        ],
    },
    {
        "category": "Changement personne",
        "endpoint": "/ask",
        "question": (
            "Dans l'exemple des exercices, comment le pronom « tu » "
            "change-t-il au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["je", "j'"],
        ],
    },
    {
        "category": "Changement possessif",
        "endpoint": "/ask",
        "question": (
            "Dans l'exemple des exercices, comment l'adjectif possessif "
            "« tes » change-t-il au discours indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["mes"],
        ],
    },
    {
        "category": "Tableau des temps",
        "endpoint": "/ask",
        "question": (
            "Résume les trois changements de temps présentés dans "
            "le tableau du cours."
        ),
        "expected_status": "success",
        "required_groups": [
            ["présent"],
            ["imparfait"],
            ["passé composé"],
            ["plus-que-parfait", "plus que parfait"],
            ["futur simple"],
            ["conditionnel présent"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": (
            "Comant on transforme une question totale ou partielle et "
            "une phrase imperatif au discour indirect ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["si"],
            ["même mot interrogatif"],
            ["infinitif"],
            ["de"],
        ],
    },
    {
        "category": "Résumé",
        "endpoint": "/summarize",
        "question": (
            "Résume le cours sur les phrases interrogatives et impératives "
            "au discours rapporté."
        ),
        "expected_status": "success",
        "required_groups": [
            ["guillemets"],
            ["pronoms personnels"],
            ["adjectifs possessifs"],
            ["interrogation totale"],
            ["si"],
            ["interrogation partielle"],
            ["mot interrogatif"],
            ["impératif"],
            ["infinitif"],
            ["présent"],
            ["imparfait"],
            ["passé composé"],
            ["plus-que-parfait", "plus que parfait"],
            ["futur simple"],
            ["conditionnel présent"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": (
            "Comment fonctionne un système solaire photovoltaïque ?"
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
        "Test initial du cours : Phrase interrogative et "
        "phrase impérative au discours rapporté"
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
