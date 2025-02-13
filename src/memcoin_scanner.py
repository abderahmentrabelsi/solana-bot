import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any

from loguru import logger

# Solana RPC and WebSocket clients
from solana.rpc.websocket_api import connect as solana_ws_connect

from solders.rpc.responses import LogsNotification, RpcLogsResponse

from .db import DatabaseManager
from .env import MEME_COIN_LIQUIDITY_THRESHOLD, WS_URL
from .system_tuning import optimize_system
from .trade_executor import TradeExecutor

class MemeCoinScanner:
    def __init__(self, trade_executor: TradeExecutor, db_manager: DatabaseManager) -> None:
        self.trade_executor = trade_executor
        self.db_manager = db_manager
        self.ws_url = WS_URL
        self._run_scanner = True

    async def scan_and_trade(self) -> None:
        async with solana_ws_connect(self.ws_url) as websocket:
            logger.info("[MemeCoinScanner] Connected to Solana WebSocket.")

            params = [
                {"mentions": ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"]},
                {"commitment": "processed"}
            ]
            subscription_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "logsSubscribe",
                "params": params
            }

            await websocket.send(json.dumps(subscription_message))
            logger.info("[MemeCoinScanner] Subscribed to token minting and transfer logs.")

            while self._run_scanner:
                logger.debug("[MemeCoinScanner] Awaiting WebSocket message...")
                try:
                    msg = await websocket.recv()
                    if not msg:
                        continue
                    for data in msg:
                        # Handle subscription response
                        if isinstance(data, LogsNotification) and data.result:
                            subscription_id = data.subscription
                            result = data.result.value
                            logger.debug(f"[MemeCoinScanner] Subscription response: id={subscription_id}, result={result}")

                        # Handle log notification (token transfer/mint events)
                        elif isinstance(data, LogsNotification) and data.result and isinstance(data.result, RpcLogsResponse):
                            log_info = data.result
                            log_msg = log_info.get("msg", "")
                            logger.debug(f"[MemeCoinScanner] Log message received: {log_msg}")
                            # Token Mint Event: Look for token minting activity (first appearance of tokens)
                            if "TokenMinted" in log_msg:
                                coin_details = self.parse_log_for_coin_details(log_msg)
                                if coin_details and self.filter_coin(coin_details):
                                    trade_response = await self.trade_executor.execute_market_order(
                                        coin_details.get("mint", ""), "buy", coin_details["trade_amount"]
                                    )
                                    if trade_response and trade_response.get("result"):
                                        logger.success(f"[MemeCoinScanner] Market order successful for coin {coin_details.get('mint')}.")
                                    else:
                                        logger.error(f"[MemeCoinScanner] Market order failed for coin {coin_details.get('mint')}.")
                                    await self.db_manager.store_trade_log({
                                        "event": "MemeCoinMarketOrder",
                                        "coin_details": coin_details,
                                        "trade_response": trade_response,
                                        "timestamp": datetime.utcnow().isoformat()
                                    })

                    await asyncio.sleep(0)
                except Exception as e:
                    logger.exception(f"[MemeCoinScanner] Error processing WebSocket message: {e}")
                    continue

                await asyncio.sleep(0)

    def stop(self) -> None:
        self._run_scanner = False
        logger.info("[MemeCoinScanner] Stopping meme coin scanner.")

    def parse_log_for_coin_details(self, log_msg: str) -> Optional[Dict[str, Any]]:
        try:
            parts = log_msg.split("|")
            details: Dict[str, Any] = {}

            for part in parts[1:]:
                try:
                    key, value = part.split("=", 1)
                    details[key.strip()] = value.strip()
                except Exception as inner_e:
                    logger.debug(f"[MemeCoinScanner] Skipping invalid log part: {part} ({inner_e})")

            details["initial_supply"] = float(details.get("initial_supply", 0))
            details["trade_amount"] = int(details.get("trade_amount", 1000))  # Default trade amount (adjustable)
            logger.debug(f"[MemeCoinScanner] Parsed coin details: {details}")
            return details
        except Exception as e:
            logger.error(f"[MemeCoinScanner] Error parsing log: {e}")
            return None

    def filter_coin(self, coin_details: Dict[str, Any]) -> bool:
        # Filter meme coins based on initial supply, liquidity, and symbols like "DOGE", "SHIB"
        symbol = coin_details.get("symbol", "").upper()
        liquidity = coin_details.get("initial_supply", 0) * coin_details.get("trade_amount", 0)  # A simple liquidity proxy
        if liquidity < MEME_COIN_LIQUIDITY_THRESHOLD and "MEME" in symbol:
            logger.info(f"[MemeCoinScanner] Coin passes filter: {coin_details}")
            return True
        logger.info(f"[MemeCoinScanner] Coin rejected based on filter: {coin_details}")
        return False