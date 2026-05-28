import asyncio

from src.core.logger import logger

REDIS_KEY_START_TIME = "bot_start_time"
REDIS_KEY_ALIVE = "bot_alive"
HEARTBEAT_INTERVAL = 15  # секунд
ALIVE_TTL = 30  # секунд


async def _heartbeat(redis) -> None:
    while True:
        try:
            await redis.set(REDIS_KEY_ALIVE, "1", ex=ALIVE_TTL)
        except Exception:
            logger.debug("Heartbeat Redis write failed, will retry in %ds", HEARTBEAT_INTERVAL)
        await asyncio.sleep(HEARTBEAT_INTERVAL)
