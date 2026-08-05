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
EXPECTED_SOURCE = "1-la-typologie-des-reseaux.pdf"
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
TEST_VERSION = "v1-network-typology-baseline"

JSON_REPORT = Path("typologie_reseaux_test_results.json")
CSV_REPORT = Path("typologie_reseaux_test_results.csv")

TEST_CASES = [
    {
        "category": "Définition du réseau",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un réseau selon le document ?",
        "expected_status": "success",
        "required_groups": [
            ["ensemble"],
            ["entités", "objets"],
            ["reliés entre eux"],
        ],
    },
    {
        "category": "Réseau informatique",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un réseau informatique ?",
        "expected_status": "success",
        "required_groups": [
            ["ensemble d'ordinateurs", "ensemble des ordinateurs"],
            ["matériels informatiques", "matériel informatique"],
            ["reliés entre eux"],
        ],
    },
    {
        "category": "Types de réseaux",
        "endpoint": "/ask",
        "question": "Quels sont les trois types de réseaux mentionnés dans le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["LAN"],
            ["MAN"],
            ["WAN"],
        ],
    },
    {
        "category": "Définition LAN",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un réseau LAN ?",
        "expected_status": "success",
        "required_groups": [
            ["réseau local"],
            ["Local Area Network"],
        ],
    },
    {
        "category": "Échelle LAN",
        "endpoint": "/ask",
        "question": "À quelle échelle fonctionne un réseau LAN ?",
        "expected_status": "success",
        "required_groups": [
            ["salle"],
            ["bâtiment"],
            ["entreprise"],
        ],
    },
    {
        "category": "Utilités LAN",
        "endpoint": "/ask",
        "question": "Que peut-on faire avec un réseau local ?",
        "expected_status": "success",
        "required_groups": [
            ["communiquer"],
            ["échanger des informations"],
            ["partager des ressources informatiques", "partager les ressources informatiques"],
        ],
    },
    {
        "category": "Définition MAN",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un réseau MAN ?",
        "expected_status": "success",
        "required_groups": [
            ["réseau régional"],
            ["Metropolitan Area Network"],
        ],
    },
    {
        "category": "Échelle MAN",
        "endpoint": "/ask",
        "question": "À quelle échelle fonctionne un réseau MAN ?",
        "expected_status": "success",
        "required_groups": [
            ["réseaux LAN", "réseau LAN"],
            ["ville"],
            ["région"],
        ],
    },
    {
        "category": "Définition WAN",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un réseau WAN ?",
        "expected_status": "success",
        "required_groups": [
            ["réseau international"],
            ["Wide Area Network"],
        ],
    },
    {
        "category": "Échelle WAN",
        "endpoint": "/ask",
        "question": "À quelle échelle fonctionne un réseau WAN ?",
        "expected_status": "success",
        "required_groups": [
            ["réseaux LAN", "réseau LAN"],
            ["MAN"],
            ["pays"],
            ["planète"],
        ],
    },
    {
        "category": "WAN et Internet",
        "endpoint": "/ask",
        "question": "Comment le réseau WAN est-il aussi appelé dans le document ?",
        "expected_status": "success",
        "required_groups": [
            ["réseau international"],
            ["Internet"],
            ["International network"],
        ],
    },
    {
        "category": "Connexion WAN",
        "endpoint": "/ask",
        "question": "Que faut-il faire pour relier un ordinateur au réseau WAN ou à Internet ?",
        "expected_status": "success",
        "required_groups": [
            ["brancher l'ordinateur", "relier l'ordinateur"],
            ["modem"],
            ["routeur"],
        ],
    },
    {
        "category": "Comparaison des réseaux",
        "endpoint": "/ask",
        "question": "Compare les réseaux LAN, MAN et WAN selon leur étendue.",
        "expected_status": "success",
        "required_groups": [
            ["LAN"],
            ["local", "salle", "bâtiment", "entreprise"],
            ["MAN"],
            ["ville", "région"],
            ["WAN"],
            ["pays", "planète", "international"],
        ],
    },
    {
        "category": "Définition modem",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un modem ?",
        "expected_status": "success",
        "required_groups": [
            ["dispositif"],
            ["liaison"],
            ["PC", "ordinateur"],
            ["réseau Internet", "Internet"],
        ],
    },
    {
        "category": "Signification modem",
        "endpoint": "/ask",
        "question": "Que signifie le mot modem ?",
        "expected_status": "success",
        "required_groups": [
            ["modulateur"],
            ["démodulateur"],
        ],
    },
    {
        "category": "Rôle modem",
        "endpoint": "/ask",
        "question": "Quel est le rôle du modem dans l'échange des informations ?",
        "expected_status": "success",
        "required_groups": [
            ["échange d'informations", "échanger des informations"],
            ["grand nombre d'ordinateurs", "plusieurs ordinateurs"],
            ["lignes téléphoniques"],
        ],
    },
    {
        "category": "Définition routeur",
        "endpoint": "/ask",
        "question": "Qu'est-ce qu'un routeur ?",
        "expected_status": "success",
        "required_groups": [
            ["appareil"],
            ["envoyer les informations"],
            ["bons endroits"],
        ],
    },
    {
        "category": "Fonction routeur",
        "endpoint": "/ask",
        "question": "Quelle est la fonction principale d'un routeur ?",
        "expected_status": "success",
        "required_groups": [
            ["envoyer", "acheminer"],
            ["informations"],
            ["bons endroits", "bonne destination"],
        ],
    },
    {
        "category": "Routeur et Wi-Fi",
        "endpoint": "/ask",
        "question": "Un routeur peut-il jouer le rôle d'un modem en Wi-Fi ?",
        "expected_status": "success",
        "required_groups": [
            ["oui"],
            ["routeur"],
            ["rôle d'un modem", "rôle de modem"],
            ["Wi-Fi", "Wifi"],
        ],
    },
    {
        "category": "Modem et routeur",
        "endpoint": "/ask",
        "question": "Quelle est la différence entre le modem et le routeur selon le cours ?",
        "expected_status": "success",
        "required_groups": [
            ["modem"],
            ["liaison", "Internet"],
            ["routeur"],
            ["envoyer les informations", "bons endroits", "acheminer"],
        ],
    },
    {
        "category": "Identification LAN",
        "endpoint": "/ask",
        "question": "Quel type de réseau relie des ordinateurs dans une salle, un bâtiment ou une entreprise ?",
        "expected_status": "success",
        "required_groups": [
            ["LAN"],
            ["réseau local"],
        ],
    },
    {
        "category": "Identification MAN",
        "endpoint": "/ask",
        "question": "Quel type de réseau regroupe des réseaux LAN à l'échelle d'une ville ou d'une région ?",
        "expected_status": "success",
        "required_groups": [
            ["MAN"],
            ["réseau régional"],
        ],
    },
    {
        "category": "Identification WAN",
        "endpoint": "/ask",
        "question": "Quel type de réseau regroupe les réseaux LAN et MAN au niveau d'un pays ou de la planète ?",
        "expected_status": "success",
        "required_groups": [
            ["WAN"],
            ["réseau international"],
        ],
    },
    {
        "category": "Hiérarchie MAN",
        "endpoint": "/ask",
        "question": "Quels réseaux sont regroupés par un réseau MAN ?",
        "expected_status": "success",
        "required_groups": [
            ["réseaux LAN", "LAN"],
        ],
    },
    {
        "category": "Hiérarchie WAN",
        "endpoint": "/ask",
        "question": "Quels réseaux sont regroupés par un réseau WAN ?",
        "expected_status": "success",
        "required_groups": [
            ["LAN"],
            ["MAN"],
        ],
    },
    {
        "category": "Explication courte",
        "endpoint": "/ask",
        "question": "Explique brièvement la typologie des réseaux.",
        "expected_status": "success",
        "required_groups": [
            ["LAN"],
            ["MAN"],
            ["WAN"],
            ["local"],
            ["régional"],
            ["international"],
        ],
    },
    {
        "category": "Erreur orthographique",
        "endpoint": "/ask",
        "question": "Quels sont les types de réseaus informatiques et leurs echelles ?",
        "expected_status": "success",
        "required_groups": [
            ["LAN"],
            ["MAN"],
            ["WAN"],
            ["salle", "bâtiment", "entreprise"],
            ["ville", "région"],
            ["pays", "planète"],
        ],
    },
    {
        "category": "Résumé général",
        "endpoint": "/summarize",
        "question": "Résume le cours sur la typologie des réseaux.",
        "expected_status": "success",
        "required_groups": [
            ["réseau informatique"],
            ["LAN"],
            ["Local Area Network"],
            ["MAN"],
            ["Metropolitan Area Network"],
            ["WAN"],
            ["Wide Area Network"],
            ["modem"],
            ["routeur"],
        ],
    },
    {
        "category": "Résumé modem-routeur",
        "endpoint": "/summarize",
        "question": "Résume la partie du cours consacrée au modem et au routeur.",
        "expected_status": "success",
        "required_groups": [
            ["modem"],
            ["modulateur", "démodulateur"],
            ["liaison", "Internet"],
            ["routeur"],
            ["envoyer les informations", "bons endroits"],
            ["Wi-Fi", "Wifi"],
        ],
    },
    {
        "category": "Refus correct",
        "endpoint": "/ask",
        "question": "Quelle est la capitale du Brésil ?",
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
            f" | page "
            f"{source.get('page', '?')}"
        )
        for source in sources
    )


def main() -> None:
    configure_console()

    print("=" * 100)
    print("Test initial du cours : La typologie des réseaux")
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
                endpoint=endpoint,
                question=question,
            )
            actual_status = response_data.get(
                "status",
                "",
            )
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
            error_text = (
                "Erreur inattendue : "
                f"{error}"
            )

        duration = round(
            time.perf_counter() - started_at,
            3,
        )

        missing_groups = find_missing_groups(
            response_text=response_text,
            required_groups=test_case[
                "required_groups"
            ],
        )

        requires_source = (
            expected_status == "success"
        )

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
            f"{summary['passed']}/"
            f"{summary['total']}"
        )

    print()
    print("Rapports enregistrés:")
    print(JSON_REPORT.resolve())
    print(CSV_REPORT.resolve())


if __name__ == "__main__":
    main()
