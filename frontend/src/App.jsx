import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

// Get the API base URL from environment variables
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// Create a pre-configured axios instance for API calls
const apiClient = axios.create({ baseURL: API_BASE_URL });

/**
 * A dedicated component to fetch and display an image from a private S3 bucket
 * using a presigned URL.
 * @param {{s3Key: string}} props - The S3 object key for the image.
 */
function ResultImage({ s3Key }) {
  const [imageUrl, setImageUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchUrl = async () => {
      if (!s3Key) return;
      try {
        const response = await apiClient.get("/submissions/download-url", {
          params: { key: s3Key },
        });
        setImageUrl(response.data.download_url);
      } catch (err) {
        console.error("Failed to get download URL for key:", s3Key, err);
        setError("Could not load image.");
      }
    };
    fetchUrl();
  }, [s3Key]); // This effect runs whenever the s3Key changes

  if (error) return <p className="result-error">{error}</p>;
  if (!imageUrl) return <p>Loading image...</p>;

  return (
    <img src={imageUrl} alt="Generated Artwork" className="result-image" />
  );
}

function App() {
  // State for the input form
  const [prompt, setPrompt] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // State for tracking the lifecycle of a goal
  const [goalId, setGoalId] = useState(null);
  const [status, setStatus] = useState("idle"); // 'idle', 'processing', 'completed', 'error'
  const [processingMessage, setProcessingMessage] = useState("");
  const [finalResults, setFinalResults] = useState([]);
  const [error, setError] = useState("");

  // Effect to handle polling for results when a goal is processing
  useEffect(() => {
    let intervalId = null;
    if (goalId && status === "processing") {
      console.log(`Starting polling for goalId: ${goalId}`);
      intervalId = setInterval(() => fetchResults(goalId), 10000); // Poll every 10 seconds
    }
    // Cleanup function to stop polling when the component unmounts or status changes
    return () => {
      if (intervalId) {
        console.log("Stopping polling.");
        clearInterval(intervalId);
      }
    };
  }, [goalId, status]);

  // Effect to update the user-facing status message during processing
  useEffect(() => {
    let timer1, timer2;
    if (status === "processing") {
      setProcessingMessage(
        "Stage 1/3: Agent-Manager is deconstructing your goal..."
      );
      timer1 = setTimeout(() => {
        setProcessingMessage(
          "Stage 2/3: Freelancer Agents are working on the contracts..."
        );
      }, 15000); // 15 seconds
      timer2 = setTimeout(() => {
        setProcessingMessage(
          "Stage 3/3: Critic Agent is evaluating the submissions..."
        );
      }, 90000); // 1.5 minutes
    }
    // Cleanup function to clear timers if the process finishes early
    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
    };
  }, [status]);

  // Fetches the results for a given goal ID
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

  // Handles the submission of the initial goal
  const handleSubmit = async () => {
    if (!prompt.trim() || isLoading) return;

    // Reset state for a new submission
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
        <h1>KratosNOVA 🚀!</h1>
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
            <p className="processing-status">{processingMessage}</p>
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
                  <ResultImage s3Key={result.submission_data} />
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
