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
EXPECTED_SOURCE = 'ecrit-4-2-rediger-une-lettre-ouverte-projet-2.pdf'
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = 'v1-lettre-ouverte-projet-baseline'

JSON_REPORT = Path('lettre_ouverte_projet_test_results.json')
CSV_REPORT = Path('lettre_ouverte_projet_test_results.csv')

TEST_CASES = [{'category': 'Type de projet', 'endpoint': '/ask', 'question': 'Quel type de texte doit être rédigé dans ce projet ?', 'expected_status': 'success', 'required_groups': [['lettre ouverte']]}, {'category': 'Cadre', 'endpoint': '/ask', 'question': 'Dans quel cadre la lettre ouverte doit-elle être rédigée ?', 'expected_status': 'success', 'required_groups': [["club de l'environnement"], ['établissement']]}, {'category': 'But', 'endpoint': '/ask', 'question': 'Quel est le but principal de la lettre ouverte ?', 'expected_status': 'success', 'required_groups': [['sensibiliser'], ['opinion publique']]}, {'category': 'Thème général', 'endpoint': '/ask', 'question': "À quelle question générale la lettre doit-elle sensibiliser l'opinion publique ?", 'expected_status': 'success', 'required_groups': [['environnement']]}, {'category': 'Espace concerné', 'endpoint': '/ask', 'question': "À quel espace géographique la question de l'environnement est-elle liée ?", 'expected_status': 'success', 'required_groups': [['région']]}, {'category': 'Choix du thème', 'endpoint': '/ask', 'question': 'Qui choisit le thème de la lettre ouverte ?', 'expected_status': 'success', 'required_groups': [['vous', 'élève', 'groupe']]}, {'category': 'Critère du thème', 'endpoint': '/ask', 'question': 'Quel critère doit respecter le thème choisi ?', 'expected_status': 'success', 'required_groups': [["beaucoup d'intérêt", 'intérêt'], ['population']]}, {'category': 'Population', 'endpoint': '/ask', 'question': "Pour qui le thème choisi doit-il présenter beaucoup d'intérêt ?", 'expected_status': 'success', 'required_groups': [['population'], ['région']]}, {'category': 'Projet établissement', 'endpoint': '/ask', 'question': "À quel club de l'établissement le projet est-il lié ?", 'expected_status': 'success', 'required_groups': [["club de l'environnement"]]}, {'category': 'Destinataire public', 'endpoint': '/ask', 'question': "La lettre ouverte vise-t-elle une personne précise ou l'opinion publique ?", 'expected_status': 'success', 'required_groups': [['opinion publique']]}, {'category': 'Mission', 'endpoint': '/ask', 'question': "Que doit faire la lettre ouverte vis-à-vis de l'opinion publique ?", 'expected_status': 'success', 'required_groups': [['sensibiliser']]}, {'category': 'Sujet local', 'endpoint': '/ask', 'question': "La question environnementale est-elle traitée à l'échelle de la région ?", 'expected_status': 'success', 'required_groups': [['région']]}, {'category': 'Thème pertinent', 'endpoint': '/ask', 'question': "Le thème peut-il être choisi sans tenir compte de l'intérêt de la population ?", 'expected_status': 'success', 'required_groups': [['intérêt'], ['population']]}, {'category': 'Production collective', 'endpoint': '/ask', 'question': "Que doit faire l'élève avec la lettre rédigée par son groupe ?", 'expected_status': 'success', 'required_groups': [['recopie', 'recopier'], ['lettre'], ['groupe']]}, {'category': 'Groupe', 'endpoint': '/ask', 'question': 'La lettre finale est-elle liée à un travail individuel isolé ou à un travail de groupe ?', 'expected_status': 'success', 'required_groups': [['groupe']]}, {'category': 'Club environnement', 'endpoint': '/ask', 'question': 'Quel domaine représente le club mentionné dans le projet ?', 'expected_status': 'success', 'required_groups': [['environnement']]}, {'category': 'Lettre ouverte locale', 'endpoint': '/ask', 'question': "Quel lien la lettre ouverte doit-elle établir entre l'environnement et la région ?", 'expected_status': 'success', 'required_groups': [['environnement'], ['région']]}, {'category': 'Public cible', 'endpoint': '/ask', 'question': 'Quel public doit être sensibilisé par la lettre ?', 'expected_status': 'success', 'required_groups': [['opinion publique']]}, {'category': 'Choix sujet', 'endpoint': '/ask', 'question': "Que doit choisir l'élève avant de rédiger la lettre ouverte ?", 'expected_status': 'success', 'required_groups': [['thème']]}, {'category': 'Intérêt régional', 'endpoint': '/ask', 'question': 'Pourquoi le thème choisi doit-il être important ?', 'expected_status': 'success', 'required_groups': [['intérêt'], ['population'], ['région']]}, {'category': 'Nature activité', 'endpoint': '/ask', 'question': 'Le document présente-t-il une compréhension, une production guidée ou un projet ?', 'expected_status': 'success', 'required_groups': [['projet']]}, {'category': 'Établissement', 'endpoint': '/ask', 'question': "Où se situe le club de l'environnement mentionné ?", 'expected_status': 'success', 'required_groups': [['établissement']]}, {'category': 'Objectif civique', 'endpoint': '/ask', 'question': 'Quelle action de communication est demandée envers le public ?', 'expected_status': 'success', 'required_groups': [['sensibiliser'], ['opinion publique']]}, {'category': 'Choix pertinent', 'endpoint': '/ask', 'question': 'Sur quoi doit se baser le choix du thème ?', 'expected_status': 'success', 'required_groups': [['intérêt'], ['population']]}, {'category': 'Travail final', 'endpoint': '/ask', 'question': "Quel texte l'élève doit-il recopier à la fin ?", 'expected_status': 'success', 'required_groups': [['lettre'], ['groupe']]}, {'category': 'Synthèse', 'endpoint': '/ask', 'question': 'Quels sont les trois éléments essentiels du projet ?', 'expected_status': 'success', 'required_groups': [['lettre ouverte'], ['opinion publique'], ['environnement'], ['région']]}, {'category': 'Paraphrase', 'endpoint': '/ask', 'question': 'Explique brièvement ce que demande le projet Écrit 4-2.', 'expected_status': 'success', 'required_groups': [['lettre ouverte'], ['sensibiliser'], ['opinion publique'], ['environnement']]}, {'category': 'Erreur orthographique', 'endpoint': '/ask', 'question': 'Coman redijé une letr ouver pour sansibilizé lopinion publik a lenvironeman dan la rejion ?', 'expected_status': 'success', 'required_groups': [['lettre ouverte'], ['sensibiliser'], ['opinion publique'], ['environnement'], ['région']]}, {'category': 'Résumé', 'endpoint': '/summarize', 'question': "Résume le projet de rédaction d'une lettre ouverte.", 'expected_status': 'success', 'required_groups': [['lettre ouverte'], ["club de l'environnement"], ['sensibiliser'], ['opinion publique'], ['environnement'], ['région'], ['thème'], ['population'], ['groupe']]}, {'category': 'Refus correct', 'endpoint': '/ask', 'question': "Comment calcule-t-on la pression d'un gaz parfait ?", 'expected_status': 'insufficient_context', 'required_groups': []}]

