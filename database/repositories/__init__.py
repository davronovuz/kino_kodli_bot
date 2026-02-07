from database.repositories.movie_repo import MovieRepository
from database.repositories.user_repo import UserRepository
from database.repositories.stats_repo import StatsRepository
from database.repositories.serial_repo import SerialRepository
from database.repositories.extra_repo import (
    CollectionRepository, ReferralRepository, MovieRequestRepository,
    AdvertisementRepository, DailyMovieRepository, LeaderboardRepository,
)

__all__ = [
    "MovieRepository", "UserRepository", "StatsRepository",
    "SerialRepository", "CollectionRepository", "ReferralRepository",
    "MovieRequestRepository", "AdvertisementRepository",
    "DailyMovieRepository", "LeaderboardRepository",
]