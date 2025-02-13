import os
import sys
import signal
import asyncio
import base58
import base64
import json
import random
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any

import aiohttp
import numpy as np
import talib
from loguru import logger
from dotenv import load_dotenv

# Solana RPC and WebSocket clients
from solana.rpc.async_api import AsyncClient
from solana.rpc.websocket_api import connect as solana_ws_connect

# Use solders for transaction and keypair functionality
from solders.transaction import Transaction as SolanaTransaction
from solders.keypair import Keypair as SolanaKeypairPySolders
from solders.pubkey import Pubkey
from solders.rpc.responses import LogsNotification, RpcLogsResponse

# Database imports
from peewee import DateTimeField, AutoField
from playhouse.postgres_ext import JSONField
from peewee_async import PooledPostgresqlDatabase, AioModel

from .system_tuning import optimize_system

class StrategyManager:
    def __init__(self) -> None:
        self.prices: list[float] = []

    def update_price(self, price: float) -> None:
        self.prices.append(price)
        if len(self.prices) > 1000:
            self.prices.pop(0)
        logger.debug(f"[StrategyManager] Price updated: {price:.2f}")

    def generate_trading_signal(self) -> Optional[str]:
        if len(self.prices) < 30:
            return None
        prices_array = np.array(self.prices, dtype=float)
        sma = talib.SMA(prices_array, timeperiod=30)
        rsi = talib.RSI(prices_array, timeperiod=14)
        upperband, middleband, lowerband = talib.BBANDS(prices_array, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        macd, macd_signal, macd_hist = talib.MACD(prices_array, fastperiod=12, slowperiod=26, signalperiod=9)

        current_price = prices_array[-1]
        current_sma = sma[-1]
        current_rsi = rsi[-1]
        current_upper = upperband[-1]
        current_lower = lowerband[-1]
        current_macd_hist = macd_hist[-1]

        score = 0
        if current_price < current_lower:
            score += 1
        elif current_price > current_upper:
            score -= 1
        if current_rsi < 30:
            score += 1
        elif current_rsi > 70:
            score -= 1
        if current_macd_hist > 0:
            score += 1
        elif current_macd_hist < 0:
            score -= 1
        if current_price > current_sma:
            score += 1
        elif current_price < current_sma:
            score -= 1

        logger.info(
            f"[StrategyManager] Indicators - Price: {current_price:.2f}, SMA: {current_sma:.2f}, "
            f"RSI: {current_rsi:.2f}, UpperBand: {current_upper:.2f}, LowerBand: {current_lower:.2f}, "
            f"MACD_hist: {current_macd_hist:.2f}. Score: {score}"
        )

        if score >= 2:
            return "BUY"
        elif score <= -2:
            return "SELL"
        return None

    def run_backtest(self) -> int:
        logger.info("[StrategyManager] run_backtest() called - no real logic implemented.")
        return 0