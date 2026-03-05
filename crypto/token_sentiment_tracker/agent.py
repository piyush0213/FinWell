"""Token Sentiment & Price Tracker Agent (Optimized Version)

Optimized version of the agent with official chat protocol.
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
AGENT_NAME = "Token-Sentiment-Price-Tracker"
AGENT_VERSION = "0.1.0"
AGENT_PORT = 8002
AGENT_SEED = os.getenv("AGENT_SEED", str(uuid4()))

# API keys (optional)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
# Removed CryptoPanic due to connectivity issues

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

# Common token ID mappings (CoinGecko IDs)
TOKEN_ID_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "link": "chainlink",
    "dot": "polkadot",
    "ada": "cardano",
    "avax": "avalanche-2",
    "matic": "matic-network",
    "doge": "dogecoin",
    "shib": "shiba-inu",
    "xrp": "ripple",
    "bnb": "binancecoin",
    "uni": "uniswap",
    "atom": "cosmos",
}

# News sources for sentiment analysis - using reliable sources only
NEWS_SOURCES = [
    # Primary news sources
    "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h",
    "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h",
    
    # News and updates
    "https://api.coingecko.com/api/v3/news",
    "https://api.coingecko.com/api/v3/status_updates",
    
    # Alternative news source
    "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
]

# Price and market data sources for analysis
MARKET_DATA_SOURCES = [
    # Price and volume data
    lambda token_id: f"https://api.coingecko.com/api/v3/coins/{token_id}/market_chart?vs_currency=usd&days=14",

    # Exchange data
    lambda token_id: f"https://api.coingecko.com/api/v3/coins/{token_id}/tickers",

    # General token data
    lambda token_id: f"https://api.coingecko.com/api/v3/coins/{token_id}?localization=false&tickers=false&community_data=true&developer_data=false"
]

# Chat protocol definition (using the official protocol)
chat_proto = Protocol(spec=chat_protocol_spec)

# Create the agent
token_agent = Agent(
    name=AGENT_NAME,
    port=AGENT_PORT,
    seed=AGENT_SEED,
    # Do not specify endpoint to avoid overlap with mailbox
    mailbox=True,
    publish_agent_details=True
)

# Ensure agent balance (optional)
fund_agent_if_low(token_agent.wallet.address())

# Helper functions
def extract_token_from_query(query: str) -> Optional[str]:
    """Extract token symbol from a natural language query"""
    # Convert to lowercase for easier matching
    query = query.lower()

    # Search for common token symbols directly in the text
    for token in TOKEN_ID_MAP.keys():
        # Search for the token as an independent word
        pattern = fr'\b{re.escape(token)}\b'
        if re.search(pattern, query):
            return token

    # Search for mentions of full token names
    for symbol, name in TOKEN_ID_MAP.items():
        if name in query.lower():
            return symbol

    # Try to extract a generic token symbol (3-5 letters)
    matches = re.findall(r'\b[A-Za-z]{3,5}\b', query)
    for match in matches:
        if match.lower() in TOKEN_ID_MAP:
            return match.lower()

    # If no known token is found
    return None

async def get_crypto_price(token_symbol: str):
    """Get cryptocurrency price data from CoinGecko API with improved error handling"""
    # Map symbol to CoinGecko ID
    token_id = TOKEN_ID_MAP.get(token_symbol.lower(), token_symbol.lower())
    
    # Default values in case of errors
    default_data = {
        "symbol": token_symbol.upper(),
        "name": token_symbol.upper(),
        "price_usd": 0.0,
        "market_cap": 0.0,
        "volume_24h": 0.0,
        "change_24h": 0.0,
        "price_change_7d": 0.0,
        "price_change_30d": 0.0,
        "last_updated": int(time.time())
    }

    try:
        # Build API URL
        url = f"https://api.coingecko.com/api/v3/coins/{token_id}"
        params = {}
        if COINGECKO_API_KEY:
            params['x_cg_api_key'] = COINGECKO_API_KEY

        # Make the request with timeout
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        
        # Try to parse JSON response
        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            return {"error": "Invalid JSON response from API", **default_data}

        # Check if we have the expected data structure
        if not isinstance(data, dict) or 'market_data' not in data:
            logger.error(f"Unexpected API response structure: {data}")
            return {"error": "Unexpected API response structure", **default_data}

        # Safely extract data with defaults
        market_data = data.get('market_data', {})
        current_price = market_data.get('current_price', {}).get('usd', 0.0)
        market_cap = market_data.get('market_cap', {}).get('usd', 0.0)
        volume = market_data.get('total_volume', {}).get('usd', 0.0)
        
        # Handle potential None values for percentage changes
        price_change_24h = market_data.get('price_change_percentage_24h', 0.0) or 0.0
        price_change_7d = market_data.get('price_change_percentage_7d_in_currency', {}).get('usd', 0.0) or 0.0
        price_change_30d = market_data.get('price_change_percentage_30d_in_currency', {}).get('usd', 0.0) or 0.0
        
        # Safely parse last_updated timestamp
        last_updated = data.get('last_updated', '')
        try:
            if last_updated:
                last_updated_timestamp = int(datetime.fromisoformat(last_updated.replace('Z', '+00:00')).timestamp())
            else:
                last_updated_timestamp = int(time.time())
        except (ValueError, AttributeError):
            last_updated_timestamp = int(time.time())

        # Return structured data with fallbacks
        return {
            "symbol": data.get('symbol', token_symbol).upper(),
            "name": data.get('name', token_symbol.upper()),
            "price_usd": float(current_price) if current_price is not None else 0.0,
            "market_cap": float(market_cap) if market_cap is not None else 0.0,
            "volume_24h": float(volume) if volume is not None else 0.0,
            "change_24h": float(price_change_24h) if price_change_24h is not None else 0.0,
            "price_change_7d": float(price_change_7d) if price_change_7d is not None else 0.0,
            "price_change_30d": float(price_change_30d) if price_change_30d is not None else 0.0,
            "last_updated": last_updated_timestamp
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {"error": f"Network error: {str(e)}", **default_data}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"error": f"Error fetching price data: {str(e)}", **default_data}

async def analyze_sentiment(token_symbol: str):
    """Analyze sentiment for a cryptocurrency from news and social media"""
    # Initialize sentiment analyzer
    sia = SentimentIntensityAnalyzer()

    # Collect relevant texts for sentiment analysis
    texts = []
    sources = []

    # Successful sources counter
    successful_sources = 0

    try:
        # Fetch news from various sources
        for source_url in NEWS_SOURCES:
            # Skip after we have enough data from reliable sources
            if successful_sources >= 2 and len(texts) >= 10:
                break

            try:
                # Increase timeout to avoid connection issues
                response = requests.get(source_url, timeout=15)

                # Check if the response is valid
                if response.status_code == 200 and response.content:  # Ensure there is content
                    try:
                        data = response.json()
                    except ValueError as e:
                        logger.warning(f"Invalid response from {source_url}: {str(e)}")
                        continue  # Skip to the next source
                    items_found = 0

                    # Handle different API response structures
                    if 'results' in data:  # CryptoPanic format
                        items = data.get('results', [])
                        for item in items:
                            title = item.get('title', '').lower()
                            if token_symbol.lower() in title or TOKEN_ID_MAP.get(token_symbol.lower(), '') in title:
                                texts.append(title)
                                source_name = item.get('source', {}).get('title', 'News')
                                if source_name not in sources:
                                    sources.append(source_name)
                                items_found += 1

                    elif 'data' in data:  # CoinGecko news format
                        items = data.get('data', [])
                        for item in items:
                            title = item.get('title', '').lower()
                            description = item.get('description', '').lower()
                            content_text = title + ' ' + description

                            if token_symbol.lower() in content_text or TOKEN_ID_MAP.get(token_symbol.lower(), '') in content_text:
                                texts.append(content_text)
                                if 'CoinGecko' not in sources:
                                    sources.append('CoinGecko')
                                items_found += 1

                    elif 'status_updates' in data:  # CoinGecko status format
                        items = data.get('status_updates', [])
                        for item in items:
                            description = item.get('description', '').lower()
                            project = item.get('project', {}).get('name', '').lower()

                            if (token_symbol.lower() in description or
                                TOKEN_ID_MAP.get(token_symbol.lower(), '') in description or
                                token_symbol.lower() in project):
                                texts.append(description)
                                if 'CoinGecko Status' not in sources:
                                    sources.append('CoinGecko Status')
                                items_found += 1

                    # CryptoCompare format
                    elif 'Data' in data and isinstance(data['Data'], list):
                        items = data['Data']
                        for item in items:
                            title = item.get('title', '').lower()
                            body = item.get('body', '').lower()
                            content_text = title + ' ' + body

                            if token_symbol.lower() in content_text or TOKEN_ID_MAP.get(token_symbol.lower(), '') in content_text:
                                texts.append(content_text)
                                source_name = item.get('source', 'CryptoCompare')
                                if source_name not in sources:
                                    sources.append(source_name)
                                items_found += 1

                    # NewsAPI format
                    elif 'articles' in data and isinstance(data['articles'], list):
                        items = data['articles']
                        for item in items:
                            title = item.get('title', '').lower()
                            description = item.get('description', '').lower()
                            content_text = title + ' ' + description

                            if token_symbol.lower() in content_text or TOKEN_ID_MAP.get(token_symbol.lower(), '') in content_text:
                                texts.append(content_text)
                                source_name = item.get('source', {}).get('name', 'NewsAPI')
                                if source_name not in sources:
                                    sources.append(source_name)
                                items_found += 1

                    # Increment successful sources counter if we found relevant items
                    if items_found > 0:
                        successful_sources += 1
                        logger.info(f"Found {items_found} relevant items from {source_url}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error for {source_url}: {str(e)}")
                # Do not retry this source in this execution
                continue
            except requests.exceptions.Timeout as e:
                logger.warning(f"Timeout error for {source_url}: {str(e)}")
                # Do not retry this source in this execution
                continue
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error for {source_url}: {str(e)}")
                continue
            except ValueError as e:
                logger.warning(f"Invalid JSON from {source_url}: {str(e)}")
                continue
            except Exception as e:
                logger.warning(f"Unexpected error from {source_url}: {str(e)}")
                continue

        # Fallback to generic web search if not enough news is found
        if len(texts) < 5:
            # Use defined market data sources
            token_id = TOKEN_ID_MAP.get(token_symbol.lower(), token_symbol.lower())

            # Iterate through market data sources
            for source_generator in MARKET_DATA_SOURCES:
                # Generate URL based on token ID
                fallback_url = source_generator(token_id)

                try:
                    # Increase timeout to avoid issues
                    response = requests.get(fallback_url, timeout=15)

                    if response.status_code == 200:
                        data = response.json()

                        # Process ticker data (exchanges)
                        if 'tickers' in data:
                            # Use exchange names as an indicator of interest
                            for ticker in data.get('tickers', [])[:10]:
                                exchange_name = ticker.get('market', {}).get('name', '')
                                if exchange_name:
                                    trade_info = f"Trading on {exchange_name}"
                                    texts.append(trade_info)
                            if "CoinGecko Exchanges" not in sources:
                                sources.append("CoinGecko Exchanges")

                        # Process market chart data
                        elif 'prices' in data:
                            # Analyze price data to generate texts about trends
                            prices = data.get('prices', [])
                            if len(prices) > 1:
                                first_price = prices[0][1]
                                last_price = prices[-1][1]
                                change = ((last_price - first_price) / first_price) * 100 if first_price != 0 else 0


                                if change > 5:
                                    texts.append(f"{token_symbol.upper()} has increased by {change:.2f}% in the last 14 days")
                                elif change < -5:
                                    texts.append(f"{token_symbol.upper()} has decreased by {abs(change):.2f}% in the last 14 days")
                                else:
                                    texts.append(f"{token_symbol.upper()} has been relatively stable in the last 14 days")

                                # Analyze volatility
                                price_changes = [abs(prices[i+1][1] - prices[i][1])/prices[i][1]*100 for i in range(len(prices)-1) if prices[i][1] != 0]
                                if price_changes:
                                    avg_volatility = sum(price_changes) / len(price_changes)

                                    if avg_volatility > 5:
                                        texts.append(f"{token_symbol.upper()} shows high volatility in recent trading")
                                    elif avg_volatility < 1:
                                        texts.append(f"{token_symbol.upper()} shows low volatility in recent trading")

                                # Analyze volumes
                                if 'total_volumes' in data:
                                    volumes = data.get('total_volumes', [])
                                    if len(volumes) > 1:
                                        first_volume = volumes[0][1]
                                        last_volume = volumes[-1][1]
                                        volume_change = ((last_volume - first_volume) / first_volume) * 100 if first_volume > 0 else 0

                                        if volume_change > 50:
                                            texts.append(f"Trading volume for {token_symbol.upper()} has increased significantly by {volume_change:.2f}%")
                                        elif volume_change < -50:
                                            texts.append(f"Trading volume for {token_symbol.upper()} has decreased significantly by {abs(volume_change):.2f}%")

                                if "CoinGecko Market Data" not in sources:
                                    sources.append("CoinGecko Market Data")

                        # Process community data
                        elif 'community_data' in data:
                            community = data.get('community_data', {})

                            # Extract social media data
                            twitter_followers = community.get('twitter_followers', 0)
                            reddit_subscribers = community.get('reddit_subscribers', 0)
                            telegram_channel_user_count = community.get('telegram_channel_user_count', 0)

                            if twitter_followers > 100000:
                                texts.append(f"{token_symbol.upper()} has a large Twitter following with {twitter_followers:,} followers")

                            if reddit_subscribers > 50000:
                                texts.append(f"{token_symbol.upper()} has an active Reddit community with {reddit_subscribers:,} subscribers")

                            if telegram_channel_user_count > 10000:
                                texts.append(f"{token_symbol.upper()} has a significant Telegram presence with {telegram_channel_user_count:,} users")

                            if "CoinGecko Community Data" not in sources:
                                sources.append("CoinGecko Community Data")

                except Exception as e:
                    logger.warning(f"Error fetching market data from {fallback_url}: {str(e)}")
                    continue

        # Analyze sentiment in all collected texts
        if texts:
            sentiment_result = {
                'sentiment_score': 0.0,
                'sentiment_category': 'neutral',
                'sample_size': 0,
                'sources': [],
                'analysis': 'No recent news or data available for analysis.'
            }
            
            try:
                if texts and len(texts) > 0:
                    # Calculate sentiment scores with error handling for each text
                    scores = []
                    for text in texts:
                        try:
                            if text and isinstance(text, str) and len(text.strip()) > 0:
                                score = sia.polarity_scores(text)['compound']
                                scores.append(score)
                        except Exception as e:
                            logger.warning(f"Error analyzing sentiment for text: {str(e)}")
                            continue
                    
                    if scores:  # Only proceed if we have valid scores
                        avg_score = sum(scores) / len(scores)
                        
                        # Categorize sentiment with more granular thresholds
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
                        
                        # Update result with analysis
                        sentiment_result.update({
                            'sentiment_score': float(avg_score),
                            'sentiment_category': sentiment,
                            'sample_size': len(scores),
                            'sources': sources[:5],  # Limit to top 5 sources
                            'analysis': ' '.join(text[:100] + '...' for text in texts[:3])  # Include preview of first 3 texts
                        })
                
                return sentiment_result
                
            except Exception as e:
                logger.error(f"Error in sentiment analysis: {str(e)}")
                sentiment_result['error'] = f"Error in sentiment analysis: {str(e)}"
                return sentiment_result
        else:
            return {
                "sentiment_score": 0,
                "sentiment_category": "neutral",
                "sample_size": 0,
                "sources": ["No data"]
            }
    except Exception as e:
        return {"error": f"Error analyzing sentiment: {str(e)}"}

async def get_token_outlook(token_symbol: str) -> str:
    """Get comprehensive outlook for a token including price and sentiment"""
    try:
        # Get price data
        price_data = await get_crypto_price(token_symbol)
        if "error" in price_data:
            return f"Error: {price_data['error']}"

        # Analyze sentiment
        sentiment_data = await analyze_sentiment(token_symbol)
        if "error" in sentiment_data:
            return f"Error in sentiment analysis: {sentiment_data['error']}"

        # Generate analysis with ASI LLM or fallback
        if ASI_LLM_KEY:
            try:
                # Determine price trend for additional context
                price_trend = "stable"
                if price_data['change_24h'] > 5:
                    price_trend = "in a significant uptrend"
                elif price_data['change_24h'] > 2:
                    price_trend = "in a moderate uptrend"
                elif price_data['change_24h'] < -5:
                    price_trend = "in a significant downtrend"
                elif price_data['change_24h'] < -2:
                    price_trend = "in a moderate downtrend"

                # Market context based on capitalization
                market_context = ""
                if price_data['market_cap'] > 100000000000:  # > $100B
                    market_context = "one of the largest cryptocurrencies in the market"
                elif price_data['market_cap'] > 10000000000:  # > $10B
                    market_context = "a large-cap cryptocurrency"
                elif price_data['market_cap'] > 1000000000:  # > $1B
                    market_context = "a mid-cap cryptocurrency"
                else:
                    market_context = "a small-cap cryptocurrency"

                # Prepare enhanced prompt for ASI LLM
                prompt = f"""
                Analyze the following data about the cryptocurrency {price_data['name']} ({price_data['symbol']}), {market_context} currently {price_trend}:

                Price and market data:
                - Current price: ${price_data['price_usd']:.4f}
                - 24h Change: {price_data['change_24h']:.2f}%
                - 7d Change: {price_data['price_change_7d']:.2f}%
                - 30d Change: {price_data['price_change_30d']:.2f}%
                - 24h Volume: ${price_data['volume_24h']:,.2f}
                - Market capitalization: ${price_data['market_cap']:,.2f}

                Market sentiment analysis:
                - Category: {sentiment_data['sentiment_category']}
                - Numeric score: {sentiment_data['sentiment_score']:.2f}
                - Based on {sentiment_data['sample_size']} data sources
                - Sources include: {', '.join(sentiment_data['sources'][:3])}

                Please provide a structured analysis with:
                1. Summary of the token's current situation and its market positioning
                2. Main technical and fundamental factors affecting the price
                3. Short-term outlook (next few days) based on the presented data
                4. Key points for investors interested in this asset

                Keep the response concise (maximum 200 words), neutral, and strictly based on the provided data.
                """

                # Call ASI LLM API with retry and increased timeout
                max_retries = 3  # Increased to 3 attempts
                retry_count = 0
                analysis = None

                while retry_count < max_retries and not analysis:
                    try:
                        payload = {
                            "model": "asi1-mini",
                            "temperature": 0.7,
                            "messages": [{"role": "user", "content": prompt}]
                        }

                        # Increase timeout to 30 seconds to avoid timeout on the first call
                        response = requests.post(ASI_LLM_URL, headers=ASI_HEADERS, json=payload, timeout=30)

                        if response.status_code == 200:
                            data = response.json()
                            analysis = data['choices'][0]['message']['content'].strip()
                            logger.info(f"Successfully obtained ASI analysis for {token_symbol}")
                        else:
                            logger.warning(f"ASI API returned status code {response.status_code}: {response.text}")
                            retry_count += 1
                            if retry_count < max_retries:
                                # Increase waiting time between attempts
                                wait_time = 2 * retry_count  # Exponential backoff: 2s, 4s, 6s...
                                logger.info(f"Retrying ASI API call ({retry_count}/{max_retries}) after {wait_time}s")
                                await asyncio.sleep(wait_time)
                    except requests.exceptions.Timeout as e:
                        logger.warning(f"Timeout error in ASI API call: {str(e)}")
                        retry_count += 1
                        if retry_count < max_retries:
                            # Increase waiting time between attempts for timeouts
                            wait_time = 3 * retry_count  # Longer backoff for timeouts: 3s, 6s, 9s...
                            logger.info(f"Retrying ASI API call after timeout ({retry_count}/{max_retries}) after {wait_time}s")
                            await asyncio.sleep(wait_time)
                    except Exception as e:
                        logger.warning(f"Error in ASI API call: {str(e)}")
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 2 * retry_count
                            logger.info(f"Retrying ASI API call ({retry_count}/{max_retries}) after {wait_time}s")
                            await asyncio.sleep(wait_time)

                # If all attempts fail, use fallback
                if not analysis:
                    logger.warning("All ASI API calls failed, using fallback analysis")
                    analysis = fallback_analysis(price_data, sentiment_data)
            except Exception as e:
                logger.warning(f"Error getting ASI analysis: {str(e)}")
                analysis = fallback_analysis(price_data, sentiment_data)
        else:
            # Fallback to simple analysis without LLM
            analysis = fallback_analysis(price_data, sentiment_data)

        # Format the final response with rich markdown
        # Price change emoji
        change_24h = price_data['change_24h']
        change_emoji = '🟢' if change_24h > 0 else '🔴' if change_24h < 0 else '⚪'
        
        # Sentiment emoji
        sentiment_score = sentiment_data['sentiment_score']
        if sentiment_score > 0.5:
            sentiment_emoji = '🚀'
        elif sentiment_score > 0.1:
            sentiment_emoji = '👍'
        elif sentiment_score < -0.5:
            sentiment_emoji = '⚠️'
        elif sentiment_score < -0.1:
            sentiment_emoji = '👎'
        else:
            sentiment_emoji = '➖'
            
        # Format numbers
        def format_currency(value):
            if value >= 1_000_000_000:
                return f'${value/1_000_000_000:.2f}B'
            elif value >= 1_000_000:
                return f'${value/1_000_000:.2f}M'
            elif value >= 1_000:
                return f'${value/1_000:.1f}K'
            return f'${value:.2f}'
            
        def format_percent(value):
            return f'+{value:.2f}%' if value > 0 else f'{value:.2f}%'

        # Format price trend with more visual indicators (simplified for better compatibility)
        def get_trend_arrow(change):
            try:
                change = float(change)
                if change > 5: return '↑↑'  # Strong up
                if change > 2: return '↑'    # Up
                if change < -5: return '↓↓'  # Strong down
                if change < -2: return '↓'   # Down
                return '→'                   # Neutral
            except (TypeError, ValueError):
                return '→'
            
        # Format sentiment with more visual indicators (simplified for better compatibility)
        def get_sentiment_visual(score):
            try:
                score = float(score)
                if score > 0.7: return '🚀 Extremely Bullish'
                if score > 0.4: return '↑ Very Bullish'
                if score > 0.1: return '↑ Bullish'
                if score > -0.1: return '→ Neutral'
                if score > -0.4: return '↓ Bearish'
                if score > -0.7: return '↓↓ Very Bearish'
                return '⚠️ Extremely Bearish'
            except (TypeError, ValueError):
                return '→ Neutral'
            
        # Generate price chart indicator (simplified)
        def get_price_indicator(change_24h, change_7d):
            try:
                change_24h = float(change_24h)
                change_7d = float(change_7d)
                if change_24h > 5 and change_7d > 5: return '↑↑'
                if change_24h > 2 and change_7d > 2: return '↑'
                if change_24h < -5 and change_7d < -5: return '↓↓'
                if change_24h < -2 and change_7d < -2: return '↓'
                if change_24h * change_7d < 0: return '↕️'
                return '→'
            except (TypeError, ValueError):
                return '→'
            
        # Build the response with UI format matching AVAX reference
        response = f"""
