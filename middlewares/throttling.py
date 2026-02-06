from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from loguru import logger

from services.cache_service import CacheService
from config import config


class ThrottlingMiddleware(BaseMiddleware):
    """Rate limiting middleware using Redis."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            is_limited = await CacheService.check_rate_limit(
                user.id, config.RATE_LIMIT
            )
            if is_limited:
                # Silently ignore rate-limited requests
                return

        return await handler(event, data)
