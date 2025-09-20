import { useState, useEffect } from "react";
import axios from "axios";
import "./HomePage.css";

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
  }, [s3Key]);

  if (error) return <p className="result-error">{error}</p>;
  if (!imageUrl) return <p>Loading image...</p>;

  return (
    <img src={imageUrl} alt="Generated Artwork" className="result-image" />
  );
}

function HomePage() {
  // State for the user's current input
  const [userInput, setUserInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // State to manage the entire process lifecycle
  const [conversation, setConversation] = useState({
    id: null,
    history: [],
    status: "idle", // idle, awaiting_user_input, processing, completed, error
  });

  const [finalResults, setFinalResults] = useState([]);

  // Effect to handle polling for results when a goal is processing
  useEffect(() => {
    let intervalId = null;
    if (conversation.id && conversation.status === "processing") {
      console.log(`Starting polling for goalId: ${conversation.id}`);
      intervalId = setInterval(() => fetchResults(conversation.id), 10000);
    }
    return () => {
      if (intervalId) {
        console.log("Stopping polling.");
        clearInterval(intervalId);
      }
    };
  }, [conversation.id, conversation.status]);

  const fetchResults = async (goalId) => {
    try {
      console.log(`Polling for results of goal: ${goalId}`);
      const response = await apiClient.get(`/goals/${goalId}`);
      console.log("Polling response:", response.data);
      if (response.data.status === "COMPLETED") {
        setConversation((prev) => ({ ...prev, status: "completed" }));
        setFinalResults(response.data.results || []);
      }
    } catch (err) {
      console.error("Polling Error:", err);
      setError("Failed to fetch results.");
      setConversation((prev) => ({ ...prev, status: "error" }));
    }
  };

  // Handles both starting a new conversation and sending replies
  const handleSubmit = async () => {
    if (!userInput.trim() || isLoading) return;
    setIsLoading(true);
    setError("");

    const currentHistory = [
      ...conversation.history,
      { role: "user", content: userInput },
    ];
    let endpoint = "/goals";
    let payload = { description: userInput };

    if (conversation.id && conversation.status === "awaiting_user_input") {
      endpoint = `/goals/conversation/${conversation.id}`;
      payload = { message: userInput, history: conversation.history };
    }

    try {
      const response = await apiClient.post(endpoint, payload);
      setUserInput(""); // Clear input after sending

      if (response.status === 202 && response.data.goal_id) {
        // Goal was accepted directly and we got a goal_id to poll
        setConversation({
          id: response.data.goal_id,
          history: currentHistory,
          status: "processing",
        });
      } else if (response.status === 200 && response.data.conversation_id) {
        // AI is asking a clarifying question
        setConversation({
          id: response.data.conversation_id,
          history: [
            ...currentHistory,
            { role: "assistant", content: response.data.next_question },
          ],
          status: "awaiting_user_input",
        });
      } else {
        // Fallback for unexpected responses
        throw new Error("Received an unexpected response from the server.");
      }
    } catch (err) {
      console.error("API Error:", err);
      const errorMessage =
        err.response?.data?.error || "An unknown error occurred.";
      setError(errorMessage);
      setConversation((prev) => ({ ...prev, status: "error" }));
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setUserInput("");
    setIsLoading(false);
    setError("");
    setConversation({ id: null, history: [], status: "idle" });
    setFinalResults([]);
  };

  return (
    <div className="container">
      <header>
        <h1>KratosNOVA 🚀</h1>
        <p>The Autonomous AI Agent Economy</p>
      </header>

      <main className="interaction-area">
        {conversation.status === "idle" && (
          <p className="instructions">
            Describe your goal, and I will ask clarifying questions to help you
            get the best results.
          </p>
        )}

        <div className="chat-history">
          {conversation.history.map((msg, index) => (
            <div key={index} className={`chat-message ${msg.role}`}>
              <p>{msg.content}</p>
            </div>
          ))}
        </div>

        {conversation.status !== "processing" &&
          conversation.status !== "completed" && (
            <div className="input-form">
              <textarea
                className="prompt-input"
                placeholder={
                  conversation.status === "awaiting_user_input"
                    ? "Your answer..."
                    : "e.g., I need a logo for my coffee shop..."
                }
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                disabled={isLoading}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
              />
              <button
                className="submit-button"
                onClick={handleSubmit}
                disabled={isLoading || !userInput.trim()}
              >
                {isLoading ? "Thinking..." : "Send"}
              </button>
            </div>
          )}
      </main>

      <footer className="results-area">
        {conversation.status === "processing" && (
          <div className="result-processing">
            <p>
              <strong>Goal accepted! The agent economy is at work.</strong>
            </p>
            <p>
              Your Goal ID is: <code>{conversation.id}</code>
            </p>
            <div className="loader"></div>
          </div>
        )}
        {conversation.status === "completed" && (
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
            <button className="reset-button" onClick={handleReset}>
              Start a New Goal
            </button>
          </div>
        )}
        {error && (
          <div className="result-error">
            <p>
              <strong>Error:</strong> {error}
            </p>
            <button className="reset-button" onClick={handleReset}>
              Try Again
            </button>
          </div>
        )}
      </footer>
    </div>
  );
}

export default HomePage;
