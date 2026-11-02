import os
import sqlite3
import secrets

from telegram import LabeledPrice, Update
from telegram.ext import (
    Application,
    CommandHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
STAR_PRICE = 250
DB_NAME = "payments.db"


def init_db():
    with sqlite3.connect(DB_NAME) as db:
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
                payload TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL
            )
        """)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to ABC Codes Store!\n"
        "Digital service payment demo."
    )


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Unique invoice payload
    payload = secrets.token_urlsafe(24)

    with sqlite3.connect(DB_NAME) as db:
        db.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            (payload, user_id, STAR_PRICE, "PENDING")
        )

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="ABC Digital Service",
        description="Digital service demo purchase",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice("Digital Service", STAR_PRICE)
        ],
    )


async def precheckout(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.pre_checkout_query

    with sqlite3.connect(DB_NAME) as db:
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
        and order[1] == query.total_amount
        and order[2] == "PENDING"
        and query.currency == "XTR"
    )

    if not valid:
        await query.answer(
            ok=False,
            error_message="Order invalid or already processed."
        )
        return

    await query.answer(ok=True)


async def successful_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    payment = update.message.successful_payment
    user_id = update.effective_user.id

    if payment.currency != "XTR":
        return

    if payment.total_amount != STAR_PRICE:
        return

    charge_id = payment.telegram_payment_charge_id
    payload = payment.invoice_payload

    with sqlite3.connect(DB_NAME) as db:
        order = db.execute(
            """
            SELECT user_id, amount, status
            FROM orders
            WHERE payload = ?
            """,
            (payload,)
        ).fetchone()

        if not order:
            await update.message.reply_text(
                "Payment received, but order verification is pending."
            )
            return

        if order[0] != user_id or order[1] != STAR_PRICE:
            return

        try:
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
                    payment.currency,
                )
            )

            db.execute(
                """
                UPDATE orders
                SET status = 'PAID'
                WHERE payload = ?
                """,
                (payload,)
            )

        except sqlite3.IntegrityError:
            await update.message.reply_text(
                "This payment has already been recorded."
            )
            return

    await update.message.reply_text(
        "✅ PAYMENT SUCCESSFUL!\n\n"
        "⭐ Received: 250 Stars\n"
        "🧾 Payment recorded successfully.\n"
        "Thank you for your purchase!"
    )


async def pay_support(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "For payment support, please contact ABC Codes Store Admin."
    )


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("paysupport", pay_support))

    app.add_handler(
        PreCheckoutQueryHandler(precheckout)
    )

    app.add_handler(
        MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            successful_payment
        )
    )

    app.run_polling()


if __name__ == "__main__":
    main()
