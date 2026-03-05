import os
from enum import Enum

from uagents import Agent, Context, Model
from uagents.experimental.quota import QuotaProtocol, RateLimit
from uagents.models import ErrorMessage

from chat_proto import chat_proto, struct_output_client_proto
from solana_service import (
    get_balance_from_address, SolanaRequest, SolanaResponse,
    get_recent_transactions, get_token_balances, get_account_info
)
from uagents import Model, Field

agent = Agent()

proto = QuotaProtocol(
    storage_reference=agent.storage,
    name="Solana-Wallet-Protocol",
    version="0.1.0",
    default_rate_limit=RateLimit(window_size_minutes=60, max_requests=30),
)

@proto.on_message(
    SolanaRequest, replies={SolanaResponse, ErrorMessage}
)
async def handle_request(ctx: Context, sender: str, msg: SolanaRequest):
    ctx.logger.info(f"Received wallet balance request for address: {msg.address}")
    try:
        balance = await get_balance_from_address(msg.address)
        ctx.logger.info(f"Successfully fetched wallet balance for {msg.address}")
        await ctx.send(sender, SolanaResponse(balance=balance))
    except Exception as err:
        ctx.logger.error(err)
        await ctx.send(sender, ErrorMessage(error=str(err)))

class TransactionsRequest(Model):
    address: str = Field(description="Solana wallet address")

class TransactionsResponse(Model):
    transactions: list = Field(description="List of recent transaction signatures")

class TokenBalancesRequest(Model):
    address: str = Field(description="Solana wallet address")

class TokenBalancesResponse(Model):
    tokens: list = Field(description="List of SPL tokens and balances")

class AccountInfoRequest(Model):
    address: str = Field(description="Solana wallet address")

class AccountInfoResponse(Model):
    info: dict = Field(description="Account info")

@proto.on_message(TransactionsRequest, replies={TransactionsResponse, ErrorMessage})
async def handle_transactions(ctx: Context, sender: str, msg: TransactionsRequest):
    try:
        txs = await get_recent_transactions(msg.address)
        await ctx.send(sender, TransactionsResponse(transactions=txs))
    except Exception as err:
        await ctx.send(sender, ErrorMessage(error=str(err)))

@proto.on_message(TokenBalancesRequest, replies={TokenBalancesResponse, ErrorMessage})
async def handle_token_balances(ctx: Context, sender: str, msg: TokenBalancesRequest):
    try:
        tokens = await get_token_balances(msg.address)
        await ctx.send(sender, TokenBalancesResponse(tokens=tokens))
    except Exception as err:
        await ctx.send(sender, ErrorMessage(error=str(err)))

@proto.on_message(AccountInfoRequest, replies={AccountInfoResponse, ErrorMessage})
async def handle_account_info(ctx: Context, sender: str, msg: AccountInfoRequest):
    try:
        info = await get_account_info(msg.address)
        await ctx.send(sender, AccountInfoResponse(info=info))
    except Exception as err:
        await ctx.send(sender, ErrorMessage(error=str(err)))

agent.include(proto, publish_manifest=True)

### Health check related code
def agent_is_healthy() -> bool:
    """
    Implement the actual health check logic here.
    For example, check if the agent can connect to the Solana RPC API.
    """
    try:
        import asyncio
        asyncio.run(get_balance_from_address("AtTjQKXo1CYTa2MuxPARtr382ZyhPU5YX4wMMpvaa1oy"))
        return True
    except Exception:
        return False

class HealthCheck(Model):
    pass

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"

class AgentHealth(Model):
    agent_name: str
    status: HealthStatus

health_protocol = QuotaProtocol(
    storage_reference=agent.storage, name="HealthProtocol", version="0.1.0"
)

@health_protocol.on_message(HealthCheck, replies={AgentHealth})
async def handle_health_check(ctx: Context, sender: str, msg: HealthCheck):
    status = HealthStatus.UNHEALTHY
    try:
        if agent_is_healthy():
            status = HealthStatus.HEALTHY
    except Exception as err:
        ctx.logger.error(err)
    finally:
        await ctx.send(sender, AgentHealth(agent_name="solana_wallet_agent", status=status))

agent.include(health_protocol, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)
agent.include(struct_output_client_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()