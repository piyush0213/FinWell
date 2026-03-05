from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool
from crewai_tools import ScrapeWebsiteTool
from pydantic import BaseModel, Field
import requests
from dotenv import load_dotenv
import os

# --- ENVIRONMENT & LLM SETUP ---
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
ASI_KEY = os.getenv("ASI_KEY")
if not ASI_KEY or ASI_KEY == "your_asi_key_here":
    print("⚠️  WARNING: ASI_KEY not set in .env. News summarization will not work.")
    print("   Add your ASI key to .env")
    ASI_KEY = None

llm = LLM(
    model="asi1-mini",
    endpoint="https://api.asi1.ai/v1/chat/completions",
    api_key=ASI_KEY,
    temperature=0.0
)

# --- TOOL DEFINITIONS ---
class YahooFinanceArgs(BaseModel):
    endpoint: str = Field(..., description="API endpoint path, e.g., /stock/news")
    payload: dict = Field(..., description="POST data for the request.")

class YahooFinanceTool(BaseTool):
    name: str = "Yahoo Finance API Tool"
    description: str = (
        "Accesses the local Yahoo Finance FastAPI server. "
        "Arguments: endpoint (e.g., '/stock/news'), payload (JSON body for request)."
    )
    args_schema: type = YahooFinanceArgs

    def _run(self, endpoint, payload):
        url = f"http://localhost:8000{endpoint}"
        response = requests.post(url, json=payload)
        try:
            response.raise_for_status()
        except Exception as e:
            return f"Error: {str(e)}"
        return response.json()

yahoo_tool = YahooFinanceTool()
scraper_tool = ScrapeWebsiteTool()

def get_news_list(ticker):
    news_list = yahoo_tool._run(
        endpoint='/stock/news',
        payload={'ticker': ticker}
    )
    if isinstance(news_list, list) and len(news_list) > 0:
        return news_list
    else:
        raise Exception("No news found.")

# --- TICKER AND NUMBER EXTRACTOR AGENT ---
extractor_agent = Agent(
    role="Ticker and Count Extractor",
    goal="Extract the stock ticker and desired number of news articles to summarize from user queries.",
    backstory=(
        "You're an expert at interpreting requests for financial news. Extract BOTH the stock ticker (e.g. TSLA, VEDL.NS) "
        "and the number of articles to summarize. If the user specifies a number (e.g., 'top 3'), use it. If not, make a smart guess: "
        "- Use 1 for queries like 'top article', 'latest news', or similar. "
        "- Use 5 for general requests like 'recent events', 'summarise news', or if the user seems to want more than one. "
        "Return your answer as: TICKER | NUMBER (e.g., 'TSLA | 3'). If no ticker is found, return 'UNKNOWN | 0'."
    ),
    tools=[],
    llm=llm,
    verbose=True
)

def extract_ticker_and_count(user_query):
    extraction_prompt = (
        f"User message: \"{user_query}\"\n"
        "Extract the stock ticker and the number of news articles to summarize. "
        "If the user says 'top 3', use 3; if they say 'summarise the latest', use 1; if they say 'recent news', guess 5. "
        "Output ONLY: <TICKER> | <NUMBER> (e.g. 'TSLA | 3'). If no ticker, return 'UNKNOWN | 0'."
    )
    extract_task = Task(
        description=extraction_prompt,
        expected_output="Ticker and number (e.g., 'TCS.NS | 3'), or 'UNKNOWN | 0'.",
        agent=extractor_agent
    )
    crew_extract = Crew(agents=[extractor_agent], tasks=[extract_task], verbose=False)
    extracted = crew_extract.kickoff()
    if hasattr(extracted, "final_output"):
        result = extracted.final_output.strip().upper()
    elif hasattr(extracted, "output"):
        result = extracted.output.strip().upper()
    elif isinstance(extracted, str):
        result = extracted.strip().upper()
    else:
        result = str(extracted).strip().upper()
    if "|" not in result:
        return "UNKNOWN", 0
    ticker, number = [x.strip() for x in result.split("|", 1)]
    try:
        number = int(number)
    except Exception:
        number = 0
    return ticker, number

# --- NEWS SUMMARIZER AGENT ---
summarizer_agent = Agent(
    role="News Summarizer",
    goal="Summarize the most important news for a stock.",
    backstory="A financial analyst bot who distills web articles into actionable investment summaries.",
    tools=[scraper_tool],
    llm=llm,
    verbose=True,
)

