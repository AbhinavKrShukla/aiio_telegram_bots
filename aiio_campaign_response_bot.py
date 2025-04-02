from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
import logging
import requests
from datetime import datetime, timedelta

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# API Configuration
INSTANTLY_API_KEY = 'NzFhYjkxN2ItNTlhYy00MTUzLWI2NzUtN2IwMGIzODhlOTI1Ok5yTXFzcGV4WVFNYw=='
BASE_URL = 'https://api.instantly.ai/api/v2'

# Hardcoded user credentials
USERS = {
    'go@123': 'go@123',
    'triplea@123': 'triplea@123'
}

# Conversation states
USERNAME, PASSWORD, AUTHENTICATED = range(3)

# Menu keyboard for authenticated users
menu_keyboard = [
    [KeyboardButton('/start'), KeyboardButton('/logout')],
    [KeyboardButton('/replies')]
]
auth_reply_markup = ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True)

# Simple keyboard for unauthenticated users
start_keyboard = [[KeyboardButton('/start')]]
start_reply_markup = ReplyKeyboardMarkup(start_keyboard, resize_keyboard=True)

# Cache for campaign data
campaigns_cache = {
    'go': [],
    'triplea': [],
    'last_updated': None
}

def fetch_all_campaigns():
    """Fetch all campaigns from Instantly.ai API with proper error handling"""
    try:
        url = f'{BASE_URL}/campaigns/analytics'
        headers = {
            'Authorization': f'Bearer {INSTANTLY_API_KEY}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if not isinstance(data, list):
            logger.error("Unexpected API response format for campaigns")
            return None
            
        campaigns_cache['go'] = [c for c in data if 'go' in c.get('campaign_name', '').lower()]
        campaigns_cache['triplea'] = [c for c in data if 'triplea' in c.get('campaign_name', '').lower() or 'aaa' in c.get('campaign_name', '').lower()]
        campaigns_cache['last_updated'] = datetime.now()
        
        logger.info(f"Fetched campaigns: {len(data)} total, {len(campaigns_cache['go'])} Go, {len(campaigns_cache['triplea'])} TripleA")
        return data
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}")
        return None

