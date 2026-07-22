import sys
import time
import unicodedata

from services.llm_service import generate_answer
from services.retrieval_service import (
    retrieve_relevant_passages,
)


TEST_CASES = [
    {
        "name": "Rôles des aliments en SVT",
        "question": (
            "Quels sont les rôles des aliments ?"
        ),
        "program": "Programme marocain",
        "subject": "SVT",
        "semester": "S1",
        "expected_answerable": True,
        "expected_evidence_terms": [
            "batiseurs",
            "energetiques",
            "protecteurs",
        ],
    },
    {
        "name": "Définition de la guerre de mouvement",
        "question": (
            "Qu'est-ce qu'une guerre de mouvement ?"
        ),
        "program": "Programme français",
        "subject": "Histoire-Géographie",
        "semester": None,
        "expected_answerable": True,
        "expected_evidence_terms": [
            "offensives",
            "front",
            "mobile",
        ],
    },
    {
        "name": "Question de mathématiques dans SVT",
        "question": (
            "Qu'est-ce que le théorème de Pythagore ?"
        ),
        "program": "Programme marocain",
        "subject": "SVT",
        "semester": "S1",
        "expected_answerable": False,
        "expected_evidence_terms": [],
    },
]


def normalize_text(text: str) -> str:
    """
    Normalise un texte pour faciliter les comparaisons.
    """

    normalized_text = unicodedata.normalize(
        "NFKD",
        text.lower(),
    )

    normalized_text = "".join(
        character
        for character in normalized_text
        if not unicodedata.combining(character)
    )

    return " ".join(
        normalized_text.split()
    )


def display_separator() -> None:
    """
    Affiche un séparateur entre les tests.
    """

    print(
        "\n"
        + "=" * 70
    )


def validate_passage_filters(
    passages: list[dict],
    program: str,
    subject: str,
    semester: str | None,
) -> list[str]:
    """
    Vérifie que les passages respectent
    les filtres pédagogiques demandés.
    """

    errors = []

    for index, passage in enumerate(
        passages,
        start=1,
    ):
        passage_program = passage.get(
            "program"
        )

        passage_subject = passage.get(
            "subject"
        )

        passage_semester = passage.get(
            "semester"
        )

        if passage_program != program:
            errors.append(
                (
                    f"Le passage {index} appartient au programme "
                    f"« {passage_program} » au lieu de "
                    f"« {program} »."
                )
            )

        if passage_subject != subject:
            errors.append(
                (
                    f"Le passage {index} appartient à la matière "
                    f"« {passage_subject} » au lieu de "
                    f"« {subject} »."
                )
            )

        if (
            semester is not None
            and passage_semester != semester
        ):
            errors.append(
                (
                    f"Le passage {index} appartient au semestre "
                    f"« {passage_semester} » au lieu de "
                    f"« {semester} »."
                )
            )

    return errors


def validate_expected_evidence(
    evidence: list[str],
    expected_terms: list[str],
) -> list[str]:
    """
    Vérifie que les preuves contiennent
    les termes importants attendus.
    """

    if not expected_terms:
        return []

    combined_evidence = normalize_text(
        " ".join(evidence)
    )

    missing_terms = []

    for term in expected_terms:
        normalized_term = normalize_text(
            term
        )

        if normalized_term not in combined_evidence:
            missing_terms.append(
                term
            )

    return missing_terms