def build_summarize_task(news_url, title, mcp_summary):
    return Task(
        description=(
            f"Title of article: {title}\n"
            f"Original short summary: {mcp_summary}\n"
            f"Scrape the news article at the following URL:\n{news_url}\n"
            "IMPORTANT: These sites often include large blocks of irrelevant or repetitive content (navigation bars, service/product menus, footers, boilerplate, etc.). "
            "You MUST NOT include or refer to the following types of content in your summary:\n\n"
            "- **Navigation or menu sections** (e.g., 'Our Services', 'Stock Market News', 'Help', 'Log In', 'Accessibility', 'Home', 'Join The Motley Fool')\n"
            "- **Branding, mission, or about us text** (e.g., 'Our Purpose: To make the world smarter, happier, and richer.', 'About Us', 'Founded in 1993...')\n"
            "- **Site boilerplate or footer/legal** (e.g., 'Terms of Use', 'Privacy Policy', 'Copyright', 'All rights reserved', 'Contact', 'CAPS - Stock Picking Community')\n"
            "- **Subscription, upgrade, or newsletter ads** (e.g., 'Become a member', 'Sign up for Premium', 'View Premium Services', 'Newsletter')\n"
            "- **Stock tickers, market widgets, or sidebars** (e.g., 'S&P 500 5,911.69 -0.0%', 'NASDAQ 19,113.77', 'AAPL $201.47')\n"
            "- **Social media or sharing widgets** (e.g., 'Facebook', 'Twitter', 'YouTube', 'Share', 'LinkedIn')\n"
            "- **Repeated lists of products/services** (e.g., 'Stock Advisor', 'Epic', 'Fool Portfolios', 'Fool Podcasts')\n"
            "- **Lists of unrelated or 'related articles'** (e.g., 'Related Articles', 'See also', 'More from...')\n"
            "- **Search bars, login prompts, cookie banners, accessibility menus**\n"
            "- **Any repeated, generic, or unrelated investing tips not specific to this article's topic**\n\n"
            "Carefully read both the title and the provided short summary, and ONLY extract and summarize content from the scraped data that is relevant to BOTH the title and the summary. "
            "If most of the scraped page is menus, site footers, boilerplate, or unrelated information, or you cannot find relevant content matching the title/summary, reply with:\n"
            "'⚠️ No relevant article content found.'\n"
            "Otherwise, give a concise summary of the main points from the relevant article content (focus on financial/investment implications), and IGNORE all the categories above. "
            "Your output must be a plain English readable summary—never include any HTML, navigation, or site menus. If you are unsure, **err on the side of skipping irrelevant content**."
        ),
        expected_output="A summary of the article's main points (no code, no table, just text).",
        agent=summarizer_agent
    )

if __name__ == "__main__":
    print("Welcome to the News Summarizer! (Type 'exit' or 'quit' to stop.)\n")
    while True:
        try:
            user_query = input("You: ").strip()
            if user_query.lower() in ["exit", "quit", "q"]:
                print("Exiting. Have a great day!")
                break

            ticker, num_articles = extract_ticker_and_count(user_query)
            if not ticker or ticker == "UNKNOWN":
                print("Sorry, I could not identify a ticker symbol. Please try again (e.g., 'summarize news for TSLA').\n")
                continue
            if num_articles <= 0:
                print("Sorry, I could not figure out how many articles you want. Please clarify (e.g., 'top 3 TSLA news').\n")
                continue

            print(f"\nFetching news articles for {ticker} ...")
            try:
                news_list = get_news_list(ticker)
            except Exception as e:
                print(f"Error fetching news for {ticker}: {e}")
                continue
            total_articles = len(news_list)
            if total_articles == 0:
                print(f"No news articles found for {ticker}.\n")
                continue
            print(f"{total_articles} news articles found.")

            num_to_summarize = min(num_articles, total_articles)
            results = []

            for idx in range(num_to_summarize):
                article = news_list[idx]
                news_url = article.get('url', '')
                title = article.get('title', 'Untitled')
                mcp_summary = article.get('summary', '')

                print(f"\nScraping and summarizing article {idx + 1} of {num_to_summarize}: {title}\nURL: {news_url}")
                scraper_tool.website_url = news_url
                summarize_task = build_summarize_task(news_url, title, mcp_summary)
                crew = Crew(
                    agents=[summarizer_agent],
                    tasks=[summarize_task],
                    verbose=True,
                )
                summary_output = crew.kickoff()
                if hasattr(summary_output, "final_output"):
                    summary = summary_output.final_output
                elif hasattr(summary_output, "output"):
                    summary = summary_output.output
                elif isinstance(summary_output, str):
                    summary = summary_output
                else:
                    summary = str(summary_output)
                results.append({
                    'title': title,
                    'summary': summary,
                    'link': news_url
                })

            print("\n=== NEWS SUMMARIES ===")
            for idx, item in enumerate(results, start=1):
                print(f"{idx}. Title: {item['title']}\n")
                print(f"Summary: {item['summary']}\n")
                print(f"Link: {item['link']}\n")
                print("-" * 80)
            print()  # Print an extra line for readability
        except KeyboardInterrupt:
            print("\nExiting. Have a great day!")
            break
