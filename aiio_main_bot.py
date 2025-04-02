from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
TOKEN = "8167237932:AAF4q_LlPBri5Ov1VZiasVJ70UTw1axZZZs"  # Replace with your bot token

# Bot URLs
CAMPAIGN_RESPONSE_BOT_URL = "https://t.me/aiio_campaign_response_bot"
DAILY_ANALYTICS_BOT_URL = "https://t.me/aiio_daily_analytics_bot"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message and prompt with bot options."""
    user = update.effective_user
    
    # Create keyboard with bot options
    keyboard = [
        [
            InlineKeyboardButton("Campaign Response Bot", url=CAMPAIGN_RESPONSE_BOT_URL),
            InlineKeyboardButton("Daily Analytics Bot", url=DAILY_ANALYTICS_BOT_URL)
        ],
        [InlineKeyboardButton("Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Hello, {user.first_name}!\n\n"
        f"Welcome to the AIIO Bot Gateway.\n\n"
        f"Please select one of our bots below to help with your needs:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display help information about the available bots."""
    keyboard = [
        [
            InlineKeyboardButton("Campaign Response Bot", url=CAMPAIGN_RESPONSE_BOT_URL),
            InlineKeyboardButton("Daily Analytics Bot", url=DAILY_ANALYTICS_BOT_URL)
        ],
        [InlineKeyboardButton("Back to Start", callback_data="start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📚 *AIIO Bot Information*\n\n"
        "*Campaign Response Bot*\n"
        "View real-time responses to your email campaigns. See who replied, what they said, and when.\n\n"
        "*Daily Analytics Bot*\n"
        "Track daily metrics for your campaigns including opens, clicks, and response rates.\n\n"
        "Please select a bot to get started:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        keyboard = [
            [
                InlineKeyboardButton("Campaign Response Bot", url=CAMPAIGN_RESPONSE_BOT_URL),
                InlineKeyboardButton("Daily Analytics Bot", url=DAILY_ANALYTICS_BOT_URL)
            ],
            [InlineKeyboardButton("Back to Start", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📚 *AIIO Bot Information*\n\n"
            "*Campaign Response Bot*\n"
            "View real-time responses to your email campaigns. See who replied, what they said, and when.\n\n"
            "*Daily Analytics Bot*\n"
            "Track daily metrics for your campaigns including opens, clicks, and response rates.\n\n"
            "Please select a bot to get started:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif query.data == "start":
        keyboard = [
            [
                InlineKeyboardButton("Campaign Response Bot", url=CAMPAIGN_RESPONSE_BOT_URL),
                InlineKeyboardButton("Daily Analytics Bot", url=DAILY_ANALYTICS_BOT_URL)
            ],
            [InlineKeyboardButton("Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"👋 Hello!\n\n"
            f"Welcome to the AIIO Bot Gateway.\n\n"
            f"Please select one of our bots below to help with your needs:",
            reply_markup=reply_markup
        )

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown commands or regular messages."""
    keyboard = [
        [
            InlineKeyboardButton("Campaign Response Bot", url=CAMPAIGN_RESPONSE_BOT_URL),
            InlineKeyboardButton("Daily Analytics Bot", url=DAILY_ANALYTICS_BOT_URL)
        ],
        [InlineKeyboardButton("Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "I don't understand that command. Please select one of our bots below:",
        reply_markup=reply_markup
    )

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Handle unknown commands and regular messages
    application.add_handler(MessageHandler(filters.COMMAND, handle_unknown))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()