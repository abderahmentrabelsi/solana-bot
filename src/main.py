import os
import sys
import signal
import asyncio
import random
from datetime import datetime
from loguru import logger
from .db import DatabaseManager
from .dex_screener_scanner import DexScreenerScanner
from .market_data_streamer import MarketDataStreamer
from .memcoin_scanner import MemeCoinScanner
from .strategy_manager import StrategyManager
from .trade_executor import TradeExecutor

from .env import DEFAULT_MEME_MINT, ORDER_QUANTITY, SOL_MINT, STRATEGY_LOOP_INTERVAL

async def strategy_loop(strategy_manager: StrategyManager, executor: TradeExecutor, db_manager: DatabaseManager) -> None:
    while True:
        try:
            price = random.uniform(0, 100)
            strategy_manager.update_price(price)
            signal = strategy_manager.generate_trading_signal()
            if signal:
                logger.info(f"[strategy_loop] Trading signal: {signal} at price {price:.2f}")
                target_mint = DEFAULT_MEME_MINT if DEFAULT_MEME_MINT else SOL_MINT
                response = await executor.execute_market_order(target_mint, signal.lower(), ORDER_QUANTITY)
                trade_details = {
                    "signal": signal,
                    "price": price,
                    "response": response,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await db_manager.store_trade_log(trade_details)
                if response and response.get("result"):
                    logger.success("[strategy_loop] Profitable trade executed successfully.")
            await asyncio.sleep(STRATEGY_LOOP_INTERVAL)
        except asyncio.CancelledError:
            logger.info("[strategy_loop] Task cancelled.")
            break
        except Exception as e:
            logger.error(f"[strategy_loop] Error: {e}")
            await asyncio.sleep(STRATEGY_LOOP_INTERVAL)

def shutdown_handler(loop: asyncio.AbstractEventLoop) -> None:
    for task in asyncio.all_tasks(loop):
        task.cancel()
    logger.info("[shutdown_handler] All tasks cancelled.")

async def main() -> None:
    logger.remove()
    logger.add(sys.stdout, level="DEBUG")
    logger.add("trading_bot.log", rotation="1 MB", level="DEBUG")
    logger.info("[main] Starting Meme Coin Trading Bot...")

    db_manager = DatabaseManager()
    await db_manager.connect()

    trade_executor = TradeExecutor()
    strategy_manager = StrategyManager()

    market_streamer = MarketDataStreamer(db_manager)
    dex_scanner = DexScreenerScanner(trade_executor, db_manager)
    meme_scanner = MemeCoinScanner(trade_executor, db_manager)

    market_streamer_task = asyncio.create_task(market_streamer.stream_data())
    dex_scanner_task = asyncio.create_task(dex_scanner.scan_for_new_coins())
    meme_scanner_task = asyncio.create_task(meme_scanner.scan_and_trade())
    strategy_task = asyncio.create_task(strategy_loop(strategy_manager, trade_executor, db_manager))

    loop = asyncio.get_running_loop()
    if os.name != 'nt':  
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: shutdown_handler(loop))

    try:
        await asyncio.gather(
            market_streamer_task,
            dex_scanner_task,
            meme_scanner_task,
            strategy_task
        )
    except asyncio.CancelledError:
        logger.info("[main] Cancellation signal received.")
    except Exception as e:
        logger.error(f"[main] Unexpected error: {e}")
    finally:
        logger.info("[main] Shutting down tasks and resources.")
        market_streamer.stop()
        dex_scanner.stop()
        meme_scanner.stop()
        await trade_executor.close()
        await db_manager.close()
        logger.info("[main] Meme Coin Trading Bot shut down.")
        
def run_bot():
    try:
        # optimize_system()
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[__main__] KeyboardInterrupt - shutting down.")
