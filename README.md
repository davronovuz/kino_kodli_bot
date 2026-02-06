# 🎬 Kino Kodli Telegram Bot

Professional Telegram bot for movie sharing with code-based search system.

## Features

### 👤 User Features
- 🔢 Search movies by code (e.g., send `123`)
- 🔤 Search movies by name
- 🎭 Browse by genre
- 🔥 Top/popular movies
- 🆕 Latest movies
- ⭐ Favorites list
- 📊 Personal statistics

### 🔐 Admin Features
- ➕ Add movies (step-by-step wizard)
- 📥 Bulk import (forward, Excel/CSV)
- 📋 Manage movies (list, edit, delete)
- 👥 User management (ban, unban, info)
- 📢 Broadcast messages
- 📡 Mandatory channel management
- 📊 Statistics dashboard

### 🛡 Security & Performance
- Rate limiting (Redis-based)
- Force channel subscription
- Global error handling with admin notifications
- PostgreSQL + Redis caching
- Docker deployment

---

## 🚀 Quick Start

### 1. Prerequisites
- Docker & Docker Compose installed
- Telegram Bot Token (from @BotFather)
- Your Telegram User ID

### 2. Setup

```bash
# Clone/copy the project
cd kino_bot

# Edit .env file
nano .env
```

**Edit `.env` file:**
```
BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMINS=123456789
DB_PASS=your_secure_password
```

### 3. Launch

```bash
# Start all services
docker compose up -d --build

# Check logs
docker compose logs -f bot

# Seed default genres
docker compose exec bot python seed.py
```

### 4. Stop

```bash
docker compose down
```

---

## 📥 Importing 1000 Movies

### Method 1: Forward Import (Recommended)
1. Open bot → `/admin` → `📥 Import kinolar` → `📤 Forward qilib import`
2. Go to your group/channel with movies
3. Select videos → Forward to bot
4. Bot automatically assigns codes and saves
5. When done, press `❌ Bekor qilish` or send `/done`

**Tips for mass forwarding:**
- Select multiple videos at once (up to 100)
- Forward in batches of 50-100
- Wait a few seconds between batches
- Bot skips duplicates automatically

### Method 2: Excel Import
1. Create Excel file with columns: `code`, `title`, `year`, `quality`, `language`
2. `/admin` → `📥 Import kinolar` → `📄 Excel/CSV import`
3. Send the file
4. Note: You'll need to add video files separately

---

## 📋 Admin Commands

| Command | Description |
|---------|-------------|
| `/admin` | Open admin panel |
| `/ban USER_ID` | Ban a user |
| `/unban USER_ID` | Unban a user |
| `/userinfo USER_ID` | View user info |

---

## 🗂 Project Structure

```
kino_bot/
├── bot.py              # Entry point
├── config.py           # Settings
├── seed.py             # Genre seeder
├── handlers/
│   ├── users/          # User handlers
│   │   ├── start.py    # /start, /help
│   │   ├── search.py   # Genre, top, new, stats
│   │   └── movie_view.py  # Movie display, favorites
│   └── admin/          # Admin handlers
│       ├── dashboard.py    # Admin panel, stats
│       ├── add_movie.py    # Add movie wizard
│       ├── manage_movies.py # List, delete
│       ├── broadcast.py    # Broadcast
│       ├── manage_channels.py # Channel mgmt
│       └── import_movies.py # Bulk import
├── middlewares/
│   ├── throttling.py   # Rate limiting
│   ├── database.py     # DB session injection
│   ├── force_join.py   # Channel subscription
│   └── error_handler.py # Global errors
├── database/
│   ├── models.py       # SQLAlchemy models
│   ├── engine.py       # DB connection
│   └── repositories/   # Data access layer
├── keyboards/          # Telegram keyboards
├── services/           # Redis cache
├── states/             # FSM states
├── filters/            # Admin filter
├── utils/              # Helpers
├── Dockerfile
├── docker-compose.yml
├── .env
└── requirements.txt
```

---

## 🔧 Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL and Redis locally
# Edit .env: DB_HOST=localhost, REDIS_HOST=localhost

# Run
python seed.py
python bot.py
```

---

## 🔄 Backup & Restore

```bash
# Backup database
docker compose exec db pg_dump -U postgres kino_bot > backup.sql

# Restore database
docker compose exec -T db psql -U postgres kino_bot < backup.sql
```

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot not responding | Check `docker compose logs bot` |
| DB connection error | Ensure DB is healthy: `docker compose ps` |
| Redis error | Bot works without Redis (just no cache) |
| Rate limited | Increase `RATE_LIMIT` in `.env` |
| Import fails | Check logs, try smaller batches |

---

## License

MIT
