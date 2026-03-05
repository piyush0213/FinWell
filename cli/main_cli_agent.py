from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent,
    chat_protocol_spec,
)
from datetime import datetime
from uuid import uuid4

main_cli_agent = Agent(name="main_cli_agent", seed="main_cli_seed_phrase")
chat_proto = Protocol(spec=chat_protocol_spec)

# Advisor address
ADVISOR_ADDRESS = "agent1qv3dag4483k5dv4wkcncy65xpyrq4hgwk6nvuf0xzrhfz33cxaqj6xpg9c7"


def create_text_chat(text: str) -> ChatMessage:
    """Helper to create a ChatMessage with TextContent."""
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text)],
    )


def extract_text(msg: ChatMessage) -> str:
    """Extract plain text from a ChatMessage's content list."""
    for item in msg.content:
        if isinstance(item, TextContent):
            return item.text
    return str(msg.content)


@main_cli_agent.on_event("startup")
async def intro(ctx: Context):
    ctx.logger.info("🤖 Welcome to FinWell – Your Personal Finance & Wellness Copilot")


@main_cli_agent.on_interval(period=10)
async def query_input(ctx: Context):
    user_input = input("🧑 You: ").strip()
    if user_input:
        await ctx.send(ADVISOR_ADDRESS, create_text_chat(user_input))


@chat_proto.on_message(ChatMessage)
async def show_reply(ctx: Context, sender: str, msg: ChatMessage):
    print(f"🤖 FinWell: {extract_text(msg)}")


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Ack from {sender} for {msg.acknowledged_msg_id}")


main_cli_agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    main_cli_agent.run()
