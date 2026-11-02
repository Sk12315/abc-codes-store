from telegram import LabeledPrice
from telegram.ext import PreCheckoutQueryHandler

STAR_PRICE = 250

async def buy_ticket(update, context):
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="ABC Codes Store Ticket",
        description="One Unique ABC Ticket",
        payload=f"ticket_{update.effective_user.id}",
        currency="XTR",
        prices=[
            LabeledPrice("ABC Ticket", STAR_PRICE)
        ]
    )


async def precheckout(update, context):
    query = update.pre_checkout_query

    await query.answer(ok=True)


async def successful_payment(update, context):

    payment = update.message.successful_payment

    if payment.currency != "XTR":
        return

    if payment.total_amount != STAR_PRICE:
        return

    user_id = update.effective_user.id

    # यहां डेटाबेस से सुरक्षित यूनिक टिकट बनाएं
    token = generate_unique_ticket()

    await update.message.reply_text(
        "🎉 PAYMENT SUCCESSFUL!\n\n"
        "⭐ Payment: 250 Stars\n"
        f"🎟️ Your Ticket: {token}\n\n"
        "धन्यवाद! ABC Codes Store में आपका स्वागत है।"
    )