**{price_data.get('name', 'N/A')} ({price_data.get('symbol', 'N/A').upper()}) Market Overview**

💎 **Price & Market Data**
• Current Price: ${float(price_data.get('price_usd', 0)):,.2f}
• Market Cap: ${format_currency(price_data.get('market_cap', 0))}
• 24h Volume: ${format_currency(price_data.get('volume_24h', 0))}
• 24h Change: {change_emoji} {format_percent(change_24h)}
• 7d Change: {('🟢' if price_data.get('price_change_7d', 0) > 0 else '🔴')} {format_percent(price_data.get('price_change_7d', 0))}
• 30d Change: {('🟢' if price_data.get('price_change_30d', 0) > 0 else '🔴')} {format_percent(price_data.get('price_change_30d', 0))}

{'-' * 60}

🎯 **Sentiment Analysis**
• Score: {float(sentiment_data.get('sentiment_score', 0)):.2f}/1.0
• Category: {('🔥' if sentiment_score > 0.7 else '')} {str(sentiment_data.get('sentiment_category', 'N/A')).title()}

{'-' * 60}

🔍 **Market Analysis**
**Current Situation & Market Positioning**
{price_data.get('symbol', 'N/A').upper()} is a {('large' if price_data.get('market_cap', 0) > 10000000000 else 'mid' if price_data.get('market_cap', 0) > 1000000000 else 'small')}-cap cryptocurrency with a market cap of ${format_currency(price_data.get('market_cap', 0))}. Despite a {('minor' if abs(change_24h) < 2 else 'significant')} 24-hour {('gain' if change_24h > 0 else 'decline')} of {format_percent(change_24h)}, it shows {('strong' if abs(price_data.get('price_change_30d', 0)) > 20 else 'moderate')} resilience with a {format_percent(price_data.get('price_change_30d', 0))} gain over 30 days. The ${format_currency(price_data.get('volume_24h', 0))} 24-hour trading volume indicates {('high' if price_data.get('volume_24h', 0) > price_data.get('market_cap', 0) * 0.1 else 'moderate' if price_data.get('volume_24h', 0) > price_data.get('market_cap', 0) * 0.05 else 'low')} liquidity in the market.

