from datetime import datetime
from uuid import uuid4
from typing import Any

from uagents import Context, Model, Protocol, Field

# Import the necessary components of the chat protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from solana_service import (
    get_balance_from_address,
    get_recent_transactions,
    get_token_balances,
    get_account_info,
)

# AI Agent Address for structured output processing
AI_AGENT_ADDRESS = 'agent1q0h70caed8ax769shpemapzkyk65uscw4xwk6dc4t3emvp5jdcvqs9xs32y'

if not AI_AGENT_ADDRESS:
    raise ValueError("AI_AGENT_ADDRESS not set")

def create_text_chat(text: str, end_session: bool = True) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=content,
    )

chat_proto = Protocol(spec=chat_protocol_spec)
struct_output_client_proto = Protocol(
    name="StructuredOutputClientProtocol", version="0.1.0"
)

# --- Updated schema with action field ---
class SolanaActionRequest(Model):
    address: str = Field(description="Solana wallet address")
    action: str = Field(description="Action to perform: balance, transactions, tokens, info")

class StructuredOutputPrompt(Model):
    prompt: str
    output_schema: dict[str, Any]

class StructuredOutputResponse(Model):
    output: dict[str, Any]

@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Got a message from {sender}: {msg}")
    ctx.storage.set(str(ctx.session), sender)
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id),
    )

    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Got a start session message from {sender}")
            continue
        elif isinstance(item, TextContent):
            ctx.logger.info(f"Got a message from {sender}: {item.text}")
            ctx.storage.set(str(ctx.session), sender)
            await ctx.send(
                AI_AGENT_ADDRESS,
                StructuredOutputPrompt(
                    prompt=item.text, output_schema=SolanaActionRequest.schema()
                ),
            )
        else:
            ctx.logger.info(f"Got unexpected content from {sender}")

@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}"
    )

@struct_output_client_proto.on_message(StructuredOutputResponse)
async def handle_structured_output_response(
    ctx: Context, sender: str, msg: StructuredOutputResponse
):
    session_sender = ctx.storage.get(str(ctx.session))
    if session_sender is None:
        ctx.logger.error(
            "Discarding message because no session sender found in storage"
        )
        return

    if "<UNKNOWN>" in str(msg.output):
        await ctx.send(
            session_sender,
            create_text_chat(
                "Sorry, I couldn't process your request. Please include a valid Solana wallet address."
            ),
        )
        return

    try:
        # Parse the structured output to get the address and action
        wallet_request = SolanaActionRequest.parse_obj(msg.output)
        address = wallet_request.address
        action = wallet_request.action.lower() if hasattr(wallet_request, "action") else "balance"
        
        if not address:
            await ctx.send(
                session_sender,
                create_text_chat(
                    "Sorry, I couldn't find a valid Solana wallet address in your query."
                ),
            )
            return

        response_text = ""

        if "transaction" in action or "history" in action or "recent" in action:
            txs = await get_recent_transactions(address)
            if isinstance(txs, str):
                response_text = f"Error fetching transactions: {txs}"
            else:
                tx_list = "\n".join(f"- [{sig}](https://explorer.solana.com/tx/{sig})" for sig in txs)
                response_text = (
                    f"Recent Transactions for `{address}`:\n{tx_list or 'No transactions found.'}\n\n"
                    f"[View on Solana Explorer](https://explorer.solana.com/address/{address})"
                )
        elif "token" in action:
            tokens = await get_token_balances(address)
            if isinstance(tokens, str):
                response_text = f"Error fetching token balances: {tokens}"
            else:
                token_lines = "\n".join(f"- Mint: `{t['mint']}` | Amount: {t['amount']}" for t in tokens)
                response_text = (
                    f"Token Balances for `{address}`:\n{token_lines or 'No tokens found.'}\n\n"
                    f"[View on Solana Explorer](https://explorer.solana.com/address/{address})"
                )
        elif "info" in action or "account" in action:
            info = await get_account_info(address)
            if isinstance(info, str):
                response_text = f"Error fetching account info: {info}"
            else:
                import json
                response_text = (
                    f"Account Info for `{address}`:\n```json\n{json.dumps(info, indent=2)}\n```\n"
                    f"[View on Solana Explorer](https://explorer.solana.com/address/{address})"
                )
        else:
            # Default: show balance
            balance = await get_balance_from_address(address)
            response_text = (
                f"Wallet Balance for `{address}`:\n{balance}\n\n"
                f"[View on Solana Explorer](https://explorer.solana.com/address/{address})"
            )

        await ctx.send(session_sender, create_text_chat(response_text))

    except Exception as err:
        ctx.logger.error(err)
        await ctx.send(
            session_sender,
            create_text_chat(
                "Sorry, I couldn't process your request. Please try again later."
            ),
        )
        return