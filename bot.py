import os
import sqlite3
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = 6121000907

UPI_ID = "9153219049@ptaxis"
PRICE = 100

DB = "abc_store.db"


# DATABASE SETUP

def connect():
    return sqlite3.connect(DB)


def setup_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                code TEXT PRIMARY KEY,
                user_id INTEGER UNIQUE
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                utr TEXT UNIQUE,
                amount INTEGER,
                status TEXT DEFAULT 'PENDING',
                token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for i in range(1, 10001):
            con.execute(
                "INSERT OR IGNORE INTO tokens (code) VALUES (?)",
                (f"ABCcod{i}",)
            )


# START COMMAND

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id

    with connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO users VALUES (?)",
            (uid,)
        )

    keyboard = [
        [InlineKeyboardButton(
            "🛒 Buy Token ₹100",
            callback_data="buy"
        )],
        [InlineKeyboardButton(
            "📋 कोड की जानकारी",
            callback_data="codes"
        )],
        [InlineKeyboardButton(
            "ℹ️ सहायता",
            callback_data="help"
        )]
    ]

    await update.message.reply_text(
        "नमस्ते! ABC Codes Store में आपका स्वागत है। 😊\n\nअपना विकल्प चुनें:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# BUTTON HANDLER

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    if data == "buy":

        context.user_data["waiting_utr"] = True

        keyboard = [
            [InlineKeyboardButton(
                "📋 Copy UPI ID",
                callback_data="show_upi"
            )]
        ]

        await query.edit_message_text(
            f"🛒 ABC Codes Store\n\n"
            f"Token Price: ₹{PRICE}\n\n"
            f"Paytm UPI ID:\n{UPI_ID}\n\n"
            "कृपया ₹100 का भुगतान करें।\n"
            "इसके बाद अपना UPI Transaction ID भेजें।\n\n"
            "⚠️ पेमेंट की जाँच Admin करेगा।",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "show_upi":

        await query.message.reply_text(
            f"आपकी UPI ID: {UPI_ID}\n"
            f"Payment Amount: ₹{PRICE}"
        )

    elif data == "codes":

        await query.edit_message_text(
            "ABC Codes Store में कुल 10,000 टोकन उपलब्ध हैं।"
        )

    elif data == "help":

        await query.edit_message_text(
            "सहायता के लिए ABC Codes Store Admin से संपर्क करें।"
        )

    elif data.startswith("approve:"):

        if uid != ADMIN_ID:
            return

        payment_id = int(data.split(":")[1])

        with connect() as con:

            con.execute("BEGIN IMMEDIATE")

            payment = con.execute(
                "SELECT user_id, status FROM payments WHERE id=?",
                (payment_id,)
            ).fetchone()

            if not payment or payment[1] != "PENDING":
                await query.message.reply_text(
                    "यह Payment पहले ही Process हो चुका है।"
                )
                return

            user_id = payment[0]

            token = con.execute("""
                SELECT code FROM tokens
                WHERE user_id IS NULL
                ORDER BY CAST(SUBSTR(code, 7) AS INTEGER)
                LIMIT 1
            """).fetchone()

            if not token:
                await query.message.reply_text(
                    "सभी टोकन समाप्त हो चुके हैं।"
                )
                return

            code = token[0]

            con.execute(
                "UPDATE tokens SET user_id=? WHERE code=?",
                (user_id, code)
            )

            con.execute("""
                UPDATE payments
                SET status='APPROVED', token=?
                WHERE id=?
            """, (code, payment_id))

        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 आपका Payment Approved!\n\n"
                 f"आपका ABC Token:\n{code}\n\n"
                 "धन्यवाद! ABC Codes Store"
        )

        await query.edit_message_text(
            f"✅ Payment Approved\n"
            f"User ID: {user_id}\n"
            f"Token: {code}"
        )

    elif data.startswith("reject:"):

        if uid != ADMIN_ID:
            return

        payment_id = int(data.split(":")[1])

        with connect() as con:

            result = con.execute("""
                UPDATE payments SET status='REJECTED'
                WHERE id=? AND status='PENDING'
            """, (payment_id,))

            payment = con.execute(
                "SELECT user_id FROM payments WHERE id=?",
                (payment_id,)
            ).fetchone()

        if result.rowcount and payment:
            await context.bot.send_message(
                payment[0],
                "❌ आपका Payment Request Reject कर दिया गया है।"
            )

            await query.edit_message_text(
                "❌ Payment Rejected"
            )
        else:
            await query.message.reply_text(
                "यह Request पहले ही Process हो चुकी है।"
            )


# TRANSACTION ID RECEIVER

async def receive_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_utr"):
        return

    utr = update.message.text.strip()

    if not 6 <= len(utr) <= 40:
        await update.message.reply_text(
            "कृपया सही Transaction ID भेजें।"
        )
        return

    uid = update.effective_user.id

    try:
        with connect() as con:

            cur = con.execute("""
                INSERT INTO payments (user_id, utr, amount)
                VALUES (?, ?, ?)
            """, (uid, utr, PRICE))

            payment_id = cur.lastrowid

    except sqlite3.IntegrityError:
        await update.message.reply_text(
            "यह Transaction ID पहले जमा हो चुकी है।"
        )
        return

    context.user_data["waiting_utr"] = False

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Approve",
                callback_data=f"approve:{payment_id}"
            ),
            InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"reject:{payment_id}"
            )
        ]
    ]

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💰 New Payment Request\n\n"
             f"Payment ID: {payment_id}\n"
             f"User ID: {uid}\n"
             f"Amount: ₹{PRICE}\n"
             f"Transaction ID: {utr}\n\n"
             "Paytm में पेमेंट चेक करें।",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text(
        "✅ आपका Payment Request Admin को भेज दिया गया है।\n"
        "Payment Verify होने के बाद Token मिलेगा।"
    )


# ADMIN PANEL

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    with connect() as con:

        users = con.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        approved = con.execute(
            "SELECT COUNT(*) FROM payments WHERE status='APPROVED'"
        ).fetchone()[0]

        pending = con.execute(
            "SELECT COUNT(*) FROM payments WHERE status='PENDING'"
        ).fetchone()[0]

        available = con.execute(
            "SELECT COUNT(*) FROM tokens WHERE user_id IS NULL"
        ).fetchone()[0]

        history = con.execute("""
            SELECT id, user_id, utr, status, token
            FROM payments
            ORDER BY id DESC LIMIT 10
        """).fetchall()

    message = (
        "👑 ABC CODES STORE ADMIN PANEL\n\n"
        f"👥 Total Users: {users}\n"
        f"💰 Approved Payments: {approved}\n"
        f"⏳ Pending Payments: {pending}\n"
        f"🎟️ Available Tokens: {available}\n\n"
        "📜 LAST 10 PAYMENTS\n"
    )

    for row in history:
        message += (
            f"\nID: {row[0]} | User: {row[1]}\n"
            f"UTR: {row[2]} | {row[3]}\n"
            f"Token: {row[4] or '-'}\n"
        )

    await update.message.reply_text(message)


# MAIN

def main():

    if not TOKEN:
        raise RuntimeError("Bot Token सेट नहीं है!")

    setup_database()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_payment
        )
    )

    print("ABC Codes Store Bot Started!")

    app.run_polling()


if __name__ == "__main__":
    main()
