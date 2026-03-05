"""
FinWell — Integrated Web Frontend
FastAPI server that serves the dashboard and provides API endpoints for all agent modules.
"""
import os
import sys
import json
import math
import requests
import yfinance as yf
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

app = FastAPI(title="FinWell", description="Personal Finance & Wellness Copilot")

# Serve static files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ── Request/Response Models ──────────────────────────────────────────────────

class HealthQuery(BaseModel):
    message: str
    income: int = None

class StockQuery(BaseModel):
    message: str
    risk_appetite: str = "medium"
    time_horizon: str = "medium-term"
    goal: str = "growth"

class CryptoQuery(BaseModel):
    message: str

class CrisisQuery(BaseModel):
    target_amount: int
    portfolio: list | None = None  # Optional custom portfolio from frontend



# ── Health Endpoint ──────────────────────────────────────────────────────────

def mock_asi_analysis(symptoms: str) -> str:
    """Mock ASI1 LLM analysis for health symptoms."""
    symptom_responses = {
        "headache": "Possible causes: tension headache, migraine, dehydration, eye strain, or sinusitis. "
                    "Recommendations: Rest in a quiet dark room, stay hydrated, take OTC pain relief (ibuprofen/acetaminophen). "
                    "Consult a doctor if headache persists for more than 3 days or is severe.",
        "fever": "Possible causes: viral infection, bacterial infection, flu, or inflammatory condition. "
                 "Recommendations: Rest, drink plenty of fluids, take acetaminophen to reduce fever. "
                 "Seek medical attention if fever exceeds 103F (39.4C) or lasts more than 3 days.",
        "cough": "Possible causes: common cold, bronchitis, allergies, or respiratory infection. "
                 "Recommendations: Stay hydrated, use honey for soothing, try steam inhalation. "
                 "See a doctor if cough produces blood or lasts more than 2 weeks.",
        "chest pain": "WARNING: Chest pain can indicate serious conditions including heart attack. "
                      "If pain is severe, radiating to arm/jaw, or accompanied by shortness of breath, CALL EMERGENCY SERVICES. "
                      "Otherwise, consult a doctor immediately.",
        "stomach": "Possible causes: gastritis, food poisoning, acid reflux, or stress. "
                   "Recommendations: Eat bland foods, avoid spicy/fatty meals, stay hydrated. "
                   "Consult a doctor if pain persists or if there is blood in stool.",
    }
    
    analysis_parts = []
    symptoms_lower = symptoms.lower()
    matched = False
    for keyword, response in symptom_responses.items():
        if keyword in symptoms_lower:
            analysis_parts.append(response)
            matched = True
    
    if not matched:
        analysis_parts.append(
            f"Based on your symptoms: '{symptoms}', I recommend monitoring your condition. "
            f"If symptoms persist or worsen, please consult a healthcare professional. "
            f"General advice: Stay hydrated, get adequate rest, and maintain a balanced diet."
        )
    
    is_serious = any(w in symptoms_lower for w in ["chest pain", "emergency", "breathing", "severe"])
    
    return json.dumps({
        "analysis": " ".join(analysis_parts),
        "is_serious": is_serious,
        "disclaimer": "This is AI-generated guidance and not a substitute for professional medical advice."
    })


