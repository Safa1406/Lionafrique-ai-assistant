import traceback

from services.llm_service import (
    detect_question_intent,
    generate_answer,
)
from services.retrieval_service import (
    retrieve_relevant_passages,
)


question = "Qu'est-ce qu'une guerre de mouvement ?"


try:
    print(
        "Intention détectée :",
        detect_question_intent(question),
    )

    passages = retrieve_relevant_passages(
        question=question,
        number_of_results=3,
    )

    print(
        "Nombre de passages trouvés :",
        len(passages),
    )

    for index, passage in enumerate(
        passages,
        start=1,
    ):
        print(
            f"\nPassage {index} :"
        )
        print(
            passage.get("text", "")
        )

    result = generate_answer(
        question=question,
        passages=passages,
    )

    print(
        "\nRésultat final :"
    )
    print(result)

except Exception:
    print(
        "\nErreur détectée :"
    )
    traceback.print_exc()