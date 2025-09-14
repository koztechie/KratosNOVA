import { useState } from "react";
import "./App.css"; // Ми створимо цей файл

function App() {
  // Створюємо стан для зберігання тексту з поля вводу
  const [prompt, setPrompt] = useState("");

  // Створюємо стан для відстеження завантаження
  const [isLoading, setIsLoading] = useState(false);

  // Функція, яка буде викликатися при натисканні кнопки
  const handleSubmit = () => {
    // Поки що просто виводимо в консоль
    console.log("Submitting goal:", prompt);

    // TODO: Add API call logic here in the next step
    // setIsLoading(true);
    // axios.post(...)
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
          placeholder="e.g., I need marketing assets for a new mobile game called 'CyberDragon'. I need a cool logo of a dragon made of circuits and two powerful slogans."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={isLoading}
        />

        <button
          className="submit-button"
          onClick={handleSubmit}
          disabled={isLoading || !prompt}
        >
          {isLoading ? "Processing..." : "Launch KratosNOVA"}
        </button>
      </main>
    </div>
  );
}

export default App;
