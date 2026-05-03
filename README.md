# revlm cards

Minimal Telegram card bot with admin panel and text RPG commands.

Channel: @revolutom

## Commands
- /start
- /help
- /pull
- /collection
- /stats
- /admin

## Admin setup
Put admin IDs into `.env`:
`ADMIN_IDS=7568599598`

## Language / Язык
EN:
You can change bot language in `.env`:
`LANGUAGE=ru` or `LANGUAGE=en`

RU:
Ты можешь менять язык бота в `.env`:
`LANGUAGE=ru` или `LANGUAGE=en`

## Setup
1. Create `.env` with `BOT_TOKEN=...`
2. Install deps: `pip install -r requirements.txt`
3. Run: `python main.py`

## Personal Use Agreement
This bot is provided for personal and educational use only.
It is not designed, hardened, or supported for production workloads.
If you need a production-grade bot, this codebase is not a good fit without major security, reliability, and architecture upgrades.
If you want a production version, contact me directly via Telegram: @revolutom.


## Media support
Admin panel supports media for cards and RPG commands: photo, GIF, MP4.
Maximum file size: 10MB per file.


Media files are stored locally in the iles/ directory.

