from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import os

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 कोड की जानकारी", callback_data="codes")],
        [InlineKeyboardButton("ℹ️ सहायता", callback_data="help")]
    ]

    await update.message.reply_text(
        "नमस्ते! ABC Codes Store में आपका स्वागत है। 😊\n\nअपना विकल्प चुनें:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "codes":
        await query.edit_message_text(
            "ABC Codes Store में आपका स्वागत है।\nकोड की जानकारी जल्द उपलब्ध होगी।"
        )

    elif query.data == "help":
        await query.edit_message_text(
            "सहायता के लिए बॉट एडमिन से संपर्क करें।"
        )

def main():
    if not TOKEN:
        raise RuntimeError("Bot token सेट नहीं है!")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
