import { useState, useEffect } from "react";
import axios from "axios";
import "./MarketplacePage.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const apiClient = axios.create({ baseURL: API_BASE_URL });

function MarketplacePage() {
  const [data, setData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchData = async () => {
    try {
      const response = await apiClient.get("/marketplace");
      setData(response.data.marketplace_data || []);
    } catch (error) {
      console.error("Failed to fetch marketplace data", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData(); // Завантажити дані одразу
    const intervalId = setInterval(fetchData, 15000); // Оновлювати кожні 15 секунд
    return () => clearInterval(intervalId); // Очищення
  }, []);

  if (isLoading) return <p>Loading marketplace...</p>;

  return (
    <div className="marketplace-container">
      <h1>Live Marketplace</h1>
      {data.length === 0 ? (
        <p>No open contracts at the moment. Check back soon!</p>
      ) : (
        data.map((contract) => (
          <div key={contract.contract_id} className="contract-card-large">
            <h3>
              {contract.title}{" "}
              <span className={`status-${contract.status}`}>
                {contract.status}
              </span>
            </h3>
            <p>
              <strong>Type:</strong> {contract.contract_type}
            </p>
            <p>
              <strong>Budget:</strong> {contract.budget} credits
            </p>
            <p>
              <strong>Description:</strong> {contract.description}
            </p>
            <h4>Submissions ({contract.submissions.length})</h4>
            {contract.submissions.length > 0 ? (
              <ul className="submission-list">
                {contract.submissions.map((sub) => (
                  <li key={sub.submission_id}>
                    <code>{sub.submission_data}</code> by {sub.agent_id}
                  </li>
                ))}
              </ul>
            ) : (
              <p>
                <i>No submissions yet.</i>
              </p>
            )}
          </div>
        ))
      )}
    </div>
  );
}
export default MarketplacePage;
