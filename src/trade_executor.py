import base64
from typing import Optional, Dict, Any

import aiohttp
from loguru import logger

# Solana RPC and WebSocket clients
from solana.rpc.async_api import AsyncClient

# Use solders for transaction and keypair functionality
from solders.transaction import Transaction as SolanaTransaction

from .keypair import SolanaKeypair
from .env import JUPITER_API_KEY, SOL_MINT, SOLANA_RPC_URL

class TradeExecutor:
    def __init__(self) -> None:
        self.rpc_url = SOLANA_RPC_URL
        self.client = AsyncClient(self.rpc_url)
        self.keypair = SolanaKeypair()
        # New Jupiter API endpoints (v1) as per update
        self.jupiter_api_quote = "https://api.jup.ag/swap/v1/quote"
        self.jupiter_api_swap = "https://api.jup.ag/swap/v1/swap"
        self.api_key = JUPITER_API_KEY
        pubkey_str = self.keypair.public_key.to_string() if hasattr(self.keypair.public_key, "to_string") else str(self.keypair.public_key)
        logger.info(f"[TradeExecutor] Initialized with public key: {pubkey_str}")

    async def execute_swap(self, input_mint: str, output_mint: str, amount: int, slippage: float = 1) -> Optional[Dict[str, Any]]:
        logger.info("[TradeExecutor] Initiating swap execution...")
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(int(slippage * 100))
        }
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        logger.debug(f"[TradeExecutor] Fetching swap quote with params: {params}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.jupiter_api_quote, params=params, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"[TradeExecutor] Quote request failed with status {response.status}")
                        return None
                    data = await response.json()
        except Exception as e:
            logger.error(f"[TradeExecutor] Exception during quote request: {e}")
            return None

        if not data or "routes" not in data or not data["routes"]:
            logger.error("[TradeExecutor] No swap routes found.")
            return None

        best_route = data["routes"][0]
        logger.debug(f"[TradeExecutor] Best route selected: {best_route}")
        payload = {
            "route": best_route,
            "userPublicKey": self.keypair.public_key.to_string() if hasattr(self.keypair.public_key, "to_string") else str(self.keypair.public_key),
            "wrapUnwrapSOL": True,
            "dynamicSlippage": {"maxBps": 300}
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.jupiter_api_swap, json=payload, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"[TradeExecutor] Swap request failed with status {response.status}")
                        return None
                    swap_data = await response.json()
        except Exception as e:
            logger.error(f"[TradeExecutor] Exception during swap request: {e}")
            return None

        if "swapTransaction" not in swap_data:
            logger.error("[TradeExecutor] Swap transaction not received.")
            return None

        tx_base64 = swap_data["swapTransaction"]
        try:
            raw_tx = base64.b64decode(tx_base64)
        except Exception as e:
            logger.error(f"[TradeExecutor] Base64 decoding failed: {e}")
            return None

        try:
            txn = SolanaTransaction.from_bytes(raw_tx)
            logger.debug("[TradeExecutor] Transaction deserialized successfully.")
        except Exception as e:
            logger.error(f"[TradeExecutor] Failed to deserialize transaction: {e}")
            return None

        try:
            txn.sign([self.keypair._keypair])
            logger.debug("[TradeExecutor] Transaction signed successfully.")
        except Exception as e:
            logger.error(f"[TradeExecutor] Failed to sign transaction: {e}")
            return None

        try:
            raw_signed_tx = txn.serialize()
        except Exception as e:
            logger.error(f"[TradeExecutor] Transaction serialization failed: {e}")
            return None

        logger.info("[TradeExecutor] Sending raw transaction to RPC client.")
        try:
            response = await self.client.send_raw_transaction(raw_signed_tx)
        except Exception as e:
            logger.error(f"[TradeExecutor] Failed to send raw transaction: {e}")
            return None

        if response.get("result"):
            logger.success(f"[TradeExecutor] Swap executed successfully. Tx signature: {response.get('result')}")
        else:
            logger.error(f"[TradeExecutor] Swap execution failed: {response}")
        return response

    async def execute_market_order(self, meme_coin_mint: str, side: str, amount: float) -> Optional[Dict[str, Any]]:
        decimals = 6  # Assume token decimals = 6; in production, fetch dynamically.
        amt_in_smallest = int(amount * (10 ** decimals))
        if side.lower() == "buy":
            input_mint = SOL_MINT
            output_mint = meme_coin_mint
        else:
            input_mint = meme_coin_mint
            output_mint = SOL_MINT
        logger.info(f"[TradeExecutor] Executing market order: side={side.upper()}, amount={amount}, input_mint={input_mint}, output_mint={output_mint}")
        return await self.execute_swap(input_mint, output_mint, amt_in_smallest, slippage=1)

    async def close(self) -> None:
        await self.client.close()
        logger.info("[TradeExecutor] RPC client closed.")