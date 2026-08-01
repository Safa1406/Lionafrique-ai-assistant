import re
import traceback
import unicodedata
from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.llm_service import (
    generate_answer,
)
from services.pdf_service import (
    extract_pdf_pages,
)
from services.retrieval_service import (
    retrieve_relevant_passages,
)
from services.summary_service import (
    generate_summary,
)
from services.vector_store_service import (
    get_metadata_options,
    search_similar_chunks,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

DATA_RAW_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw"
).resolve()

TEST_DOCUMENT_PATH = (
    PROJECT_ROOT
    / "data"
    / "sample"
    / "les_aliments_partie_2.pdf"
)


app = FastAPI(
    title=(
        "Assistant pédagogique LionAfrique"
    ),
    description=(
        "API de recherche documentaire, "
        "de génération de réponses "
        "et de résumés pédagogiques."
    ),
    version="1.3.0",
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
        description=(
            "Question posée par l'utilisateur."
        ),
    )

    number_of_results: int = Field(
        default=3,
        ge=1,
        le=10,
        description=(
            "Nombre de segments à retourner."
        ),
    )

    program: str | None = Field(
        default=None,
        description=(
            "Programme pédagogique sélectionné."
        ),
    )

    subject: str | None = Field(
        default=None,
        description=(
            "Matière sélectionnée."
        ),
    )

    semester: str | None = Field(
        default=None,
        description=(
            "Semestre sélectionné."
        ),
    )

    source: str | None = Field(
        default=None,
        description=(
            "Nom exact du document PDF "
            "à utiliser comme source."
        ),
    )


class AskRequest(BaseModel):
    question: str = Field(
        min_length=2,
        description=(
            "Question posée par l'élève."
        ),
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
        description=(
            "Programme pédagogique sélectionné."
        ),
    )

    subject: str | None = Field(
        default=None,
        description=(
            "Matière sélectionnée."
        ),
    )

    semester: str | None = Field(
        default=None,
        description=(
            "Semestre sélectionné."
        ),
    )

    source: str | None = Field(
        default=None,
        description=(
            "Nom exact du document PDF "
            "à utiliser comme source."
        ),
    )


class SummaryRequest(BaseModel):
    question: str = Field(
        min_length=2,
        description=(
            "Sujet ou question à résumer."
        ),
    )

    number_of_results: int = Field(
        default=5,
        ge=1,
        le=8,
        description=(
            "Nombre de passages utilisés "
            "pour produire le résumé."
        ),
    )

    program: str | None = Field(
        default=None,
        description=(
            "Programme pédagogique sélectionné."
        ),
    )

    subject: str | None = Field(
        default=None,
        description=(
            "Matière sélectionnée."
        ),
    )

    semester: str | None = Field(
        default=None,
        description=(
            "Semestre sélectionné."
        ),
    )

    source: str | None = Field(
        default=None,
        description=(
            "Nom exact du document PDF "
            "à utiliser comme source."
        ),
    )


def build_selection(
    program: str | None,
    subject: str | None,
    semester: str | None,
    source: str | None = None,
) -> dict:
    """
    Prépare les filtres pédagogiques
    retournés dans la réponse de l'API.
    """

    return {
        "program": program,
        "subject": subject,
        "semester": semester,
        "source": source,
    }


def normalize_path_value(
    path_value: str,
) -> str:
    """
    Normalise un chemin pour faciliter
    la comparaison avec les fichiers physiques.
    """

    normalized_value = (
        path_value
        .replace("\\", "/")
        .strip()
        .lower()
    )

    normalized_value = (
        unicodedata.normalize(
            "NFKD",
            normalized_value,
        )
    )

    normalized_value = "".join(
        character
        for character in normalized_value
        if not unicodedata.combining(
            character
        )
    )

    normalized_value = re.sub(
        r"[^a-z0-9/._-]",
        "",
        normalized_value,
    )

    normalized_value = re.sub(
        r"/+",
        "/",
        normalized_value,
    )

    return normalized_value.strip(
        "/"
    )


