from uagents import Agent, Context, Model
import requests

# Define schemas
class ASI1miniRequest(Model):
    query: str

class ASI1miniResponse(Model):
    response: str

# Using the exact same seed to maintain the agent ID
asi1_agent = Agent(
    name="ASIWrapperAgent",
    seed="asi_wrapper_seed",
    port=8009,
    endpoint=["http://127.0.0.1:8009/submit"],
)

ASI1_LLM_ENDPOINT = "https://asi1.ai/chat"
HEADERS = {
    "Authorization": "sk_d28825f98e2944d69f4f87750bcb711605e09bdda4a94176b467fc88fe11b19f",
    "Content-Type": "application/json"
}

@asi1_agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("[ASI1] Wrapper Agent is live!")
    ctx.logger.info(f"[ASI1] Agent address: {asi1_agent.address}")

@asi1_agent.on_message(model=ASI1miniRequest)
async def handle_query(ctx: Context, sender: str, msg: ASI1miniRequest):
    ctx.logger.info(f"[ASI1] Received query from {sender}: {msg.query}")

    try:
        response = f"[Mock ASI Response] Insight based on your query: {msg.query}"
        ctx.logger.info(f"[ASI1] Response generated: {response}")
        
        await ctx.send(sender, ASI1miniResponse(response=response))
        ctx.logger.info(f"[ASI1] Response sent back to {sender}")
        
    except Exception as e:
        response = "Sorry, failed to reach ASI1 endpoint."
        ctx.logger.error(f"[ASI1] Error: {str(e)}")
        await ctx.send(sender, ASI1miniResponse(response=response))

if __name__ == "__main__":
    asi1_agent.run()