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

TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
OWNER_ID = 7936569231

pool: asyncpg.Pool | None = None

# =====================
# DB INIT (POST_INIT)
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
    "🐶 Tere tulemast DoggieMarketisse!\n\n"
    "Kasuta allolevaid nuppe."
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
            reply_markup=main_menu()
        )

# =====================
# STOCK
# =====================
async def set_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    text = update.message.text.split(" ", 1)[1]

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE stock SET text=$1 WHERE id=1",
            text
        )

    await update.message.reply_text("✅ Stock salvestatud")

# =====================
# OPERATORS
# =====================
async def add_operator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    username = context.args[0]

    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO operators (username, loc, online, delivery)
        VALUES ($1, 'Not set', false, false)
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
    if not username:
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
    if not username:
        return

    value = context.args[0].lower() == "yes"

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
    if update.effective_user.id != OWNER_ID:
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
                reply_markup=back()
            )

        elif q.data == "operators":
            rows = await conn.fetch("SELECT * FROM operators")

            if not rows:
                text = "👤 OPERATORS\n\nInfo puudub."
            else:
                out = ["👤 OPERATORS\n"]
                for r in rows:
                    out.append(
                        f"{r['username']} | 📍 {r['loc']} | "
                        f"{'🟢 Online' if r['online'] else '🔴 Offline'} | "
                        f"🚚 {'Yes' if r['delivery'] else 'No'}"
                    )
                text = "\n".join(out)

            await q.edit_message_caption(
                caption=text,
                reply_markup=back()
            )

        elif q.data == "links":
            rows = await conn.fetch("SELECT * FROM links")

            if not rows:
                text = "🔗 LINKS\n\nInfo puudub."
            else:
                out = ["🔗 LINKS\n"]
                for r in rows:
                    out.append(f"📢 {r['name']}\n🔗 {r['url']}\n")
                text = "\n".join(out)

            await q.edit_message_caption(
                caption=text,
                reply_markup=back()
            )

        elif q.data == "back":
            await q.edit_message_caption(
                caption=HOME_CAPTION,
                reply_markup=main_menu()
            )

# =====================
# MAIN (ÕIGE!)
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

    print("Bot töötab (PostgreSQL)")
    app.run_polling()

if __name__ == "__main__":
    main()