**Technical & Fundamental Drivers**

• **Technical**: {('Mixed short-term signals with a slight 24h dip but positive 7d and 30d trends' if change_24h < 0 and price_data.get('price_change_7d', 0) > 0 and price_data.get('price_change_30d', 0) > 0 else 'Consistent bullish pattern across all timeframes' if change_24h > 0 and price_data.get('price_change_7d', 0) > 0 and price_data.get('price_change_30d', 0) > 0 else 'Consistent bearish pattern across all timeframes' if change_24h < 0 and price_data.get('price_change_7d', 0) < 0 and price_data.get('price_change_30d', 0) < 0 else 'Short-term volatility with mixed signals across different timeframes')}.

• **Fundamentals**: Strong {str(sentiment_data.get('sentiment_category', 'neutral')).lower()} sentiment at {float(sentiment_data.get('sentiment_score', 0)):.2f} score driven by community confidence and adoption.

• **Sources**: {', '.join(sentiment_data.get('sources', ['N/A'])[:3])}

**Short-Term Outlook**
Expect potential {('consolidation or uptrend' if sentiment_score > 0.5 else 'consolidation or retracement')}, depending on broader crypto market sentiment. The {('stable' if abs(change_24h) < 2 else 'volatile')} 7-day performance suggests {('resilience' if change_24h > 0 else 'caution')} against short-term bearish pressure.

