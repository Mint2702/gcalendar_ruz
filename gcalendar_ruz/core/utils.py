import re
from functools import wraps
import asyncio
from loguru import logger
import time
import sys


GOOGLE = "google"
NVR = "nvr"
RUZ = "ruz"

sem_dict = {
    NVR: asyncio.Semaphore(100),
    GOOGLE: asyncio.Semaphore(5),
    RUZ: asyncio.Semaphore(10),
}


def camel_to_snake(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def semlock(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        service = self.SERVICE
        sem = sem_dict.get(service)
        if not sem:
            logger.error("Unsupported service")

        async with sem:
            # logger.debug(f"{service} semaphore for function {func.__name__}")
            return await func(self, *args, **kwargs)

    return wrapper


def token_check(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.creds or self.creds.expired:
            logger.info("Refresh google tokens")
            self.refresh_token()

        self.HEADERS = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.creds.token}",
        }

        return await func(self, *args, **kwargs)

    return wrapper


def handle_google_errors(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        result = await func(self, *args, **kwargs)
        try:
            error = result["error"]["errors"][0]["reason"]
        except Exception:
            return result

        if error == "rateLimitExceeded":
            logger.error("Rate limit for google exceeded")
            time.sleep(11)
            return await func(self, *args, **kwargs)
        elif error == "quotaExceeded":
            logger.error("Usage limit for google exceeded")
            sys.exit(1)
        else:
            return result

    return wrapper
