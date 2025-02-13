import asyncio
from datetime import datetime
import random

import aiohttp
from loguru import logger

from .env import DEXSCREENER_POLL_INTERVAL, MEME_COIN_LIQUIDITY_THRESHOLD, ORDER_QUANTITY, TRENDING_API_ENDPOINT

from .trade_executor import TradeExecutor

from .db import DatabaseManager

class DexScreenerScanner:
    def __init__(self, trade_executor: TradeExecutor, db_manager: DatabaseManager) -> None:
        self.trade_executor = trade_executor
        self.db_manager = db_manager
        self.last_seen_tokens: set[str] = set()
        self._run_scanner = True
        self.endpoint = TRENDING_API_ENDPOINT

    async def scan_for_new_coins(self) -> None:
        while self._run_scanner:
            logger.debug("[DexScreenerScanner] Beginning new scan iteration.")
            try:
                logger.debug("[DexScreenerScanner] Fetching trending token data...")
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.endpoint, timeout=10) as response:
                        if response.status != 200:
                            logger.error(f"[DexScreenerScanner] Trending API returned status {response.status}")
                            await asyncio.sleep(DEXSCREENER_POLL_INTERVAL)
                            continue
                        data = await response.json()
                        logger.debug(f"[DexScreenerScanner] Trending API response: {data}")
                        # Expecting data to be a list per new schema
                        tokens = data if isinstance(data, list) else []

                if tokens:
                    for token_info in tokens:
                        token_mint = token_info.get("tokenAddress")
                        if not token_mint or token_mint in self.last_seen_tokens:
                            continue
                        self.last_seen_tokens.add(token_mint)
                        total_amount = int(token_info.get("totalAmount", 0))
                        # Check if token qualifies based on totalAmount threshold
                        if 0 < total_amount < MEME_COIN_LIQUIDITY_THRESHOLD:
                            logger.success(
                                f"[DexScreenerScanner] Candidate token found: {token_mint} with totalAmount {total_amount}"
                            )
                            trade_response = await self.trade_executor.execute_market_order(
                                token_mint, "buy", ORDER_QUANTITY
                            )
                            if trade_response and trade_response.get("result"):
                                logger.success(f"[DexScreenerScanner] Market order successful for token {token_mint}.")
                            else:
                                logger.error(f"[DexScreenerScanner] Market order failed for token {token_mint}.")
                            await self.db_manager.store_trade_log({
                                "event": "TrendingMarketOrder",
                                "token_info": token_info,
                                "trade_response": trade_response,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                        else:
                            logger.debug(
                                f"[DexScreenerScanner] Token {token_mint} does not meet liquidity threshold: {total_amount}"
                            )
                else:
                    logger.warning("[DexScreenerScanner] No trending tokens found in response.")
                logger.debug("[DexScreenerScanner] Finished scan iteration.")
                await asyncio.sleep(DEXSCREENER_POLL_INTERVAL)
            except Exception as e:
                logger.exception(f"[DexScreenerScanner] Error scanning trending tokens: {e}")
                await asyncio.sleep(DEXSCREENER_POLL_INTERVAL)

    def stop(self) -> None:
        self._run_scanner = False
        logger.info("[DexScreenerScanner] Stopping scanner.")