def get_insurance_plans(income: int) -> list:
    """Return insurance plans based on income bracket."""
    if income < 20000:
        return [
            {"name": "Star Health Medi-Classic", "premium": "Rs.4,500/yr", "coverage": "Rs.3L", "rating": 4.2},
            {"name": "Care Health Joy Plan", "premium": "Rs.3,800/yr", "coverage": "Rs.2L", "rating": 4.0},
            {"name": "HDFC ERGO Health Suraksha", "premium": "Rs.5,000/yr", "coverage": "Rs.3L", "rating": 4.3},
        ]
    elif income < 50000:
        return [
            {"name": "Niva Bupa ReAssure", "premium": "Rs.8,500/yr", "coverage": "Rs.5L", "rating": 4.5},
            {"name": "ICICI Lombard iHealth", "premium": "Rs.7,200/yr", "coverage": "Rs.5L", "rating": 4.4},
            {"name": "Tata AIG Medicare", "premium": "Rs.9,000/yr", "coverage": "Rs.7L", "rating": 4.6},
        ]
    else:
        return [
            {"name": "Max Bupa Health Companion", "premium": "Rs.15,000/yr", "coverage": "Rs.15L", "rating": 4.7},
            {"name": "HDFC ERGO Optima Restore", "premium": "Rs.12,000/yr", "coverage": "Rs.10L", "rating": 4.8},
            {"name": "Religare Care Supreme", "premium": "Rs.18,000/yr", "coverage": "Rs.25L", "rating": 4.9},
        ]


@app.post("/api/health")
async def health_endpoint(query: HealthQuery):
    if query.income is not None:
        plans = get_insurance_plans(query.income)
        return JSONResponse(content={
            "type": "insurance",
            "plans": plans,
            "message": f"Based on your income of Rs.{query.income}/month, here are recommended plans:"
        })
    
    result = json.loads(mock_asi_analysis(query.message))
    return JSONResponse(content={
        "type": "analysis",
        "analysis": result["analysis"],
        "is_serious": result["is_serious"],
        "disclaimer": result["disclaimer"]
    })


# ── Stocks Endpoint ─────────────────────────────────────────────────────────

GEMINI_KEY = os.getenv("GEMINI_KEY")

def analyze_intent(message: str, agent_type: str) -> dict:
    """Use Gemini (if available) to determine if message is conversational or data query."""
    if GEMINI_KEY and GEMINI_KEY != "your_gemini_api_key_here":
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
            prompt = (
                f"You are a helpful {agent_type} AI assistant in a finance app. "
                f"Analyze this user message: '{message}'. "
                f"If the user is just saying hi or chatting conversationally, reply with JSON: "
                f'{{"type": "conversation", "message": "your friendly response"}} '
                f"If the user is asking about a specific stock/crypto or mentioning one, reply with JSON: "
                f'{{"type": "query", "entity": "EXACT_TICKER_OR_TOKEN_SYMBOL"}} '
                f"Only output the raw JSON."
            )
            resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text.startswith("```json"):
                    text = text.replace("```json", "").replace("```", "").strip()
                return json.loads(text)
        except Exception:
            pass
            
    # Fallback heuristic if no API key
    msg_lower = message.lower()
    if len(message) > 6 and any(greet in msg_lower for greet in ["hi", "hello", "hey", "how are", "who are"]):
        return {
            "type": "conversation",
            "message": f"Hello! I am your {agent_type} AI assistant. Which asset would you like me to analyze for you today?"
        }
    
    # Assume it's a direct entity query if short or fallback
    # Filter out common punctuation for basic ticker extraction fallback
    entity = message.strip().split()[-1].replace('?', '').replace('.', '')
    return {"type": "query", "entity": entity}