def configure_console():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

def normalize_text(text):
    normalized = unicodedata.normalize("NFKD", (text or "").lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = re.sub(r"[^\w\s'-]", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()

def make_request(endpoint, question):
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
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code == 503 and attempt < MAX_ATTEMPTS:
                print("HTTP 503 : nouvelle tentative dans 2 secondes...")
                time.sleep(2)
                continue
            raise
        except urllib.error.URLError as error:
            last_error = error
            if attempt < MAX_ATTEMPTS:
                print("Connexion indisponible : nouvelle tentative dans 2 secondes...")
                time.sleep(2)
                continue
            raise
    raise last_error

def extract_response_text(endpoint, response_data):
    if endpoint == "/summarize":
        return response_data.get("summary", "")
    return response_data.get("answer", "")

def source_is_correct(sources):
    return bool(sources) and all(
        source.get("file", "") == EXPECTED_SOURCE for source in sources
    )

def find_missing_groups(response_text, required_groups):
    normalized_response = normalize_text(response_text)
    missing = []
    for group in required_groups:
        alternatives = [normalize_text(term) for term in group]
        if not any(term and term in normalized_response for term in alternatives):
            missing.append(group)
    return missing

def format_sources(sources):
    return " ; ".join(
        f"{s.get('file','source inconnue')} | page {s.get('page','?')}"
        for s in sources
    )

def main():
    configure_console()
    print("=" * 100)
    print('Test initial : Écrit 4-2 - Rédiger une lettre ouverte (Projet)')
    print("=" * 100)
    print("Version du test:", TEST_VERSION)
    print("Nombre de tests:", len(TEST_CASES))
    print("Source attendue:", EXPECTED_SOURCE)

    results = []
    passed_count = 0

    for index, tc in enumerate(TEST_CASES, 1):
        print("\n" + "-" * 100)
        print(f"[{index}/{len(TEST_CASES)}] [{tc['category']}]")
        print("Question:", tc["question"])

        started = time.perf_counter()
        actual_status = ""
        response_text = ""
        sources = []
        error_text = ""

        try:
            data = make_request(tc["endpoint"], tc["question"])
            actual_status = data.get("status", "")
            response_text = extract_response_text(tc["endpoint"], data)
            sources = data.get("sources") or []
        except Exception as error:
            error_text = str(error)

        duration = round(time.perf_counter() - started, 3)
        missing = find_missing_groups(response_text, tc["required_groups"])
        requires_source = tc["expected_status"] == "success"
        correct_source = source_is_correct(sources) if requires_source else True

        passed = (
            not error_text
            and actual_status == tc["expected_status"]
            and not missing
            and correct_source
        )
        passed_count += int(passed)

        print("Statut attendu:", tc["expected_status"])
        print("Statut obtenu:", actual_status or "absent")
        print("Durée:", duration, "seconde(s)")
        if response_text:
            print("\nRéponse:\n" + response_text)
        if sources:
            print("\nSources:", format_sources(sources))
        if missing:
            print("\nConcepts manquants:", missing)
        if requires_source and not correct_source:
            print("\nLa source attendue est absente.")
        if error_text:
            print("\nErreur:", error_text)
        print("\nRésultat:", "RÉUSSI ✅" if passed else "ÉCHEC ❌")

        results.append({
            "number": index,
            "category": tc["category"],
            "endpoint": tc["endpoint"],
            "question": tc["question"],
            "expected_status": tc["expected_status"],
            "actual_status": actual_status,
            "test_passed": "oui" if passed else "non",
            "duration_seconds": duration,
            "response": response_text,
            "missing_groups": json.dumps(missing, ensure_ascii=False),
            "correct_source": "oui" if correct_source else "non",
            "sources": format_sources(sources),
            "error": error_text,
        })

    failed_count = len(TEST_CASES) - passed_count
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "test_version": TEST_VERSION,
        "program": PROGRAM,
        "subject": SUBJECT,
        "source": EXPECTED_SOURCE,
        "total_tests": len(TEST_CASES),
        "passed_tests": passed_count,
        "failed_tests": failed_count,
        "results": results,
    }

    JSON_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with CSV_REPORT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print("\n" + "=" * 100)
    print("RÉSULTAT FINAL")
    print("=" * 100)
    print("Réussis:", passed_count)
    print("Échoués:", failed_count)
    print("Total:", len(TEST_CASES))
    print("JSON:", JSON_REPORT.resolve())
    print("CSV:", CSV_REPORT.resolve())

if __name__ == "__main__":
    main()
