import asyncio
import os
import random
import sqlite3
import uuid
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery, FSInputFile
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = "revlm_cards.db"
FILES_DIR = "files"
BOT_TITLE = "revlm cards"
LANGUAGE = (os.getenv("LANGUAGE", "en").strip().lower() or "en")
if LANGUAGE not in {"ru", "en"}:
    LANGUAGE = "en"
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
MAX_MEDIA_SIZE = 10 * 1024 * 1024
PULL_COOLDOWN_SECONDS = 2 * 60 * 60

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Put it in .env")
os.makedirs(FILES_DIR, exist_ok=True)

RARITY_SET = {"Common", "Rare", "Epic", "Legendary"}
RARITY_WEIGHTS = [
    ("Common", 70),
    ("Rare", 20),
    ("Epic", 8),
    ("Legendary", 2),
]
BUILTIN_CMDS = {"start", "help", "pull", "collection", "stats", "admin"}

router = Router()


class AddCardFSM(StatesGroup):
    waiting_name = State()
    waiting_rarity = State()
    waiting_media = State()


class AddRpgFSM(StatesGroup):
    waiting_command = State()
    waiting_template = State()
    waiting_media = State()


TXT = {
    "en": {
        "start": (
            "🎴 {title}\n\n"
            "Commands:\n"
            "/pull - get one card from catalog\n"
            "/collection - your latest cards\n"
            "/help - command list\n\n"
            "📢 Channel: @revolutom"
        ),
        "help": "🧭 /pull, /collection\n📢 Channel: @revolutom",
        "catalog_empty": "Card catalog is empty. Ask admin to add cards.",
        "you_got": "🎁 You got: {name} [{rarity}]",
        "no_cards": "No cards yet. Use /pull",
        "your_cards": "Your latest cards:",
        "stats_title": "📊 {title} stats",
        "total_pulls": "Total pulls: {count}",
        "access_denied": "Access denied",
        "admin_panel": "🛠 Admin panel",
        "send_card_name": "Send card name:",
        "send_rarity": "Send rarity (Common/Rare/Epic/Legendary):",
        "invalid_rarity": "Invalid rarity. Use Common/Rare/Epic/Legendary",
        "state_expired": "State expired. Start again from /admin",
        "send_card_media": "Send media for card (photo/gif/mp4) or type 'skip'. Max 10MB.",
        "card_added": "✅ Card added: {name} [{rarity}]",
        "card_exists": "Card with this name already exists",
        "no_cards_catalog": "No cards in catalog",
        "catalog_cards": "🗂 Catalog cards:",
        "send_rpg_name": "Send RPG command name without '/'. Example: attack",
        "invalid_command": "Invalid command. Example: attack",
        "send_rpg_template": "Send template text. You can use {{user}} and {{target}}.",
        "send_rpg_media": "Send media for RPG command (photo/gif/mp4) or type 'skip'. Max 10MB.",
        "rpg_saved": "✅ RPG command saved: /{cmd}",
        "no_rpg_commands": "No RPG commands",
        "rpg_commands": "⚔️ RPG commands:",
        "invalid_media": "Unsupported media. Send photo, GIF, or MP4.",
        "media_too_large": "File is too large. Max size is 10MB.",
        "target_required": "Reply to another user's message or specify @username.",
        "pull_cooldown": "Cooldown active. Try again in {time_left}.",
    },
    "ru": {
        "start": (
            "🎴 {title}\n\n"
            "Команды:\n"
            "/pull - вытянуть карту из каталога\n"
            "/collection - твои последние карты\n"
            "/help - список команд\n\n"
            "📢 Канал: @revolutom"
        ),
        "help": "🧭 /pull, /collection\n📢 Канал: @revolutom",
        "catalog_empty": "Каталог карт пуст. Попроси админа добавить карты.",
        "you_got": "🎁 Ты получил: {name} [{rarity}]",
        "no_cards": "Карт пока нет. Используй /pull",
        "your_cards": "Твои последние карты:",
        "stats_title": "📊 Статистика {title}",
        "total_pulls": "Всего пуллов: {count}",
        "access_denied": "Доступ запрещен",
        "admin_panel": "🛠 Админ-панель",
        "send_card_name": "Отправь название карты:",
        "send_rarity": "Отправь редкость (Common/Rare/Epic/Legendary):",
        "invalid_rarity": "Неверная редкость. Используй Common/Rare/Epic/Legendary",
        "state_expired": "Состояние сброшено. Начни заново через /admin",
        "send_card_media": "Отправь медиа для карты (фото/gif/mp4) или напиши 'skip'. Макс 10MB.",
        "card_added": "✅ Карта добавлена: {name} [{rarity}]",
        "card_exists": "Карта с таким именем уже существует",
        "no_cards_catalog": "В каталоге нет карт",
        "catalog_cards": "🗂 Карты в каталоге:",
        "send_rpg_name": "Отправь имя RPG-команды без '/'. Пример: attack",
        "invalid_command": "Неверная команда. Пример: attack",
        "send_rpg_template": "Отправь шаблон текста. Можно использовать {{user}} и {{target}}.",
        "send_rpg_media": "Отправь медиа для RPG команды (фото/gif/mp4) или напиши 'skip'. Макс 10MB.",
        "rpg_saved": "✅ RPG-команда сохранена: /{cmd}",
        "no_rpg_commands": "RPG-команд нет",
        "rpg_commands": "⚔️ RPG-команды:",
        "invalid_media": "Неподдерживаемый тип. Отправь фото, GIF или MP4.",
        "media_too_large": "Файл слишком большой. Максимум 10MB.",
        "target_required": "Ответь на сообщение другого пользователя или укажи @username.",
        "pull_cooldown": "Кулдаун активен. Попробуй снова через {time_left}.",
    },
}


