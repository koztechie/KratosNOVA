import { useState } from "react";
import axios from "axios"; // Імпортуємо axios
import "./App.css";

// Отримуємо базовий URL з конфігурації
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function App() {
  const [prompt, setPrompt] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Новий стан для зберігання результату
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!prompt || isLoading) return;

    console.log("Submitting goal:", prompt);
    setIsLoading(true);
    setError("");
    setResult(null);

    try {
      // Створюємо екземпляр axios
      const apiClient = axios.create({
        baseURL: API_BASE_URL,
        headers: {
          "Content-Type": "application/json",
        },
      });

      // Робимо POST запит
      const response = await apiClient.post("/goals", {
        description: prompt,
      });

      console.log("API Response:", response.data);
      setResult(response.data);

      // TODO: Add logic to start polling for results in the next step
    } catch (err) {
      console.error("API Error:", err);
      const errorMessage =
        err.response?.data?.error || "An unknown error occurred.";
      setError(`Failed to submit goal: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container">
      <header>
        <h1>KratosNOVA 🚀</h1>
        <p>The Autonomous AI Agent Economy</p>
      </header>

      <main>
        <p className="instructions">
          Describe your high-level goal, and the agent economy will deconstruct
          it into tasks, execute them, and select the best results.
        </p>

        <textarea
          className="prompt-input"
          placeholder="e.g., I need marketing assets for a new mobile game called 'CyberDragon'..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={isLoading}
        />

        <button
          className="submit-button"
          onClick={handleSubmit}
          disabled={isLoading || !prompt.trim()}
        >
          {isLoading ? "Submitting goal..." : "Launch KratosNOVA"}
        </button>
      </main>

      {/* Секція для відображення результатів та помилок */}
      <footer className="results-area">
        {result && (
          <div className="result-success">
            <p>
              <strong>Goal accepted!</strong>
            </p>
            <p>
              Your Goal ID is: <code>{result.goal_id}</code>
            </p>
            <p>Status: {result.status}</p>
            <p>{result.message}</p>
          </div>
        )}
        {error && (
          <div className="result-error">
            <p>
              <strong>Error!</strong>
            </p>
            <p>{error}</p>
          </div>
        )}
      </footer>
    </div>
  );
}

export default App;
