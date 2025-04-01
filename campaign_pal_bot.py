import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
from collections import defaultdict
from datetime import datetime, timedelta
import json

# Configuration
INSTANTLY_API_KEY = 'NzFhYjkxN2ItNTlhYy00MTUzLWI2NzUtN2IwMGIzODhlOTI1Ok5yTXFzcGV4WVFNYw=='
TELEGRAM_BOT_TOKEN = '7750573826:AAE5_k6g4iEnMZzFrzM74EJLCgeG8OZi8Is'
BASE_URL = 'https://api.instantly.ai/api/v2'

# User credentials (username: password)
VALID_USERS = {
    'triplea@123': 'triplea@123',
    'go@123': 'go@123'
}

# Store user sessions {chat_id: username}
user_sessions = {}

# Data caching
campaigns_cache = {
    'go': [],
    'triplea': [],
    'last_updated': None
}

daily_analytics_cache = {
    'go': defaultdict(dict),
    'triplea': defaultdict(dict),
    'last_updated': None
}

def ensure_single_instance():
    """Check if another instance is running and terminate if needed"""
    import psutil
    current_pid = psutil.Process().pid
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['name'] == 'python.exe' and 'tg_bot_new.py' in ' '.join(proc.info['cmdline'] or []) and proc.info['pid'] != current_pid:
            proc.terminate()

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
            print("Unexpected API response format for campaigns")
            return None
            
        campaigns_cache['go'] = [c for c in data if 'go' in c.get('campaign_name', '').lower()]
        campaigns_cache['triplea'] = [c for c in data if 'triplea' in c.get('campaign_name', '').lower() or 'aaa' in c.get('campaign_name', '').lower()]
        campaigns_cache['last_updated'] = datetime.now()
        print(data)
        return data
    except Exception as e:
        print(f"Error fetching campaigns: {e}")
        return None

