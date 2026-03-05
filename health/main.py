from uagents import Agent, Context, Model
import asyncio

# Global flag to control CLI loop
insurance_handled = False

# Message Models
class Message(Model):
    query: str
    response: str = None

class SymptomResponse(Model):
    response: str

class MedicationResponse(Model):
    response: str

class InsuranceQuery(Model):
    income: int

class InsuranceOptions(Model):
    options: list

# Constants for agent addresses - FIXED ADDRESSES
ANALYSER_AGENT = "agent1qdkulla80gkjdumy6qp867x6u9wwqkrya0r4eks6zs520lqp6r3g200d83u"
COLLECTOR_AGENT = "agent1qv35ejh6fx6p5smyqzk9ts2qklhkk7gn5470nt0x3s7an3f7jvfxvlf5222"
INSURANCE_AGENT = "agent1qvwjtya8ncl5shwr7m8p80jw7l20lplt0ahtx40gzl3vsaeq4jr3kzuhfz4"

# Response queue
response_queue = asyncio.Queue()

# CLI Agent
cli_agent = Agent(
    name="CLIFrontendAgent",
    seed="cli_agent_seed_phrase",
    port=8000,
    endpoint=["http://127.0.0.1:8000/submit"],
)

# Routing Function
def route_query(query: str) -> str:
    q = query.lower()
    if any(word in q for word in ["medication", "pill", "reminder", "dose", "tablet"]):
        return ANALYSER_AGENT
    return COLLECTOR_AGENT

# Symptom Response Handler
@cli_agent.on_message(model=SymptomResponse)
async def symptom_response(ctx: Context, sender: str, msg: SymptomResponse):
    ctx.logger.info(f"Received symptom response from {sender}: {msg.response}")
    await response_queue.put(("symptom", sender, msg.response))

# Medication Response Handler
@cli_agent.on_message(model=MedicationResponse)
async def medication_response(ctx: Context, sender: str, msg: MedicationResponse):
    ctx.logger.info(f"Received medication response from {sender}: {msg.response}")
    await response_queue.put(("medication", sender, msg.response))

# Insurance Recommendations Handler
@cli_agent.on_message(model=InsuranceOptions)
async def show_insurance(ctx: Context, sender: str, msg: InsuranceOptions):
    global insurance_handled
    ctx.logger.info(f"Received insurance options from {sender}: {msg.options}")
    print("\n[Insurance] Recommended Health Insurance Plans:")
    for i, plan in enumerate(msg.options, 1):
        print(f"{i}. {plan}")
    print("\n[Done] Exiting after showing insurance recommendations.")
    insurance_handled = True
    print("[OK] Session completed. Waiting for final messages...\n")

# Main CLI Loop
@cli_agent.on_event("startup")
async def startup(ctx: Context):
    global insurance_handled
    print("[FinWell Health] MedAgent CLI is running!")
    print(f"Your agent address: {cli_agent.address}")
    print("Type your health query below (type 'exit' to quit):")

    # Give some time for agent to fully start
    await asyncio.sleep(2)

    while not insurance_handled:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ["exit", "quit"]:
                print("Exiting CLI.")
                break

            # Check if user entered income directly
            if user_input.isdigit():
                try:
                    income = int(user_input)
                    await ctx.send(INSURANCE_AGENT, InsuranceQuery(income=income))
                    print(f"[Sent] Income sent to insurance agent")
                    await asyncio.sleep(3)
                    continue
                except ValueError:
                    print("[Error] Invalid income. Please enter a valid number.")
                    continue

            # Route query to appropriate agent
            target = route_query(user_input)
            msg = Message(query=user_input)

            await ctx.send(target, msg)
            print(f"[Sent] Message sent. Waiting for response...\n")

            # Wait for response with timeout
            try:
                response_data = await asyncio.wait_for(response_queue.get(), timeout=30.0)
                response_type, sender, response = response_data
                print(f"[Response] {response}\n")

                # Check for serious conditions
                if any(keyword in response.lower() for keyword in [
                    "serious", "emergency", "critical", "life-threatening", "chest pain"
                ]):
                    print("[Alert] This condition may be serious.")
                    print("[Insurance] Do you have health insurance? If not, enter your monthly income.")

            except asyncio.TimeoutError:
                print("[Timeout] No response received. Please try again.")

        except KeyboardInterrupt:
            print("\nExiting CLI.")
            break
        except Exception as e:
            print(f"[Error] {e}")

# Run Agent
if __name__ == "__main__":
    cli_agent.run()