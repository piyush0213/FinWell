import json
import requests
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


# --- COMPANY NAME HELPER ---
def get_company_name(ticker):
    names = {
        "SUNPHARMA.NS": "Sun Pharma",
        "ICICIBANK.NS": "ICICI Bank",
        "HDFCBANK.NS": "HDFC Bank",
        "RELIANCE.NS": "Reliance Industries",
        "TCS.NS": "Tata Consultancy Services",
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "GOOG": "Google",
        "AMZN": "Amazon",
        "META": "Meta Platforms",
        "HAL.NS": "Hindustan Aeronautics",
        "VEDL.NS": "Vedanta Ltd",
    }
    return names.get(ticker.upper(), ticker.split(".")[0])

# --- LLM SETUP ---
GEMINI_KEY = os.getenv("GEMINI_KEY")
if not GEMINI_KEY or GEMINI_KEY == "your_gemini_api_key_here":
    print("⚠️  WARNING: GEMINI_KEY not set in .env. Stock analysis will not work.")
    print("   Get a key from https://aistudio.google.com/apikey and add it to .env")
    GEMINI_KEY = None

llm = LLM(
    model="google/gemini-2.0-flash",
    api_key=GEMINI_KEY or "placeholder",
    temperature=0.0
)

# --- TOOL DEFINITION ---
class YahooFinanceArgs(BaseModel):
    endpoint: str = Field(..., description="e.g. /stock/financial-statement")
    payload: dict = Field(..., description="POST body")

class YahooFinanceTool(BaseTool):
    name: str = "Yahoo Finance API Tool"
    description: str = (
        "POST to the local Yahoo MCP FastAPI server.\n"
        "Args:\n"
        "  • endpoint – '/stock/financial-statement', '/stock/holder-info', '/stock/info'\n"
        "  • payload  – JSON dict with required fields"
    )
    args_schema: type = YahooFinanceArgs

    def _run(self, endpoint: str, payload: dict):
        url = f"http://localhost:8000{endpoint}"
        print(f"Fetching from {url} with payload {payload}...")
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            print(f"Fetched successfully.")
            return response.json()
        except Exception as e:
            print(f"Fetch failed: {e}")
            return f"Error: {str(e)}"

yahoo_tool = YahooFinanceTool()

# --- AGENT DEFINITION ---
selector_agent = Agent(
    role="Profile and Ticker Selector",
    goal="In each turn, review the profile list and user reply. For each missing field among risk appetite (low/medium/high), time horizon (short/medium/long), and primary goal (income/growth/moonshot), ask the next relevant question. If the user's latest reply contains a relevant answer, return it in the format field-value (e.g., risk-high) for your driver code to append to profile. Ignore irrelevant answers. Once all 3 fields are present in the profile, ask for the ticker. When the user replies, extract and return ONLY the ticker symbol from the user's message (like 'APPL', 'HAL.NS', 'VEDL.NS'), or return 'UNKNOWN' if not found.",
    backstory="You are a concise, context-aware onboarding assistant. You always check what info is missing in the profile, ask for it one by one, and only return relevant info to be appended to profile. For ticker, extract it robustly from any user phrasing.",
    tools=[],
    llm=llm,
    verbose=True,
)

def make_analyst_agent(company_name, display_ticker):
    return Agent(
        role="Equity Research Analyst",
        goal=f"Turn raw JSON statements, holder info, and stock info for {company_name} ({display_ticker}) into a concise yet insightful investment memo.",
        backstory=(
            "15-year sell-side analyst, CFA. Skilled at bottom-up fundamental analysis, ratio work, and clear communication."
        ),
        tools=[],
        llm=llm,
        verbose=True,
    )

# --- FETCHING FUNCTION ---
def fetch_all(ticker):
    balance_json = yahoo_tool._run(
        endpoint="/stock/financial-statement",
        payload={'ticker': ticker, 'financial_type': 'balance_sheet'}
    )
    income_json = yahoo_tool._run(
        endpoint="/stock/financial-statement",
        payload={'ticker': ticker, 'financial_type': 'income_stmt'}
    )
    cashflow_json = yahoo_tool._run(
        endpoint="/stock/financial-statement",
        payload={'ticker': ticker, 'financial_type': 'cashflow'}
    )
    holder_json = yahoo_tool._run(
        endpoint="/stock/holder-info",
        payload={'ticker': ticker, 'holder_type': 'major_holders'}
    )
    stock_json = yahoo_tool._run(
        endpoint="/stock/info",
        payload={'ticker': ticker}
    )
    return {
        'balance_json': balance_json,
        'income_json': income_json,
        'cashflow_json': cashflow_json,
        'holder_json': holder_json,
        'stock_json': stock_json
    }

