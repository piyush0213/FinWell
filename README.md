# FinWell: Your Personal Finance & Wellness Copilot Using Fetch.ai

---

## Pipeline 

![WhatsApp Image 2025-06-02 at 20 50 19_b246eea7](https://github.com/user-attachments/assets/f420b868-3a9a-46c0-a1e8-cf146590e921)

---


## Overview

**FinWell** is a decentralized AI copilot that empowers users to manage their **stock portfolio**, **crypto assets**, and **health insurance decisions**—all through a conversational agent network built using **uAgents**, **ChatProtocol**, and **ASI1 Mini LLM**.

Whether you’re planning investments or understanding insurance eligibility based on your symptoms, FinWell brings it all together—intelligently.

---

## Domains & Agents

| Domain               | Agent File(s)                       | Purpose                                         |
|---------------------|-------------------------------------|-------------------------------------------------|
| Stocks & Equity   | `analyst_agent.py`, `news_agent.py` | Stock research & news sentiment analysis        |
| Crypto & Wallets  | `solana_wallet_agent`, `token-sentiment-tracker` | Solana balance + Crypto market outlook |
| Health & Insurance| `collector_agent.py`, `analyser_agent.py`, `insurance_agent.py`, `asi1_wrapper_agent.py` | Symptom analysis & plan recommendation |
| Central Routing   | `main_cli_agent.py`, `advisor_agent.py` | Routes user queries to relevant agents         |

---

## Project Structure

```
FinWell/
│
├── advisor/
│   └── advisor_agent.py
├── cli/
│   └── main_cli_agent.py
├── crypto/
│   ├── solana_wallet_agent/
│   └── token-sentiment-tracker/
├── health/
│   ├── collector_agent.py
│   ├── analyser_agent.py
│   ├── insurance_agent.py
│   ├── asi1_wrapper_agent.py
│   └── main.py
├── shared/
│   └── chat_model.py
├── stocks/
│   ├── analyst_agent.py
│   └── news_agent.py
└── README.md
```

---

## Registered Agents on AgentVerse

The following FinWell agents are publicly accessible on [AgentVerse](https://agentverse.ai/) for decentralized communication:

| Agent Name             | Role Description                      | AgentVerse Profile |
|------------------------|----------------------------------------|--------------------|
| `stock_analyst_agent`  | Performs deep equity research and ratio-based valuation analysis | [View Profile](https://agentverse.ai/agents/details/agent1qfsn5hlut0qarzlharnvljprgjqpjytrephh2xy5x9ncdk0w5w4zyhfxrdd/profile) |
| `news_summariser`      | Fetches and summarizes sentiment from the latest stock news articles | [View Profile](https://agentverse.ai/agents/details/agent1qw8zfyazf0ajmsl3gm6gdnm0m824sp6qq6xw9krtvuva9lt5xfvf55c0wce/profile) |
| `solana_wallet_agent`  | Fetches real-time wallet balance and transaction data from Solana | [View Profile](https://agentverse.ai/agents/details/agent1qd97kcgz4lp2kh5kd9jrdp6ltpfuran0fk034ur8fkfe3kqymgua5cj69hw/profile) |
| `solana_token_sentiment_agent` | Tracks market sentiment and token-level insights for Solana assets | [View Profile](https://agentverse.ai/agents/details/agent1q2txzqr7gvr0w0mnp7neqd0hnn0yn447pc9g99m3u6aql00w8kfl23a3qd2/profile) |
| `collector_agent`      | Collects user symptoms for medical triage | [View Profile](https://agentverse.ai/agents/details/agent1qv35ejh6fx6p5smyqzk9ts2qklhkk7gn5470nt0x3s7an3f7jvfxvlf5222/profile) |
| `analyser_agent`       | Evaluates symptoms and prepares health analysis memos | [View Profile](https://agentverse.ai/agents/details/agent1qdkulla80gkjdumy6qp867x6u9wwqkrya0r4eks6zs520lqp6r3g200d83u/profile) |
| `asi1_wrapper_agent`   | Interfaces with ASI1 Mini LLM to provide smart coordination and query resolution | [View Profile](https://agentverse.ai/agents/details/agent1qt69zmtdwud67k7t3nmp353l0y7u8j3q6t9fdy6f4v54258huxre6pnxgwz/profile) |
| `insurance_agent`      | Recommends personalized insurance plans based on user profile and analysis | [View Profile](https://agentverse.ai/agents/details/agent1qww0dg3n263hcvehsw535unx6wmxg0ntduqw8keun78wx5pv87nsckexrpj/profile) |

---

## Setup Instructions

### 1. Clone Repo

```bash
git clone https://github.com/Kavinesh11/FinWell.git
cd FinWell
```

### 2. Create `.env` Files

Place `.env` files in relevant directories, including:

- `ASI_LLM_KEY` for ASI1 wrapper
- `ASI_KEY` for analyst/news agents

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

(Each agent may have its own `requirements.txt`; consolidate as needed)

---

## Run Example Agents

### CLI Agent

```bash
python cli/main_cli_agent.py
```

### Health Stack

```bash
python health/main.py
python health/collector_agent.py
python health/analyser_agent.py
python health/insurance_agent.py
python health/asi1_wrapper_agent.py
```

### Stocks Stack

```bash
python stocks/analyst_agent.py
python stocks/news_agent.py
```

### Crypto Stack

```bash
python crypto/solana_wallet_agent/agent.py
python crypto/token-sentiment-tracker/agent.py
```

---

## AgentVerse Deployment 

You can register agents (e.g., Solana or Token Tracker) to [AgentVerse](https://chat.agentverse.ai/) for public communication.

---

## Project Pitch

>**"FinWell is a decentralized personal finance & wellness agent network that helps users manage stock investments, crypto portfolios, and health coverage through intelligent, autonomous agents. Powered by Fetch.ai’s uAgents framework, ChatProtocol, and ASI1 Mini LLM, it delivers conversational access to expert insights across domains—making your financial and wellness decisions smarter, faster, and fully connected."**

---

## Links
- [Youtube](https://youtu.be/YB_L2Te5VQk)
- [Devpost](https://devpost.com/software/finwell-your-personal-finance-health-copilot-on-fetch-ai)
- [Medium Blog](https://medium.com/@24f2007585/finwell-your-personal-finance-wellness-copilot-e5f26f727f08)

Let FinWell guide your financial and wellness journey.