def run_test(
    test_case: dict,
) -> dict:
    """
    Exécute un test complet de recherche
    et de génération documentaire.
    """

    start_time = time.perf_counter()

    question = test_case["question"]
    program = test_case["program"]
    subject = test_case["subject"]
    semester = test_case["semester"]

    print(
        f"Test : {test_case['name']}"
    )

    print(
        f"Question : {question}"
    )

    print(
        f"Programme : {program}"
    )

    print(
        f"Matière : {subject}"
    )

    print(
        "Semestre : "
        f"{semester or 'Tous les semestres'}"
    )

    passages = retrieve_relevant_passages(
        question=question,
        number_of_results=3,
        program=program,
        subject=subject,
        semester=semester,
    )

    print(
        "Passages trouvés : "
        f"{len(passages)}"
    )

    filter_errors = validate_passage_filters(
        passages=passages,
        program=program,
        subject=subject,
        semester=semester,
    )

    result = generate_answer(
        question=question,
        passages=passages,
    )

    answerable = bool(
        result.get(
            "answerable",
            False,
        )
    )

    expected_answerable = test_case[
        "expected_answerable"
    ]

    evidence = result.get(
        "evidence",
        [],
    )

    answer = result.get(
        "answer",
        "",
    )

    missing_evidence_terms = (
        validate_expected_evidence(
            evidence=evidence,
            expected_terms=test_case[
                "expected_evidence_terms"
            ],
        )
    )

    errors = list(
        filter_errors
    )

    if answerable != expected_answerable:
        errors.append(
            (
                "Le statut obtenu est incorrect. "
                f"Attendu : {expected_answerable}. "
                f"Obtenu : {answerable}."
            )
        )

    if (
        expected_answerable
        and not answer.strip()
    ):
        errors.append(
            "La réponse générée est vide."
        )

    if (
        expected_answerable
        and not evidence
    ):
        errors.append(
            "Aucune preuve documentaire n'a été retournée."
        )

    if (
        not expected_answerable
        and evidence
    ):
        errors.append(
            (
                "Des preuves ont été retournées "
                "pour une question qui devait être refusée."
            )
        )

    if missing_evidence_terms:
        errors.append(
            (
                "Les preuves ne contiennent pas "
                "les termes attendus : "
                + ", ".join(
                    missing_evidence_terms
                )
            )
        )

    elapsed_time = (
        time.perf_counter()
        - start_time
    )

    print(
        "Réponse possible : "
        f"{answerable}"
    )

    print(
        f"Réponse : {answer}"
    )

    print(
        "Nombre de sources : "
        f"{len(result.get('sources', []))}"
    )

    print(
        "Nombre de preuves : "
        f"{len(evidence)}"
    )

    print(
        "Durée : "
        f"{elapsed_time:.2f} seconde(s)"
    )

    if errors:
        print(
            "\nRésultat : ÉCHEC"
        )

        for error in errors:
            print(
                f"- {error}"
            )

        return {
            "success": False,
            "name": test_case["name"],
            "errors": errors,
            "duration": elapsed_time,
        }

    print(
        "\nRésultat : SUCCÈS"
    )

    return {
        "success": True,
        "name": test_case["name"],
        "errors": [],
        "duration": elapsed_time,
    }


def run_all_tests() -> None:
    """
    Exécute tous les tests et affiche
    un rapport final.
    """

    print(
        "=== TESTS DE QUALITÉ DE L'ASSISTANT ==="
    )

    results = []

    for test_case in TEST_CASES:
        display_separator()

        try:
            result = run_test(
                test_case
            )

        except Exception as error:
            print(
                "\nRésultat : ERREUR"
            )

            print(
                "Erreur pendant le test : "
                f"{error}"
            )

            result = {
                "success": False,
                "name": test_case["name"],
                "errors": [
                    str(error)
                ],
                "duration": 0.0,
            }

        results.append(
            result
        )

    display_separator()

    successful_tests = sum(
        1
        for result in results
        if result["success"]
    )

    failed_tests = (
        len(results)
        - successful_tests
    )

    total_duration = sum(
        result["duration"]
        for result in results
    )

    print(
        "=== RAPPORT FINAL ==="
    )

    print(
        f"Tests exécutés : {len(results)}"
    )

    print(
        f"Tests réussis : {successful_tests}"
    )

    print(
        f"Tests échoués : {failed_tests}"
    )

    print(
        "Durée totale : "
        f"{total_duration:.2f} seconde(s)"
    )

    if failed_tests:
        print(
            "\nTests en échec :"
        )

        for result in results:
            if not result["success"]:
                print(
                    f"- {result['name']}"
                )

        sys.exit(1)

    print(
        "\nTous les tests ont réussi."
    )

    sys.exit(0)


if __name__ == "__main__":
    run_all_tests()