# KratosNOVA 🚀

> A decentralized economy of AI agents for the AWS AI Agent Global Hackathon. This project explores emergent problem-solving through market-based competition.

## 📜 Overview

KratosNOVA is not a single monolithic AI. It's a complex adaptive system where hundreds of specialized AI agents compete and collaborate in a market-based environment to solve high-level goals. This project is our submission to the **AWS AI Agent Global Hackathon**, designed to showcase the full potential of **Amazon Bedrock AgentCore** as an orchestrator of complex, multi-agent systems.

---

## ✨ Key Features (Planned)

### 🎯 Minimum Viable Product (MVP) Scope for the Hackathon

To ensure a successful and functional submission, the initial version of KratosNOVA will focus on a single, end-to-end user story: **"As a user, I want to request a simple promotional package (a poster and a slogan) for a given topic, and receive a result selected by the AI agent economy."**

This core functionality will be achieved with the following components:

- **1. User Goal:**

  - The user submits a single text prompt, e.g., "An indie sci-fi movie named 'Echoes of Jupiter'".

- **2. The "Agent-Manager" (1 agent):**

  - Receives the user's goal.
  - Performs **one** deconstruction action.
  - Creates exactly **two** fixed contracts on the marketplace:
    1.  A contract of type `IMAGE` to generate a movie poster.
    2.  A contract of type `TEXT` to generate five slogan options.

- **3. The "Agent-Freelancers" (2 types of agents):**

  - **`Artist Agents`**: A pool of agents that only look for `IMAGE` contracts. Upon finding one, they will use the Amazon Bedrock (Stable Diffusion) API to generate a poster.
  - **`Copywriter Agents`**: A pool of agents that only look for `TEXT` contracts. Upon finding one, they will use the Amazon Bedrock (Claude 3 Haiku) API to generate slogans.

- **4. The "Agent-Critic" (1 agent):**

  - After a set time, this agent reviews all submissions for both contracts.
  - It will use Amazon Bedrock (Claude 3 Sonnet) to select the **one** best poster and the **one** best slogan.
  - It will mark the winning agents and store the final result.

- **5. The Result:**
  - The user can view the final selected package: one poster and one slogan.

**What is explicitly OUT of MVP scope:**

- Dynamic budget allocation.
- Complex, multi-step goal deconstruction.
- Reputation system influencing agent selection.
- Agents creating their own tools or modifying their logic.
- User accounts and authentication.

#### MVP Workflow

```
[User] -> "Indie sci-fi movie: 'Echoes of Jupiter'" -> [API Gateway]
   |
   v
[Agent-Manager (Lambda + Bedrock Sonnet)]
   |
   +--> Creates Contract #1: { type: IMAGE, prompt: "Poster for..." }
   |
   +--> Creates Contract #2: { type: TEXT, prompt: "Slogans for..." }
   |
   v
[Marketplace (DynamoDB)]
   ^                                      ^
   | (reads contracts)                    | (reads contracts)
   |                                      |
[Artist Agents (Lambda + Bedrock SD)]   [Copywriter Agents (Lambda + Bedrock Haiku)]
   |                                      |
   | (submits work)                       | (submits work)
   v                                      v
[Marketplace (DynamoDB)] <-- (reviews submissions) -- [Agent-Critic (Lambda + Bedrock Sonnet)]
   |
   v
[Final Result (DynamoDB)]
   ^
   |
[User checks results via API]
```

---

## 🏛️ Architecture (Draft)

_A high-level overview of the planned architecture. The final diagram will be placed here._

![Architecture Diagram Placeholder](https://via.placeholder.com/800x400.png?text=Architecture+Diagram+Coming+Soon)

---

## 🛠️ Tech Stack

The technology stack for KratosNOVA is chosen to maximize development speed, leverage the full power of the AWS ecosystem, and ensure a robust, scalable solution.

| Category                   | Technology / Service         | Rationale                                                                                                                        |
| :------------------------- | :--------------------------- | :------------------------------------------------------------------------------------------------------------------------------- |
| **AI Core**                | **Amazon Bedrock**           | Provides managed access to powerful foundation models (Claude, Stable Diffusion) which are the "brains" of our agents.           |
|                            | **Amazon Bedrock AgentCore** | The central piece of our project, used by the Agent-Manager for advanced reasoning, planning, and orchestration of other agents. |
| **Backend**                | **Python 3**                 | The primary language for all backend logic (agents), chosen for its excellent AWS SDK (Boto3) and clean syntax.                  |
|                            | **AWS Lambda**               | The serverless compute engine for all our agents. It ensures scalability and cost-effectiveness (pay-per-invocation).            |
| **Database**               | **Amazon DynamoDB**          | A fully managed NoSQL database for storing contracts, submissions, and agent data, chosen for its speed and scalability.         |
| **API**                    | **Amazon API Gateway**       | Provides a secure and scalable REST API endpoint for user and agent interactions.                                                |
| **Storage**                | **Amazon S3**                | Used for storing generated artifacts, primarily images created by Artist Agents.                                                 |
| **Infrastructure as Code** | **AWS CDK (Python)**         | Allows us to define our entire cloud infrastructure in Python, keeping the project consistent and easily reproducible.           |
| **Frontend**               | **React + Vite**             | A modern, high-performance combination for building a fast and responsive user interface to interact with the system.            |

---

## 🏁 Getting Started

_(Instructions on how to set up and run the project locally will be added here.)_

---

## 👥 Authors

- **Eugene Kozlovsky** - [https://github.com/koztechie](https://github.com/koztechie)
