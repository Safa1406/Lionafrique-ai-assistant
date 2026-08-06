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
EXPECTED_SOURCE = "la-coordination.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = "v1-coordination-baseline"

JSON_REPORT = Path("coordination_test_results.json")
CSV_REPORT = Path("coordination_test_results.csv")

TEST_CASES = [
    {
        "category": "Définition",
        "endpoint": "/ask",
        "question": "En quoi consiste la coordination ?",
        "expected_status": "success",
        "required_groups": [
            ["joindre", "relier"],
            ["mots", "groupes de mots"],
            ["même classe grammaticale"],
        ],
    },
    {
        "category": "Classes grammaticales",
        "endpoint": "/ask",
        "question": (
            "Quelles classes grammaticales peuvent être reliées "
            "par la coordination selon le cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["noms"],
            ["adjectifs"],
            ["verbes"],
            ["propositions"],
        ],
    },
    {
        "category": "Exemple et",
        "endpoint": "/ask",
        "question": (
            "Dans « J'aime mon père et ma mère », "
            "quel mot assure la coordination ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["et"],
            ["coordination"],
        ],
    },
    {
        "category": "Exemple mais",
        "endpoint": "/ask",
        "question": (
            "Dans « Il pensait à lui mais il ne voulait pas "
            "le voir », quelle conjonction relie les deux propositions ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["mais"],
            ["conjonction"],
        ],
    },
    {
        "category": "Moyens",
        "endpoint": "/ask",
        "question": (
            "Quels sont les trois types de moyens qui assurent "
            "la coordination ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["conjonctions de coordination"],
            ["adverbes de liaison"],
            ["expressions"],
        ],
    },
    {
        "category": "Conjonctions",
        "endpoint": "/ask",
        "question": (
            "Quelles sont les conjonctions de coordination "
            "citées dans le cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["mais"],
            ["ou"],
            ["et"],
            ["donc"],
            ["or"],
            ["ni"],
            ["car"],
        ],
    },
    {
        "category": "Adverbes",
        "endpoint": "/ask",
        "question": (
            "Quels adverbes de liaison sont donnés comme exemples ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["ainsi"],
            ["aussi"],
            ["alors"],
            ["puis"],
            ["ensuite"],
            ["enfin"],
        ],
    },
    {
        "category": "Expressions",
        "endpoint": "/ask",
        "question": (
            "Quelles expressions peuvent assurer la coordination "
            "selon le cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["à savoir"],
            ["au contraire"],
            ["en effet"],
            ["c'est pourquoi"],
        ],
    },
    {
        "category": "Sens mais",
        "endpoint": "/ask",
        "question": (
            "Quels sens proches la conjonction « mais » peut-elle avoir ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["pourtant"],
            ["toutefois"],
            ["au contraire"],
        ],
    },
    {
        "category": "Nuances mais",
        "endpoint": "/ask",
        "question": (
            "Quelles nuances la conjonction « mais » peut-elle marquer ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["opposition"],
            ["différence"],
            ["restriction"],
        ],
    },
    {
        "category": "Exemple mais",
        "endpoint": "/ask",
        "question": (
            "Dans « Paul est gentil, mais un peu agité », "
            "quelle nuance exprime « mais » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["opposition", "restriction", "différence"],
            ["mais"],
        ],
    },
    {
        "category": "Sens ou",
        "endpoint": "/ask",
        "question": (
            "Que sert à présenter la conjonction « ou » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["alternative"],
            ["choix"],
            ["ou bien"],
        ],
    },
    {
        "category": "Exemple ou",
        "endpoint": "/ask",
        "question": (
            "Dans « Veux-tu du thé ou du café ? », "
            "quelle relation exprime « ou » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["alternative", "choix"],
            ["thé"],
            ["café"],
        ],
    },
    {
        "category": "Valeurs et",
        "endpoint": "/ask",
        "question": (
            "Quelles valeurs la conjonction « et » peut-elle exprimer ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["énumération"],
            ["addition"],
            ["succession"],
            ["temps"],
        ],
    },
    {
        "category": "Exemple énumération",
        "endpoint": "/ask",
        "question": (
            "Dans la phrase de Bob avec les livres, les vêtements "
            "et les jouets, quelle valeur de « et » est illustrée ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["énumération", "addition"],
            ["livres"],
            ["vêtements"],
            ["jouets"],
        ],
    },
    {
        "category": "Sens donc",
        "endpoint": "/ask",
        "question": (
            "Quelle relation logique la conjonction « donc » exprime-t-elle ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["conséquence"],
        ],
    },
    {
        "category": "Donc et car",
        "endpoint": "/ask",
        "question": (
            "Selon le cours, quelle relation existe entre « donc » et « car » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["contraire"],
            ["donc"],
            ["car"],
        ],
    },
    {
        "category": "Exemple donc",
        "endpoint": "/ask",
        "question": (
            "Dans « Mon ami ne se sent pas bien, donc il n'ira pas "
            "au cinéma », quelle conséquence est exprimée ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["il n'ira pas au cinéma"],
            ["conséquence"],
        ],
    },
    {
        "category": "Sens car",
        "endpoint": "/ask",
        "question": (
            "Quelle relation logique la conjonction « car » exprime-t-elle ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["cause"],
            ["parce que"],
        ],
    },
    {
        "category": "Exemple car",
        "endpoint": "/ask",
        "question": (
            "Dans « Mon frère passera un très bel été, car il a réussi "
            "son année », quelle cause est donnée ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["il a réussi son année"],
            ["cause"],
        ],
    },
    {
        "category": "Valeur ni",
        "endpoint": "/ask",
        "question": (
            "Dans quel type de contexte emploie-t-on la conjonction « ni » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["contexte négatif"],
        ],
    },
    {
        "category": "Comparaison ni",
        "endpoint": "/ask",
        "question": (
            "À quelles conjonctions la valeur de « ni » est-elle similaire ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["et"],
            ["ou"],
        ],
    },
    {
        "category": "Virgule ni",
        "endpoint": "/ask",
        "question": (
            "Quand met-on une virgule devant « ni » selon la remarque du cours ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["plus d'un élément", "plusieurs éléments"],
            ["virgule"],
        ],
    },
    {
        "category": "Exemple ni",
        "endpoint": "/ask",
        "question": (
            "Quels éléments sont coordonnés par « ni » dans "
            "« Il ne craint ni la pluie, ni le froid, ni la neige » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["pluie"],
            ["froid"],
            ["neige"],
        ],
    },
    {
        "category": "Sens or",
        "endpoint": "/ask",
        "question": (
            "Que fait la conjonction « or » dans un contexte ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["nouvelle donnée"],
            ["décisive"],
            ["contexte"],
        ],
    },
    {
        "category": "Exemple or",
        "endpoint": "/ask",
        "question": (
            "Dans la phrase du Petit Chaperon Rouge, "
            "quelle nouvelle donnée introduit « or » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["le loup rôdait", "loup rôdait"],
            ["nouvelle donnée"],
        ],
    },
    {
        "category": "Mais et or",
        "endpoint": "/ask",
        "question": (
            "Quelle différence le cours établit-il entre « mais » et « or » ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["mais"],
            ["opposition"],
            ["or"],
            ["nouvelle donnée"],
            ["décisive"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": (
            "Comant la coordinasion reli des mots et quelle sont les "
            "valeurs de mais ou et donc car ni et or ?"
        ),
        "expected_status": "success",
        "required_groups": [
            ["relier", "joindre"],
            ["mais"],
            ["ou"],
            ["et"],
            ["donc"],
            ["car"],
            ["ni"],
            ["or"],
        ],
    },
    {
        "category": "Résumé",
        "endpoint": "/summarize",
        "question": (
            "Résume le cours sur la coordination et les différentes "
            "nuances exprimées par ses conjonctions."
        ),
        "expected_status": "success",
        "required_groups": [
            ["même classe grammaticale"],
            ["conjonctions de coordination"],
            ["adverbes de liaison"],
            ["mais"],
            ["ou"],
            ["et"],
            ["donc"],
            ["car"],
            ["ni"],
            ["or"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": "Comment fonctionne une centrale nucléaire ?",
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
    print("Test initial du cours : La coordination")
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
