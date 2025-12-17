import os
import asyncpg
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from telegram.constants import ParseMode

TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
OWNER_ID = 7936569231

pool: asyncpg.Pool | None = None

# =====================
# DB INIT
# =====================
async def init_db(app):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id INT PRIMARY KEY DEFAULT 1,
            text TEXT
        );
        INSERT INTO stock (id, text)
        VALUES (1, '📦 Stock\n\nNo stock information available.')
        ON CONFLICT (id) DO NOTHING;
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS operators (
            username TEXT PRIMARY KEY,
            user_id BIGINT,
            loc TEXT,
            online BOOLEAN,
            delivery BOOLEAN
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id SERIAL PRIMARY KEY,
            name TEXT,
            url TEXT
        );
        """)

# =====================
# UI TEXTS
# =====================
HOME_CAPTION = (
    "🐶 **Welcome to DoggieMarket**\n\n"
    "Your trusted marketplace.\n"
    "Fast • Discreet • Reliable\n\n"
    "Please choose an option below."
)

def main_menu():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📦 Stock", callback_data="stock"),
        InlineKeyboardButton("👤 Operators", callback_data="operators"),
        InlineKeyboardButton("🔗 Links", callback_data="links")
    ]])

def back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="back")]
    ])

# =====================
# FORMATTERS
# =====================
def format_operator_card(r) -> str:
    operating_area = r["loc"].strip() if r["loc"] else "Not specified"
    status_icon = "🟢" if r["online"] else "🔴"
    status_text = "Online" if r["online"] else "Offline"
    delivery_text = "Available" if r["delivery"] else "Not available"

    return (
        "**Operator Contact**\n"
        f"👤 **{r['username']}**\n\n"
        f"📍 **Operating Area:** {operating_area}\n"
        f"📡 **Current Status:** {status_icon} {status_text}\n"
        f"🚚 **Delivery Service:** {delivery_text}"
    )

def format_links(rows) -> str:
    if not rows:
        return "🔗 **Links**\n\nNo links available."

    out = ["🔗 **Useful Links**\n"]
    for r in rows:
        out.append(f"📢 **{r['name']}**")
        out.append(f"🔗 {r['url']}")
        out.append("────────────")
    return "\n".join(out).rstrip("────────────")

# =====================
# /start
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open("doggie.png", "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=HOME_CAPTION,
            reply_markup=main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )

# =====================
# STOCK
# =====================
async def set_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID or not context.args:
        return

    text = " ".join(context.args)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE stock SET text=$1 WHERE id=1",
            text
        )

    await update.message.reply_text("✅ Stock updated")

# =====================
# OPERATORS
# =====================
async def add_operator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID or not context.args:
        return

    raw = context.args[0]
    username = raw if raw.startswith("@") else f"@{raw}"

    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO operators (username, loc, online, delivery)
        VALUES ($1, NULL, false, false)
        ON CONFLICT (username) DO NOTHING
        """, username)

    await update.message.reply_text(f"✅ Operator added: {username}")

async def get_operator(user):
    if not user.username:
        return None

    username = f"@{user.username}"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT username FROM operators WHERE username=$1",
            username
        )
        if row:
            await conn.execute(
                "UPDATE operators SET user_id=$1 WHERE username=$2",
                user.id, username
            )
            return username
    return None

async def set_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = await get_operator(update.effective_user)
    if not username or not context.args:
        return

    loc = " ".join(context.args)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE operators SET loc=$1 WHERE username=$2",
            lo