**Investor Considerations**

• **Monitor**: Sustainability of the {('30-day growth' if price_data.get('price_change_30d', 0) > 10 else 'current')} trend.

• **Evaluate**: {('High bullish' if sentiment_score > 0.7 else 'Moderate' if sentiment_score > 0.5 else 'Low')} sentiment against short-term volatility.

• **Assess**: {price_data.get('name', 'Token')}'s blockchain upgrades and foundational utility.

• **Strategy**:
  - **Risk-tolerant investors**: Consider dips as potential entry points.
  - **Cautious investors**: Wait for clearer trends before acting.

{'-' * 60}

📊 **Metadata**
• **Last Updated**: {datetime.fromtimestamp(price_data.get('last_updated', time.time())).strftime('%b %d, %Y, %H:%M:%S')}
"""
        
        # No need for extra separation with new formatting
        response = response.strip()
        return response

    except Exception as e:
        return f"Error generating token outlook: {str(e)}"

def fallback_analysis(price_data, sentiment_data):
    """Generate a fallback analysis when ASI LLM is unavailable"""
    # Determine price trend in different periods
    trend_24h = "stable"
    if price_data['change_24h'] > 5:
        trend_24h = "in a strong uptrend"
    elif price_data['change_24h'] > 2:
        trend_24h = "in an uptrend"
    elif price_data['change_24h'] < -5:
        trend_24h = "in a strong downtrend"
    elif price_data['change_24h'] < -2:
        trend_24h = "in a downtrend"

    trend_7d = "stable"
    if price_data['price_change_7d'] > 10:
        trend_7d = "in a strong uptrend"
    elif price_data['price_change_7d'] > 5:
        trend_7d = "in an uptrend"
    elif price_data['price_change_7d'] < -10:
        trend_7d = "in a strong downtrend"
    elif price_data['price_change_7d'] < -5:
        trend_7d = "in a downtrend"

    # Analyze volume in relation to market capitalization
    volume_analysis = ""
    if price_data['market_cap'] > 0: # Avoid division by zero
        volume_to_mcap = (price_data['volume_24h'] / price_data['market_cap']) * 100
        if volume_to_mcap > 15:
            volume_analysis = "Very high trading volume, indicating strong market interest."
        elif volume_to_mcap > 10:
            volume_analysis = "Above-average trading volume, showing significant interest."
        elif volume_to_mcap < 3:
            volume_analysis = "Low trading volume, suggesting little current market interest."
        else:
            volume_analysis = "Trading volume at normal levels."
    else:
        volume_analysis = "Market capitalization data unavailable for volume analysis."


    # Classify the token by market capitalization
    market_position = ""
    if price_data['market_cap'] > 100000000000:  # > $100B
        market_position = "one of the main cryptocurrencies in the market (top tier)"
    elif price_data['market_cap'] > 10000000000:  # > $10B
        market_position = "a large-cap cryptocurrency"
    elif price_data['market_cap'] > 1000000000:  # > $1B
        market_position = "a mid-cap cryptocurrency"
    else:
        market_position = "a small-cap cryptocurrency"

    # Determine sentiment
    sentiment = sentiment_data['sentiment_category']
    sentiment_strength = abs(sentiment_data['sentiment_score'])
    sentiment_intensity = "moderate"
    if sentiment_strength > 0.5:
        sentiment_intensity = "strong"
    elif sentiment_strength < 0.2:
        sentiment_intensity = "weak"

    # Generate structured analysis
    analysis = f"""**Current Situation Summary:**
{price_data['name']} ({price_data['symbol']}) is {market_position} currently priced at ${price_data['price_usd']:.4f}. The token is {trend_24h} in the last 24 hours ({price_data['change_24h']:.2f}%) and {trend_7d} in the last week ({price_data['price_change_7d']:.2f}%). {volume_analysis}

