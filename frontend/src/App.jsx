import { useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [message, setMessage] = useState(
    "Posez une question sur les cours disponibles."
  );
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();

    const cleanedQuestion = question.trim();

    if (cleanedQuestion.length < 2) {
      setMessage("Veuillez saisir une question valide.");
      setAnswer("");
      setSources([]);
      return;
    }

    setLoading(true);
    setMessage("Génération de la réponse en cours...");
    setAnswer("");
    setSources([]);

    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: cleanedQuestion,
          number_of_results: 3,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Une erreur est survenue pendant la génération."
        );
      }

      setAnswer(data.answer || "");
      setSources(data.sources || []);
      setMessage("La réponse a été générée avec succès.");
    } catch (error) {
      console.error("Erreur de génération :", error);

      setMessage(
        error.message ||
          "La connexion au serveur a échoué."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="app">
      <section className="assistant-container">
        <header className="assistant-header">
          <p className="school-name">LIONAFRIQUE</p>
          <h1>Assistant pédagogique intelligent</h1>
          <p>
            Posez une question et obtenez une réponse basée sur
            les documents pédagogiques.
          </p>
        </header>

        <form className="search-form" onSubmit={handleSubmit}>
          <label htmlFor="question">
            Votre question
          </label>

          <textarea
            id="question"
            value={question}
            onChange={(event) =>
              setQuestion(event.target.value)
            }
            placeholder="Exemple : Quels sont les rôles des aliments ?"
            rows="4"
            disabled={loading}
          />

          <button type="submit" disabled={loading}>
            {loading
              ? "Génération en cours..."
              : "Envoyer la question"}
          </button>
        </form>

        <div className="status-message">
          {message}
        </div>

        {answer && (
          <section className="answer-card">
            <h2>Réponse</h2>

            <div className="answer-text">
              {answer}
            </div>

            {sources.length > 0 && (
              <div className="sources-section">
                <h3>Sources</h3>

                <ul>
                  {sources.map((source, index) => (
                    <li key={`${source.file}-${source.page}-${index}`}>
                      {source.file} — Page {source.page}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </section>
    </main>
  );
}

export default App;