def resolve_document_path(
    relative_path: str,
) -> Path:
    """
    Résout un chemin relatif vers un document PDF
    sans autoriser l'accès en dehors de data/raw.
    """

    cleaned_relative_path = (
        relative_path.strip()
    )

    if not cleaned_relative_path:
        raise ValueError(
            "Le chemin du document est vide."
        )

    requested_path = Path(
        cleaned_relative_path
    )

    if requested_path.is_absolute():
        raise ValueError(
            "Le chemin absolu est interdit."
        )

    if (
        requested_path.suffix.lower()
        != ".pdf"
    ):
        raise ValueError(
            "Seuls les documents PDF peuvent être ouverts."
        )

    exact_document_path = (
        DATA_RAW_DIRECTORY
        / requested_path
    ).resolve()

    try:
        exact_document_path.relative_to(
            DATA_RAW_DIRECTORY
        )
    except ValueError as error:
        raise ValueError(
            "Le chemin demandé est interdit."
        ) from error

    if (
        exact_document_path.exists()
        and exact_document_path.is_file()
    ):
        return exact_document_path

    normalized_requested_path = (
        normalize_path_value(
            cleaned_relative_path
        )
    )

    requested_filename = (
        requested_path.name
    )

    matching_documents = []

    for candidate_path in (
        DATA_RAW_DIRECTORY.rglob(
            requested_filename
        )
    ):
        if not candidate_path.is_file():
            continue

        if (
            candidate_path.suffix.lower()
            != ".pdf"
        ):
            continue

        resolved_candidate_path = (
            candidate_path.resolve()
        )

        try:
            resolved_candidate_path.relative_to(
                DATA_RAW_DIRECTORY
            )
        except ValueError:
            continue

        candidate_relative_path = (
            resolved_candidate_path.relative_to(
                DATA_RAW_DIRECTORY
            )
        )

        normalized_candidate_path = (
            normalize_path_value(
                str(
                    candidate_relative_path
                )
            )
        )

        if normalized_candidate_path.endswith(
            normalized_requested_path
        ):
            return resolved_candidate_path

        matching_documents.append(
            resolved_candidate_path
        )

    if len(matching_documents) == 1:
        return matching_documents[0]

    if len(matching_documents) > 1:
        raise FileNotFoundError(
            "Plusieurs documents portent ce nom. "
            "Le chemin stocké ne permet pas de les distinguer."
        )

    raise FileNotFoundError(
        "Le document demandé est introuvable."
    )


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
    et semestres disponibles.
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


@app.get("/documents/open")
def open_document(
    relative_path: str,
):
    """
    Ouvre un document PDF stocké dans data/raw.
    """

    try:
        document_path = (
            resolve_document_path(
                relative_path
            )
        )

        return FileResponse(
            path=document_path,
            media_type=(
                "application/pdf"
            ),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except Exception as error:
        print(
            "Erreur pendant l'ouverture "
            "du document : "
            f"{error}"
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Une erreur est survenue pendant "
                "l'ouverture du document."
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
            if page.get(
                "has_text",
                False,
            )
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
                "total_pages": len(
                    pages
                ),
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
    Recherche les segments similaires.
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
            source=request.source,
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
                source=request.source,
            ),
            "number_of_results": len(
                results
            ),
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
        passages = (
            retrieve_relevant_passages(
                question=request.question,
                number_of_results=(
                    request.number_of_results
                ),
                program=request.program,
                subject=request.subject,
                semester=request.semester,
                source=request.source,
            )
        )

        generation_result = (
            generate_answer(
                question=request.question,
                passages=passages,
            )
        )

        selection = build_selection(
            program=request.program,
            subject=request.subject,
            semester=request.semester,
            source=request.source,
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


@app.post("/summarize")
def summarize_documents(
    request: SummaryRequest,
):
    """
    Recherche les passages pertinents
    puis produit un résumé documenté.
    """

    try:
        passages = (
            retrieve_relevant_passages(
                question=request.question,
                number_of_results=(
                    request.number_of_results
                ),
                program=request.program,
                subject=request.subject,
                semester=request.semester,
                source=request.source,
            )
        )

        summary_result = (
            generate_summary(
                question=request.question,
                passages=passages,
            )
        )

        selection = build_selection(
            program=request.program,
            subject=request.subject,
            semester=request.semester,
            source=request.source,
        )

        if not summary_result[
            "answerable"
        ]:
            return {
                "status": (
                    "insufficient_context"
                ),
                "message": (
                    "Le résumé n'a pas pu être produit "
                    "avec les preuves disponibles."
                ),
                "question": request.question,
                "selection": selection,
                "summary": summary_result[
                    "summary"
                ],
                "sources": [],
                "evidence": [],
            }

        return {
            "status": "success",
            "message": (
                "Le résumé a été produit "
                "à partir de preuves validées."
            ),
            "question": request.question,
            "selection": selection,
            "summary": summary_result[
                "summary"
            ],
            "sources": summary_result[
                "sources"
            ],
            "evidence": summary_result[
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
            "du résumé : "
            f"{error}"
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Une erreur est survenue pendant "
                "la génération du résumé."
            ),
        ) from error