**Technical and Fundamental Factors:**
Market sentiment is {sentiment} with {sentiment_intensity} intensity, based on {sentiment_data['sample_size']} sources, including {', '.join(sentiment_data['sources'][:2])}. """

    # Add short-term outlook
    if sentiment == "bullish" and price_data['change_24h'] > 0:
        analysis += f"""\n\n**Short-Term Outlook:**
The combination of rising price and positive sentiment suggests potential for continued upward movement in the short term. Technical support appears to be strengthened by current volume."""
    elif sentiment == "bearish" and price_data['change_24h'] < 0:
        analysis += f"""\n\n**Short-Term Outlook:**
The combination of falling price and negative sentiment suggests possible continuation of selling pressure in the short term. Investors should watch important support levels."""
    elif sentiment == "bullish" and price_data['change_24h'] < 0:
        analysis += f"""\n\n**Short-Term Outlook:**
Despite the recent drop, positive sentiment may indicate a possible reversal or stabilization in the short term. This divergence deserves special attention."""
    elif sentiment == "bearish" and price_data['change_24h'] > 0:
        analysis += f"""\n\n**Short-Term Outlook:**
Despite the recent rise, negative sentiment suggests caution, as there may be resistance to continued movement. Consider the possibility of profit-taking."""
    else:
        analysis += f"""\n\n**Short-Term Outlook:**