def fetch_daily_analytics_for_campaign(campaign_id):
    """Fetch daily analytics for a specific campaign"""
    try:
        url = f'{BASE_URL}/campaigns/analytics/daily?campaign_id={campaign_id}'
        headers = {
            'Authorization': f'Bearer {INSTANTLY_API_KEY}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if not isinstance(data, list):
            print(f"Unexpected API response format for daily analytics for campaign {campaign_id}")
            return None
            
        return data
    except Exception as e:
        print(f"Error fetching daily analytics for campaign {campaign_id}: {e}")
        return None

def update_daily_analytics_cache():
    """Update daily analytics cache by fetching data for each campaign"""
    try:
        if not campaigns_cache['last_updated'] or (datetime.now() - campaigns_cache['last_updated']).seconds > 300:
            fetch_all_campaigns()
        
        daily_analytics_cache['go'].clear()
        daily_analytics_cache['triplea'].clear()
        
        for campaign_type in ['go', 'triplea']:
            for campaign in campaigns_cache[campaign_type]:
                campaign_id = campaign.get('campaign_id')
                if not campaign_id:
                    continue
                
                daily_data = fetch_daily_analytics_for_campaign(campaign_id)
                if not daily_data:
                    continue
                
                for day in daily_data:
                    date = day.get('date')
                    if not date:
                        continue
                    
                    if date not in daily_analytics_cache[campaign_type]:
                        daily_analytics_cache[campaign_type][date] = {
                            'sent': 0,
                            'unique_opened': 0,
                            'unique_clicks': 0,
                            'replies': 0
                        }
                    
                    daily_analytics_cache[campaign_type][date]['sent'] += day.get('sent', 0)
                    daily_analytics_cache[campaign_type][date]['unique_opened'] += day.get('unique_opened', 0)
                    daily_analytics_cache[campaign_type][date]['unique_clicks'] += day.get('unique_clicks', 0)
                    daily_analytics_cache[campaign_type][date]['replies'] += day.get('replies', 0)
        
        daily_analytics_cache['last_updated'] = datetime.now()
        return True
    except Exception as e:
        print(f"Error updating daily analytics cache: {e}")
        return False

def format_campaign_message(campaigns):
    """Format campaign data for Telegram message"""
    if not campaigns:
        return "No campaign data available"
    
    message = ""
    for campaign in campaigns:
        message += (
            f"📌 <b>{campaign.get('campaign_name', 'N/A')}</b>\n"
            f"🆔 ID: <code>{campaign.get('campaign_id', 'N/A')}</code>\n"
            f"📈 Status: {'🟢 Active' if campaign.get('campaign_status') == 1 else '🔴 Inactive'}\n"
            f"👥 Total Leads: {campaign.get('leads_count', 0)}\n"
            f"✉ Contacted: {campaign.get('contacted_count', 0)}\n"
            f"📤 Emails Sent: {campaign.get('emails_sent_count', 0)}\n"
            f"👀 Unique Opens: {campaign.get('open_count', 0)}\n"
            f"🖱 Link Clicks: {campaign.get('link_click_count', 0)}\n"
            f"💬 Replies: {campaign.get('reply_count', 0)}\n"
            f"📉 Bounced: {campaign.get('bounced_count', 0)}\n"
            f"✅ Completed: {campaign.get('completed_count', 0)}\n"
            "────────────────────\n"
        )
    return message

def format_daily_analytics_message(daily_data):
    """Format daily analytics data for Telegram message"""
    if not daily_data:
        return "No daily analytics available"
    
    sorted_dates = sorted(daily_data.keys(), reverse=True)
    
    message = ""
    for date in sorted_dates:
        stats = daily_data[date]
        message += (
            f"📅 <b>{date}</b>\n"
            f"✉ Sent: {stats['sent']}\n"
            f"👀 Unique Opens: {stats['unique_opened']}\n"
            f"🖱 Unique Clicks: {stats['unique_clicks']}\n"
            f"💬 Replies: {stats['replies']}\n"
            "────────────────────\n"
        )
    
    today = datetime.now().strftime('%Y-%m-%d')
    if today not in daily_data:
        message = (
            f"📅 <b>{today} (Today - no data yet)</b>\n"
            f"✉ Sent: 0\n"
            f"👀 Unique Opens: 0\n"
            f"🖱 Unique Clicks: 0\n"
            f"💬 Replies: 0\n"
            "────────────────────\n"
        ) + message
    
    return message

async def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message and prompt for login"""
    chat_id = update.effective_chat.id
    if chat_id in user_sessions:
        await show_main_menu(update, context)
        return
    
    keyboard = [
        [InlineKeyboardButton("Login", callback_data='login')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔒 Welcome to Compaign Pal Bot\n\n"
        "Please login to access your analytics",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def login_prompt(update: Update, context: CallbackContext) -> None:
    """Prompt for username"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Please enter your username:",
        parse_mode='HTML'
    )
    context.user_data['awaiting'] = 'username'

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle username/password input"""
    chat_id = update.effective_chat.id
    text = update.message.text
    
    if 'awaiting' not in context.user_data:
        return
    
    if context.user_data['awaiting'] == 'username':
        context.user_data['username'] = text
        await update.message.reply_text("Please enter your password:", parse_mode='HTML')
        context.user_data['awaiting'] = 'password'
    
    elif context.user_data['awaiting'] == 'password':
        username = context.user_data['username']
        if username in VALID_USERS and text == VALID_USERS[username]:
            user_sessions[chat_id] = username
            await update.message.reply_text(f"✅ Login successful! Welcome {username}", parse_mode='HTML')
            await show_main_menu(update, context)
        else:
            await update.message.reply_text("❌ Invalid credentials. Please try again.", parse_mode='HTML')
            await login_prompt(update, context)
        
        del context.user_data['awaiting']
        if 'username' in context.user_data:
            del context.user_data['username']

async def show_main_menu(update: Update, context: CallbackContext) -> None:
    """Show the main menu based on user type"""
    chat_id = update.effective_chat.id
    username = user_sessions.get(chat_id)
    
    if not username:
        await start(update, context)
        return
    
    if username == 'triplea@123':
        keyboard = [
            [InlineKeyboardButton("TripleA Campaigns", callback_data='triplea_campaigns')],
            [InlineKeyboardButton("Daily TripleA Analytics", callback_data='daily_triplea')],
            [InlineKeyboardButton("Refresh Data", callback_data='refresh_data')],
            [InlineKeyboardButton("Logout", callback_data='logout')]
        ]
    else:  # go@123
        keyboard = [
            [InlineKeyboardButton("Go Campaigns", callback_data='go_campaigns')],
            [InlineKeyboardButton("Daily Go Analytics", callback_data='daily_go')],
            [InlineKeyboardButton("Refresh Data", callback_data='refresh_data')],
            [InlineKeyboardButton("Logout", callback_data='logout')]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"👋 Welcome <b>{username}</b>\n\n"
            "Select an option:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            f"👋 Welcome <b>{username}</b>\n\n"
            "Select an option:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

async def logout(update: Update, context: CallbackContext) -> None:
    """Handle logout"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    if chat_id in user_sessions:
        del user_sessions[chat_id]
    
    await query.edit_message_text("You have been logged out.", parse_mode='HTML')
    await start(update, context)

async def refresh_data(update: Update, context: CallbackContext) -> None:
    """Handle data refresh"""
    query = update.callback_query
    await query.answer()
    
    try:
        fetch_all_campaigns()
        update_daily_analytics_cache()
        await query.edit_message_text("✅ Data refreshed successfully!", parse_mode='HTML')
        await show_main_menu(update, context)
    except Exception as e:
        await query.edit_message_text(f"❌ Error refreshing data: {str(e)}", parse_mode='HTML')