def get_stock_analysis(ticker: str, risk: str, horizon: str, goal: str) -> dict:
    """Generate stock analysis. Uses Gemini API if key is available, otherwise mock data."""
    # Try real API call if key exists
    if GEMINI_KEY and GEMINI_KEY != "your_gemini_api_key_here":
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
            prompt = (
                f"Provide a brief investment analysis for {ticker} stock. "
                f"Investor profile: {risk} risk appetite, {horizon} horizon, goal is {goal}. "
                f"Include: 1) Company overview (2 lines) 2) Key metrics 3) Rating (Buy/Hold/Sell) 4) Brief rationale. "
                f"Keep it concise, under 200 words."
            )
            resp = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}]
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return {"ticker": ticker, "analysis": text, "source": "Gemini AI"}
        except Exception as e:
            pass  # Fall through to mock
    
    # Mock analysis
    mock_data = {
        "AAPL": {"name": "Apple Inc.", "price": "$178.72", "change": "+1.2%", "rating": "BUY",
                 "analysis": "Apple continues to show strong performance with robust iPhone sales and growing services revenue. The company's AI initiatives and Vision Pro position it well for future growth."},
        "GOOGL": {"name": "Alphabet Inc.", "price": "$141.80", "change": "+0.8%", "rating": "BUY",
                  "analysis": "Google's dominance in search and advertising remains unchallenged. Cloud growth is accelerating, and AI integration across products provides significant upside potential."},
        "TSLA": {"name": "Tesla Inc.", "price": "$248.50", "change": "-0.5%", "rating": "HOLD",
                 "analysis": "Tesla faces increasing competition in the EV market but maintains technological leadership. Valuation remains stretched — suitable for high-risk investors only."},
        "MSFT": {"name": "Microsoft Corp.", "price": "$415.30", "change": "+1.5%", "rating": "BUY",
                 "analysis": "Microsoft's Azure cloud and AI partnership with OpenAI continue to drive growth. Enterprise adoption of Copilot products shows strong momentum."},
    }
    
    ticker_upper = ticker.upper()
    if ticker_upper in mock_data:
        return {"ticker": ticker_upper, **mock_data[ticker_upper], "source": "Mock Data"}
    
    return {
        "ticker": ticker_upper,
        "name": f"{ticker_upper} Corp.",
        "price": "N/A",
        "change": "N/A",
        "rating": "HOLD",
        "analysis": f"Analysis for {ticker_upper}: Unable to fetch real-time data. Please ensure a valid ticker symbol.",
        "source": "Mock Data"
    }


@app.post("/api/stocks")
async def stocks_endpoint(query: StockQuery):
    intent = analyze_intent(query.message, "Stock Analyst")
    
    if intent.get("type") == "conversation":
        return JSONResponse(content={"type": "conversation", "message": intent.get("message")})
        
    ticker = intent.get("entity", query.message).strip().upper()
    # Strip any potential conversational lead-up fallback
    if ' ' in ticker:
        ticker = ticker.split()[-1]
    ticker = "".join(c for c in ticker if c.isalpha())
    
    result = get_stock_analysis(ticker, query.risk_appetite, query.time_horizon, query.goal)
    result["type"] = "data"
    return JSONResponse(content=result)


# ── Crypto Endpoint ──────────────────────────────────────────────────────────

def get_crypto_data(token: str) -> dict:
    """Fetch crypto data from CoinGecko API."""
    token_map = {
        "btc": "bitcoin", "bitcoin": "bitcoin",
        "eth": "ethereum", "ethereum": "ethereum",
        "sol": "solana", "solana": "solana",
        "ada": "cardano", "cardano": "cardano",
        "dot": "polkadot", "polkadot": "polkadot",
        "bnb": "binancecoin",
        "xrp": "ripple", "ripple": "ripple",
        "doge": "dogecoin", "dogecoin": "dogecoin",
        "avax": "avalanche-2",
        "matic": "matic-network", "polygon": "matic-network",
        "fet": "fetch-ai", "fetch": "fetch-ai",
        "asi": "fetch-ai",
    }
    
    coin_id = token_map.get(token.lower(), token.lower())
    
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        params = {"localization": "false", "tickers": "false", "community_data": "true", "sparkline": "false"}
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            market = data.get("market_data", {})
            
            price = market.get("current_price", {}).get("usd", 0)
            change_24h = market.get("price_change_percentage_24h", 0)
            change_7d = market.get("price_change_percentage_7d", 0)
            market_cap = market.get("market_cap", {}).get("usd", 0)
            volume = market.get("total_volume", {}).get("usd", 0)
            high_24h = market.get("high_24h", {}).get("usd", 0)
            low_24h = market.get("low_24h", {}).get("usd", 0)
            
            # Simple sentiment based on price changes
            if change_24h > 3:
                sentiment = "Very Bullish"
                sentiment_score = 0.8
            elif change_24h > 0:
                sentiment = "Bullish"
                sentiment_score = 0.6
            elif change_24h > -3:
                sentiment = "Bearish"
                sentiment_score = 0.4
            else:
                sentiment = "Very Bearish"
                sentiment_score = 0.2
            
            return {
                "name": data.get("name", token),
                "symbol": data.get("symbol", token).upper(),
                "price": price,
                "change_24h": round(change_24h, 2),
                "change_7d": round(change_7d, 2),
                "market_cap": market_cap,
                "volume_24h": volume,
                "high_24h": high_24h,
                "low_24h": low_24h,
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "image": data.get("image", {}).get("large", ""),
                "source": "CoinGecko"
            }
    except Exception as e:
        pass
    
    # Fallback mock data
    return {
        "name": token.capitalize(),
        "symbol": token.upper(),
        "price": 0,
        "change_24h": 0,
        "change_7d": 0,
        "market_cap": 0,
        "volume_24h": 0,
        "high_24h": 0,
        "low_24h": 0,
        "sentiment": "Neutral",
        "sentiment_score": 0.5,
        "image": "",
        "source": "Unavailable — CoinGecko API limit reached"
    }


