import { useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [question, setQuestion] = useState("");
  const [results, setResults] = useState([]);
  const [message, setMessage] = useState(
    "Posez une question sur le contenu des documents pédagogiques."
  );
  const [loading, setLoading] = useState(false);

  const handleSearch = async (event) => {
    event.preventDefault();

    const cleanedQuestion = question.trim();

    if (cleanedQuestion.length < 2) {
      setMessage("Veuillez saisir une question valide.");
      setResults([]);
      return;
    }

    setLoading(true);
    setMessage("Recherche dans les documents en cours...");
    setResults([]);

    try {
      const response = await fetch(`${API_URL}/search`, {
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
          data.detail || "Une erreur est survenue pendant la recherche."
        );
      }

      const searchResults = data.results ?? [];

      setResults(searchResults);

      if (searchResults.length === 0) {
        setMessage(
          "Aucun passage pertinent n'a été trouvé dans les documents."
        );
      } else {
        setMessage(
          `${searchResults.length} passage(s) pertinent(s) trouvé(s).`
        );
      }
    } catch (error) {
      console.error("Erreur de recherche :", error);

      setMessage(
        error.message ||
          "La connexion au serveur a échoué. Vérifiez que FastAPI est actif."
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
            Recherchez une information dans les cours disponibles.
          </p>
        </header>

        <form className="search-form" onSubmit={handleSearch}>
          <label htmlFor="question">
            Votre question
          </label>

          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Exemple : Quels sont les rôles des aliments ?"
            rows="4"
            disabled={loading}
          />

          <button type="submit" disabled={loading}>
            {loading ? "Recherche en cours..." : "Rechercher"}
          </button>
        </form>

        <div className="status-message">
          {message}
        </div>

        {results.length > 0 && (
          <section className="results-section">
            <h2>Passages trouvés</h2>

            <div className="results-list">
              {results.map((result, index) => (
                <article
                  className="result-card"
                  key={result.chunk_id}
                >
                  <div className="result-header">
                    <span>Résultat {index + 1}</span>

                    <span>
                      Pertinence :{" "}
                      {Number(result.distance).toFixed(4)}
                    </span>
                  </div>

                  <p className="result-text">
                    {result.text}
                  </p>

                  <footer className="result-source">
                    <span>
                      Source : {result.source}
                    </span>

                    <span>
                      Page : {result.page}
                    </span>

                    <span>
                      Segment : {result.chunk_number}
                    </span>
                  </footer>
                </article>
              ))}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}

export default App;