# --- ANALYSIS PROMPT ---
def make_analysis_task(company_name, profile):
    # Add the weights JSON as a string
    archetype_weights_json = """
ARCHETYPE_WEIGHTS = {
    "Defensive Income": {
        "free_cash_flow": 3,
        "debt_equity": 3,
        "net_cash_debt": 2,
        "roe": 2,
        "current_ratio": 2,
        "intangibles_assets": 1,
        "pe_ratio": 1,
        "revenue_yoy": 1
    },
    "Core Growth": {
        "roe": 3,
        "revenue_yoy": 3,
        "free_cash_flow": 2,
        "debt_equity": 2,
        "current_ratio": 1,
        "pe_ratio": 1,
        "intangibles_assets": 1
    },
    "Opportunistic Alpha": {
        "revenue_yoy": 3,
        "roe": 2,
        "free_cash_flow": 2,
        "debt_equity": 1,
        "intangibles_assets": 1,
        "pe_ratio": 1
    }
}
"""
    analysis_prompt = f"""
You are a professional equity research analyst at a top investment bank.

**You will receive:**
- User profile: {profile}
- A balance sheet (list of dicts, first = most recent)
- An income statement (list of dicts, first = most recent)
- A cash flow statement (list of dicts, first = most recent)
- Major holders info (dict)
- General stock info (dict: industry, sector, exchange, market cap, etc.)

**Instructions:**
1. **Classify the user** as one of: 'Defensive Income', 'Core Growth', or 'Opportunistic Alpha', using their profile.
2. **Calculate all the listed metrics** using the latest and previous (where needed) financial data. *Show formulas step by step.*
3. **Use the following weights table to prioritize and score metrics for this user:**  
{archetype_weights_json}
   - For the assigned archetype, score/prioritize the metrics accordingly.
4. **Suitability:** Assess and explain in detail why the stock is or isn't suitable for this user's archetype, referencing the most weighted metrics.
5. **Final call:** Assign a buy/hold/sell rating with a clear rationale for this user and archetype.

**Output strictly in the following markdown format:**  
=== INVESTMENT MEMO ===

{company_name} – Quick Take (FY <YEAR>)
<one-sentence elevator pitch>

Investor Archetype: <archetype>  
Suitability: <explanation for this user/archetype>

Key Ratios

| Metric                | Value      |
|-----------------------|------------|
| Revenue (₹ cr)        | …          |
| Revenue YoY %         | …          |
| Net-profit margin %   | …          |
| ROE %                 | …          |
| Debt/Equity           | …          |
| Net cash/(debt)       | …          |
| Current ratio         | …          |
| Intangibles % assets  | …          |
| Free Cash Flow        | …          |
| EPS (Diluted)         | …          |
| PE Ratio              | …          |
| Market Cap (₹)        | …          |
| Cap Category          | …          |

Shareholder Summary

- Major Holders: <summary from holder_json>
- Free float: <float info from stock_json>
- Sector/Industry: <from stock info>

What Stands Out
• …

Risks / Watch-list
• …

Rating: <BUY/HOLD/SELL> – <reason>
**Do NOT output any code, Python, JSON, or sample calculations at the end. Only output the memo in markdown as specified above.**
"""

    return Task(
        description=analysis_prompt,
        expected_output="Investment memo including archetype, suitability, metrics, explanation, and a final rating.",
        agent=None,
        context_keys=["balance_json", "income_json", "cashflow_json", "holder_json", "stock_json"],
        share_context=False,
    )



