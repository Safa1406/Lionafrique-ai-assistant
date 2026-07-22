import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.llm_service import generate_answer
from services.pdf_service import extract_pdf_pages
from services.retrieval_service import (
    retrieve_relevant_passages,
)
from services.vector_store_service import (
    get_metadata_options,
    search_similar_chunks,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEST_DOCUMENT_PATH = (
    PROJECT_ROOT
    / "data"
    / "sample"
    / "les_aliments_partie_2.pdf"
)


app = FastAPI(
    title="Assistant pédagogique LionAfrique",
    description=(
        "API de recherche documentaire "
        "et de génération de réponses pédagogiques."
    ),
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    question: str = Field(
        min_length=2,
        description="Question posée par l'utilisateur.",
    )

    number_of_results: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Nombre de segments à retourner.",
    )

    program: str | None = Field(
        default=None,
        description="Programme pédagogique sélectionné.",
    )

    subject: str | None = Field(
        default=None,
        description="Matière sélectionnée.",
    )

    semester: str | None = Field(
        default=None,
        description="Semestre sélectionné.",
    )


class AskRequest(BaseModel):
    question: str = Field(
        min_length=2,
        description="Question posée par l'élève.",
    )

    number_of_results: int = Field(
        default=3,
        ge=1,
        le=5,
        description=(
            "Nombre de passages utilisés "
            "pour produire la réponse."
        ),
    )

    program: str | None = Field(
        default=None,
        description="Programme pédagogique sélectionné.",
    )

    subject: str | None = Field(
        default=None,
        description="Matière sélectionnée.",
    )

    semester: str | None = Field(
        default=None,
        description="Semestre sélectionné.",
    )


def build_selection(
    program: str | None,
    subject: str | None,
    semester: str | None,
) -> dict:
    """
    Prépare les filtres pédagogiques
    retournés dans la réponse de l'API.
    """

    return {
        "program": program,
        "subject": subject,
        "semester": semester,
    }


@app.get("/")
def read_root():
    """
    Retourne les informations générales de l'API.
    """

    return {
        "status": "success",
        "message": (
            "L'API de l'assistant pédagogique "
            "LionAfrique est active."
        ),
        "documentation": "/docs",
    }


@app.get("/health")
def health_check():
    """
    Vérifie que le serveur FastAPI fonctionne.
    """

    return {
        "status": "success",
        "message": (
            "Le serveur fonctionne correctement."
        ),
    }


@app.get("/metadata/options")
def read_metadata_options():
    """
    Retourne les programmes, matières
    et semestres disponibles dans ChromaDB.
    """

    try:
        options = get_metadata_options()

        programs = sorted(
            {
                option["program"]
                for option in options
            },
            key=str.lower,
        )

        return {
            "status": "success",
            "message": (
                "Les options pédagogiques "
                "ont été récupérées avec succès."
            ),
            "programs": programs,
            "options": options,
        }

    except Exception as error:
        print(
            "Erreur pendant la récupération "
            "des options pédagogiques : "
            f"{error}"
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Une erreur est survenue pendant "
                "la récupération des options pédagogiques."
            ),
        ) from error


@app.get("/documents/test")
def read_test_document():
    """
    Extrait le contenu du document PDF de test.
    """

    if not TEST_DOCUMENT_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Le document PDF de test "
                "est introuvable."
            ),
        )

    try:
        pages = extract_pdf_pages(
            TEST_DOCUMENT_PATH
        )

        pages_with_text = sum(
            1
            for page in pages
            if page.get("has_text", False)
        )

        previews = []

        for page in pages:
            previews.append(
                {
                    "page": page.get(
                        "page",
                        0,
                    ),
                    "has_text": page.get(
                        "has_text",
                        False,
                    ),
                    "preview": page.get(
                        "text",
                        "",
                    )[:500],
                }
            )

        return {
            "status": "success",
            "message": (
                "Le document de test "
                "a été extrait avec succès."
            ),
            "summary": {
                "source": (
                    TEST_DOCUMENT_PATH.name
                ),
                "total_pages": len(pages),
                "pages_with_text": (
                    pages_with_text
                ),
                "pages_without_text": (
                    len(pages)
                    - pages_with_text
                ),
            },
            "pages": previews,
        }

    except Exception as error:
        print(
            "Erreur pendant l'extraction "
            "du document de test : "
            f"{error}"
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Une erreur est survenue pendant "
                "l'extraction du document de test."
            ),
        ) from error


@app.post("/search")
def search_documents(
    request: SearchRequest,
):
    """
    Recherche les segments similaires
    avec des filtres pédagogiques facultatifs.
    """

    try:
        results = search_similar_chunks(
            question=request.question,
            number_of_results=(
                request.number_of_results
            ),
            program=request.program,
            subject=request.subject,
            semester=request.semester,
        )

        return {
            "status": "success",
            "message": (
                "La recherche documentaire "
                "a été effectuée avec succès."
            ),
            "question": request.question,
            "selection": build_selection(
                program=request.program,
                subject=request.subject,
                semester=request.semester,
            ),
            "number_of_results": len(results),
            "results": results,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        print(
            "Erreur pendant la recherche "
            "documentaire : "
            f"{error}"
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Une erreur est survenue pendant "
                "la recherche documentaire."
            ),
        ) from error


@app.post("/ask")
def ask_assistant(
    request: AskRequest,
):
    """
    Recherche les preuves documentaires
    puis produit une réponse pédagogique.
    """

    try:
        passages = retrieve_relevant_passages(
            question=request.question,
            number_of_results=(
                request.number_of_results
            ),
            program=request.program,
            subject=request.subject,
            semester=request.semester,
        )

        generation_result = generate_answer(
            question=request.question,
            passages=passages,
        )

        selection = build_selection(
            program=request.program,
            subject=request.subject,
            semester=request.semester,
        )

        if not generation_result[
            "answerable"
        ]:
            return {
                "status": (
                    "insufficient_context"
                ),
                "message": (
                    "Aucune preuve documentaire "
                    "directe n'a été trouvée."
                ),
                "question": request.question,
                "selection": selection,
                "answer": generation_result[
                    "answer"
                ],
                "sources": [],
                "evidence": [],
            }

        return {
            "status": "success",
            "message": (
                "La réponse a été générée "
                "à partir de preuves validées."
            ),
            "question": request.question,
            "selection": selection,
            "answer": generation_result[
                "answer"
            ],
            "sources": generation_result[
                "sources"
            ],
            "evidence": generation_result[
                "evidence"
            ],
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except Exception as error:
        print(
            "Erreur pendant la génération "
            "de la réponse : "
            f"{error}"
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Une erreur est survenue pendant "
                "la génération de la réponse."
            ),
        ) from error