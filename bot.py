import os
import sqlite3
import secrets
import logging

from telegram import LabeledPrice, Update
from telegram.ext import (
    Application,
    CommandHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIGURATION
# =========================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

STAR_PRICE = 250
CURRENCY = "XTR"

DB_NAME = "payments.db"

# 50 CRORE TICKETS
MAX_TICKETS = 500_000_000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================
# DATABASE
# =========================

def get_db():
    return sqlite3.connect(DB_NAME, timeout=30)


def init_db():

    with get_db() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                payload TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                charge_id TEXT PRIMARY KEY,
                payload TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_no INTEGER PRIMARY KEY,
                ticket_code TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                payload TEXT UNIQUE NOT NULL,
                charge_id TEXT UNIQUE NOT NULL
            )
        """)


# =========================
# START COMMAND
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🎉 Welcome to ABC Codes Store!\n\n"
        "⭐ Ticket Price: 250 Telegram Stars\n\n"
        "Available Commands:\n\n"
        "/buy - Buy Ticket\n"
        "/mytickets - My Tickets\n"
        "/paysupport - Payment Support\n"
    )


# =========================
# BUY TICKET
# =========================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    payload = secrets.token_urlsafe(24)

    with get_db() as db:

        db.execute(
            """
            INSERT INTO orders
            VALUES (?, ?, ?, ?)
            """,
            (payload, user_id, STAR_PRICE, "PENDING")
        )

    await context.bot.send_invoice(

        chat_id=update.effective_chat.id,

        title="ABC Codes Store Ticket",

        description="Purchase one unique ABC ticket.",

        payload=payload,

        provider_token="",

        currency=CURRENCY,

        prices=[
            LabeledPrice(
                "ABC Ticket",
                STAR_PRICE
            )
        ],

    )


# =========================
# PRE CHECKOUT
# =========================

async def precheckout(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.pre_checkout_query

    with get_db() as db:

        order = db.execute(
            """
            SELECT user_id, amount, status
            FROM orders
            WHERE payload = ?
            """,
            (query.invoice_payload,)
        ).fetchone()

    valid = (

        order is not None

        and order[0] == query.from_user.id

        and order[1] == STAR_PRICE

        and order[2] == "PENDING"

        and query.total_amount == STAR_PRICE

        and query.currency == CURRENCY

    )

    if not valid:

        await query.answer(
            ok=False,
            error_message="Invalid or already processed order."
        )

        return

    await query.answer(ok=True)


# =========================
# AUTOMATIC TICKET SYSTEM
# =========================

def allocate_ticket(user_id, payload, charge_id, payment):

    with get_db() as db:

        db.execute("BEGIN IMMEDIATE")

        # Duplicate payment protection

        existing = db.execute(
            """
            SELECT ticket_code
            FROM tickets
            WHERE charge_id = ?
            """,
            (charge_id,)
        ).fetchone()

        if existing:
            return existing[0]

        order = db.execute(
            """
            SELECT user_id, amount, status
            FROM orders
            WHERE payload = ?
            """,
            (payload,)
        ).fetchone()

        if not order:
            raise ValueError("Order not found")

        if order[0] != user_id:
            raise ValueError("User mismatch")

        if order[1] != STAR_PRICE:
            raise ValueError("Amount mismatch")

        if order[2] != "PENDING":
            raise ValueError("Order already processed")

        if payment.currency != CURRENCY:
            raise ValueError("Invalid currency")

        if payment.total_amount != STAR_PRICE:
            raise ValueError("Invalid payment amount")

        # Next ticket number

        last_number = db.execute(
            """
            SELECT COALESCE(MAX(ticket_no), 0)
            FROM tickets
            """
        ).fetchone()[0]

        ticket_number = last_number + 1

        if ticket_number > MAX_TICKETS:
            raise ValueError("All tickets sold")

        ticket_code = f"A{ticket_number:010d}"

        # Save real Telegram payment

        db.execute(
            """
            INSERT INTO payments
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                charge_id,
                payload,
                user_id,
                payment.total_amount,
                payment.currency
            )
        )

        # Generate ticket

        db.execute(
            """
            INSERT INTO tickets
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                ticket_number,
                ticket_code,
                user_id,
                payload,
                charge_id
            )
        )

        # Mark order paid

        db.execute(
            """
            UPDATE orders
            SET status = 'PAID'
            WHERE payload = ?
            """,
            (payload,)
        )

        return ticket_code


# =========================
# SUCCESSFUL PAYMENT
# =========================

async def successful_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    payment = update.message.successful_payment

    user_id = update.effective_user.id

    payload = payment.invoice_payload

    charge_id = payment.telegram_payment_charge_id

    try:

        ticket = allocate_ticket(
            user_id,
            payload,
            charge_id,
            payment
        )

        await update.message.reply_text(

            "✅ PAYMENT SUCCESSFUL!\n\n"

            "⭐ Stars Received: 250\n\n"

            f"🎟 Your Ticket: {ticket}\n\n"

            "ABC Codes Store Thanks You!"

        )

        # ADMIN NOTIFICATION

        if ADMIN_ID:

            await context.bot.send_message(

                ADMIN_ID,

                "💰 NEW PAYMENT RECEIVED\n\n"

                f"User ID: {user_id}\n"

                "Stars: 250\n"

                f"Ticket: {ticket}\n"

                f"Charge ID: {charge_id}"

            )

    except Exception:

        logger.exception("Payment processing failed")

        await update.message.reply_text(

            "Your payment was received by Telegram, "
            "but ticket processing needs admin verification. "
            "Please contact support. Do not pay again."

        )


# =========================
# MY TICKETS
# =========================

async def mytickets(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    with get_db() as db:

        rows = db.execute(
            """
            SELECT ticket_code
            FROM tickets
            WHERE user_id = ?
            ORDER BY ticket_no DESC
            LIMIT 30
            """,
            (user_id,)
        ).fetchall()

    if not rows:

        await update.message.reply_text(
            "You have not purchased any tickets yet."
        )

        return

    codes = "\n".join(
        row[0] for row in rows
    )

    await update.message.reply_text(

        "🎟 YOUR ABC TICKETS\n\n"

        f"{codes}"

    )


# =========================
# ADMIN STATISTICS
# =========================

async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not ADMIN_ID or update.effective_user.id != ADMIN_ID:

        await update.message.reply_text("Access denied.")

        return

    with get_db() as db:

        total_tickets = db.execute(
            "SELECT COUNT(*) FROM tickets"
        ).fetchone()[0]

        total_users = db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM tickets"
        ).fetchone()[0]

        total_stars = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments"
        ).fetchone()[0]

    await update.message.reply_text(

        "📊 ABC CODES STORE ADMIN\n\n"

        f"🎟 Tickets Sold: {total_tickets}\n"

        f"👥 Paying Users: {total_users}\n"

        f"⭐ Stars Received: {total_stars}\n\n"

        f"Remaining Tickets: {MAX_TICKETS - total_tickets}"

    )


# =========================
# PAYMENT SUPPORT
# =========================

async def pay_support(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(

        "ABC Codes Store Payment Support\n\n"

        "If your payment succeeded but ticket was not issued, "
        "please contact the administrator."

    )


# =========================
# MAIN
# =========================

def main():

    if not TOKEN:

        raise ValueError(
            "TELEGRAM_BOT_TOKEN is missing"
        )

    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("buy", buy)
    )

    app.add_handler(
        CommandHandler("mytickets", mytickets)
    )

    app.add_handler(
        CommandHandler("stats", stats)
    )

    app.add_handler(
        CommandHandler("paysupport", pay_support)
    )

    app.add_handler(
        PreCheckoutQueryHandler(precheckout)
    )

    app.add_handler(
        MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            successful_payment
        )
    )

    print("ABC Codes Store Bot Started!")

    app.run_polling()


if __name__ == "__main__":

    main()