# New handler for "Back to Menu" button
async def back_to_menu(update: Update, context: CallbackContext) -> None:
    """Handle the Back to Menu button click"""
    await show_main_menu(update, context)

async def show_go_campaigns(update: Update, context: CallbackContext) -> None:
    """Show Go campaigns with a Back to Menu button"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    if user_sessions.get(chat_id) != 'go@123':
        await query.edit_message_text("❌ Unauthorized access", parse_mode='HTML')
        return
    
    try:
        if not campaigns_cache['last_updated'] or (datetime.now() - campaigns_cache['last_updated']).seconds > 300:
            fetch_all_campaigns()
        
        if not campaigns_cache['go']:
            await query.edit_message_text("No Go campaigns found.", parse_mode='HTML')
            return
        
        message = format_campaign_message(campaigns_cache['go'])
        back_button = InlineKeyboardButton("Back to Menu", callback_data='back_to_menu')
        reply_markup = InlineKeyboardMarkup([[back_button]])
        await query.edit_message_text(
            message[:4000],
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error fetching Go campaigns: {str(e)}", parse_mode='HTML')

async def show_triplea_campaigns(update: Update, context: CallbackContext) -> None:
    """Show TripleA campaigns with a Back to Menu button"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    if user_sessions.get(chat_id) != 'triplea@123':
        await query.edit_message_text("❌ Unauthorized access", parse_mode='HTML')
        return
    
    try:
        if not campaigns_cache['last_updated'] or (datetime.now() - campaigns_cache['last_updated']).seconds > 300:
            fetch_all_campaigns()
        
        if not campaigns_cache['triplea']:
            await query.edit_message_text("No TripleA campaigns found.", parse_mode='HTML')
            return
        
        message = format_campaign_message(campaigns_cache['triplea'])
        back_button = InlineKeyboardButton("Back to Menu", callback_data='back_to_menu')
        reply_markup = InlineKeyboardMarkup([[back_button]])
        await query.edit_message_text(
            message[:4000],
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error fetching TripleA campaigns: {str(e)}", parse_mode='HTML')

async def show_daily_go(update: Update, context: CallbackContext) -> None:
    """Show aggregated daily analytics for Go campaigns with a Back to Menu button"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    if user_sessions.get(chat_id) != 'go@123':
        await query.edit_message_text("❌ Unauthorized access", parse_mode='HTML')
        return
    
    try:
        if not daily_analytics_cache['last_updated'] or (datetime.now() - daily_analytics_cache['last_updated']).seconds > 300:
            update_daily_analytics_cache()
        
        if not daily_analytics_cache['go']:
            await query.edit_message_text("No analytics data available for Go campaigns.", parse_mode='HTML')
            return
        
        message = format_daily_analytics_message(daily_analytics_cache['go'])
        back_button = InlineKeyboardButton("Back to Menu", callback_data='back_to_menu')
        reply_markup = InlineKeyboardMarkup([[back_button]])
        await query.edit_message_text(
            message[:4000],
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error fetching Go analytics: {str(e)}", parse_mode='HTML')

async def show_daily_triplea(update: Update, context: CallbackContext) -> None:
    """Show aggregated daily analytics for TripleA campaigns with a Back to Menu button"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    if user_sessions.get(chat_id) != 'triplea@123':
        await query.edit_message_text("❌ Unauthorized access", parse_mode='HTML')
        return
    
    try:
        if not daily_analytics_cache['last_updated'] or (datetime.now() - daily_analytics_cache['last_updated']).seconds > 300:
            update_daily_analytics_cache()
        
        if not daily_analytics_cache['triplea']:
            await query.edit_message_text("No analytics data available for TripleA campaigns.", parse_mode='HTML')
            return
        
        message = format_daily_analytics_message(daily_analytics_cache['triplea'])
        back_button = InlineKeyboardButton("Back to Menu", callback_data='back_to_menu')
        reply_markup = InlineKeyboardMarkup([[back_button]])
        await query.edit_message_text(
            message[:4000],
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error fetching TripleA analytics: {str(e)}", parse_mode='HTML')

def main():
    """Start the bot"""
    ensure_single_instance()
    
    fetch_all_campaigns()
    update_daily_analytics_cache()
    
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(login_prompt, pattern='^login$'))
    application.add_handler(CallbackQueryHandler(logout, pattern='^logout$'))
    application.add_handler(CallbackQueryHandler(refresh_data, pattern='^refresh_data$'))
    application.add_handler(CallbackQueryHandler(show_go_campaigns, pattern='^go_campaigns$'))
    application.add_handler(CallbackQueryHandler(show_triplea_campaigns, pattern='^triplea_campaigns$'))
    application.add_handler(CallbackQueryHandler(show_daily_go, pattern='^daily_go$'))
    application.add_handler(CallbackQueryHandler(show_daily_triplea, pattern='^daily_triplea$'))
    application.add_handler(CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$'))  # New handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == '__main__':
    main()