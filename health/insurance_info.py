"""Health & Life Insurance Analysis Agent

An agent that analyzes health and life insurance products, providing insights on 
coverage options, market trends, and consumer sentiment.
"""

import asyncio
import json
import logging
import os
import re
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Any
from uuid import uuid4

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from uagents import Agent, Context, Protocol, Model
from uagents.setup import fund_agent_if_low
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent,
    chat_protocol_spec
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s: %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Download NLTK data if not already present
try:
    nltk.data.find("vader_lexicon")
except LookupError:
    nltk.download('vader_lexicon')

# Environment variables and configuration
AGENT_NAME = "Health-Life-Insurance-Analyzer"
AGENT_VERSION = "0.1.0"
AGENT_PORT = 8003
AGENT_SEED = os.getenv("AGENT_SEED", str(uuid4()))

# ASI LLM API configuration
ASI_LLM_URL = "https://api.asi1.ai/v1/chat/completions"
ASI_LLM_KEY = os.getenv("ASI_LLM_KEY", "")

# Check if ASI key is defined
if not ASI_LLM_KEY:
    logger.warning("ASI_LLM_KEY is not defined. Advanced analysis with LLM will not be available.")
else:
    # Show only the first and last 4 characters of the key for security
    masked_key = ASI_LLM_KEY[:4] + "*" * (len(ASI_LLM_KEY) - 8) + ASI_LLM_KEY[-4:]
    logger.info(f"ASI_LLM_KEY loaded successfully: {masked_key}")
    logger.info("Advanced analysis with ASI LLM is available.")

ASI_HEADERS = {
    "Authorization": f"Bearer {ASI_LLM_KEY}",
    "Content-Type": "application/json"
}

# Insurance company mappings and data
MAJOR_INSURANCE_COMPANIES = {
    "aetna": {"name": "Aetna", "type": "health", "website": "aetna.com"},
    "anthem": {"name": "Anthem", "type": "health", "website": "anthem.com"},
    "cigna": {"name": "Cigna", "type": "health", "website": "cigna.com"},
    "humana": {"name": "Humana", "type": "health", "website": "humana.com"},
    "kaiser": {"name": "Kaiser Permanente", "type": "health", "website": "kp.org"},
    "united": {"name": "UnitedHealthcare", "type": "health", "website": "uhc.com"},
    "bcbs": {"name": "Blue Cross Blue Shield", "type": "health", "website": "bcbs.com"},
    
    # Life Insurance Companies
    "metlife": {"name": "MetLife", "type": "life", "website": "metlife.com"},
    "prudential": {"name": "Prudential", "type": "life", "website": "prudential.com"},
    "newyorklife": {"name": "New York Life", "type": "life", "website": "newyorklife.com"},
    "northwestern": {"name": "Northwestern Mutual", "type": "life", "website": "northwesternmutual.com"},
    "massmutual": {"name": "MassMutual", "type": "life", "website": "massmutual.com"},
    "lincoln": {"name": "Lincoln Financial", "type": "life", "website": "lfg.com"},
    "transamerica": {"name": "Transamerica", "type": "life", "website": "transamerica.com"},
    "aflac": {"name": "Aflac", "type": "supplemental", "website": "aflac.com"},
}

# Insurance types and coverage categories
INSURANCE_TYPES = {
    "health": ["medical", "health", "healthcare", "hmo", "ppo", "epo"],
    "life": ["life", "term", "whole", "universal", "variable"],
    "disability": ["disability", "income", "di"],
    "long_term_care": ["ltc", "long term care", "nursing"],
    "dental": ["dental", "orthodontic"],
    "vision": ["vision", "eye", "optical"]
}

# News sources for insurance industry analysis
NEWS_SOURCES = [
    # Insurance industry news
    "https://newsapi.org/v2/everything?q=health+insurance&sortBy=publishedAt&language=en",
    "https://newsapi.org/v2/everything?q=life+insurance&sortBy=publishedAt&language=en",
    "https://newsapi.org/v2/everything?q=insurance+premiums&sortBy=publishedAt&language=en",
    "https://newsapi.org/v2/everything?q=healthcare+costs&sortBy=publishedAt&language=en",
    
    # Alternative sources (if API keys available)
    "https://api.marketaux.com/v1/news/all?filter_entities=true&symbols=UNH,ANTM,CI,HUM&language=en",
]

# Market data sources for insurance companies (if publicly traded)
MARKET_DATA_SOURCES = [
    # Stock tickers for major insurance companies
    lambda symbol: f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev",
    lambda symbol: f"https://api.alpha-vantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}",
]

