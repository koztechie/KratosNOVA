import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const apiClient = axios.create({ baseURL: API_BASE_URL });

function App() {
  const [prompt, setPrompt] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const [goalId, setGoalId] = useState(null);
  const [status, setStatus] = useState("idle");
  const [processingMessage, setProcessingMessage] = useState(""); // Новий стан для повідомлень
  const [finalResults, setFinalResults] = useState([]);
  const [error, setError] = useState("");

  // useEffect для полінгу
  useEffect(() => {
    let intervalId = null;
    if (goalId && status === "processing") {
      console.log(`Starting polling for goalId: ${goalId}`);
      intervalId = setInterval(() => fetchResults(goalId), 10000);
    }
    return () => {
      if (intervalId) {
        console.log("Stopping polling.");
        clearInterval(intervalId);
      }
    };
  }, [goalId, status]);

  // НОВИЙ useEffect для оновлення повідомлень
  useEffect(() => {
    let timer1, timer2;
    if (status === "processing") {
      setProcessingMessage(
        "Stage 1/3: Agent-Manager is deconstructing your goal..."
      );
      // Змінити повідомлення через 15 секунд
      timer1 = setTimeout(() => {
        setProcessingMessage(
          "Stage 2/3: Freelancer Agents are working on the contracts..."
        );
      }, 15000); // 15 секунд
      // Змінити повідомлення через 90 секунд
      timer2 = setTimeout(() => {
        setProcessingMessage(
          "Stage 3/3: Critic Agent is evaluating the submissions..."
        );
      }, 90000); // 1.5 хвилини
    }
    // Очищення таймерів
    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
    };
  }, [status]);

  const fetchResults = async (currentGoalId) => {
    try {
      console.log(`Polling for results of goal: ${currentGoalId}`);
      const response = await apiClient.get(`/goals/${currentGoalId}`);
      console.log("Polling response:", response.data);

      if (response.data.status === "COMPLETED") {
        setStatus("completed");
        setFinalResults(response.data.results || []);
      }
    } catch (err) {
      console.error("Polling Error:", err);
      setError("Failed to fetch results. Please try again later.");
      setStatus("error");
    }
  };

  const handleSubmit = async () => {
    if (!prompt || isLoading) return;

    setIsLoading(true);
    setError("");
    setFinalResults([]);
    setGoalId(null);
    setStatus("idle");

    try {
      const response = await apiClient.post("/goals", { description: prompt });
      setGoalId(response.data.goal_id);
      setStatus("processing");
    } catch (err) {
      console.error("API Error:", err);
      const errorMessage =
        err.response?.data?.error || "An unknown error occurred.";
      setError(`Failed to submit goal: ${errorMessage}`);
      setStatus("error");
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
        {status !== "processing" && status !== "completed" && (
          <>
            <p className="instructions">
              Describe your goal, and the agent economy will bring it to life.
            </p>
            <textarea
              className="prompt-input"
              placeholder="e.g., I need a logo and slogan for my new coffee brand 'Cosmic Brew'..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </>
        )}

        <button
          className="submit-button"
          onClick={handleSubmit}
          disabled={isLoading || (status !== "processing" && !prompt.trim())}
        >
          {isLoading
            ? "Submitting..."
            : status === "processing"
            ? "Processing..."
            : "Launch KratosNOVA"}
        </button>
      </main>

      <footer className="results-area">
        {status === "processing" && (
          <div className="result-processing">
            <p>
              <strong>Goal accepted! The agent economy is at work.</strong>
            </p>
            <p>
              Your Goal ID is: <code>{goalId}</code>
            </p>
            <p className="processing-status">{processingMessage}</p>{" "}
            {/* Використовуємо новий стан */}
            <div className="loader"></div>
          </div>
        )}
        {status === "completed" && (
          <div className="result-success">
            <h3>Mission Accomplished!</h3>
            {finalResults.map((result, index) => (
              <div key={index} className="result-card">
                <h4>
                  {result.contract_type === "IMAGE"
                    ? "Generated Logo"
                    : "Generated Slogan"}
                </h4>
                {result.contract_type === "IMAGE" ? (
                  <p>
                    <i>(Image will be displayed here in the next step)</i>
                    <br />
                    S3 Key: <code>{result.submission_data}</code>
                  </p>
                ) : (
                  <p className="slogan">"{result.submission_data}"</p>
                )}
              </div>
            ))}
          </div>
        )}
        {error && (
          <div className="result-error">
            <p>
              <strong>Error:</strong> {error}
            </p>
          </div>
        )}
      </footer>
    </div>
  );
}

export default App;
