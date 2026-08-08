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
EXPECTED_SOURCE = 'exemples-cv-et-lettre-motivation.pdf'
NUMBER_OF_RESULTS = 5
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 2
TEST_VERSION = 'v1-cv-lettre-motivation-baseline'

JSON_REPORT = Path('cv_lettre_motivation_test_results.json')
CSV_REPORT = Path('cv_lettre_motivation_test_results.csv')

TEST_CASES = [{'category': 'Objet du document', 'endpoint': '/ask', 'question': 'Quel est le sujet général du document ?', 'expected_status': 'success', 'required_groups': [['C.V.', 'CV'], ['lettres de motivation']]}, {'category': 'Nombre cas', 'endpoint': '/ask', 'question': 'Combien de profils ou situations professionnelles sont présentés dans le sommaire ?', 'expected_status': 'success', 'required_groups': [['dix', '10']]}, {'category': 'Recherche longue', 'endpoint': '/ask', 'question': "Quel conseil est donné à une personne en recherche d'emploi depuis plus d'un an ?", 'expected_status': 'success', 'required_groups': [['dernière expérience'], ['sans indiquer de date']]}, {'category': '50 ans', 'endpoint': '/ask', 'question': "Quel conseil est donné concernant l'âge sur le CV pour une personne proche de 50 ans ou plus ?", 'expected_status': 'success', 'required_groups': [['omettre', 'omettant', 'ne pas indiquer'], ['âge']]}, {'category': '50 ans expérience', 'endpoint': '/ask', 'question': "Combien d'années récentes de vie professionnelle faut-il détailler dans ce cas ?", 'expected_status': 'success', 'required_groups': [['dix dernières années', '10 dernières années']]}, {'category': 'Bougeotte', 'endpoint': '/ask', 'question': 'Quel risque un parcours avec de nombreux emplois courts peut-il donner dans un CV ?', 'expected_status': 'success', 'required_groups': [['instabilité']]}, {'category': 'Bougeotte solution', 'endpoint': '/ask', 'question': "Comment faut-il organiser les expériences lorsqu'on a beaucoup changé d'emploi ?", 'expected_status': 'success', 'required_groups': [['grands domaines'], ['peu de dates']]}, {'category': 'Fidèle', 'endpoint': '/ask', 'question': 'Quel type de CV est conseillé à une personne ayant longtemps travaillé dans la même entreprise ?', 'expected_status': 'success', 'required_groups': [['CV fonctionnel']]}, {'category': 'Fidèle logique', 'endpoint': '/ask', 'question': 'Que met en avant le CV fonctionnel dans ce cas ?', 'expected_status': 'success', 'required_groups': [['fonctions'], ['entreprise']]}, {'category': 'Débutant', 'endpoint': '/ask', 'question': 'Que doit mettre en valeur un débutant dans son CV ?', 'expected_status': 'success', 'required_groups': [['courte expérience'], ['stages', 'petits boulots'], ['motivation'], ['projet professionnel']]}, {'category': 'Jeune sans diplôme', 'endpoint': '/ask', 'question': 'Quel atout principal est mis en avant pour un jeune sans diplôme ayant toujours travaillé ?', 'expected_status': 'success', 'required_groups': [['courageux', 'courage']]}, {'category': 'Jeune sans diplôme organisation', 'endpoint': '/ask', 'question': 'Comment faut-il présenter ses expériences si elles sont dans des secteurs différents ?', 'expected_status': 'success', 'required_groups': [["domaine d'activité", "domaines d'activité"]]}, {'category': 'Surdiplômé', 'endpoint': '/ask', 'question': "Que doit mettre en valeur le CV d'une personne surdiplômée ayant peu travaillé ?", 'expected_status': 'success', 'required_groups': [['compétences intellectuelles']]}, {'category': 'Surdiplômé pratique', 'endpoint': '/ask', 'question': 'Quelles connaissances pratiques le document conseille-t-il de souligner ?', 'expected_status': 'success', 'required_groups': [['dactylographie'], ['orthographe'], ['logiciel']]}, {'category': 'Changer métier', 'endpoint': '/ask', 'question': "Que faut-il indiquer clairement lorsqu'on a décidé de changer de métier ?", 'expected_status': 'success', 'required_groups': [['projet professionnel']]}, {'category': 'Changer métier stages', 'endpoint': '/ask', 'question': 'Que faut-il valoriser dans le nouveau métier ?', 'expected_status': 'success', 'required_groups': [['stages'], ['CDD']]}, {'category': 'Interruption enfants', 'endpoint': '/ask', 'question': 'Quel type de présentation est conseillé après une interruption pour élever ses enfants ?', 'expected_status': 'success', 'required_groups': [['présentation par compétences'], ['chronologique']]}, {'category': 'Interruption bénévolat', 'endpoint': '/ask', 'question': 'Pourquoi faut-il indiquer les activités bénévoles pendant une interruption ?', 'expected_status': 'success', 'required_groups': [['dynamisme']]}, {'category': 'Intérim', 'endpoint': '/ask', 'question': 'Quel type de CV est recommandé pour une personne ayant toujours travaillé en intérim ?', 'expected_status': 'success', 'required_groups': [['CV fonctionnel'], ["domaines d'activité"]]}, {'category': 'Intérim poste fixe', 'endpoint': '/ask', 'question': 'Où faut-il annoncer le souhait de trouver un poste fixe ?', 'expected_status': 'success', 'required_groups': [['lettre de motivation']]}, {'category': 'Jeanne Colin', 'endpoint': '/ask', 'question': "Quel métier exerce Jeanne Colin dans l'exemple ?", 'expected_status': 'success', 'required_groups': [['comptable']]}, {'category': 'Josette Carré', 'endpoint': '/ask', 'question': 'Quel est le poste de Josette Carré ?', 'expected_status': 'success', 'required_groups': [['assistante de direction trilingue']]}, {'category': 'Philippe Dumas', 'endpoint': '/ask', 'question': 'Quel domaine Philippe Dumas met-il en avant dans son profil ?', 'expected_status': 'success', 'required_groups': [['vente']]}, {'category': 'Arnaud Vanecke', 'endpoint': '/ask', 'question': 'Quel objectif professionnel Arnaud Vanecke indique-t-il ?', 'expected_status': 'success', 'required_groups': [['technicien de maintenance']]}, {'category': 'Franck Muller', 'endpoint': '/ask', 'question': 'Quel objectif professionnel Franck Muller indique-t-il ?', 'expected_status': 'success', 'required_groups': [['serveur']]}, {'category': 'Alice Jacquemain', 'endpoint': '/ask', 'question': 'Quelles deux capacités intellectuelles Alice Jacquemain met-elle en avant ?', 'expected_status': 'success', 'required_groups': [['analyse'], ['synthèse']]}, {'category': 'Daniel Kader', 'endpoint': '/ask', 'question': "Vers quel métier Daniel Kader s'est-il reconverti ?", 'expected_status': 'success', 'required_groups': [['maquettiste PAO', 'PAO'], ['graphisme']]}, {'category': 'Erreur orthographique', 'endpoint': '/ask', 'question': 'Coman adaptè un CV si on é debutan, surdiplomé, en reconversion ou intérim ?', 'expected_status': 'success', 'required_groups': [['débutant'], ['compétences intellectuelles'], ['projet professionnel'], ['CV fonctionnel']]}, {'category': 'Résumé', 'endpoint': '/summarize', 'question': 'Résume les principaux conseils du document pour adapter un CV et une lettre de motivation à différents profils.', 'expected_status': 'success', 'required_groups': [["recherche d'emploi"], ['50 ans'], ['instabilité'], ['CV fonctionnel'], ['débutant'], ['sans diplôme'], ['surdiplômé'], ['changer de métier'], ['enfants'], ['intérim'], ['lettre de motivation']]}, {'category': 'Refus correct', 'endpoint': '/ask', 'question': 'Quelle est la vitesse de la lumière dans le vide ?', 'expected_status': 'insufficient_context', 'required_groups': []}]

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
    print('Test initial : Exemples de C.V. et de lettres de motivation')
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
