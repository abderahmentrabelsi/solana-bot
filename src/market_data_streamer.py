import asyncio
import json
from loguru import logger
from solana.rpc.websocket_api import connect as solana_ws_connect

# Use solders for transaction and keypair functionality
from solders.rpc.responses import LogsNotification, RpcLogsResponse
from .db import DatabaseManager
from .env import WS_URL

class MarketDataStreamer:
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager
        self.ws_url = WS_URL
        self._run_stream = True
        self.subscriptions = {}  # Track active subscriptions by id

    async def stream_data(self) -> None:
        async with solana_ws_connect(self.ws_url) as websocket:
            logger.info("[MarketDataStreamer] Connected to Solana WebSocket.")

            # Send a subscription request
            subscription_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "logsSubscribe",
                "params": {
                    "mentions": "mint",
                    "filters": ["programId", "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"]
                }
            }

            # Track the subscription ID
            self.subscriptions[1] = websocket  # Map the ID to the WebSocket connection

            await websocket.send(json.dumps(subscription_request))
            logger.info("[MarketDataStreamer] Sent subscription request to WebSocket.")

            while self._run_stream:
                try:
                    msg = await websocket.recv()
                    if not msg:
                        continue
                    logger.trace(f"[MarketDataStreamer] Received WebSocket message: {msg}")

                    # Process the response
                    for response_data in msg:
                        # Handle the result based on the subscription id
                        subscription_id = response_data.id
                        if subscription_id and subscription_id in self.subscriptions:
                            logger.debug(f"[MarketDataStreamer] Subscription response: id={subscription_id}, result={response_data.result}")
                        else:
                            logger.warning(f"[MarketDataStreamer] Received response for an unrecognized subscription ID: {subscription_id}")

                        # Process logs from the 'result' field if available
                        if isinstance(response_data, LogsNotification) and response_data.result:
                            log_info = response_data.result.value
                            log_msg = log_info.get("msg", "")
                            logger.debug(f"[MarketDataStreamer] Log message: {log_msg}")
                            await self.db_manager.store_market_data({"log": log_msg})
                            logger.debug(f"[MarketDataStreamer] Stored log: {log_msg}")

                except KeyError as e:
                    logger.error(f"[MarketDataStreamer] KeyError occurred while processing WebSocket message: {e}")
                except Exception as e:
                    logger.exception(f"[MarketDataStreamer] Error processing WebSocket message: {e}")

                await asyncio.sleep(0)

    def stop(self) -> None:
        self._run_stream = False
        logger.info("[MarketDataStreamer] Stopping data stream.")
