import math
from typing import Optional
from database.models import Movie


def format_movie_caption(movie: Movie, show_code: bool = True, avg_rating: float = 0, rating_count: int = 0) -> str:
    """Enhanced movie caption with beautiful formatting."""
    lines = []

    lines.append("━━━━━━━━━━━━━━━━━━━━━")

    if show_code:
        lines.append(f"🎬 <b>Kod:</b> <code>{movie.code}</code>")

    lines.append(f"📽 <b>{movie.title}</b>")

    if movie.title_uz and movie.title_uz != movie.title:
        lines.append(f"🇺🇿 {movie.title_uz}")

    if movie.title_ru and movie.title_ru != movie.title:
        lines.append(f"🇷🇺 {movie.title_ru}")

    lines.append("")

    info_parts = []
    if movie.year:
        info_parts.append(f"📅 {movie.year}")
    if movie.quality:
        info_parts.append(f"📺 {movie.quality}")
    if movie.language:
        info_parts.append(f"🌐 {movie.language}")

    if info_parts:
        lines.append(" │ ".join(info_parts))

    if movie.genres:
        genre_str = ", ".join(
            f"{g.emoji or '🎭'} {g.name_uz}" for g in movie.genres
        )
        lines.append(f"🎭 {genre_str}")

    if movie.duration:
        hours = movie.duration // 3600
        minutes = (movie.duration % 3600) // 60
        if hours:
            lines.append(f"⏱ {hours}s {minutes}d")
        else:
            lines.append(f"⏱ {minutes} daqiqa")

    if movie.file_size:
        size_mb = movie.file_size / (1024 * 1024)
        if size_mb > 1024:
            lines.append(f"📦 {size_mb / 1024:.1f} GB")
        else:
            lines.append(f"📦 {size_mb:.1f} MB")

    if avg_rating > 0:
        stars = "⭐" * round(avg_rating) + "☆" * (5 - round(avg_rating))
        lines.append(f"\n{stars} {avg_rating}/5 ({rating_count} ta baho)")

    if movie.description:
        desc = movie.description[:200]
        if len(movie.description) > 200:
            desc += "..."
        lines.append(f"\n📝 {desc}")

    lines.append("")
    lines.append(f"👁 {movie.view_count} marta ko'rildi")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🔢 Ulashing: <code>{movie.code}</code>")

    return "\n".join(lines)


def format_movie_list_item(movie: Movie, index: int = 0) -> str:
    year_str = f" ({movie.year})" if movie.year else ""
    quality_str = f" [{movie.quality}]" if movie.quality else ""
    return f"{index}. <code>{movie.code}</code> — {movie.title}{year_str}{quality_str}"


def calculate_pages(total: int, per_page: int) -> int:
    return max(1, math.ceil(total / per_page))


def format_file_size(size_bytes: Optional[int]) -> str:
    if not size_bytes:
        return "Noma'lum"
    mb = size_bytes / (1024 * 1024)
    if mb > 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.1f} MB"


def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "Noma'lum"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours:
        return f"{hours}s {minutes}d"
    return f"{minutes} daqiqa"


LANG_MAP = {
    "uz": "🇺🇿 O'zbek tilida",
    "ru": "🇷🇺 Rus tilida",
    "en": "🇺🇸 Ingliz tilida",
    "tr": "🇹🇷 Turk tilida",
    "kr": "🇰🇷 Koreys tilida",
}