def main():
    print("\nWelcome! Let's profile your investing style for a personalized analysis.")
    profile = {}

    fields = [
        ("risk", "What's your risk appetite? (low/medium/high)"),
        ("horizon", "What is your investment time horizon? (short/medium/long)"),
        ("goal", "What's your primary goal? (income/growth/moonshot)")
    ]
    valid_map = {
        "risk": ["risk-low", "risk-medium", "risk-high"],
        "horizon": ["horizon-short", "horizon-medium", "horizon-long"],
        "goal": ["goal-income", "goal-growth", "goal-moonshot"]
    }

    def next_missing_field(profile):
        for k, _ in fields:
            if k not in profile:
                return k
        return None

    # --- Profile ONCE ---
    while True:
        missing = next_missing_field(profile)
        if missing:
            question = dict(fields)[missing]
            print(question)
            user_reply = input("You: ").strip()

            agent_prompt = f"""
Given PROFILE: {profile}
CURRENT FIELD TO FILL: {missing.upper()}
USER REPLY: "{user_reply}"

RULES:
- Only extract a valid value for the current field '{missing.upper()}'.
- Output must be one of: {', '.join(valid_map[missing])} or NONE.
- If a valid value is found, reply with it (e.g., '{missing}-medium').
- If not, reply with NONE.
"""
            task = Task(
                description=agent_prompt,
                expected_output=f"One of {valid_map[missing]} or NONE.",
                agent=selector_agent,
                context_keys=[],
                share_context=False,
            )
            crew = Crew(agents=[selector_agent], tasks=[task], verbose=False)
            agent_output = crew.kickoff()
            if hasattr(agent_output, "final_output"):
                agent_output = agent_output.final_output
            elif not isinstance(agent_output, str):
                agent_output = str(agent_output)
            agent_output = agent_output.strip().lower()

            if agent_output in valid_map[missing]:
                profile[missing] = agent_output
            elif agent_output == "none":
                print("Sorry, I didn't catch that. Please answer the question directly.")
                continue
            else:
                print("Sorry, please answer directly with your risk/horizon/goal.")
                continue
        else:
            break

    print(f"\nProfile captured: {profile}")

    # --- LOOP: Analyze as many stocks as user wants ---
    while True:
        try:
            print("\nWhich stock would you like analyzed? (e.g., 'analyze AAPL', 'do HAL.NS', 'let's start with VEDL.NS')")
            user_reply = input("You: ").strip()

            agent_prompt = f"""
PROFILE: {profile}
USER REPLY: "{user_reply}"

RULES:
- Extract and return ONLY the ticker symbol from the user's latest message, or 'UNKNOWN' if no ticker is found.
- Example replies: 'TCS.NS', 'AAPL', 'UNKNOWN'
"""
            task = Task(
                description=agent_prompt,
                expected_output="A ticker symbol or 'UNKNOWN'.",
                agent=selector_agent,
                context_keys=[],
                share_context=False,
            )
            crew = Crew(agents=[selector_agent], tasks=[task], verbose=False)
            agent_output = crew.kickoff()
            if hasattr(agent_output, "final_output"):
                agent_output = agent_output.final_output
            elif not isinstance(agent_output, str):
                agent_output = str(agent_output)
            ticker = agent_output.strip().upper()

            if not ticker or ticker == "UNKNOWN":
                print("Sorry, couldn't identify a valid ticker. Please try again (e.g., 'analyze AAPL', 'do HAL.NS', etc.).")
                continue

            company_name = get_company_name(ticker)
            display_ticker = ticker

            # --- Fetch financials, holders, and stock info ---
            print(f"\n>>> Fetching all financial, holder, and stock info for {company_name} ({display_ticker})...\n")
            data = fetch_all(ticker)
            print("All data fetched successfully.\n")

            # --- Run analyst agent and analysis task ---
            analyst_agent = make_analyst_agent(company_name, display_ticker)
            analysis_task = make_analysis_task(company_name, profile)
            analysis_task.agent = analyst_agent

            print(">>> Running LLM for analysis...\n")
            crew = Crew(
                agents=[analyst_agent],
                tasks=[analysis_task],
                initial_state={
                    "balance_json": data['balance_json'],
                    "income_json": data['income_json'],
                    "cashflow_json": data['cashflow_json'],
                    "holder_json": data['holder_json'],
                    "stock_json": data['stock_json'],
                },
                verbose=True,
            )
            result = crew.kickoff()
            print("\n=== INVESTMENT MEMO ===\n")
            if isinstance(result, dict):
                print(result.get("Final Answer") or result)
            else:
                print(result if result else "No output from LLM. Check context size or API limits.")

        except KeyboardInterrupt:
            print("\nExiting! Thank you for using the analyst tool.")
            break
if __name__ == "__main__":
    main()

