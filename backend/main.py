from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.pdf_service import extract_pdf_pages, get_pdf_summary
from services.vector_store_service import search_similar_chunks
from services.llm_service import generate_answer


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

class AskRequest(BaseModel):
    question: str = Field(
        min_length=2,
        description="Question posée par l'élève.",
    )

    number_of_results: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Nombre de passages utilisés comme contexte.",
    )

app = FastAPI(
    title="API de l'assistant pédagogique LionAfrique",
    description="Backend de l'assistant pédagogique LionAfrique",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

SAMPLE_PDF_PATH = (
    PROJECT_ROOT
    / "data"
    / "sample"
    / "les_aliments_partie_2.pdf"
)


@app.get("/")
def home():
    return {
        "message": "Le backend LionAfrique fonctionne correctement."
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


@app.get("/documents/test")
def test_document():
    try:
        summary = get_pdf_summary(SAMPLE_PDF_PATH)
        pages = extract_pdf_pages(SAMPLE_PDF_PATH)

        preview = pages[0]["text"][:500] if pages else ""

        return {
            "status": "success",
            "message": "Le document PDF a été analysé avec succès.",
            "source": summary["source"],
            "total_pages": summary["total_pages"],
            "pages_with_text": summary["pages_with_text"],
            "empty_pages": summary["empty_pages"],
            "preview": preview,
        }

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        print(f"Erreur inattendue : {error}")

        raise HTTPException(
            status_code=500,
            detail=(
                "Une erreur est survenue pendant "
                "l'analyse du document."
            ),
        ) from error


@app.post("/search")
def search_documents(request: SearchRequest):
    try:
        results = search_similar_chunks(
            question=request.question,
            number_of_results=request.number_of_results,
        )

        return {
            "status": "success",
            "message": (
                "La recherche sémantique "
                "a été effectuée avec succès."
            ),
            "question": request.question,
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
            "Erreur pendant la recherche sémantique : "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Une erreur est survenue "
                "pendant la recherche."
            ),
        ) from error
    
@app.post("/ask")
def ask_assistant(request: AskRequest):
    try:
        passages = search_similar_chunks(
            question=request.question,
            number_of_results=request.number_of_results,
        )

        answer = generate_answer(
            question=request.question,
            passages=passages,
        )

        sources = []

        for passage in passages:
            source = {
                "file": passage["source"],
                "page": passage["page"],
            }

            if source not in sources:
                sources.append(source)

        return {
            "status": "success",
            "message": "La réponse a été générée avec succès.",
            "question": request.question,
            "answer": answer,
            "sources": sources,
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
            "Erreur pendant la génération de la réponse : "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Une erreur est survenue pendant "
                "la génération de la réponse."
            ),
        ) from error