# Insurance company stock symbols
INSURANCE_STOCK_SYMBOLS = {
    "united": "UNH",
    "anthem": "ANTM", 
    "cigna": "CI",
    "humana": "HUM",
    "aetna": "CVS",  # Owned by CVS Health
    "metlife": "MET",
    "prudential": "PRU",
    "lincoln": "LNC",
    "aflac": "AFL"
}

# Chat protocol definition
chat_proto = Protocol(spec=chat_protocol_spec)

# Create the agent
insurance_agent = Agent(
    name=AGENT_NAME,
    port=AGENT_PORT,
    seed=AGENT_SEED,
    mailbox=True,
    publish_agent_details=True
)

# Ensure agent balance
fund_agent_if_low(insurance_agent.wallet.address())

# Helper functions
def extract_insurance_info_from_query(query: str) -> Dict[str, Any]:
    """Extract insurance company and type from a natural language query"""
    query_lower = query.lower()
    
    # Initialize result
    result = {
        "company": None,
        "insurance_type": None,
        "company_data": None,
        "specific_terms": []
    }
    
    # Search for insurance companies
    for key, company_data in MAJOR_INSURANCE_COMPANIES.items():
        company_name_lower = company_data["name"].lower()
        # Check for exact matches or partial matches
        if (key in query_lower or 
            company_name_lower in query_lower or
            any(word in query_lower for word in company_name_lower.split())):
            result["company"] = key
            result["company_data"] = company_data
            break
    
    # Search for insurance types
    for ins_type, keywords in INSURANCE_TYPES.items():
        if any(keyword in query_lower for keyword in keywords):
            result["insurance_type"] = ins_type
            break
    
    # Extract specific insurance terms
    insurance_terms = [
        "premium", "deductible", "copay", "coinsurance", "out-of-pocket",
        "network", "coverage", "benefits", "claim", "policy", "renewal",
        "exclusion", "rider", "beneficiary", "death benefit", "cash value"
    ]
    
    for term in insurance_terms:
        if term in query_lower:
            result["specific_terms"].append(term)
    
    return result