The market seems to be in a moment of indecision, with mixed technical signals. Caution and observation of trend breaks are recommended before making decisions."""

    # Add key points to watch
    analysis += f"""\n\n**Key Points to Watch:**
- Monitor trading volume to confirm the strength of the current trend
- Stay alert to specific news about {price_data['symbol']} that could impact its price
- Consider the overall cryptocurrency market context when making decisions"""

    return analysis

# Handlers for the chat protocol
@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages and respond with token analysis"""
    # Extract message content in the correct format
    # Logging message structure for debugging
    ctx.logger.info(f"Received message structure: {type(msg)} with content: {type(msg.content)}")

    # Process content which may be in different formats
    if isinstance(msg.content, list):
        # If content is a list, take the first element
        content_list = msg.content
        if content_list and hasattr(content_list[0], 'text'):
            user_message = content_list[0].text
        else:
            # Fallback to convert list to string
            user_message = str(content_list)
    elif hasattr(msg.content, 'text'):
        # If content is an object with a text attribute
        user_message = msg.content.text
    else:
        # Fallback for any other type
        user_message = str(msg.content)

    logger.info(f"Received message from {sender}: {user_message}")

    # Extract token symbol from message
    token_symbol = extract_token_from_query(user_message)

    if not token_symbol:
        # Send response when we cannot identify a token
        response_text = "I couldn't identify a cryptocurrency in your message. Please specify a cryptocurrency like BTC, ETH, or LINK."

        # Send using the official ChatMessage format
        response_msg = ChatMessage(
            timestamp=datetime.now().timestamp(),
            msg_id=str(uuid4()),
            content=[{"type": "text", "text": response_text}]
        )

        # Log message for debugging
        ctx.logger.info(f"Sending response: {response_text} with format {type(response_msg)}")

        await ctx.send(
            sender,
            response_msg
        )
        return

    # Get complete token analysis
    response = await get_token_outlook(token_symbol)

    # Send using the most compatible ChatMessage format
    response_msg = ChatMessage(
        timestamp=datetime.now().timestamp(),
        msg_id=str(uuid4()),
        content=[{"type": "text", "text": response}]
    )

    # Log message for debugging
    ctx.logger.info(f"Sending token analysis with format {type(response_msg)}")

    try:
        await ctx.send(
            sender,
            response_msg
        )
    except Exception as e:
        # Catch and log any error when sending the message
        ctx.logger.error(f"Error sending message: {str(e)}")

        # Try alternative format as a last resort
        try:
            alt_msg = {"message": response}
            ctx.logger.info("Trying alternative message format as last resort")
            await ctx.send(sender, alt_msg)
        except Exception as e2:
            ctx.logger.error(f"Alternative format also failed: {str(e2)}")