def t(key: str, **kwargs) -> str:
    template = TXT[LANGUAGE][key]
    return template.format(**kwargs)


def db_connect():
    return sqlite3.connect(DB_NAME)


def ensure_column(cur, table: str, column: str, ddl: str):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pulls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            rarity TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS card_catalog (
            card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            rarity TEXT NOT NULL,
            created_at TEXT NOT NULL,
            media_type TEXT,
            media_file_id TEXT,
            media_size INTEGER,
            media_path TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            card_id INTEGER NOT NULL,
            obtained_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(card_id) REFERENCES card_catalog(card_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rpg_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT UNIQUE NOT NULL,
            text_template TEXT NOT NULL,
            created_at TEXT NOT NULL,
            media_type TEXT,
            media_file_id TEXT,
            media_size INTEGER,
            media_path TEXT
        )
        """
    )

    ensure_column(cur, "card_catalog", "media_type", "media_type TEXT")
    ensure_column(cur, "card_catalog", "media_file_id", "media_file_id TEXT")
    ensure_column(cur, "card_catalog", "media_size", "media_size INTEGER")
    ensure_column(cur, "card_catalog", "media_path", "media_path TEXT")
    ensure_column(cur, "rpg_commands", "media_type", "media_type TEXT")
    ensure_column(cur, "rpg_commands", "media_file_id", "media_file_id TEXT")
    ensure_column(cur, "rpg_commands", "media_size", "media_size INTEGER")
    ensure_column(cur, "rpg_commands", "media_path", "media_path TEXT")
    ensure_column(cur, "users", "last_pull_at", "last_pull_at TEXT")

    conn.commit()
    conn.close()


def upsert_user(user_id: int, username: str | None, first_name: str | None) -> None:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users(user_id, username, first_name, joined_at)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
        """,
        (user_id, username, first_name, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_pull_cooldown_left(user_id: int) -> int:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT last_pull_at FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return 0
    try:
        last_pull = datetime.fromisoformat(row[0])
    except ValueError:
        return 0
    now = datetime.utcnow()
    elapsed = int((now - last_pull).total_seconds())
    left = PULL_COOLDOWN_SECONDS - elapsed
    return left if left > 0 else 0


def set_last_pull(user_id: int) -> None:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET last_pull_at = ? WHERE user_id = ?",
        (datetime.utcnow().isoformat(), user_id),
    )
    conn.commit()
    conn.close()


def format_seconds(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def choose_rarity() -> str:
    labels = [r[0] for r in RARITY_WEIGHTS]
    weights = [r[1] for r in RARITY_WEIGHTS]
    return random.choices(labels, weights=weights, k=1)[0]


def save_pull(user_id: int, rarity: str) -> None:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pulls(user_id, rarity, created_at) VALUES(?, ?, ?)",
        (user_id, rarity, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_stats(user_id: int) -> dict:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pulls WHERE user_id = ?", (user_id,))
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT rarity, COUNT(*) FROM pulls WHERE user_id = ? GROUP BY rarity", (user_id,)
    )
    by_rarity = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return {"total": total, "by_rarity": by_rarity}


def add_card(
    name: str,
    rarity: str,
    media_type: str | None,
    media_file_id: str | None,
    media_size: int | None,
    media_path: str | None,
) -> bool:
    conn = db_connect()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO card_catalog(name, rarity, created_at, media_type, media_file_id, media_size, media_path)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (name, rarity, datetime.utcnow().isoformat(), media_type, media_file_id, media_size, media_path),
        )
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    conn.close()
    return ok


def list_cards(limit: int = 20):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT card_id, name, rarity, media_type FROM card_catalog ORDER BY card_id DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def pull_card(user_id: int):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT card_id, name, rarity, media_type, media_file_id, media_path FROM card_catalog")
    cards = cur.fetchall()
    if not cards:
        conn.close()
        return None
    card = random.choice(cards)
    cur.execute(
        "INSERT INTO user_cards(user_id, card_id, obtained_at) VALUES(?, ?, ?)",
        (user_id, card[0], datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return card


def get_user_cards(user_id: int, limit: int = 20):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.name, c.rarity, uc.obtained_at
        FROM user_cards uc
        JOIN card_catalog c ON c.card_id = uc.card_id
        WHERE uc.user_id = ?
        ORDER BY uc.id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def upsert_rpg_command(
    command: str,
    text_template: str,
    media_type: str | None,
    media_file_id: str | None,
    media_size: int | None,
    media_path: str | None,
):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO rpg_commands(command, text_template, created_at, media_type, media_file_id, media_size, media_path)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(command) DO UPDATE SET
            text_template = excluded.text_template,
            media_type = excluded.media_type,
            media_file_id = excluded.media_file_id,
            media_size = excluded.media_size,
            media_path = excluded.media_path
        """,
        (command, text_template, datetime.utcnow().isoformat(), media_type, media_file_id, media_size, media_path),
    )
    conn.commit()
    conn.close()


def list_rpg_commands(limit: int = 30):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT command, text_template, media_type FROM rpg_commands ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_rpg_command(command: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT text_template, media_type, media_file_id, media_path FROM rpg_commands WHERE command = ?",
        (command,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def extract_media_info(message: Message):
    if message.photo:
        ph = message.photo[-1]
        return "photo", ph.file_id, ph.file_size or 0
    if message.animation:
        return "animation", message.animation.file_id, message.animation.file_size or 0
    if message.video:
        return "video", message.video.file_id, message.video.file_size or 0
    return None


async def send_media_message(bot: Bot, chat_id: int, media_type: str, media_file_id: str, caption: str):
    if media_type == "photo":
        await bot.send_photo(chat_id, media_file_id, caption=caption)
    elif media_type == "animation":
        await bot.send_animation(chat_id, media_file_id, caption=caption)
    elif media_type == "video":
        await bot.send_video(chat_id, media_file_id, caption=caption)
    else:
        await bot.send_message(chat_id, caption)


async def send_media_with_fallback(
    bot: Bot,
    chat_id: int,
    media_type: str | None,
    media_file_id: str | None,
    media_path: str | None,
    caption: str,
):
    if not media_type:
        await bot.send_message(chat_id, caption)
        return

    try:
        if media_path and os.path.exists(media_path):
            media = FSInputFile(media_path)
            if media_type == "photo":
                await bot.send_photo(chat_id, media, caption=caption)
            elif media_type == "animation":
                await bot.send_animation(chat_id, media, caption=caption)
            elif media_type == "video":
                await bot.send_video(chat_id, media, caption=caption)
            else:
                await bot.send_message(chat_id, caption)
            return
    except Exception:
        pass

    if media_file_id:
        await send_media_message(bot, chat_id, media_type, media_file_id, caption)
    else:
        await bot.send_message(chat_id, caption)


async def save_media_to_files(bot: Bot, media_type: str, file_id: str) -> str:
    ext = {"photo": "jpg", "animation": "gif", "video": "mp4"}.get(media_type, "bin")
    name = f"{media_type}_{uuid.uuid4().hex}.{ext}"
    rel_path = os.path.join(FILES_DIR, name)
    telegram_file = await bot.get_file(file_id)
    await bot.download_file(telegram_file.file_path, destination=rel_path)
    return rel_path


@router.message(Command("start"))
async def start_cmd(message: Message):
    upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(t("start", title=BOT_TITLE))


@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(t("help"))


@router.message(Command("pull"))
async def pull_cmd(message: Message, bot: Bot):
    upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    left = get_pull_cooldown_left(message.from_user.id)
    if left > 0:
        await message.answer(t("pull_cooldown", time_left=format_seconds(left)))
        return
    card = pull_card(message.from_user.id)
    if not card:
        await message.answer(t("catalog_empty"))
        return
    _, name, rarity, media_type, media_file_id, media_path = card
    save_pull(message.from_user.id, rarity)
    set_last_pull(message.from_user.id)
    text = t("you_got", name=name, rarity=rarity)
    await send_media_with_fallback(bot, message.chat.id, media_type, media_file_id, media_path, text)


@router.message(Command("collection"))
async def collection_cmd(message: Message):
    upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    rows = get_user_cards(message.from_user.id)
    if not rows:
        await message.answer(t("no_cards"))
        return
    lines = [t("your_cards")]
    for name, rarity, _ in rows:
        lines.append(f"- {name} [{rarity}]")
    await message.answer("\n".join(lines))


@router.message(Command("stats"))
async def stats_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(t("access_denied"))
        return
    upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    s = get_stats(message.from_user.id)
    lines = [t("stats_title", title=BOT_TITLE), t("total_pulls", count=s["total"])]
    for key in ["Common", "Rare", "Epic", "Legendary"]:
        lines.append(f"{key}: {s['by_rarity'].get(key, 0)}")
    await message.answer("\n".join(lines))


@router.message(Command("admin"))
async def admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(t("access_denied"))
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Add card", callback_data="admin_add_card")],
            [InlineKeyboardButton(text="List cards", callback_data="admin_list_cards")],
            [InlineKeyboardButton(text="Add RPG command", callback_data="admin_add_rpg")],
            [InlineKeyboardButton(text="List RPG commands", callback_data="admin_list_rpg")],
        ]
    )
    await message.answer(t("admin_panel"), reply_markup=kb)


@router.callback_query(F.data == "admin_add_card")
async def admin_add_card(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer(t("access_denied"), show_alert=True)
        return
    await state.set_state(AddCardFSM.waiting_name)
    await call.answer()
    await call.message.answer(t("send_card_name"))


@router.message(AddCardFSM.waiting_name)
async def step_card_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddCardFSM.waiting_rarity)
    await message.answer(t("send_rarity"))


@router.message(AddCardFSM.waiting_rarity)
async def step_card_rarity(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    rarity = message.text.strip()
    if rarity not in RARITY_SET:
        await message.answer(t("invalid_rarity"))
        return
    await state.update_data(rarity=rarity)
    await state.set_state(AddCardFSM.waiting_media)
    await message.answer(t("send_card_media"))


@router.message(AddCardFSM.waiting_media)
async def step_card_media(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    media_type = None
    media_file_id = None
    media_size = None
    media_path = None

    if message.text and message.text.strip().lower() == "skip":
        pass
    else:
        info = extract_media_info(message)
        if not info:
            await message.answer(t("invalid_media"))
            return
        media_type, media_file_id, media_size = info
        if media_size and media_size > MAX_MEDIA_SIZE:
            await message.answer(t("media_too_large"))
            return
        media_path = await save_media_to_files(bot, media_type, media_file_id)

    data = await state.get_data()
    name = data.get("name")
    rarity = data.get("rarity")
    if not name or not rarity:
        await state.clear()
        await message.answer(t("state_expired"))
        return

    ok = add_card(name, rarity, media_type, media_file_id, media_size, media_path)
    await state.clear()
    if ok:
        await message.answer(t("card_added", name=name, rarity=rarity))
    else:
        await message.answer(t("card_exists"))


@router.callback_query(F.data == "admin_list_cards")
async def admin_list_cards_cb(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer(t("access_denied"), show_alert=True)
        return
    rows = list_cards()
    await call.answer()
    if not rows:
        await call.message.answer(t("no_cards_catalog"))
        return
    lines = [t("catalog_cards")]
    for _, name, rarity, media_type in rows:
        media_flag = " [media]" if media_type else ""
        lines.append(f"- {name} [{rarity}]{media_flag}")
    await call.message.answer("\n".join(lines))


@router.callback_query(F.data == "admin_add_rpg")
async def admin_add_rpg(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer(t("access_denied"), show_alert=True)
        return
    await state.set_state(AddRpgFSM.waiting_command)
    await call.answer()
    await call.message.answer(t("send_rpg_name"))


@router.message(AddRpgFSM.waiting_command)
async def step_rpg_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    cmd = message.text.strip().lower().lstrip("/")
    if not cmd or " " in cmd:
        await message.answer(t("invalid_command"))
        return
    await state.update_data(command=cmd)
    await state.set_state(AddRpgFSM.waiting_template)
    await message.answer(t("send_rpg_template"))


@router.message(AddRpgFSM.waiting_template)
async def step_rpg_template(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(text_template=message.text.strip())
    await state.set_state(AddRpgFSM.waiting_media)
    await message.answer(t("send_rpg_media"))


@router.message(AddRpgFSM.waiting_media)
async def step_rpg_media(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    media_type = None
    media_file_id = None
    media_size = None
    media_path = None

    if message.text and message.text.strip().lower() == "skip":
        pass
    else:
        info = extract_media_info(message)
        if not info:
            await message.answer(t("invalid_media"))
            return
        media_type, media_file_id, media_size = info
        if media_size and media_size > MAX_MEDIA_SIZE:
            await message.answer(t("media_too_large"))
            return
        media_path = await save_media_to_files(bot, media_type, media_file_id)

    data = await state.get_data()
    cmd = data.get("command")
    text_template = data.get("text_template")
    if not cmd or not text_template:
        await state.clear()
        await message.answer(t("state_expired"))
        return

    upsert_rpg_command(cmd, text_template, media_type, media_file_id, media_size, media_path)
    await state.clear()
    await message.answer(t("rpg_saved", cmd=cmd))


@router.callback_query(F.data == "admin_list_rpg")
async def admin_list_rpg_cb(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer(t("access_denied"), show_alert=True)
        return
    rows = list_rpg_commands()
    await call.answer()
    if not rows:
        await call.message.answer(t("no_rpg_commands"))
        return
    lines = [t("rpg_commands")]
    for cmd, text, media_type in rows:
        preview = text if len(text) <= 60 else text[:57] + "..."
        media_flag = " [media]" if media_type else ""
        lines.append(f"/{cmd} -> {preview}{media_flag}")
    await call.message.answer("\n".join(lines))


def build_rpg_response(message: Message, cmd: str, target_text: str | None):
    row = get_rpg_command(cmd)
    if not row:
        return None
    text_template, media_type, media_file_id, media_path = row
    target = None
    if target_text and target_text.strip():
        target = target_text.strip()
    elif message.reply_to_message and message.reply_to_message.from_user:
        replied = message.reply_to_message.from_user
        target = replied.first_name or replied.username or str(replied.id)
    if not target:
        return "TARGET_REQUIRED", None, None
    user = message.from_user.first_name or message.from_user.username or str(message.from_user.id)
    text = text_template.replace("{user}", user).replace("{target}", target)
    return text, media_type, media_file_id, media_path


@router.message(F.text.startswith("/"))
async def dynamic_rpg_slash(message: Message, bot: Bot):
    raw = message.text.strip()
    parts = raw.split(maxsplit=1)
    cmd = parts[0].lstrip("/").split("@")[0].lower()
    if cmd in BUILTIN_CMDS:
        return
    target = parts[1] if len(parts) > 1 else None
    payload = build_rpg_response(message, cmd, target)
    if payload:
        text, media_type, media_file_id, media_path = payload
        if text == "TARGET_REQUIRED":
            await message.answer(t("target_required"))
            return
        await send_media_with_fallback(bot, message.chat.id, media_type, media_file_id, media_path, text)


@router.message(F.text)
async def dynamic_rpg_no_slash(message: Message, bot: Bot):
    raw = message.text.strip()
    parts = raw.split(maxsplit=1)
    if not parts:
        return
    cmd = parts[0].lower()
    target = parts[1] if len(parts) > 1 else None
    payload = build_rpg_response(message, cmd, target)
    if payload:
        text, media_type, media_file_id, media_path = payload
        if text == "TARGET_REQUIRED":
            await message.answer(t("target_required"))
            return
        await send_media_with_fallback(bot, message.chat.id, media_type, media_file_id, media_path, text)


async def run_bot():
    init_db()
    bot = Bot(TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
