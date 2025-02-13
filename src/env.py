
import os
import sys
from dotenv import load_dotenv
from loguru import logger


load_dotenv()

WS_URL = os.environ.get("WS_URL", "wss://api.devnet.solana.com")
SOLANA_RPC_URL = os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com")
TIMESCALE_DB_CONN_STR = os.environ.get("TIMESCALE_DB_CONN_STR")
TRENDING_API_ENDPOINT = os.environ.get("TRENDING_API_ENDPOINT", "https://api.dexscreener.com/token-boosts/top/v1")
MEME_COIN_LIQUIDITY_THRESHOLD = float(os.environ.get("MEME_COIN_LIQUIDITY_THRESHOLD", "20000"))
RECONNECT_DELAY = float(os.environ.get("RECONNECT_DELAY", "5"))
STRATEGY_LOOP_INTERVAL = float(os.environ.get("STRATEGY_LOOP_INTERVAL", "5"))
DEXSCREENER_POLL_INTERVAL = float(os.environ.get("DEXSCREENER_POLL_INTERVAL", "30"))
SECRET_KEY_B58 = os.environ.get("SECRET_KEY_B58")
ORDER_QUANTITY = float(os.environ.get("ORDER_QUANTITY", "100"))
SOL_MINT = os.environ.get("SOL_MINT", "So11111111111111111111111111111111111111112")
DEFAULT_MEME_MINT = os.environ.get("DEFAULT_MEME_MINT", "")
JUPITER_API_KEY = os.environ.get("JUPITER_API_KEY", "")

if not SECRET_KEY_B58:
    logger.error("SECRET_KEY_B58 environment variable must be provided.")
    sys.exit(1)

if not TIMESCALE_DB_CONN_STR:
    logger.error("TIMESCALE_DB_CONN_STR environment variable must be provided.")
    sys.exit(1)