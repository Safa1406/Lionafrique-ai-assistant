import { useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [evidence, setEvidence] = useState([]);
  const [responseStatus, setResponseStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(
    "Posez une question sur les cours disponibles."
  );

  const resetResponse = () => {
    setAnswer("");
    setSources([]);
    setEvidence([]);
    setResponseStatus("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const cleanedQuestion = question.trim();

    if (cleanedQuestion.length < 2) {
      resetResponse();
      setMessage(
        "Veuillez saisir une question valide."
      );
      return;
    }

    setLoading(true);
    resetResponse();

    setMessage(
      "Recherche des informations et génération de la réponse..."
    );

    try {
      const response = await fetch(
        `${API_URL}/ask`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: cleanedQuestion,
            number_of_results: 3,
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

      setAnswer(data.answer || "");
      setSources(data.sources || []);
      setEvidence(data.evidence || []);
      setResponseStatus(data.status || "");

      if (data.status === "insufficient_context") {
        setMessage(
          "Les documents disponibles ne permettent pas de répondre avec précision."
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
            Posez une question et obtenez une réponse
            fondée sur les documents pédagogiques
            disponibles.
          </p>
        </header>

        <form
          className="search-form"
          onSubmit={handleSubmit}
        >
          <label htmlFor="question">
            Votre question
          </label>

          <textarea
            id="question"
            name="question"
            value={question}
            onChange={(event) =>
              setQuestion(event.target.value)
            }
            placeholder="Exemple : Qu'est-ce qu'une guerre de mouvement ?"
            rows="4"
            disabled={loading}
          />

          <button
            type="submit"
            disabled={loading}
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
                <h3>Sources utilisées</h3>

                <ul>
                  {sources.map(
                    (source, index) => (
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
                  Voir les preuves documentaires
                </summary>

                <ul>
                  {evidence.map(
                    (quote, index) => (
                      <li key={index}>
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