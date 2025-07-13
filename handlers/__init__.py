from aiogram import Router

from . import youtube, start, tiktok, instagram, inline

router = Router(name=__name__)

router.include_routers(
    start.router,
    youtube.router,
    tiktok.router,
    instagram.router,
    inline.router,
)

__all__ = [
    router
]