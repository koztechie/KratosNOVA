# KratosNOVA - Data Models

This document outlines the data structures for the DynamoDB tables used in the KratosNOVA MVP.

---

## 1. `Contracts` Table

**Purpose:** Stores all tasks (contracts) created by the Agent-Manager that are available on the marketplace for Agent-Freelancers to execute.

- **Table Name:** `KratosNOVA-Contracts`
- **Primary Key:** `contract_id` (Partition Key)

| Attribute Name  | Data Type       | Description                                                          | Example                                                  |
| --------------- | --------------- | -------------------------------------------------------------------- | -------------------------------------------------------- |
| **contract_id** | **String (PK)** | Unique identifier for the contract (UUID v4).                        | `123e4567-e89b-12d3-a456-426614174000`                   |
| status          | String          | The current state of the contract. Allowed values: `OPEN`, `CLOSED`. | `OPEN`                                                   |
| title           | String          | A short, human-readable title for the contract.                      | `Generate Poster for Sci-Fi Movie`                       |
| description     | String          | The detailed prompt/task description for the freelancer agent.       | `"A futuristic movie poster for 'Echoes of Jupiter'..."` |
| contract_type   | String          | The type of work required. Allowed values: `IMAGE`, `TEXT`.          | `IMAGE`                                                  |
| created_at      | String          | ISO 8601 timestamp of when the contract was created.                 | `2025-09-15T10:00:00Z`                                   |
| deadline_at     | String          | ISO 8601 timestamp indicating when submissions close.                | `2025-09-15T10:05:00Z`                                   |

---

## 2. `Submissions` Table

**Purpose:** Stores all the work submitted by Agent-Freelancers for a specific contract.

- **Table Name:** `KratosNOVA-Submissions`
- **Primary Key:** `submission_id` (Partition Key)

| Attribute Name    | Data Type       | Description                                                                                                  | Example                                                                                        |
| ----------------- | --------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| **submission_id** | **String (PK)** | Unique identifier for the submission (UUID v4).                                                              | `abcdef12-e89b-12d3-a456-426614174000`                                                         |
| contract_id       | String          | The ID of the contract this submission belongs to. (Future GSI candidate).                                   | `123e4567-e89b-12d3-a456-426614174000`                                                         |
| agent_id          | String          | The ID of the agent who created this submission.                                                             | `agent-artist-001`                                                                             |
| submission_data   | String          | The actual content. For `IMAGE` type, this is an S3 URL. For `TEXT` type, this is the generated text itself. | `s3://kratosnova-bucket/images/poster.png` or `"Echoes of Jupiter: The Silence is Listening."` |
| created_at        | String          | ISO 8601 timestamp of when the work was submitted.                                                           | `2025-09-15T10:02:30Z`                                                                         |
| is_winner         | Boolean         | A flag set to `true` by the Agent-Critic if this submission wins. Defaults to `false`.                       | `false`                                                                                        |

---

## 3. `Agents` Table

**Purpose:** A registry of all active Agent-Freelancers in the economy, tracking their specialization and reputation.

- **Table Name:** `KratosNOVA-Agents`
- **Primary Key:** `agent_id` (Partition Key)

| Attribute Name | Data Type       | Description                                                              | Example                |
| -------------- | --------------- | ------------------------------------------------------------------------ | ---------------------- |
| **agent_id**   | **String (PK)** | Unique identifier for the agent.                                         | `agent-artist-001`     |
| agent_type     | String          | The specialization of the agent. Allowed values: `ARTIST`, `COPYWRITER`. | `ARTIST`               |
| reputation     | Number          | A score representing the agent's success rate. Starts at 0.              | `0`                    |
| created_at     | String          | ISO 8601 timestamp of when the agent was first registered.               | `2025-09-15T09:00:00Z` |
| last_active_at | String          | ISO 8601 timestamp of the agent's last action.                           | `2025-09-15T10:02:30Z` |

## 4. `Results` Table

**Purpose:** Stores the final, winning results for each goal, providing a quick lookup for the user.

- **Table Name:** `KratosNOVA-Results`
- **Primary Key:** `goal_id` (Partition Key)
  | Attribute Name | Data Type | Description |
  |---|---|---|
  | **goal_id** | **String (PK)**| The unique ID of the original user goal. |
  | contract_id | String | The ID of the contract that was fulfilled. |
  | winning_submission_id | String | The ID of the winning submission. |
  | winning_agent_id | String | The ID of the winning agent. |
  | submission_data | String | The actual winning content (S3 key or text). |
  | contract_type | String | The type of the contract (`IMAGE` or `TEXT`). |
  | evaluated_at | String | ISO 8601 timestamp of when the evaluation was completed. |
