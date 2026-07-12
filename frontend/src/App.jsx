import { useState } from "react";
import "./App.css";

function App() {
  const [message, setMessage] = useState(
    "Cliquez sur le bouton pour tester la connexion avec le backend."
  );

  const [loading, setLoading] = useState(false);

  const testBackendConnection = async () => {
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/health");

      if (!response.ok) {
        throw new Error(`Erreur HTTP : ${response.status}`);
      }

      const data = await response.json();

      if (data.status === "ok") {
        setMessage("Le backend est connecté à React avec succès.");
      } else {
        setMessage("La réponse du backend est inattendue.");
      }
    } catch (error) {
      console.error("Erreur de connexion au backend :", error);

      setMessage(
        "La connexion a échoué. Vérifiez que le serveur FastAPI est actif."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="app">
      <section className="card">
        <h1>Assistant pédagogique LionAfrique</h1>

        <p>
          Première vérification de la connexion entre React et FastAPI.
        </p>

        <button onClick={testBackendConnection} disabled={loading}>
          {loading ? "Connexion en cours..." : "Tester la connexion"}
        </button>

        <div className="status">{message}</div>
      </section>
    </main>
  );
}

export default App;