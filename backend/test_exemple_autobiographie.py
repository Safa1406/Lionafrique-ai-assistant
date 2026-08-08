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
EXPECTED_SOURCE = 'exemple-d-autobiographie.pdf'
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = 'v1-exemple-autobiographie-baseline'

JSON_REPORT = Path('exemple_autobiographie_test_results.json')
CSV_REPORT = Path('exemple_autobiographie_test_results.csv')

TEST_CASES = [{'category': 'Titre', 'endpoint': '/ask', 'question': 'Quel est le titre du texte étudié ?', 'expected_status': 'success', 'required_groups': [['Le Journal de Bridget Jones']]}, {'category': 'Personnage', 'endpoint': '/ask', 'question': 'Quel est le prénom du personnage principal ?', 'expected_status': 'success', 'required_groups': [['Bridget']]}, {'category': 'Âge', 'endpoint': '/ask', 'question': 'Quel âge approximatif a Bridget ?', 'expected_status': 'success', 'required_groups': [['presque trente ans', '30 ans']]}, {'category': 'Situation matrimoniale', 'endpoint': '/ask', 'question': 'Bridget est-elle mariée ?', 'expected_status': 'success', 'required_groups': [['pas mariée', "n'est toujours pas mariée"]]}, {'category': 'Recherche', 'endpoint': '/ask', 'question': "Que cherche Bridget selon l'introduction ?", 'expected_status': 'success', 'required_groups': [['prince charmant']]}, {'category': 'Date journal', 'endpoint': '/ask', 'question': "À quelle date commence l'extrait du journal ?", 'expected_status': 'success', 'required_groups': [['dimanche 1er janvier', '1er janvier']]}, {'category': 'Poids', 'endpoint': '/ask', 'question': 'Quel poids Bridget note-t-elle au début ?', 'expected_status': 'success', 'required_groups': [['58,5 kg', '58.5 kg']]}, {'category': 'Alcool', 'endpoint': '/ask', 'question': "Combien d'unités d'alcool note-t-elle ?", 'expected_status': 'success', 'required_groups': [['14']]}, {'category': 'Cigarettes', 'endpoint': '/ask', 'question': 'Combien de cigarettes note-t-elle ?', 'expected_status': 'success', 'required_groups': [['22']]}, {'category': 'Calories', 'endpoint': '/ask', 'question': 'Combien de calories note-t-elle ?', 'expected_status': 'success', 'required_groups': [['5424']]}, {'category': 'Parents', 'endpoint': '/ask', 'question': "Où Bridget dit-elle avoir commencé l'année ?", 'expected_status': 'success', 'required_groups': [['chez mes parents', 'chez ses parents'], ['lit à une place']]}, {'category': 'État', 'endpoint': '/ask', 'question': "Comment se sent-elle lorsqu'elle arrive chez les Alconbury ?", 'expected_status': 'success', 'required_groups': [['nauséeuse'], ['mauvais poil'], ['tête comme un tambour']]}, {'category': 'Autoroute', 'endpoint': '/ask', 'question': "Quelle erreur de trajet l'a mise en colère ?", 'expected_status': 'success', 'required_groups': [["ratant la sortie d'Autoroute", 'raté la sortie'], ['Birmingham']]}, {'category': 'Una', 'endpoint': '/ask', 'question': 'Qui accueille Bridget à son arrivée ?', 'expected_status': 'success', 'required_groups': [['Una Alconbury']]}, {'category': 'Petit copain', 'endpoint': '/ask', 'question': 'Quelle question Oncle Geoffray lui pose-t-il ?', 'expected_status': 'success', 'required_groups': [['petit copain']]}, {'category': 'Père', 'endpoint': '/ask', 'question': 'Qui vient au secours de Bridget pendant la scène ?', 'expected_status': 'success', 'required_groups': [['père']]}, {'category': 'Mark Darcy', 'endpoint': '/ask', 'question': 'Quel homme la mère de Bridget veut-elle lui faire rencontrer ?', 'expected_status': 'success', 'required_groups': [['Mark Darcy']]}, {'category': 'Profession Mark', 'endpoint': '/ask', 'question': 'Quelle profession Mark Darcy exerce-t-il ?', 'expected_status': 'success', 'required_groups': [['avocat']]}, {'category': 'Auteur', 'endpoint': '/ask', 'question': "Qui est l'auteur indiqué à la fin de l'extrait ?", 'expected_status': 'success', 'required_groups': [['Helène Fielding', 'Helen Fielding', 'Fielding']]}, {'category': 'Point de vue', 'endpoint': '/ask', 'question': 'Quel point de vue narratif domine dans le journal ?', 'expected_status': 'success', 'required_groups': [['première personne', 'je']]}, {'category': 'Journal intime définition', 'endpoint': '/ask', 'question': 'Comment le document définit-il le journal intime ?', 'expected_status': 'success', 'required_groups': [['jour le jour'], ['commentaires personnels']]}, {'category': 'Destinataire journal', 'endpoint': '/ask', 'question': 'Quel est normalement le destinataire du journal intime ?', 'expected_status': 'success', 'required_groups': [['auteur lui-même', 'auteur']]}, {'category': 'Diariste', 'endpoint': '/ask', 'question': "Comment appelle-t-on l'écrivain qui tient un journal intime ?", 'expected_status': 'success', 'required_groups': [['diariste']]}, {'category': 'Correspondance', 'endpoint': '/ask', 'question': 'Quel est le but premier de la correspondance entre deux personnes selon le document ?', 'expected_status': 'success', 'required_groups': [["pas pour but premier d'être publiée", "pas d'abord publiée", 'pas pour but premier d être publiée']]}, {'category': 'Roman personnel', 'endpoint': '/ask', 'question': "Que mélange l'autobiographie romancée ?", 'expected_status': 'success', 'required_groups': [['événements réels'], ['fictifs']]}, {'category': 'Mémoires', 'endpoint': '/ask', 'question': 'Sur quoi les mémoires apportent-ils un témoignage ?', 'expected_status': 'success', 'required_groups': [['époque'], ['hommes'], ['événements']]}, {'category': 'Biographie', 'endpoint': '/ask', 'question': "Qu'est-ce qu'une biographie selon le document ?", 'expected_status': 'success', 'required_groups': [['récit de la vie'], ['personne'], ["quelqu'un d'extérieur", 'extérieur']]}, {'category': 'Erreur orthographique', 'endpoint': '/ask', 'question': 'Keské un jurnal intim, un diarist é une biografi ?', 'expected_status': 'success', 'required_groups': [['journal intime'], ['diariste'], ['biographie']]}, {'category': 'Résumé', 'endpoint': '/summarize', 'question': "Résume le document sur Bridget Jones et les genres proches de l'autobiographie.", 'expected_status': 'success', 'required_groups': [['Bridget Jones'], ['journal intime'], ['première personne', 'je'], ['diariste'], ['correspondance'], ['roman personnel', 'autobiographie romancée'], ['mémoires'], ['biographie'], ['journaux en ligne']]}, {'category': 'Refus correct', 'endpoint': '/ask', 'question': 'Comment résoudre une équation du second degré ?', 'expected_status': 'insufficient_context', 'required_groups': []}]

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
    print("Test initial : Exemple d'autobiographie / Journal de Bridget Jones")
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