@app.post("/api/crypto")
async def crypto_endpoint(query: CryptoQuery):
    intent = analyze_intent(query.message, "Crypto Tracker")
    
    if intent.get("type") == "conversation":
        return JSONResponse(content={"type": "conversation", "message": intent.get("message")})
        
    token = intent.get("entity", query.message).strip().lower()
    # Strip any potential conversational lead-up fallback
    token = token.split()[-1] if ' ' in token else token
    
    result = get_crypto_data(token)
    result["type"] = "data"
    return JSONResponse(content=result)


# ── Crisis Protocol Endpoint ─────────────────────────────────────────────────

@app.post("/api/crisis")
async def crisis_endpoint(query: CrisisQuery):
    """
    Killer Feature: Cross-Agent Emergency Protocol.
    Simulates Health Agent commanding Stock & Crypto agents to liquidate a portfolio.
    """
    target = query.target_amount
    
    # Use dynamic portfolio from frontend if provided, else format defaults
    portfolio = {}
    if query.portfolio:
        for item in query.portfolio:
            portfolio[item["symbol"]] = {
                "type": item["type"],
                "shares": float(item["shares"]),
                "avg_buy": float(item["avg_buy"])
            }
    else:
        portfolio = {
            "AAPL": {"type": "Stock", "shares": 15, "avg_buy": 150.0},
            "TSLA": {"type": "Stock", "shares": 20, "avg_buy": 200.0},
            "BTC": {"type": "Crypto", "shares": 0.5, "avg_buy": 40000.0},
            "SOL": {"type": "Crypto", "shares": 100, "avg_buy": 50.0}
        }
    
    assets = []
    
    # Fetch REAL-TIME live prices
    try:
        # Fetch Stocks via yfinance
        stock_symbols = [sym for sym, data in portfolio.items() if data["type"] == "Stock"]
        if stock_symbols:
            # Download current day data
            tickers = yf.download(stock_symbols, period="2d", progress=False)
            for sym in stock_symbols:
                try:
                    # Get latest close and previous close to calculate change
                    current_price = float(tickers['Close'][sym].iloc[-1])
                    prev_price = float(tickers['Close'][sym].iloc[-2]) if len(tickers) > 1 else current_price
                    change_pct = ((current_price - prev_price) / prev_price) * 100
                    
                    assets.append({
                        "symbol": sym, 
                        "type": "Stock", 
                        "current_price": round(current_price, 2),
                        "change": f"{'+' if change_pct >= 0 else ''}{round(change_pct, 2)}%",
                        "is_up": change_pct >= 0,
                        "qty": portfolio[sym]["shares"],
                        "value": round(current_price * portfolio[sym]["shares"], 2)
                    })
                except Exception as e:
                    print(f"Error fetching stock {sym}: {e}")
        
        # Fetch Crypto via CoinGecko (using existing helper)
        for sym, data in portfolio.items():
            if data["type"] == "Crypto":
                crypto_data = get_crypto_data(sym)
                current_price = crypto_data.get("price", 0)
                change_pct = crypto_data.get("change_24h", 0)
                
                if current_price > 0:
                    assets.append({
                        "symbol": sym,
                        "type": "Crypto",
                        "current_price": current_price,
                        "change": f"{'+' if change_pct >= 0 else ''}{change_pct}%",
                        "is_up": change_pct >= 0,
                        "qty": data["shares"],
                        "value": current_price * data["shares"]
                    })
    except Exception as e:
        print(f"Error in crisis data fetch: {e}")
        # Fallback if API fails
        assets = [
            {"symbol": "SOL", "type": "Crypto", "current_price": 145.20, "change": "+12.4%", "is_up": True, "qty": 100, "value": 14520.0},
            {"symbol": "AAPL", "type": "Stock", "current_price": 185.50, "change": "+2.1%", "is_up": True, "qty": 15, "value": 2782.5},
            {"symbol": "BTC", "type": "Crypto", "current_price": 62000.0, "change": "-3.2%", "is_up": False, "qty": 0.5, "value": 31000.0},
            {"symbol": "TSLA", "type": "Stock", "current_price": 175.00, "change": "-5.8%", "is_up": False, "qty": 20, "value": 3500.0}
        ]
    
    # "Agent Logic": Sell winners first to preserve capital/avoid selling at a loss
    amount_raised = 0.0
    sell_plan = []
    
    
    # Filter for assets that are UP today
    winners = [a for a in assets if a["is_up"]]
    
    for asset in winners:
        if amount_raised >= target:
            break
            
        # Add buffer of 5% to the target
        remaining = float(target * 1.05) - amount_raised 
        shares_to_sell = min(float(asset["qty"]), remaining / float(asset["current_price"]))
        
        # Round appropriately
        if asset["type"] == "Stock":
            shares_to_sell = math.ceil(shares_to_sell)
        else:
            shares_to_sell = round(float(shares_to_sell), 2)
            
        value_raised = shares_to_sell * asset["current_price"]
        amount_raised += value_raised
        
        if shares_to_sell > 0:
            sell_plan.append({
                "symbol": asset["symbol"],
                "type": asset["type"],
                "shares": shares_to_sell,
                "price": asset["current_price"],
                "value": value_raised,
                "reason": f"Up {asset['change']} today. Liquidating near all-time highs."
            })
            
    # If still need more money, sell losers
    if amount_raised < target:
        losers = [a for a in assets if not a["is_up"]]
        for asset in losers:
            if amount_raised >= target:
                break
            remaining = float(target * 1.05) - amount_raised
            shares_to_sell = min(float(asset["qty"]), remaining / float(asset["current_price"]))
            if asset["type"] == "Stock":
                shares_to_sell = math.ceil(shares_to_sell)
            else:
                shares_to_sell = round(float(shares_to_sell), 2)
            
            value_raised = shares_to_sell * asset["current_price"]
            amount_raised += value_raised
            if shares_to_sell > 0:
                sell_plan.append({
                    "symbol": asset["symbol"],
                    "type": asset["type"],
                    "shares": shares_to_sell,
                    "price": asset["current_price"],
                    "value": value_raised,
                    "reason": f"Down {asset['change']} today. Emergency liquidation."
                })
                
    return JSONResponse(content={
        "status": "SOS_ACTIVE",
        "target": target,
        "raised": round(amount_raised, 2),
        "plan": sell_plan,
        "message": f"🚨 CROSS-AGENT SOS TRIGGERED: Health Agent requested ${target} for medical emergency. Stock & Crypto Agents analyzed portfolio to minimize losses."
    })


# ── Serve Frontend ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = os.path.join(static_dir, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


if __name__ == "__main__":
    print("\n  FinWell Dashboard starting...")
    print("  Open http://localhost:5000 in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=5000)
