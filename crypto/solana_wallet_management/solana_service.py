import os
import logging
import requests
import json
from uagents import Model, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Solana RPC endpoint
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

class SolanaRequest(Model):
    address: str = Field(
        description="Solana wallet address to check",
    )

class SolanaResponse(Model):
    balance: str = Field(
        description="Formatted Solana wallet balance",
    )

async def get_balance_from_address(address: str) -> str:
    """
    Get the balance for a Solana address using the Solana RPC API
    
    Args:
        address: Solana wallet address
        
    Returns:
        Formatted balance string
    """
    try:
        logger.info(f"Getting balance for address: {address}")
        
        # Prepare the request payload
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address]
        }
        
        # Set headers
        headers = {
            "Content-Type": "application/json"
        }
        
        # Make the API request
        response = requests.post(SOLANA_RPC_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        
        if "error" in result:
            error_msg = f"Error: {result['error']['message']}"
            logger.error(error_msg)
            return error_msg
            
        if "result" in result and "value" in result["result"]:
            # Convert lamports to SOL (1 SOL = 1,000,000,000 lamports)
            lamports = result["result"]["value"]
            sol_balance = lamports / 1_000_000_000
            
            # Format the result
            result_str = f"{sol_balance:.9f} SOL ({lamports} lamports)"
            logger.info(f"Balance for {address}: {result_str}")
            return result_str
        else:
            error_msg = "No balance information found"
            logger.error(error_msg)
            return error_msg
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Request error: {str(e)}"
        logger.error(error_msg)
        return error_msg
    except json.JSONDecodeError as e:
        error_msg = f"JSON decode error: {str(e)}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return error_msg

async def get_recent_transactions(address: str, limit: int = 10) -> list[str] | str:
    """
    Get recent transaction signatures for a Solana address.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [address, {"limit": limit}]
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(SOLANA_RPC_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if "result" in result:
            return [tx["signature"] for tx in result["result"]]
        return "No transactions found"
    except Exception as e:
        logger.error(f"Error fetching transactions: {e}")
        return f"Error: {str(e)}"
    
async def get_token_balances(address: str) -> dict | str:
    """
    Get SPL token balances for a Solana address.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"}
        ]
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(SOLANA_RPC_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if "result" in result and "value" in result["result"]:
            tokens = []
            for acc in result["result"]["value"]:
                info = acc["account"]["data"]["parsed"]["info"]
                mint = info["mint"]
                amount = info["tokenAmount"]["uiAmount"]
                tokens.append({"mint": mint, "amount": amount})
            return tokens
        return "No tokens found"
    except Exception as e:
        logger.error(f"Error fetching token balances: {e}")
        return f"Error: {str(e)}"
    
async def get_account_info(address: str) -> dict | str:
    """
    Get Solana account info.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [address, {"encoding": "jsonParsed"}]
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(SOLANA_RPC_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if "result" in result and "value" in result["result"]:
            return result["result"]["value"]
        return "No account info found"
    except Exception as e:
        logger.error(f"Error fetching account info: {e}")
        return f"Error: {str(e)}"