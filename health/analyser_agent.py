from uagents import Agent, Context, Model

class Message(Model):
    query: str
    response: str = None

class MedicationResponse(Model):
    response: str

class ASI1miniRequest(Model):
    query: str

class ASI1miniResponse(Model):
    response: str

class SymptomResponse(Model):
    response: str

# FIXED AGENT ADDRESSES
ASI_AGENT_ID = "agent1qt69zmtdwud67k7t3nmp353l0y7u8j3q6t9fdy6f4v54258huxre6pnxgwz"
CLI_AGENT_ADDRESS = "agent1qv3dag4483k5dv4wkcncy65xpyrq4hgwk6nvuf0xzrhfz33cxaqj6xpg9c7"
INSURANCE_AGENT_ADDRESS = "agent1qvwjtya8ncl5shwr7m8p80jw7l20lplt0ahtx40gzl3vsaeq4jr3kzuhfz4"

agent = Agent(
    name="AnalyserAgent",
    seed="analyser_seed",
    port=8006,
    endpoint=["http://localhost:8006/submit"],
)

@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("[Analyser] Agent is live!")

async def prompting(query: str):
    return (
        f"Respond to the following user request about medication: {query}. "
        f"Provide reminders, dosage info, or any safety suggestions as needed."
    )

@agent.on_message(model=Message)
async def forward_to_asi(ctx: Context, sender: str, msg: Message):
    ctx.logger.info(f"[Analyser] Received user query: {msg.query}")
    prompt = await prompting(msg.query)
    await ctx.send(ASI_AGENT_ID, ASI1miniRequest(query=prompt))

@agent.on_message(model=ASI1miniResponse)
async def analyze_and_respond(ctx: Context, sender: str, msg: ASI1miniResponse):
    ctx.logger.info(f"[Analyser] Analyzing ASI1 response: {msg.response}")
    
    summary = f"[Analyzed] {msg.response}"

    try:
        await ctx.send(CLI_AGENT_ADDRESS, SymptomResponse(response=summary))
        ctx.logger.info("[Analyser] Sent response to CLI agent")
        
        await ctx.send(INSURANCE_AGENT_ADDRESS, SymptomResponse(response=summary))
        ctx.logger.info("[Analyser] Sent response to insurance agent")
        
    except Exception as e:
        ctx.logger.error(f"[Analyser] Failed to send responses: {e}")

if __name__ == "__main__":
    agent.run()