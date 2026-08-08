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
EXPECTED_SOURCE = 'ecrit-5-rediger-le-synopsis-d-une-nouvelle-1.pdf'
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = 'v1-synopsis-nouvelle-baseline'

JSON_REPORT = Path('synopsis_nouvelle_test_results.json')
CSV_REPORT = Path('synopsis_nouvelle_test_results.csv')

TEST_CASES = [{'category': 'Objectif', 'endpoint': '/ask', 'question': 'Quel texte les élèves doivent-ils rédiger collectivement ?', 'expected_status': 'success', 'required_groups': [['synopsis'], ['nouvelle']]}, {'category': 'Structure', 'endpoint': '/ask', 'question': "Combien d'étapes comporte la structure narrative rappelée dans le cours ?", 'expected_status': 'success', 'required_groups': [['cinq étapes', '5 étapes']]}, {'category': 'Étape 1', 'endpoint': '/ask', 'question': 'Quelle est la première étape de la structure narrative ?', 'expected_status': 'success', 'required_groups': [['situation stable']]}, {'category': 'Étape 2', 'endpoint': '/ask', 'question': 'Quelle est la deuxième étape de la structure narrative ?', 'expected_status': 'success', 'required_groups': [['événement inattendu']]}, {'category': 'Étape 3', 'endpoint': '/ask', 'question': 'Quelle est la troisième étape de la structure narrative ?', 'expected_status': 'success', 'required_groups': [['les événements', 'événements']]}, {'category': 'Étape 4', 'endpoint': '/ask', 'question': 'Quelle est la quatrième étape de la structure narrative ?', 'expected_status': 'success', 'required_groups': [['solution']]}, {'category': 'Étape 5', 'endpoint': '/ask', 'question': 'Quelle est la dernière étape de la structure narrative ?', 'expected_status': 'success', 'required_groups': [['situation finale'], ['chute']]}, {'category': 'Ordre narratif', 'endpoint': '/ask', 'question': "Donne l'ordre complet des cinq étapes de la structure narrative.", 'expected_status': 'success', 'required_groups': [['situation stable'], ['événement inattendu'], ['événements'], ['solution'], ['situation finale'], ['chute']]}, {'category': 'Personnage principal', 'endpoint': '/ask', 'question': 'Quel type de personnage faut-il choisir pour la nouvelle ?', 'expected_status': 'success', 'required_groups': [['personnage principal']]}, {'category': 'Personnages secondaires', 'endpoint': '/ask', 'question': 'Quels autres personnages peuvent accompagner le personnage principal ?', 'expected_status': 'success', 'required_groups': [['personnages secondaires']]}, {'category': 'Production collective', 'endpoint': '/ask', 'question': 'La nouvelle doit-elle être produite individuellement ou collectivement ?', 'expected_status': 'success', 'required_groups': [['collectivement']]}, {'category': 'Tableau', 'endpoint': '/ask', 'question': 'Quel tableau faut-il compléter pour rédiger le synopsis ?', 'expected_status': 'success', 'required_groups': [['structure narrative'], ['synopsis proposé', 'synopsis']]}, {'category': 'Identité', 'endpoint': '/ask', 'question': 'Quelle première information faut-il préciser sur le personnage choisi ?', 'expected_status': 'success', 'required_groups': [['identité']]}, {'category': 'Âge', 'endpoint': '/ask', 'question': "Quelle information personnelle sur l'âge doit être indiquée ?", 'expected_status': 'success', 'required_groups': [['âge']]}, {'category': 'Métier', 'endpoint': '/ask', 'question': 'Quelle information professionnelle faut-il préciser sur le personnage ?', 'expected_status': 'success', 'required_groups': [['métier']]}, {'category': 'Statut', 'endpoint': '/ask', 'question': 'Quel statut du personnage faut-il préciser ?', 'expected_status': 'success', 'required_groups': [['statut familial'], ['social']]}, {'category': 'Traits physiques', 'endpoint': '/ask', 'question': "Quels traits liés à l'apparence faut-il préciser ?", 'expected_status': 'success', 'required_groups': [['traits physiques']]}, {'category': 'Caractère', 'endpoint': '/ask', 'question': 'Quels traits psychologiques faut-il préciser ?', 'expected_status': 'success', 'required_groups': [['traits de caractères', 'traits de caractère']]}, {'category': 'Préparation', 'endpoint': '/ask', 'question': "Qu'ont déjà dégagé les élèves avant de rédiger le synopsis ?", 'expected_status': 'success', 'required_groups': [['structure narrative'], ['cinq étapes', '5 étapes']]}, {'category': 'Personnage découvert', 'endpoint': '/ask', 'question': "Qu'ont-ils découvert au sujet du personnage principal ?", 'expected_status': 'success', 'required_groups': [['type'], ['personnage principal']]}, {'category': 'Résumé préalable', 'endpoint': '/ask', 'question': "Qu'ont-ils déjà résumé avant cette activité ?", 'expected_status': 'success', 'required_groups': [['étapes'], ['nouvelle']]}, {'category': 'Participation', 'endpoint': '/ask', 'question': "À quoi l'élève va-t-il participer ?", 'expected_status': 'success', 'required_groups': [['rédaction'], ['synopsis'], ['nouvelle']]}, {'category': 'Choix personnages', 'endpoint': '/ask', 'question': 'Que faut-il choisir avant de compléter la description des personnages ?', 'expected_status': 'success', 'required_groups': [['personnage'], ['personnages']]}, {'category': 'Évaluation 1', 'endpoint': '/ask', 'question': "Quelle première rubrique d'autoévaluation est proposée ?", 'expected_status': 'success', 'required_groups': [['je maîtrise bien']]}, {'category': 'Évaluation 2', 'endpoint': '/ask', 'question': "Quelle deuxième rubrique d'autoévaluation est proposée ?", 'expected_status': 'success', 'required_groups': [['je maîtrise peu']]}, {'category': 'Évaluation 3', 'endpoint': '/ask', 'question': "Quelle troisième rubrique d'autoévaluation est proposée ?", 'expected_status': 'success', 'required_groups': [['je ne maîtrise pas']]}, {'category': 'Synopsis définition pratique', 'endpoint': '/ask', 'question': 'À quoi sert le tableau de structure narrative dans cette activité ?', 'expected_status': 'success', 'required_groups': [['rédiger'], ['synopsis']]}, {'category': 'Erreur orthographique', 'endpoint': '/ask', 'question': 'Coman redijé le sinopsis dune nouvel avek 5 etap é dé personaj ?', 'expected_status': 'success', 'required_groups': [['synopsis'], ['cinq étapes', '5 étapes'], ['personnage principal'], ['personnages secondaires']]}, {'category': 'Résumé', 'endpoint': '/summarize', 'question': "Résume le cours sur la rédaction du synopsis d'une nouvelle.", 'expected_status': 'success', 'required_groups': [['synopsis'], ['nouvelle'], ['cinq étapes', '5 étapes'], ['situation stable'], ['événement inattendu'], ['événements'], ['solution'], ['situation finale'], ['chute'], ['personnage principal'], ['personnages secondaires'], ['âge'], ['métier'], ['statut familial'], ['traits physiques'], ['traits de caractère']]}, {'category': 'Refus correct', 'endpoint': '/ask', 'question': 'Quelle est la formule chimique du méthane ?', 'expected_status': 'insufficient_context', 'required_groups': []}]

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
    print("Test initial : Écrit 5 - Rédiger le synopsis d'une nouvelle")
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
