from aiogram import Router

from handlers.users.start import router as start_router
from handlers.users.search import router as search_router
from handlers.users.movie_view import router as movie_view_router


def get_users_router() -> Router:
    router = Router()
    router.include_router(start_router)
    router.include_router(search_router)
    router.include_router(movie_view_router)
    return router
