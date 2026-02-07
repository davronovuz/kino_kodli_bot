from aiogram import Router

from handlers.admin.dashboard import router as dashboard_router
from handlers.admin.add_movie import router as add_movie_router
from handlers.admin.manage_movies import router as manage_movies_router
from handlers.admin.broadcast import router as broadcast_router
from handlers.admin.manage_channels import router as channels_router
from handlers.admin.import_movies import router as import_router
from handlers.admin.admin_extras import router as extras_router


def get_admin_router() -> Router:
    router = Router()
    router.include_router(dashboard_router)
    router.include_router(add_movie_router)
    router.include_router(manage_movies_router)
    router.include_router(broadcast_router)
    router.include_router(channels_router)
    router.include_router(import_router)
    router.include_router(extras_router)
    return router