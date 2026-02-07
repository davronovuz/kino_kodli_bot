from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, Table, Index, func, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


# Many-to-many: movies <-> genres
movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many: users <-> favorite movies
user_favorites = Table(
    "user_favorites",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("movie_id", Integer, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime, default=datetime.utcnow),
)


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Integer, unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    title_uz = Column(String(500), nullable=True)
    title_ru = Column(String(500), nullable=True)
    year = Column(Integer, nullable=True)
    quality = Column(String(50), nullable=True)  # 360p, 480p, 720p, 1080p, 4K
    language = Column(String(100), nullable=True)  # O'zbek tilida, Rus tilida
    description = Column(Text, nullable=True)
    file_id = Column(String(500), nullable=False)
    file_type = Column(String(50), default="video")  # video, document
    file_unique_id = Column(String(200), nullable=True, unique=True)
    duration = Column(Integer, nullable=True)  # seconds
    file_size = Column(BigInteger, nullable=True)
    poster_file_id = Column(String(500), nullable=True)
    caption = Column(Text, nullable=True)
    added_by = Column(BigInteger, nullable=True)  # admin telegram_id
    is_active = Column(Boolean, default=True)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    genres = relationship("Genre", secondary=movie_genres, back_populates="movies", lazy="selectin")
    favorited_by = relationship("User", secondary=user_favorites, back_populates="favorites", lazy="selectin")

    __table_args__ = (
        Index("ix_movies_title", "title"),
        Index("ix_movies_title_uz", "title_uz"),
        Index("ix_movies_title_ru", "title_ru"),
        Index("ix_movies_year", "year"),
        Index("ix_movies_is_active", "is_active"),
    )


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name_uz = Column(String(100), unique=True, nullable=False)
    name_ru = Column(String(100), nullable=True)
    emoji = Column(String(10), nullable=True)

    movies = relationship("Movie", secondary=movie_genres, back_populates="genres", lazy="selectin")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(500), nullable=True)
    language = Column(String(10), default="uz")
    is_banned = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    search_count = Column(Integer, default=0)
    movies_watched = Column(Integer, default=0)
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

    favorites = relationship("Movie", secondary=user_favorites, back_populates="favorited_by", lazy="selectin")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(500), nullable=True)
    role = Column(String(50), default="admin")  # superadmin, admin, moderator
    permissions = Column(JSON, default=dict)
    added_by = Column(BigInteger, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True, nullable=False)
    channel_username = Column(String(255), nullable=True)
    title = Column(String(500), nullable=True)
    is_mandatory = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Statistic(Base):
    __tablename__ = "statistics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(BigInteger, nullable=True)
    action_type = Column(String(50), nullable=False)  # view, search, download, share
    query_text = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_statistics_action_type", "action_type"),
        Index("ix_statistics_created_at", "created_at"),
    )


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(BigInteger, nullable=False)
    message_text = Column(Text, nullable=True)
    message_id = Column(Integer, nullable=True)  # original message ID for forwarding
    total_users = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    status = Column(String(50), default="pending")  # pending, running, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=False)  # 1-5
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_ratings_user_movie", "user_id", "movie_id", unique=True),
    )


class Serial(Base):
    __tablename__ = "serials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Integer, unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    title_uz = Column(String(500), nullable=True)
    year = Column(Integer, nullable=True)
    quality = Column(String(50), nullable=True)
    language = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    poster_file_id = Column(String(500), nullable=True)
    total_seasons = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    view_count = Column(Integer, default=0)
    added_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    episodes = relationship("Episode", back_populates="serial", lazy="selectin", order_by="Episode.season, Episode.episode_num")


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_id = Column(Integer, ForeignKey("serials.id", ondelete="CASCADE"), nullable=False)
    season = Column(Integer, default=1)
    episode_num = Column(Integer, nullable=False)
    title = Column(String(500), nullable=True)
    file_id = Column(String(500), nullable=False)
    file_type = Column(String(50), default="video")
    file_unique_id = Column(String(200), unique=True, nullable=True)
    duration = Column(Integer, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    serial = relationship("Serial", back_populates="episodes")

    __table_args__ = (
        Index("ix_episodes_serial_season_ep", "serial_id", "season", "episode_num", unique=True),
    )


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    emoji = Column(String(10), default="🎬")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


collection_movies = Table(
    "collection_movies",
    Base.metadata,
    Column("collection_id", Integer, ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("movie_id", Integer, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, default=0),
)


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(BigInteger, nullable=False, index=True)
    referred_id = Column(BigInteger, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MovieRequest(Base):
    __tablename__ = "movie_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    request_text = Column(Text, nullable=False)
    status = Column(String(50), default="pending")
    admin_reply = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Advertisement(Base):
    __tablename__ = "advertisements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(Text, nullable=True)
    photo_file_id = Column(String(500), nullable=True)
    url = Column(String(500), nullable=True)
    button_text = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
    show_every = Column(Integer, default=5)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyMovie(Base):
    __tablename__ = "daily_movies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