@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgement messages"""
    ctx.logger.info(f"Acknowledgement received from {sender} for msg_id {msg.acknowledged_msg_id}")

# Add handlers for direct messages
@token_agent.on_event("startup")
async def startup_handler(ctx: Context):
    addr = token_agent.address
    ctx.logger.info(f"Token Sentiment & Price Tracker is running!")
    ctx.logger.info(f"Agent Address: {addr}")
    ctx.logger.info(f"Add this agent to chat.agentverse.ai")

# Periodically check agent status
@token_agent.on_interval(period=60.0)
async def status_check(ctx: Context):
    ctx.logger.info(f"Agent is running. Address: {token_agent.address}")

# Include chat protocol in the agent with error debugging
try:
    token_agent.include(chat_proto, publish_manifest=True)
    logger.info("Chat protocol successfully included")
except Exception as e:
    logger.error(f"Error including chat protocol: {str(e)}")
    # Try including without manifest as an alternative
    try:
        token_agent.include(chat_proto)
        logger.info("Chat protocol included without manifest")
    except Exception as e2:
        logger.error(f"Complete failure including protocol: {str(e2)}")
        # Continue even with the error

if __name__ == "__main__":
    # Start the agent
    print("Starting Token Sentiment & Price Tracker Agent...")
    print(f"Agent address: {token_agent.address}")
    print("Access this agent at chat.agentverse.ai")
    print("Ctrl+C to exit")

    try:
        # Start the agent and keep it running
        token_agent.run()
    except KeyboardInterrupt:
        print("\nAgent stopped by user.")
    except Exception as e:
        print(f"\nError: {str(e)}")
        # Try to restart the agent in case of error
        print("Attempting to restart agent...")
        token_agent.run()