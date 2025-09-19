import { useState, useEffect } from "react";
import axios from "axios";
import "./LeaderboardPage.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const apiClient = axios.create({ baseURL: API_BASE_URL });

function LeaderboardPage() {
  const [agents, setAgents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await apiClient.get("/agents/leaderboard");
        setAgents(response.data.agents || []);
      } catch (error) {
        console.error("Failed to fetch leaderboard", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchAgents();
    const intervalId = setInterval(fetchAgents, 20000); // Оновлювати кожні 20 секунд
    return () => clearInterval(intervalId);
  }, []);

  if (isLoading) return <p>Loading leaderboard...</p>;

  return (
    <div className="leaderboard-container">
      <h1>Agent Hall of Fame 🏆</h1>
      <table className="leaderboard-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Agent ID</th>
            <th>Type</th>
            <th>Reputation</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent, index) => (
            <tr key={agent.agent_id}>
              <td>{index + 1}</td>
              <td>{agent.agent_id}</td>
              <td>{agent.agent_type}</td>
              <td>{agent.reputation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export default LeaderboardPage;
