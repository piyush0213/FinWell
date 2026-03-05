from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent,
    chat_protocol_spec,
)
from datetime import datetime
from uuid import uuid4

advisor = Agent(name="advisor_agent", seed="advisor_seed_phrase")
chat_proto = Protocol(spec=chat_protocol_spec)

# Replace with real addresses (AgentVerse or MCP)
ANALYST_ADDRESS = "agent1q0ejvvp7x302ulx05389ncdfellmag6up4d2raa9v7dfrjarh4v52237sq7"
NEWS_ADDRESS = "agent1qw8zfyazf0ajmsl3gm6gdnm0m824sp6qq6xw9krtvuva9lt5xfvf55c0wce"
CRYPTO_ADDRESS = "agent1q0h70caed8ax769shpemapzkyk65uscw4xwk6dc4t3emvp5jdcvqs9xs32y"
SOLANA_ADDRESS = "agent1q0h70caed8ax769shpemapzkyk65uscw4xwk6dc4t3emvp5jdcvqs9xs32y"
HEALTH_ADDRESS = "agent1qv3dag4483k5dv4wkcncy65xpyrq4hgwk6nvuf0xzrhfz33cxaqj6xpg9c7"


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


@chat_proto.on_message(ChatMessage)
async def route_message(ctx: Context, sender: str, msg: ChatMessage):
    content = extract_text(msg).lower()

    if "stock" in content or "share" in content or "market" in content:
        await ctx.send(ANALYST_ADDRESS, create_text_chat(extract_text(msg)))
        await ctx.send(NEWS_ADDRESS, create_text_chat(extract_text(msg)))

    elif "crypto" in content or "bitcoin" in content or "solana" in content:
        await ctx.send(CRYPTO_ADDRESS, create_text_chat(extract_text(msg)))
        await ctx.send(SOLANA_ADDRESS, create_text_chat(extract_text(msg)))

    elif "health" in content or "symptom" in content or "insurance" in content:
        await ctx.send(HEALTH_ADDRESS, create_text_chat(extract_text(msg)))

    else:
        await ctx.send(sender, create_text_chat("❓ Sorry, I couldn't understand your query."))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Ack from {sender} for {msg.acknowledged_msg_id}")


advisor.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    advisor.run()
