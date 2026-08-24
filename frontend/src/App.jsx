import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import "./App.css";
import LearningTools from "./LearningTools";


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


function normalizeRequestText(
  value
) {
  return (value || "")
    .normalize("NFKD")
    .replace(
      /[\u0300-\u036f\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]/g,
      ""
    )
    .toLowerCase()
    .replace(
      /[-–—_'’"“”()[\]{}:؛،,.!?؟]+/g,
      " "
    )
    .replace(/\s+/g, " ")
    .trim();
}


function isSummaryRequest(
  value
) {
  const normalizedText =
    normalizeRequestText(
      value
    );

  if (!normalizedText) {
    return false;
  }

  const summaryPrefixes = [
    "لخص",
    "تلخيص",
    "ملخص",
    "اعطني ملخص",
    "اعطيني ملخص",
    "قدم ملخص",
    "resume",
    "resumer",
    "fais moi un resume",
    "donne moi un resume",
    "summarize",
    "summarise",
  ];

  return summaryPrefixes.some(
    (prefix) =>
      normalizedText === prefix ||
      normalizedText.startsWith(
        `${prefix} `
      )
  );
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
    summary,
    setSummary,
  ] = useState("");

  const [
    summarySources,
    setSummarySources,
  ] = useState([]);

  const [
    summaryEvidence,
    setSummaryEvidence,
  ] = useState([]);

  const [
    summaryStatus,
    setSummaryStatus,
  ] = useState("");

  const [
    summaryLoading,
    setSummaryLoading,
  ] = useState(false);

  const [
    summaryError,
    setSummaryError,
  ] = useState("");

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
    lastRequestType,
    setLastRequestType,
  ] = useState("");

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


  const summaryRequestDetected =
    useMemo(
      () =>
        isSummaryRequest(
          question
        ),
      [
        question,
      ]
    );


  const isBusy =
    loading ||
    summaryLoading;


  const canSubmit =
    useMemo(() => {
      return Boolean(
        selectedProgram &&
        selectedSubject &&
        question.trim().length >= 2 &&
        !isBusy &&
        !metadataLoading &&
        !metadataError
      );
    }, [
      selectedProgram,
      selectedSubject,
      question,
      isBusy,
      metadataLoading,
      metadataError,
    ]);


  const canGenerateSummary =
    useMemo(() => {
      return Boolean(
        answer &&
        responseStatus === "success" &&
        lastRequest &&
        !isBusy
      );
    }, [
      answer,
      responseStatus,
      lastRequest,
      isBusy,
    ]);


  const resetSummary = () => {
    setSummary("");
    setSummarySources([]);
    setSummaryEvidence([]);
    setSummaryStatus("");
    setSummaryError("");
  };


  const resetResponse = () => {
    setAnswer("");
    setSources([]);
    setEvidence([]);
    setResponseStatus("");
    setSelection(null);
    setRequestError("");
    resetSummary();
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
    status,
    requestType = "question"
  ) => {
    const signature = [
      requestType,
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
      requestType,
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

    setLastRequestType(
      "question"
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
            number_of_results: 5,
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
        data.status || "success",
        "question"
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


  const sendSummary = async (
    requestData,
    replaceResponse = false,
    saveInHistory = false
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

    if (replaceResponse) {
      setAnswer("");
      setSources([]);
      setEvidence([]);
      setResponseStatus("");
      setRequestError("");
    }

    setSummaryLoading(true);
    resetSummary();

    setLastRequest(
      requestData
    );

    setLastRequestType(
      "summary"
    );

    setSelection({
      program:
        requestData.program,
      subject:
        requestData.subject,
      semester:
        requestData.semester,
    });

    setMessage(
      "Génération du résumé pédagogique en cours..."
    );

    try {
      const response = await fetch(
        `${API_URL}/summarize`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            question:
              requestData.question,
            number_of_results: 5,
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
            "Une erreur est survenue pendant la génération du résumé."
        );
      }

      setSummary(
        data.summary || ""
      );

      setSummarySources(
        Array.isArray(
          data.sources
        )
          ? data.sources
          : []
      );

      setSummaryEvidence(
        Array.isArray(
          data.evidence
        )
          ? data.evidence
          : []
      );

      setSummaryStatus(
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

      if (saveInHistory) {
        saveQuestionToHistory(
          requestData,
          data.status || "success",
          "summary"
        );
      }

      if (
        data.status ===
        "insufficient_context"
      ) {
        setMessage(
          "Le résumé n’a pas pu être produit avec les preuves disponibles."
        );
      } else {
        setMessage(
          "Le résumé a été produit à partir des documents pédagogiques."
        );
      }
    } catch (error) {
      console.error(
        "Erreur pendant la génération du résumé :",
        error
      );

      let errorMessage;

      if (
        error.name ===
        "AbortError"
      ) {
        errorMessage = (
          "Le serveur met trop de temps à produire le résumé. "
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
          "La génération du résumé a échoué.";
      }

      resetSummary();

      setSummaryError(
        errorMessage
      );

      setMessage(
        errorMessage
      );
    } finally {
      window.clearTimeout(
        timeoutId
      );

      setSummaryLoading(false);
    }
  };


  const handleGenerateSummary =
    async () => {
      if (
        !lastRequest ||
        isBusy
      ) {
        return;
      }

      await sendSummary(
        lastRequest,
        (
          lastRequestType ===
            "summary" &&
          !answer
        ),
        false
      );
    };


  const handleClearSummary = () => {
    if (summaryLoading) {
      return;
    }

    resetSummary();

    setMessage(
      "Le résumé a été masqué."
    );
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

    const requestData = {
      question:
        cleanedQuestion,
      program:
        selectedProgram,
      subject:
        selectedSubject,
      semester:
        selectedSemester || null,
    };

    if (
      isSummaryRequest(
        cleanedQuestion
      )
    ) {
      await sendSummary(
        requestData,
        true,
        true
      );

      return;
    }

    await sendQuestion(
      requestData
    );
  };


  const handleRetry = async () => {
    if (
      !lastRequest ||
      isBusy
    ) {
      return;
    }

    if (
      lastRequestType ===
      "summary"
    ) {
      await sendSummary(
        lastRequest,
        !answer,
        false
      );

      return;
    }

    await sendQuestion(
      lastRequest
    );
  };


  const handleClear = () => {
    if (isBusy) {
      return;
    }

    setQuestion("");
    setLastRequest(null);
    setLastRequestType("");

    resetResponse();

    setMessage(
      "La question et la réponse ont été effacées."
    );
  };


  const handleHistorySelection = (
    historyItem
  ) => {
    if (isBusy) {
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
    setLastRequestType("");

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
    if (isBusy) {
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


  const renderSources = (
    sourceList
  ) => {
    if (
      !Array.isArray(sourceList) ||
      sourceList.length === 0
    ) {
      return null;
    }

    return (
      <div className="sources-section">
        <h3>
          Sources utilisées
        </h3>

        <ul className="sources-list">
          {sourceList.map(
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
    );
  };


  const renderEvidence = (
    evidenceList
  ) => {
    if (
      !Array.isArray(evidenceList) ||
      evidenceList.length === 0
    ) {
      return null;
    }

    return (
      <details className="evidence-section">
        <summary>
          Voir les preuves
          documentaires
        </summary>

        <ul>
          {evidenceList.map(
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
    );
  };


  const statusClassName =
    requestError ||
    summaryError
      ? (
        "status-message "
        + "status-error"
      )
      : isBusy
        ? (
          "status-message "
          + "status-loading"
        )
        : (
          responseStatus ===
            "insufficient_context" ||
          summaryStatus ===
            "insufficient_context"
        )
          ? (
            "status-message "
            + "status-warning"
          )
          : (
            answer ||
            summary
          )
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
                    isBusy
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
                    isBusy
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
                    isBusy
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
                placeholder="Exemple : Quels sont les rôles des aliments ? ou لخص درس أسلوب المدح والذم"
                rows="5"
                maxLength="600"
                disabled={isBusy}
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
                {isBusy ? (
                  <>
                    <span
                      className="button-spinner"
                      aria-hidden="true"
                    />

                    {summaryLoading
                      ? "Génération du résumé..."
                      : "Génération en cours..."}
                  </>
                ) : summaryRequestDetected ? (
                  "Générer le résumé"
                ) : (
                  "Envoyer la question"
                )}
              </button>

              <button
                className="clear-button"
                type="button"
                onClick={handleClear}
                disabled={
                  isBusy ||
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

            {renderSources(
              sources
            )}

            {renderEvidence(
              evidence
            )}

            {responseStatus ===
              "success" && (
              <div className="form-actions">
                <button
                  type="button"
                  className="submit-button"
                  onClick={
                    handleGenerateSummary
                  }
                  disabled={
                    !canGenerateSummary
                  }
                >
                  {summaryLoading ? (
                    <>
                      <span
                        className="button-spinner"
                        aria-hidden="true"
                      />

                      Génération du résumé...
                    </>
                  ) : summary ? (
                    "Régénérer le résumé"
                  ) : (
                    "Générer un résumé"
                  )}
                </button>

                {summary && (
                  <button
                    type="button"
                    className="clear-button"
                    onClick={
                      handleClearSummary
                    }
                    disabled={
                      summaryLoading
                    }
                  >
                    Masquer le résumé
                  </button>
                )}
              </div>
            )}
          </section>
        )}

        {summaryLoading && (
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
                Création du résumé
              </h2>

              <p>
                Sélection des idées
                importantes et validation
                des preuves documentaires.
              </p>
            </div>
          </section>
        )}

        {summaryError &&
          !summaryLoading && (
          <section className="error-card">
            <div>
              <p className="card-label">
                Erreur de génération
              </p>

              <h2>
                Le résumé n’a pas pu être
                produit
              </h2>

              <p>
                {summaryError}
              </p>
            </div>

            {lastRequest && (
              <button
                type="button"
                className="retry-button"
                onClick={
                  handleGenerateSummary
                }
                disabled={isBusy}
              >
                Réessayer
              </button>
            )}
          </section>
        )}

        {summary && (
          <section
            className={`answer-card ${
              summaryStatus ===
              "insufficient_context"
                ? "answer-card-warning"
                : "answer-card-success"
            }`}
          >
            <div className="answer-header">
              <div>
                <p className="card-label">
                  Accompagnement pédagogique
                </p>

                <h2>
                  {summaryStatus ===
                  "insufficient_context"
                    ? "Résumé indisponible"
                    : "Résumé"}
                </h2>
              </div>

              <span
                className={`answer-status ${
                  summaryStatus ===
                  "insufficient_context"
                    ? "answer-status-warning"
                    : "answer-status-success"
                }`}
              >
                {summaryStatus ===
                "insufficient_context"
                  ? "Preuve insuffisante"
                  : "Résumé vérifié"}
              </span>
            </div>

            <div className="answer-text">
              {summary}
            </div>

            {renderSources(
              summarySources
            )}

            {renderEvidence(
              summaryEvidence
            )}
          </section>
        )}


        <LearningTools
          metadataOptions={metadataOptions}
          selectedProgram={selectedProgram}
          selectedSubject={selectedSubject}
          selectedSemester={selectedSemester}
          isParentBusy={isBusy}
        />

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
                disabled={isBusy}
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
                    disabled={isBusy}
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
                      {historyItem.requestType ===
                      "summary"
                        ? (
                          historyItem.status ===
                          "insufficient_context"
                            ? "Résumé indisponible"
                            : "Résumé trouvé"
                        )
                        : (
                          historyItem.status ===
                          "insufficient_context"
                            ? "Information insuffisante"
                            : "Réponse trouvée"
                        )}
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