def fetch_campaign_replies(campaign_id):
    """Fetch replies for a specific campaign"""
    try:
        url = f'{BASE_URL}/replies?campaign_id={campaign_id}'
        headers = {
            'Authorization': f'Bearer {INSTANTLY_API_KEY}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Fetched {len(data)} replies for campaign {campaign_id}")
        return data
    except Exception as e:
        logger.error(f"Error fetching replies for campaign {campaign_id}: {e}")
        return []

def format_reply(reply):
    """Format a single reply for display"""
    lead_email = reply.get('lead_email', 'Unknown')
    subject = reply.get('subject', 'No Subject')
    body = reply.get('body', 'No content')
    reply_time = reply.get('timestamp', 'Unknown time')
    
    # Try to convert timestamp to readable format
    try:
        if reply_time != 'Unknown time':
            dt = datetime.fromtimestamp(int(reply_time)/1000)  # Assuming timestamp is in milliseconds
            reply_time = dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        pass
    
    # Truncate body if too long
    if len(body) > 200:
        body = body[:197] + "..."
    
    formatted = (
        f"📧 <b>From:</b> {lead_email}\n"
        f"📝 <b>Subject:</b> {subject}\n"
        f"🕒 <b>Time:</b> {reply_time}\n"
        f"💬 <b>Message:</b>\n{body}\n"
        f"------------------\n\n"
    )
    return formatted

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message when the command /start is issued."""
    user = update.message.from_user
    await update.message.reply_text(
        f"Hi {user.first_name}! Please enter your username:",
        reply_markup=start_reply_markup
    )
    return USERNAME

async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the username and ask for password."""
    username = update.message.text
    # Store username in context
    context.user_data['username'] = username
    
    await update.message.reply_text(
        "Now, please enter your password:",
        reply_markup=start_reply_markup
    )
    return PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Verify password and complete authentication if valid."""
    password = update.message.text
    username = context.user_data.get('username')
    
    if username in USERS and USERS[username] == password:
        context.user_data['authenticated'] = True
        # Determine client type based on username
        client_type = 'triplea' if username == 'triplea@123' else 'go'
        context.user_data['client_type'] = client_type
        
        # First send welcome message with regular keyboard
        await update.message.reply_text(
            f"Welcome {username}! You are now logged in.",
            reply_markup=auth_reply_markup
        )
        
        # Then send a dedicated replies button message
        replies_keyboard = [[InlineKeyboardButton("Check Replies", callback_data="check_replies")]]
        replies_markup = InlineKeyboardMarkup(replies_keyboard)
        await update.message.reply_text(
            "Click below to check your replies:",
            reply_markup=replies_markup
        )
        
        return AUTHENTICATED
    else:
        await update.message.reply_text(
            "Invalid credentials. Please try again. Type /start to restart the login process.",
            reply_markup=start_reply_markup
        )
        return ConversationHandler.END

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Log out the user."""
    context.user_data.clear()
    await update.message.reply_text(
        "You have been logged out. Type /start to login again.",
        reply_markup=start_reply_markup
    )
    return ConversationHandler.END

async def get_all_replies(client_type):
    """Get all replies for a specific client type"""
    # Ensure we have up-to-date campaign data
    if not campaigns_cache['last_updated'] or (datetime.now() - campaigns_cache['last_updated']).seconds > 300:
        fetch_all_campaigns()
    
    # Get campaign IDs for the client type
    campaign_ids = [campaign.get('campaign_id') for campaign in campaigns_cache[client_type] if campaign.get('campaign_id')]
    
    # Fetch replies for each campaign
    all_replies = []
    for campaign_id in campaign_ids:
        replies = fetch_campaign_replies(campaign_id)
        if replies:
            all_replies.extend(replies)
    
    # Sort replies by timestamp (newest first)
    try:
        all_replies.sort(key=lambda x: int(x.get('timestamp', 0)), reverse=True)
    except:
        pass
    
    return all_replies

async def replies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show replies from the API."""
    if not context.user_data.get('authenticated', False):
        await update.message.reply_text(
            "Please login first using /start",
            reply_markup=start_reply_markup
        )
        return
    
    # Show loading message
    loading_msg = await update.message.reply_text("Fetching replies, please wait...")
    
    client_type = context.user_data.get('client_type', 'go')
    all_replies = await get_all_replies(client_type)
    
    await loading_msg.delete()
    
    if not all_replies:
        await update.message.reply_text(
            "No replies yet!",
            reply_markup=auth_reply_markup
        )
        return
    
    # Format the first 5 replies (to avoid message too long)
    formatted_replies = ""
    for i, reply in enumerate(all_replies[:5]):
        formatted_replies += format_reply(reply)
    
    # Add a summary
    total_replies = len(all_replies)
    shown_replies = min(5, total_replies)
    
    if total_replies > shown_replies:
        formatted_replies += f"Showing {shown_replies} of {total_replies} total replies."
    
    await update.message.reply_text(
        f"Latest Replies for {client_type.upper()} campaigns:\n\n{formatted_replies}",
        parse_mode='HTML',
        reply_markup=auth_reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()  # Answer the callback query to stop the loading indicator
    
    if query.data == "check_replies":
        if not context.user_data.get('authenticated', False):
            await query.message.reply_text(
                "Please login first using /start",
                reply_markup=start_reply_markup
            )
            return
        
        # Show loading message
        loading_msg = await query.message.reply_text("Fetching replies, please wait...")
        
        client_type = context.user_data.get('client_type', 'go')
        all_replies = await get_all_replies(client_type)
        
        await loading_msg.delete()
        
        if not all_replies:
            # Updated this message to match the one in the replies function
            await query.message.reply_text(
                "No replies yet!",
                reply_markup=auth_reply_markup
            )
            return
        
        # Format the first 5 replies (to avoid message too long)
        formatted_replies = ""
        for i, reply in enumerate(all_replies[:5]):
            formatted_replies += format_reply(reply)
        
        # Add a summary
        total_replies = len(all_replies)
        shown_replies = min(5, total_replies)
        
        if total_replies > shown_replies:
            formatted_replies += f"Showing {shown_replies} of {total_replies} total replies."
        
        await query.message.reply_text(
            f"Latest Replies for {client_type.upper()} campaigns:\n\n{formatted_replies}",
            parse_mode='HTML',
            reply_markup=auth_reply_markup
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel and end the conversation."""
    await update.message.reply_text(
        'Bye! I hope we can talk again some day.',
        reply_markup=start_reply_markup
    )
    return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    # Create the Application object with your bot token
    application = Application.builder().token("8198915469:AAHqZTiJoEZBHwOu_9UPWMK0qatslMSVjTc").build()

    # Initialize campaign cache
    fetch_all_campaigns()

    # Add conversation handler with the states USERNAME, PASSWORD, and AUTHENTICATED
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            AUTHENTICATED: [
                CommandHandler('replies', replies),
                CommandHandler('logout', logout)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    
    # Add standalone handler for replies command outside the conversation flow
    application.add_handler(CommandHandler('replies', replies))
    
    # Add callback handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()