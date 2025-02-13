import asyncio
import platform
import sys
from loguru import logger
import winuvloop

def optimize_system():
    logger.info("Optimizing system for high performance.")
    winuvloop.install()
    sys.setrecursionlimit(1500)
    current_platform = platform.system().lower()
    if current_platform == "windows":
        from . import windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) 
        windows.set_max_open_file_descriptors(65535)
        windows.optimize_windows_network()
    elif current_platform == "linux":
        from . import linux
        linux.set_max_open_file_descriptors(65535)
    else:
        raise Exception(f"Unsupported platform: {current_platform}")
    logger.success("System optimization complete.")