async def get_insurance_market_data(company_key: str):
    """Get market data for insurance companies (if publicly traded)"""
    if company_key not in INSURANCE_STOCK_SYMBOLS:
        return {"error": "Company not publicly traded or symbol not available"}
    
    symbol = INSURANCE_STOCK_SYMBOLS[company_key]
    
    try:
        # Try Alpha Vantage API (free tier available)
        api_key = os.getenv("ALPHA_VANTAGE_KEY", "demo")
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if "Global Quote" in data:
            quote = data["Global Quote"]
            return {
                "symbol": symbol,
                "price": float(quote.get("05. price", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_percent": quote.get("10. change percent", "0%").replace("%", ""),
                "volume": int(quote.get("06. volume", 0)),
                "high": float(quote.get("03. high", 0)),
                "low": float(quote.get("04. low", 0)),
                "last_updated": quote.get("07. latest trading day", "")
            }
        else:
            return {"error": "No market data available"}
            
    except Exception as e:
        logger.error(f"Error fetching market data: {str(e)}")
        return {"error": f"Error fetching market data: {str(e)}"}

async def analyze_insurance_sentiment(company: str = None, insurance_type: str = None):
    """Analyze sentiment for insurance companies or insurance types"""
    sia = SentimentIntensityAnalyzer()
    
    texts = []
    sources = []
    
    try:
        # Build search query
        if company and company in MAJOR_INSURANCE_COMPANIES:
            search_terms = MAJOR_INSURANCE_COMPANIES[company]["name"]
        elif insurance_type:
            search_terms = f"{insurance_type} insurance"
        else:
            search_terms = "health insurance life insurance"
        
        # Use web search to find recent news
        search_queries = [
            f"{search_terms} news",
            f"{search_terms} reviews",
            f"{search_terms} customer satisfaction",
            f"{search_terms} premiums rates"
        ]
        
        # Simulate getting news data (in production, you'd use actual news APIs)
        # For demonstration, we'll create sample data
        sample_texts = [
            f"{search_terms} announces new coverage options for 2024",
            f"Customer satisfaction ratings improve for {search_terms}",
            f"Premium increases moderate for {search_terms} policies",
            f"New regulatory changes affect {search_terms} coverage",
            f"Market competition drives innovation in {search_terms}",
        ]
        
        texts.extend(sample_texts)
        sources.append("Insurance News")
        
        # Analyze sentiment
        if texts:
            scores = []
            for text in texts:
                try:
                    score = sia.polarity_scores(text)['compound']
                    scores.append(score)
                except Exception as e:
                    logger.warning(f"Error analyzing sentiment for text: {str(e)}")
                    continue
            
            if scores:
                avg_score = sum(scores) / len(scores)
                
                # Categorize sentiment
                if avg_score >= 0.15:
                    sentiment = 'very positive'
                elif avg_score >= 0.05:
                    sentiment = 'positive'
                elif avg_score <= -0.15:
                    sentiment = 'very negative'
                elif avg_score <= -0.05:
                    sentiment = 'negative'
                else:
                    sentiment = 'neutral'
                
                return {
                    'sentiment_score': float(avg_score),
                    'sentiment_category': sentiment,
                    'sample_size': len(scores),
                    'sources': sources,
                    'analysis': ' '.join(text[:100] + '...' for text in texts[:3])
                }
        
        return {
            "sentiment_score": 0,
            "sentiment_category": "neutral",
            "sample_size": 0,
            "sources": ["Limited data available"]
        }
        
    except Exception as e:
        return {"error": f"Error analyzing sentiment: {str(e)}"}

async def get_insurance_analysis(query_info: Dict[str, Any]) -> str:
    """Get comprehensive analysis for insurance query"""
    try:
        company = query_info.get("company")
        insurance_type = query_info.get("insurance_type")
        company_data = query_info.get("company_data")
        specific_terms = query_info.get("specific_terms", [])
        
        # Get market data if company is publicly traded
        market_data = None
        if company and company in INSURANCE_STOCK_SYMBOLS:
            market_data = await get_insurance_market_data(company)
        
        # Analyze sentiment
        sentiment_data = await analyze_insurance_sentiment(company, insurance_type)
        
        # Generate analysis with ASI LLM or fallback
        if ASI_LLM_KEY:
            try:
                # Prepare prompt for insurance analysis
                company_info = ""
                if company_data:
                    company_info = f"analyzing {company_data['name']} ({company_data['type']} insurance)"
                elif insurance_type:
                    company_info = f"analyzing {insurance_type} insurance market"
                else:
                    company_info = "analyzing general insurance market"
                
                market_info = ""
                if market_data and "error" not in market_data:
                    market_info = f"""
Stock Performance (if applicable):
- Stock Price: ${market_data['price']:.2f}
- Daily Change: {market_data['change']:.2f} ({market_data['change_percent']}%)
- Trading Volume: {market_data['volume']:,}
- Day Range: ${market_data['low']:.2f} - ${market_data['high']:.2f}
"""
                
                prompt = f"""
                Provide an analysis for insurance inquiry - {company_info}:

                {market_info}

                Sentiment Analysis:
                - Category: {sentiment_data['sentiment_category']}
                - Score: {sentiment_data['sentiment_score']:.2f}
                - Based on {sentiment_data['sample_size']} sources
                
                Specific areas of interest: {', '.join(specific_terms) if specific_terms else 'General inquiry'}

                Please provide a structured analysis with:
                1. Overview of the insurance company/type and current market position
                2. Key factors affecting premiums and coverage in this segment
                3. Current market trends and consumer sentiment
                4. Recommendations for consumers considering this insurance option
                
                Keep the response informative and consumer-focused (maximum 250 words).
                """
                
                # Call ASI LLM API
                payload = {
                    "model": "asi1-mini",
                    "temperature": 0.7,
                    "messages": [{"role": "user", "content": prompt}]
                }
                
                response = requests.post(ASI_LLM_URL, headers=ASI_HEADERS, json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    analysis = data['choices'][0]['message']['content'].strip()
                    logger.info(f"Successfully obtained ASI analysis for insurance query")
                else:
                    logger.warning(f"ASI API returned status code {response.status_code}")
                    analysis = generate_fallback_insurance_analysis(query_info, market_data, sentiment_data)
                    
            except Exception as e:
                logger.warning(f"Error getting ASI analysis: {str(e)}")
                analysis = generate_fallback_insurance_analysis(query_info, market_data, sentiment_data)
        else:
            analysis = generate_fallback_insurance_analysis(query_info, market_data, sentiment_data)
        
        # Format the final response
        response = format_insurance_response(query_info, market_data, sentiment_data, analysis)
        
        return response
        
    except Exception as e:
        return f"Error generating insurance analysis: {str(e)}"

def generate_fallback_insurance_analysis(query_info, market_data, sentiment_data):
    """Generate fallback analysis when ASI LLM is unavailable"""
    company = query_info.get("company")
    insurance_type = query_info.get("insurance_type")
    company_data = query_info.get("company_data")
    
    if company_data:
        company_name = company_data["name"]
        ins_type = company_data["type"]
        
        analysis = f"""**Company Overview:**
{company_name} is a major player in the {ins_type} insurance market. """
        
        if market_data and "error" not in market_data:
            change = float(market_data.get('change_percent', '0').replace('%', ''))
            if change > 2:
                analysis += f"The company's stock performance shows strength with a {change}% gain, potentially indicating investor confidence in their business model."
            elif change < -2:
                analysis += f"Recent stock performance shows a {abs(change)}% decline, which may reflect market challenges or broader economic concerns."
            else:
                analysis += "Stock performance remains stable, suggesting steady business operations."
        
        sentiment = sentiment_data.get('sentiment_category', 'neutral')
        analysis += f"\n\n**Market Sentiment:**\nCurrent market sentiment is {sentiment}, which "
        
        if sentiment in ['positive', 'very positive']:
            analysis += "suggests consumer confidence in their products and services. This could translate to competitive pricing and expanded coverage options."
        elif sentiment in ['negative', 'very negative']:
            analysis += "indicates some consumer concerns. Potential customers should carefully review policy terms and consider alternatives."
        else:
            analysis += "shows mixed consumer opinions. This presents an opportunity to evaluate their offerings against competitors."
            
        analysis += f"\n\n**Consumer Recommendations:**\n"
        if ins_type == "health":
            analysis += "- Compare network coverage in your area\n- Review prescription drug formularies\n- Check annual out-of-pocket maximums\n- Consider HSA compatibility if relevant"
        elif ins_type == "life":
            analysis += "- Determine appropriate coverage amount (typically 10-12x annual income)\n- Compare term vs. permanent life insurance options\n- Review financial strength ratings\n- Understand policy riders and benefits"
        else:
            analysis += "- Compare coverage options and exclusions\n- Review customer service ratings\n- Check claim processing times\n- Understand premium adjustment policies"
    
    elif insurance_type:
        analysis = f"""**{insurance_type.title()} Insurance Market Analysis:**
The {insurance_type} insurance market is experiencing various trends affecting consumers and providers. """
        
        if insurance_type == "health":
            analysis += "Rising healthcare costs continue to impact premium pricing, while regulatory changes provide both opportunities and challenges for coverage expansion."
        elif insurance_type == "life":
            analysis += "Interest rate environments affect policy pricing, while increased awareness of financial planning drives demand for coverage."
        
        analysis += f"\n\n**Current Trends:**\nMarket sentiment is {sentiment_data.get('sentiment_category', 'neutral')}, reflecting current consumer and industry perspectives on {insurance_type} insurance options."
        
    else:
        analysis = "**General Insurance Market:**\nThe insurance industry continues to adapt to changing consumer needs, regulatory requirements, and economic conditions. Consider your specific needs and compare multiple providers for the best coverage options."
    
    return analysis

def format_insurance_response(query_info, market_data, sentiment_data, analysis):
    """Format the comprehensive insurance response"""
    company = query_info.get("company")
    insurance_type = query_info.get("insurance_type")
    company_data = query_info.get("company_data")
    specific_terms = query_info.get("specific_terms", [])
    
    # Header
    if company_data:
        header = f"**{company_data['name']} - {company_data['type'].title()} Insurance Analysis**"
    elif insurance_type:
        header = f"**{insurance_type.title()} Insurance Market Analysis**"
    else:
        header = "**Insurance Market Analysis**"
    
    response = f"{header}\n\n"
    
    # Market data section (if available)
    if market_data and "error" not in market_data:
        change_emoji = '🟢' if float(market_data.get('change_percent', '0').replace('%', '')) > 0 else '🔴'
        response += f"📈 **Stock Performance** ({market_data['symbol']})\n"
        response += f"• Current Price: ${market_data['price']:.2f}\n"
        response += f"• Daily Change: {change_emoji} {market_data['change_percent']}%\n"
        response += f"• Volume: {market_data['volume']:,}\n"
        response += f"• Day Range: ${market_data['low']:.2f} - ${market_data['high']:.2f}\n\n"
    
    # Sentiment analysis
    sentiment_score = sentiment_data.get('sentiment_score', 0)
    sentiment_emoji = '👍' if sentiment_score > 0.1 else '👎' if sentiment_score < -0.1 else '➖'
    
    response += f"🎯 **Market Sentiment**\n"
    response += f"• Score: {sentiment_score:.2f}/1.0\n"
    response += f"• Category: {sentiment_emoji} {sentiment_data.get('sentiment_category', 'neutral').title()}\n"
    response += f"• Sample Size: {sentiment_data.get('sample_size', 0)} sources\n\n"
    
    # Specific terms mentioned
    if specific_terms:
        response += f"🔍 **Areas of Focus:** {', '.join(specific_terms)}\n\n"
    
    # Main analysis
    response += f"📊 **Detailed Analysis**\n{analysis}\n\n"
    
    # Footer with timestamp
    response += f"---\n"
    response += f"📅 **Analysis Generated:** {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}\n"
    
    if company_data:
        response += f"🌐 **Learn More:** Visit {company_data['website']}"
    
    return response.strip()

# Chat protocol handlers
@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages and respond with insurance analysis"""
    # Extract message content
    if isinstance(msg.content, list):
        content_list = msg.content
        if content_list and hasattr(content_list[0], 'text'):
            user_message = content_list[0].text
        else:
            user_message = str(content_list)
    elif hasattr(msg.content, 'text'):
        user_message = msg.content.text
    else:
        user_message = str(msg.content)

    logger.info(f"Received message from {sender}: {user_message}")

    # Extract insurance information from message
    query_info = extract_insurance_info_from_query(user_message)

    if not query_info["company"] and not query_info["insurance_type"]:
        # Send response when we cannot identify insurance-related content
        response_text = """I specialize in analyzing health and life insurance. Please ask about:

🏥 **Health Insurance:** Aetna, Anthem, Cigna, Humana, Kaiser Permanente, UnitedHealthcare, BCBS
💰 **Life Insurance:** MetLife, Prudential, New York Life, Northwestern Mutual, MassMutual

You can ask about premiums, coverage, benefits, or market analysis for these companies."""

        response_msg = ChatMessage(
            timestamp=datetime.now().timestamp(),
            msg_id=str(uuid4()),
            content=[{"type": "text", "text": response_text}]
        )

        await ctx.send(sender, response_msg)
        return

    # Get comprehensive insurance analysis
    response = await get_insurance_analysis(query_info)

    # Send response
    response_msg = ChatMessage(
        timestamp=datetime.now().timestamp(),
        msg_id=str(uuid4()),
        content=[{"type": "text", "text": response}]
    )

    try:
        await ctx.send(sender, response_msg)
    except Exception as e:
        ctx.logger.error(f"Error sending message: {str(e)}")

@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgement messages"""
    ctx.logger.info(f"Acknowledgement received from {sender} for msg_id {msg.acknowledged_msg_id}")

# Agent event handlers
@insurance_agent.on_event("startup")
async def startup_handler(ctx: Context):
    addr = insurance_agent.address
    ctx.logger.info(f"Health & Life Insurance Analysis Agent is running!")
    ctx.logger.info(f"Agent Address: {addr}")
    ctx.logger.info(f"Add this agent to chat.agentverse.ai")

@insurance_agent.on_interval(period=60.0)
async def status_check(ctx: Context):
    ctx.logger.info(f"Insurance agent is running. Address: {insurance_agent.address}")

# Include chat protocol
try:
    insurance_agent.include(chat_proto, publish_manifest=True)
    logger.info("Chat protocol successfully included")
except Exception as e:
    logger.error(f"Error including chat protocol: {str(e)}")
    try:
        insurance_agent.include(chat_proto)
        logger.info("Chat protocol included without manifest")
    except Exception as e2:
        logger.error(f"Complete failure including protocol: {str(e2)}")

if __name__ == "__main__":
    print("Starting Health & Life Insurance Analysis Agent...")
    print(f"Agent address: {insurance_agent.address}")
    print("Access this agent at chat.agentverse.ai")
    print("Ask about health insurance companies like Aetna, Cigna, UnitedHealthcare")
    print("Or life insurance companies like MetLife, Prudential, Northwestern Mutual")
    print("Ctrl+C to exit")

    try:
        insurance_agent.run()
    except KeyboardInterrupt:
        print("\nAgent stopped by user.")
    except Exception as e:
        print(f"\nError: {str(e)}")
        print("Attempting to restart agent...")
        insurance_agent.run()
