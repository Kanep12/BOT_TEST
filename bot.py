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
        VALUES (1, '📦 Stock\n\nInfo puudub.')
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
# UI
# =====================
HOME_CAPTION = (
    "🐶 **Welcome to DoggieMarket**\n\n"
    "Your trusted marketplace.\n"
    "Fast • Discreet • Reliable\n\n"
    "Please choose an option below."
)

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 Stock", callback_data="stock"),
            InlineKeyboardButton("👤 Operators", callback_data="operators"),
            InlineKeyboardButton("🔗 Links", callback_data="links")
        ]
    ])

def back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="back")]
    ])

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
# STOCK (AINUS ÕIGE LAHENDUS)
# =====================
async def set_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    # ⬇️ peab olema reply
    if not update.message.reply_to_message or not update.message.reply_to_message.text:
        await update.message.reply_text(
            "❗ Kasuta /stock vastusena stocki tekstile.\n\n"
            "Näide:\n"
            "1️⃣ kirjuta stock tekst\n"
            "2️⃣ reply sellele sõnumile\n"
            "3️⃣ kirjuta /stock"
        )
        return

    text = update.message.reply_to_message.text

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE stock SET text=$1 WHERE id=1",
            text
        )

    await update.message.reply_text("✅ Stock salvestatud (reavahed säilisid)")

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

    await update.message.reply_text(f"✅ Operator lisatud: {username}")

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
            loc, username
        )

    await update.message.reply_text("📍 Location salvestatud")

async def online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = await get_operator(update.effective_user)
    if not username:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE operators SET online=true WHERE username=$1",
            username
        )

    await update.message.reply_text("🟢 ONLINE")

async def offline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = await get_operator(update.effective_user)
    if not username:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE operators SET online=false WHERE username=$1",
            username
        )

    await update.message.reply_text("🔴 OFFLINE")

async def delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = await get_operator(update.effective_user)
    if not username or not context.args:
        return

    value = context.args[0].lower() in ("yes", "on", "true")

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE operators SET delivery=$1 WHERE username=$2",
            value, username
        )

    await update.message.reply_text("🚚 Delivery salvestatud")

# =====================
# LINKS
# =====================
async def add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID or len(context.args) < 2:
        return

    url = context.args[-1]
    name = " ".join(context.args[:-1])

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO links (name, url) VALUES ($1, $2)",
            name, url
        )

    await update.message.reply_text("✅ Link lisatud")

# =====================
# BUTTONS
# =====================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    async with pool.acquire() as conn:

        if q.data == "stock":
            row = await conn.fetchrow("SELECT text FROM stock WHERE id=1")
            await q.edit_message_caption(
                caption=row["text"],
                reply_markup=back(),
                parse_mode=ParseMode.MARKDOWN
            )

        elif q.data == "operators":
            rows = await conn.fetch("SELECT * FROM operators")

            if not rows:
                text = "👤 Operators\n\nInfo puudub."
            else:
                out = ["👤 Operators\n"]
                for r in rows:
                    out.append(
                        f"{r['username']} | 📍 {r['loc'] or 'Not specified'} | "
                        f"{'🟢 Online' if r['online'] else '🔴 Offline'} | "
                        f"🚚 {'Available' if r['delivery'] else 'Not available'}"
                    )
                text = "\n".join(out)

            await q.edit_message_caption(
                caption=text,
                reply_markup=back(),
                parse_mode=ParseMode.MARKDOWN
            )

        elif q.data == "links":
            rows = await conn.fetch("SELECT * FROM links")

            if not rows:
                text = "🔗 Links\n\nInfo puudub."
            else:
                out = ["🔗 Useful Links\n"]
                for r in rows:
                    out.append(f"📢 {r['name']}\n🔗 {r['url']}\n")
                text = "\n".join(out)

            await q.edit_message_caption(
                caption=text,
                reply_markup=back(),
                parse_mode=ParseMode.MARKDOWN
            )

        elif q.data == "back":
            await q.edit_message_caption(
                caption=HOME_CAPTION,
                reply_markup=main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )

# =====================
# MAIN
# =====================
def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(init_db)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stock", set_stock))
    app.add_handler(CommandHandler("addoperator", add_operator))
    app.add_handler(CommandHandler("loc", set_loc))
    app.add_handler(CommandHandler("online", online))
    app.add_handler(CommandHandler("offline", offline))
    app.add_handler(CommandHandler("delivery", delivery))
    app.add_handler(CommandHandler("link", add_link))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot töötab")
    app.run_polling()

if __name__ == "__main__":
    main()
