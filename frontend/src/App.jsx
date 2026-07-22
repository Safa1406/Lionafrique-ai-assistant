import {
  useEffect,
  useMemo,
  useState,
} from "react";

import "./App.css";


const API_URL = "http://127.0.0.1:8000";


function App() {
  const [metadataOptions, setMetadataOptions] =
    useState([]);

  const [programs, setPrograms] =
    useState([]);

  const [selectedProgram, setSelectedProgram] =
    useState("");

  const [selectedSubject, setSelectedSubject] =
    useState("");

  const [selectedSemester, setSelectedSemester] =
    useState("");

  const [question, setQuestion] =
    useState("");

  const [answer, setAnswer] =
    useState("");

  const [sources, setSources] =
    useState([]);

  const [evidence, setEvidence] =
    useState([]);

  const [responseStatus, setResponseStatus] =
    useState("");

  const [selection, setSelection] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [metadataLoading, setMetadataLoading] =
    useState(true);

  const [metadataError, setMetadataError] =
    useState("");

  const [message, setMessage] =
    useState(
      "Sélectionnez votre programme et votre matière."
    );


  useEffect(() => {
    const loadMetadataOptions = async () => {
      setMetadataLoading(true);
      setMetadataError("");

      try {
        const response = await fetch(
          `${API_URL}/metadata/options`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail ||
              "Le chargement des options pédagogiques a échoué."
          );
        }

        setPrograms(
          Array.isArray(data.programs)
            ? data.programs
            : []
        );

        setMetadataOptions(
          Array.isArray(data.options)
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

        setMetadataError(
          error.message ||
            "La connexion avec le serveur a échoué."
        );

        setMessage(
          "Les options pédagogiques n'ont pas pu être chargées."
        );
      } finally {
        setMetadataLoading(false);
      }
    };

    loadMetadataOptions();
  }, []);


  const availableSubjects = useMemo(() => {
    if (!selectedProgram) {
      return [];
    }

    const subjects = metadataOptions
      .filter(
        (option) =>
          option.program === selectedProgram
      )
      .map(
        (option) => option.subject
      )
      .filter(Boolean);

    return [...new Set(subjects)].sort(
      (firstSubject, secondSubject) =>
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


  const availableSemesters = useMemo(() => {
    if (
      !selectedProgram ||
      !selectedSubject
    ) {
      return [];
    }

    const selectedOption =
      metadataOptions.find(
        (option) =>
          option.program ===
            selectedProgram &&
          option.subject ===
            selectedSubject
      );

    if (
      !selectedOption ||
      !Array.isArray(
        selectedOption.semesters
      )
    ) {
      return [];
    }

    return [
      ...new Set(
        selectedOption.semesters
      ),
    ].sort(
      (firstSemester, secondSemester) =>
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


  const resetResponse = () => {
    setAnswer("");
    setSources([]);
    setEvidence([]);
    setResponseStatus("");
    setSelection(null);
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

    setLoading(true);
    resetResponse();

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
            question: cleanedQuestion,
            number_of_results: 3,
            program: selectedProgram,
            subject: selectedSubject,
            semester:
              selectedSemester || null,
          }),
        }
      );

      let data;

      try {
        data = await response.json();
      } catch {
        throw new Error(
          "Le serveur a retourné une réponse invalide."
        );
      }

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
        Array.isArray(data.sources)
          ? data.sources
          : []
      );

      setEvidence(
        Array.isArray(data.evidence)
          ? data.evidence
          : []
      );

      setResponseStatus(
        data.status || ""
      );

      setSelection(
        data.selection || null
      );

      if (
        data.status ===
        "insufficient_context"
      ) {
        setMessage(
          "Aucune preuve suffisamment précise n'a été trouvée dans les documents sélectionnés."
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

      resetResponse();

      setMessage(
        error.message ||
          "La connexion avec le serveur a échoué."
      );
    } finally {
      setLoading(false);
    }
  };


  const getSemesterLabel = (
    semester
  ) => {
    if (
      semester === "Non défini"
    ) {
      return "Semestre non précisé";
    }

    return semester;
  };


  return (
    <main className="app">
      <section className="assistant-container">
        <header className="assistant-header">
          <p className="school-name">
            LIONAFRIQUE
          </p>

          <h1>
            Assistant pédagogique intelligent
          </h1>

          <p>
            Posez une question et obtenez
            une réponse fondée sur les
            documents pédagogiques.
          </p>
        </header>

        <form
          className="assistant-form"
          onSubmit={handleSubmit}
        >
          <section className="filters-section">
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
          </section>

          {metadataLoading && (
            <p className="metadata-message">
              Chargement des options
              pédagogiques...
            </p>
          )}

          {metadataError && (
            <p className="metadata-error">
              {metadataError}
            </p>
          )}

          <div className="question-section">
            <label htmlFor="question">
              Votre question
            </label>

            <textarea
              id="question"
              name="question"
              value={question}
              onChange={(event) =>
                setQuestion(
                  event.target.value
                )
              }
              placeholder="Exemple : Quels sont les rôles des aliments ?"
              rows="5"
              disabled={loading}
            />
          </div>

          <button
            className="submit-button"
            type="submit"
            disabled={
              loading ||
              metadataLoading ||
              Boolean(metadataError)
            }
          >
            {loading
              ? "Génération en cours..."
              : "Envoyer la question"}
          </button>
        </form>

        <p
          className="status-message"
          aria-live="polite"
        >
          {message}
        </p>

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
            <h2>
              {responseStatus ===
              "insufficient_context"
                ? "Information insuffisante"
                : "Réponse"}
            </h2>

            <div className="answer-text">
              {answer}
            </div>

            {sources.length > 0 && (
              <div className="sources-section">
                <h3>
                  Sources utilisées
                </h3>

                <ul>
                  {sources.map(
                    (
                      source,
                      index
                    ) => (
                      <li
                        key={`${source.file}-${source.page}-${index}`}
                      >
                        <strong>
                          {source.file}
                        </strong>

                        {" — "}

                        Page {source.page}
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
                        key={`${index}-${quote}`}
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
      </section>
    </main>
  );
}


export default App;