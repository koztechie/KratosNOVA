# KratosNOVA - Budget Planning & Cost Analysis (v2 - Updated Pricing)

This document provides a detailed cost estimation for running the KratosNOVA MVP, ensuring the project stays within the provided $100 AWS Promotional Credits for the hackathon.

_All prices are based on the official AWS Bedrock pricing page for the `us-east-1` (N. Virginia) region as of September 2025._

---

## 1. Core Assumptions for a Single Cycle

To calculate the cost of one full "goal-to-result" cycle, we make the following assumptions based on our MVP scope:

- **Agent-Manager:** 1 invocation using Claude 3 Sonnet.
  - Input prompt (goal, instructions): ~1,000 tokens.
  - Output JSON (2 contracts): ~500 tokens.
- **Agent-Freelancers:** We assume 5 agents of each type respond to the open contracts for healthy competition.
  - **5x Artist Agents:** 5 invocations of **Stable Image Core** (1 image each).
  - **5x Copywriter Agents:** 5 invocations of Claude 3 Haiku.
    - Input prompt (task description): ~500 tokens per agent.
    - Output JSON (5 slogans): ~200 tokens per agent.
- **Agent-Critic:** 1 invocation using Claude 3 Sonnet.
  - Input prompt (task, all submissions): ~3,000 tokens.
  - Output JSON (winner selection): ~100 tokens.
- **Infrastructure (Lambda, DynamoDB, S3, API Gateway):** Costs are considered negligible as they fall well within the AWS Free Tier.

---

## 2. Cost Breakdown per Single Cycle (Based on Official Pricing)

| Component                | Model                 | Calculation                                         |  Cost (USD) |
| ------------------------ | --------------------- | --------------------------------------------------- | ----------: |
| **1. Agent-Manager**     | Claude 3 Sonnet       | (1K in _ $0.003) + (0.5K out _ $0.015)              |     $0.0105 |
| **2. Artist Agents**     | **Stable Image Core** | **5 images \* $0.04**                               | **$0.2000** |
| **3. Copywriter Agents** | Claude 3 Haiku        | 5 _ [(0.5K in _ $0.00025) + (0.2K out \* $0.00125)] |     $0.0019 |
| **4. Agent-Critic**      | Claude 3 Sonnet       | (3K in _ $0.003) + (0.1K out _ $0.015)              |     $0.0105 |
| **Total**                |                       |                                                     | **~$0.223** |

---

## 3. Total Estimated Cost & Conclusion

- **Cost per Single Full Cycle:** Approximately **$0.23** (rounded up for safety).
- **Estimated Cost for 100 Cycles:** 100 \* $0.23 = **$23.00**.

### Verdict: ✅ **PASSED**

The updated total estimated cost of **$23.00** for 100 full, competitive cycles is still comfortably within the **$100 AWS credit budget**. This provides a robust safety margin of **$77.00** for development, extensive testing, and unforeseen complexities. The project remains financially viable for the hackathon.
