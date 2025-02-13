
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from typing import  Dict, Any
from loguru import logger

from peewee import DateTimeField, AutoField
from playhouse.postgres_ext import JSONField
from peewee_async import PooledPostgresqlDatabase, AioModel

from .env import TIMESCALE_DB_CONN_STR


def parse_database_url(url: str) -> dict:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    result = urlparse(url)
    params = {
        "database": result.path.lstrip("/"),
        "user": result.username,
        "password": result.password,
        "host": result.hostname,
        "port": result.port,
    }
    query = parse_qs(result.query)
    for key, value in query.items():
        if value:
            params[key] = value[0]
    return params

db_params = parse_database_url(TIMESCALE_DB_CONN_STR)
database = PooledPostgresqlDatabase(**db_params)
database.set_allow_sync(False)

class MarketData(AioModel):
    id = AutoField()
    timestamp = DateTimeField()
    data = JSONField()

    class Meta:
        database = database
        table_name = "market_data"

class TradeLog(AioModel):
    id = AutoField()
    timestamp = DateTimeField()
    trade_details = JSONField()

    class Meta:
        database = database
        table_name = "trade_logs"

class DatabaseManager:
    async def connect(self) -> None:
        logger.info("[DatabaseManager] Connecting to database and ensuring tables...")
        with database.allow_sync():
            database.create_tables([MarketData, TradeLog], safe=True)
        logger.info("[DatabaseManager] Database connected and tables ensured.")

    async def store_market_data(self, data: Dict[str, Any]) -> None:
        logger.debug("[DatabaseManager] Attempting to store market data...")
        try:
            await MarketData.aio_create(timestamp=datetime.utcnow(), data=data)
        except Exception as e:
            logger.exception(f"[DatabaseManager] Failed to store market data: {e}")

    async def store_trade_log(self, trade_details: Dict[str, Any]) -> None:
        try:
            await TradeLog.aio_create(timestamp=datetime.utcnow(), trade_details=trade_details)
            logger.debug("[DatabaseManager] Trade log stored.")
        except Exception as e:
            logger.error(f"[DatabaseManager] Failed to store trade log: {e}")

    async def close(self) -> None:
        await database.aio_close()
        logger.info("[DatabaseManager] Database connection closed.")