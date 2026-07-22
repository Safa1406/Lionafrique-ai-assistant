import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import "./App.css";


const API_URL =
  "http://127.0.0.1:8000";

const HISTORY_STORAGE_KEY =
  "lionafrique-question-history";

const MAX_HISTORY_ITEMS = 6;

const REQUEST_TIMEOUT = 120000;


function readStoredHistory() {
  try {
    const storedHistory =
      sessionStorage.getItem(
        HISTORY_STORAGE_KEY
      );

    if (!storedHistory) {
      return [];
    }

    const parsedHistory =
      JSON.parse(storedHistory);

    return Array.isArray(
      parsedHistory
    )
      ? parsedHistory
      : [];
  } catch (error) {
    console.error(
      "Erreur pendant la lecture de l’historique :",
      error
    );

    return [];
  }
}


function formatHistoryDate(
  dateValue
) {
  try {
    return new Intl.DateTimeFormat(
      "fr-FR",
      {
        hour: "2-digit",
        minute: "2-digit",
      }
    ).format(
      new Date(dateValue)
    );
  } catch {
    return "";
  }
}


async function readJsonResponse(
  response
) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}


function App() {
  const [
    metadataOptions,
    setMetadataOptions,
  ] = useState([]);

  const [
    programs,
    setPrograms,
  ] = useState([]);

  const [
    selectedProgram,
    setSelectedProgram,
  ] = useState("");

  const [
    selectedSubject,
    setSelectedSubject,
  ] = useState("");

  const [
    selectedSemester,
    setSelectedSemester,
  ] = useState("");

  const [
    question,
    setQuestion,
  ] = useState("");

  const [
    answer,
    setAnswer,
  ] = useState("");

  const [
    sources,
    setSources,
  ] = useState([]);

  const [
    evidence,
    setEvidence,
  ] = useState([]);

  const [
    responseStatus,
    setResponseStatus,
  ] = useState("");

  const [
    selection,
    setSelection,
  ] = useState(null);

  const [
    loading,
    setLoading,
  ] = useState(false);

  const [
    metadataLoading,
    setMetadataLoading,
  ] = useState(true);

  const [
    metadataError,
    setMetadataError,
  ] = useState("");

  const [
    requestError,
    setRequestError,
  ] = useState("");

  const [
    lastRequest,
    setLastRequest,
  ] = useState(null);

  const [
    questionHistory,
    setQuestionHistory,
  ] = useState(
    readStoredHistory
  );

  const [
    message,
    setMessage,
  ] = useState(
    "Sélectionnez votre programme et votre matière."
  );


  const loadMetadataOptions =
    useCallback(async () => {
      setMetadataLoading(true);
      setMetadataError("");

      try {
        const response = await fetch(
          `${API_URL}/metadata/options`
        );

        const data =
          await readJsonResponse(
            response
          );

        if (!response.ok) {
          throw new Error(
            data.detail ||
              "Le chargement des options pédagogiques a échoué."
          );
        }

        setPrograms(
          Array.isArray(
            data.programs
          )
            ? data.programs
            : []
        );

        setMetadataOptions(
          Array.isArray(
            data.options
          )
            ? data.options
            : []
        );

        setMessage(
          "Sélectionnez votre programme et votre matière."
        );
      } catch (error) {
        console.error(
          "Erreur pendant le chargement des options pédagogiques :",
          error
        );

        const errorMessage =
          error instanceof TypeError
            ? (
              "Impossible de joindre le serveur. "
              + "Vérifiez que FastAPI est démarré."
            )
            : (
              error.message ||
              "La connexion avec le serveur a échoué."
            );

        setMetadataError(
          errorMessage
        );

        setMessage(
          "Les options pédagogiques n’ont pas pu être chargées."
        );
      } finally {
        setMetadataLoading(false);
      }
    }, []);


  useEffect(() => {
    loadMetadataOptions();
  }, [
    loadMetadataOptions,
  ]);


  useEffect(() => {
    try {
      sessionStorage.setItem(
        HISTORY_STORAGE_KEY,
        JSON.stringify(
          questionHistory
        )
      );
    } catch (error) {
      console.error(
        "Erreur pendant l’enregistrement de l’historique :",
        error
      );
    }
  }, [
    questionHistory,
  ]);


  const availableSubjects =
    useMemo(() => {
      if (!selectedProgram) {
        return [];
      }

      const subjects =
        metadataOptions
          .filter(
            (option) =>
              option.program ===
              selectedProgram
          )
          .map(
            (option) =>
              option.subject
          )
          .filter(Boolean);

      return [
        ...new Set(subjects),
      ].sort(
        (
          firstSubject,
          secondSubject
        ) =>
          firstSubject.localeCompare(
            secondSubject,
            "fr",
            {
              sensitivity: "base",
            }
          )
      );
    }, [
      metadataOptions,
      selectedProgram,
    ]);


  const availableSemesters =
    useMemo(() => {
      if (
        !selectedProgram ||
        !selectedSubject
      ) {
        return [];
      }

      const semesters =
        metadataOptions
          .filter(
            (option) =>
              option.program ===
                selectedProgram &&
              option.subject ===
                selectedSubject
          )
          .flatMap(
            (option) =>
              Array.isArray(
                option.semesters
              )
                ? option.semesters
                : []
          )
          .filter(Boolean);

      return [
        ...new Set(semesters),
      ].sort(
        (
          firstSemester,
          secondSemester
        ) =>
          firstSemester.localeCompare(
            secondSemester,
            "fr",
            {
              sensitivity: "base",
            }
          )
      );
    }, [
      metadataOptions,
      selectedProgram,
      selectedSubject,
    ]);


  const canSubmit =
    useMemo(() => {
      return Boolean(
        selectedProgram &&
        selectedSubject &&
        question.trim().length >= 2 &&
        !loading &&
        !metadataLoading &&
        !metadataError
      );
    }, [
      selectedProgram,
      selectedSubject,
      question,
      loading,
      metadataLoading,
      metadataError,
    ]);


  const resetResponse = () => {
    setAnswer("");
    setSources([]);
    setEvidence([]);
    setResponseStatus("");
    setSelection(null);
    setRequestError("");
  };


  const handleProgramChange = (
    event
  ) => {
    setSelectedProgram(
      event.target.value
    );

    setSelectedSubject("");
    setSelectedSemester("");

    resetResponse();

    setMessage(
      "Sélectionnez maintenant votre matière."
    );
  };


  const handleSubjectChange = (
    event
  ) => {
    setSelectedSubject(
      event.target.value
    );

    setSelectedSemester("");

    resetResponse();

    setMessage(
      "Vous pouvez sélectionner un semestre puis poser votre question."
    );
  };


  const handleSemesterChange = (
    event
  ) => {
    setSelectedSemester(
      event.target.value
    );

    resetResponse();

    setMessage(
      "Vous pouvez maintenant poser votre question."
    );
  };


  const saveQuestionToHistory = (
    requestData,
    status
  ) => {
    const signature = [
      requestData.question,
      requestData.program,
      requestData.subject,
      requestData.semester || "",
    ].join("|");

    const historyItem = {
      id: (
        `${Date.now()}-`
        + Math.random()
          .toString(16)
          .slice(2)
      ),
      signature,
      question:
        requestData.question,
      program:
        requestData.program,
      subject:
        requestData.subject,
      semester:
        requestData.semester,
      status,
      createdAt:
        new Date().toISOString(),
    };

    setQuestionHistory(
      (previousHistory) => {
        const historyWithoutDuplicate =
          previousHistory.filter(
            (item) =>
              item.signature !==
              signature
          );

        return [
          historyItem,
          ...historyWithoutDuplicate,
        ].slice(
          0,
          MAX_HISTORY_ITEMS
        );
      }
    );
  };


  const sendQuestion = async (
    requestData
  ) => {
    const controller =
      new AbortController();

    const timeoutId =
      window.setTimeout(
        () => {
          controller.abort();
        },
        REQUEST_TIMEOUT
      );

    setLoading(true);
    resetResponse();

    setLastRequest(
      requestData
    );

    setMessage(
      "Recherche des preuves documentaires en cours..."
    );

    try {
      const response = await fetch(
        `${API_URL}/ask`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            question:
              requestData.question,
            number_of_results: 3,
            program:
              requestData.program,
            subject:
              requestData.subject,
            semester:
              requestData.semester,
          }),
          signal:
            controller.signal,
        }
      );

      const data =
        await readJsonResponse(
          response
        );

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Une erreur est survenue pendant la génération de la réponse."
        );
      }

      setAnswer(
        data.answer || ""
      );

      setSources(
        Array.isArray(
          data.sources
        )
          ? data.sources
          : []
      );

      setEvidence(
        Array.isArray(
          data.evidence
        )
          ? data.evidence
          : []
      );

      setResponseStatus(
        data.status || ""
      );

      setSelection(
        data.selection || {
          program:
            requestData.program,
          subject:
            requestData.subject,
          semester:
            requestData.semester,
        }
      );

      saveQuestionToHistory(
        requestData,
        data.status || "success"
      );

      if (
        data.status ===
        "insufficient_context"
      ) {
        setMessage(
          "Aucune preuve suffisamment précise n’a été trouvée dans les documents sélectionnés."
        );
      } else {
        setMessage(
          "La réponse a été générée à partir des documents pédagogiques."
        );
      }
    } catch (error) {
      console.error(
        "Erreur pendant la génération de la réponse :",
        error
      );

      let errorMessage;

      if (
        error.name ===
        "AbortError"
      ) {
        errorMessage = (
          "Le serveur met trop de temps à répondre. "
          + "Vérifiez qu’Ollama est démarré puis réessayez."
        );
      } else if (
        error instanceof TypeError
      ) {
        errorMessage = (
          "Impossible de joindre le serveur FastAPI. "
          + "Vérifiez qu’il est démarré sur le port 8000."
        );
      } else {
        errorMessage =
          error.message ||
          "La connexion avec le serveur a échoué.";
      }

      resetResponse();

      setRequestError(
        errorMessage
      );

      setMessage(
        errorMessage
      );
    } finally {
      window.clearTimeout(
        timeoutId
      );

      setLoading(false);
    }
  };


  const handleSubmit = async (
    event
  ) => {
    event.preventDefault();

    const cleanedQuestion =
      question.trim();

    if (!selectedProgram) {
      resetResponse();

      setMessage(
        "Veuillez sélectionner un programme."
      );

      return;
    }

    if (!selectedSubject) {
      resetResponse();

      setMessage(
        "Veuillez sélectionner une matière."
      );

      return;
    }

    if (
      cleanedQuestion.length < 2
    ) {
      resetResponse();

      setMessage(
        "Veuillez saisir une question valide."
      );

      return;
    }

    await sendQuestion({
      question:
        cleanedQuestion,
      program:
        selectedProgram,
      subject:
        selectedSubject,
      semester:
        selectedSemester || null,
    });
  };


  const handleRetry = async () => {
    if (
      !lastRequest ||
      loading
    ) {
      return;
    }

    await sendQuestion(
      lastRequest
    );
  };


  const handleClear = () => {
    if (loading) {
      return;
    }

    setQuestion("");
    setLastRequest(null);

    resetResponse();

    setMessage(
      "La question et la réponse ont été effacées."
    );
  };


  const handleHistorySelection = (
    historyItem
  ) => {
    if (loading) {
      return;
    }

    setSelectedProgram(
      historyItem.program
    );

    setSelectedSubject(
      historyItem.subject
    );

    setSelectedSemester(
      historyItem.semester || ""
    );

    setQuestion(
      historyItem.question
    );

    setLastRequest(null);

    resetResponse();

    setMessage(
      "La question a été restaurée. Vous pouvez la modifier ou l’envoyer."
    );

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };


  const handleClearHistory = () => {
    if (loading) {
      return;
    }

    setQuestionHistory([]);
  };


  const handleQuestionKeyDown = (
    event
  ) => {
    if (
      (
        event.ctrlKey ||
        event.metaKey
      ) &&
      event.key === "Enter" &&
      canSubmit
    ) {
      event.preventDefault();

      event.currentTarget.form
        ?.requestSubmit();
    }
  };


  const getSourceUrl = (
    source
  ) => {
    if (!source?.relative_path) {
      return "";
    }

    const parameters =
      new URLSearchParams({
        relative_path:
          source.relative_path,
      });

    const pageNumber = Math.max(
      Number(source.page) || 1,
      1
    );

    return (
      `${API_URL}/documents/open?`
      + `${parameters.toString()}`
      + `#page=${pageNumber}`
    );
  };


  const getSemesterLabel = (
    semester
  ) => {
    if (
      semester === "Non défini"
    ) {
      return (
        "Semestre non précisé"
      );
    }

    return semester;
  };


  const statusClassName =
    requestError
      ? (
        "status-message "
        + "status-error"
      )
      : loading
        ? (
          "status-message "
          + "status-loading"
        )
        : responseStatus ===
          "insufficient_context"
          ? (
            "status-message "
            + "status-warning"
          )
          : answer
            ? (
              "status-message "
              + "status-success"
            )
            : "status-message";


  return (
    <main className="app">
      <section className="assistant-container">
        <header className="assistant-header">
          <div className="header-badge">
            Assistant documentaire
          </div>

          <p className="school-name">
            LIONAFRIQUE
          </p>

          <h1>
            Assistant pédagogique intelligent
          </h1>

          <p className="header-description">
            Posez une question et obtenez
            une réponse fondée sur les
            documents pédagogiques
            sélectionnés.
          </p>
        </header>

        <form
          className="assistant-form"
          onSubmit={handleSubmit}
        >
          <section className="filters-card">
            <div className="section-heading">
              <div>
                <p className="section-number">
                  Étape 1
                </p>

                <h2>
                  Sélection pédagogique
                </h2>
              </div>

              <p>
                Choisissez le contexte
                documentaire de la
                recherche.
              </p>
            </div>

            <div className="filters-section">
              <div className="field-group">
                <label htmlFor="program">
                  Programme
                </label>

                <select
                  id="program"
                  value={selectedProgram}
                  onChange={
                    handleProgramChange
                  }
                  disabled={
                    metadataLoading ||
                    loading
                  }
                >
                  <option value="">
                    Sélectionnez un programme
                  </option>

                  {programs.map(
                    (program) => (
                      <option
                        key={program}
                        value={program}
                      >
                        {program}
                      </option>
                    )
                  )}
                </select>
              </div>

              <div className="field-group">
                <label htmlFor="subject">
                  Matière
                </label>

                <select
                  id="subject"
                  value={selectedSubject}
                  onChange={
                    handleSubjectChange
                  }
                  disabled={
                    !selectedProgram ||
                    metadataLoading ||
                    loading
                  }
                >
                  <option value="">
                    Sélectionnez une matière
                  </option>

                  {availableSubjects.map(
                    (subject) => (
                      <option
                        key={subject}
                        value={subject}
                      >
                        {subject}
                      </option>
                    )
                  )}
                </select>
              </div>

              <div className="field-group">
                <label htmlFor="semester">
                  Semestre
                </label>

                <select
                  id="semester"
                  value={selectedSemester}
                  onChange={
                    handleSemesterChange
                  }
                  disabled={
                    !selectedSubject ||
                    metadataLoading ||
                    loading
                  }
                >
                  <option value="">
                    Tous les semestres
                  </option>

                  {availableSemesters.map(
                    (semester) => (
                      <option
                        key={semester}
                        value={semester}
                      >
                        {getSemesterLabel(
                          semester
                        )}
                      </option>
                    )
                  )}
                </select>
              </div>
            </div>

            {metadataLoading && (
              <div className="metadata-state">
                <span
                  className="mini-spinner"
                  aria-hidden="true"
                />

                <p>
                  Chargement des options
                  pédagogiques...
                </p>
              </div>
            )}

            {metadataError && (
              <div className="metadata-error">
                <p>
                  {metadataError}
                </p>

                <button
                  type="button"
                  className="small-button"
                  onClick={
                    loadMetadataOptions
                  }
                  disabled={
                    metadataLoading
                  }
                >
                  Réessayer
                </button>
              </div>
            )}
          </section>

          <section className="question-card">
            <div className="section-heading">
              <div>
                <p className="section-number">
                  Étape 2
                </p>

                <h2>
                  Votre question
                </h2>
              </div>

              <p>
                Utilisez une question
                précise pour obtenir une
                réponse mieux ciblée.
              </p>
            </div>

            <div className="question-section">
              <div className="question-label-row">
                <label htmlFor="question">
                  Question
                </label>

                <span>
                  {question.length}
                  {" "}
                  caractère
                  {question.length > 1
                    ? "s"
                    : ""}
                </span>
              </div>

              <textarea
                id="question"
                name="question"
                value={question}
                onChange={(event) =>
                  setQuestion(
                    event.target.value
                  )
                }
                onKeyDown={
                  handleQuestionKeyDown
                }
                placeholder="Exemple : Quels sont les rôles des aliments ?"
                rows="5"
                maxLength="600"
                disabled={loading}
              />

              <p className="keyboard-hint">
                Utilisez Ctrl + Entrée
                pour envoyer la question.
              </p>
            </div>

            <div className="form-actions">
              <button
                className="submit-button"
                type="submit"
                disabled={!canSubmit}
              >
                {loading ? (
                  <>
                    <span
                      className="button-spinner"
                      aria-hidden="true"
                    />

                    Génération en cours...
                  </>
                ) : (
                  "Envoyer la question"
                )}
              </button>

              <button
                className="clear-button"
                type="button"
                onClick={handleClear}
                disabled={
                  loading ||
                  (
                    !question &&
                    !answer &&
                    !requestError
                  )
                }
              >
                Effacer
              </button>
            </div>
          </section>
        </form>

        <p
          className={
            statusClassName
          }
          aria-live="polite"
        >
          {message}
        </p>

        {loading && (
          <section
            className="loading-card"
            aria-live="polite"
          >
            <span
              className="loading-spinner"
              aria-hidden="true"
            />

            <div>
              <h2>
                Analyse des documents
              </h2>

              <p>
                Recherche des passages,
                validation des preuves et
                préparation de la réponse.
              </p>
            </div>
          </section>
        )}

        {requestError &&
          !loading && (
          <section className="error-card">
            <div>
              <p className="card-label">
                Erreur de connexion
              </p>

              <h2>
                La réponse n’a pas pu être
                générée
              </h2>

              <p>
                {requestError}
              </p>
            </div>

            {lastRequest && (
              <button
                type="button"
                className="retry-button"
                onClick={handleRetry}
              >
                Réessayer
              </button>
            )}
          </section>
        )}

        {selection && (
          <section className="selection-summary">
            <span>
              {selection.program}
            </span>

            <span>
              {selection.subject}
            </span>

            {selection.semester && (
              <span>
                {getSemesterLabel(
                  selection.semester
                )}
              </span>
            )}
          </section>
        )}

        {answer && (
          <section
            className={`answer-card ${
              responseStatus ===
              "insufficient_context"
                ? "answer-card-warning"
                : "answer-card-success"
            }`}
          >
            <div className="answer-header">
              <div>
                <p className="card-label">
                  Résultat documentaire
                </p>

                <h2>
                  {responseStatus ===
                  "insufficient_context"
                    ? "Information insuffisante"
                    : "Réponse"}
                </h2>
              </div>

              <span
                className={`answer-status ${
                  responseStatus ===
                  "insufficient_context"
                    ? "answer-status-warning"
                    : "answer-status-success"
                }`}
              >
                {responseStatus ===
                "insufficient_context"
                  ? "Preuve insuffisante"
                  : "Réponse vérifiée"}
              </span>
            </div>

            <div className="answer-text">
              {answer}
            </div>

            {sources.length > 0 && (
              <div className="sources-section">
                <h3>
                  Sources utilisées
                </h3>

                <ul className="sources-list">
                  {sources.map(
                    (
                      source,
                      index
                    ) => (
                      <li
                        key={
                          `${source.file}-`
                          + `${source.page}-`
                          + `${index}`
                        }
                      >
                        <div className="source-information">
                          <span className="source-index">
                            {index + 1}
                          </span>

                          <div className="source-details">
                            <strong>
                              {source.file}
                            </strong>

                            <span>
                              Document pédagogique
                            </span>
                          </div>
                        </div>

                        <div className="source-actions">
                          <span className="source-page">
                            Page {source.page}
                          </span>

                          {source.relative_path ? (
                            <a
                              className="source-open-button"
                              href={
                                getSourceUrl(
                                  source
                                )
                              }
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              Ouvrir la source
                            </a>
                          ) : (
                            <span className="source-unavailable">
                              Source indisponible
                            </span>
                          )}
                        </div>
                      </li>
                    )
                  )}
                </ul>
              </div>
            )}

            {evidence.length > 0 && (
              <details className="evidence-section">
                <summary>
                  Voir les preuves
                  documentaires
                </summary>

                <ul>
                  {evidence.map(
                    (
                      quote,
                      index
                    ) => (
                      <li
                        key={
                          `${index}-${quote}`
                        }
                      >
                        « {quote} »
                      </li>
                    )
                  )}
                </ul>
              </details>
            )}
          </section>
        )}

        {questionHistory.length > 0 && (
          <section className="history-section">
            <div className="history-header">
              <div>
                <p className="card-label">
                  Session actuelle
                </p>

                <h2>
                  Questions récentes
                </h2>
              </div>

              <button
                type="button"
                className="text-button"
                onClick={
                  handleClearHistory
                }
                disabled={loading}
              >
                Vider l’historique
              </button>
            </div>

            <div className="history-list">
              {questionHistory.map(
                (historyItem) => (
                  <button
                    type="button"
                    className="history-item"
                    key={historyItem.id}
                    onClick={() =>
                      handleHistorySelection(
                        historyItem
                      )
                    }
                    disabled={loading}
                  >
                    <span className="history-question">
                      {historyItem.question}
                    </span>

                    <span className="history-details">
                      {historyItem.subject}
                      {" · "}
                      {historyItem.semester ||
                        "Tous les semestres"}
                      {" · "}
                      {formatHistoryDate(
                        historyItem.createdAt
                      )}
                    </span>

                    <span
                      className={`history-status ${
                        historyItem.status ===
                        "insufficient_context"
                          ? "history-status-warning"
                          : "history-status-success"
                      }`}
                    >
                      {historyItem.status ===
                      "insufficient_context"
                        ? "Information insuffisante"
                        : "Réponse trouvée"}
                    </span>
                  </button>
                )
              )}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}


export default App;