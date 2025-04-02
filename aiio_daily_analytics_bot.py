import requests
import asyncio
import json
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    Application
)
from collections import defaultdict
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
INSTANTLY_API_KEY = 'NzFhYjkxN2ItNTlhYy00MTUzLWI2NzUtN2IwMGIzODhlOTI1Ok5yTXFzcGV4WVFNYw=='
TELEGRAM_BOT_TOKEN = '7870994476:AAFx76itbNyH8fYiMfky71r1QuTdu5HO6_4'
BASE_URL = 'https://api.instantly.ai/api/v2'

# File path to store group configurations
GROUP_CONFIG_FILE = 'group_config.json'

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

# Load existing group configuration
def load_group_config():
    """Load group configuration from file"""
    if os.path.exists(GROUP_CONFIG_FILE):
        try:
            with open(GROUP_CONFIG_FILE, 'r') as file:
                return json.load(file)
        except Exception as e:
            logger.error(f"Error loading group config: {e}")
            return default_group_config()
    else:
        return default_group_config()

# Default group configuration
def default_group_config():
    """Return default group configuration"""
    return {
        'go': {
            'name': 'Go',
            'chat_ids': [],
            'analytics_link': 'https://app.instantly.ai/dashboard'
        },
        'triplea': {
            'name': 'TripleA',
            'chat_ids': [],
            'analytics_link': 'https://app.instantly.ai/dashboard'
        }
    }

# Save group configuration
def save_group_config(config):
    """Save group configuration to file"""
    try:
        with open(GROUP_CONFIG_FILE, 'w') as file:
            json.dump(config, file, indent=4)
        logger.info(f"Group configuration saved to {GROUP_CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Error saving group config: {e}")

# Initialize group configuration
CLIENT_GROUPS = load_group_config()

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
            logger.error(f"Unexpected API response format for daily analytics for campaign {campaign_id}")
            return None
            
        return data
    except Exception as e:
        logger.error(f"Error fetching daily analytics for campaign {campaign_id}: {e}")
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
        logger.info("Daily analytics cache updated successfully")
        return True
    except Exception as e:
        logger.error(f"Error updating daily analytics cache: {e}")
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

async def generate_broadcast_message(client_type):
    """Generate formatted broadcast message for a client type"""
    # Ensure we have the latest data
    try:
        if not campaigns_cache['last_updated'] or (datetime.now() - campaigns_cache['last_updated']).seconds > 300:
            fetch_all_campaigns()
        
        if not daily_analytics_cache['last_updated'] or (datetime.now() - daily_analytics_cache['last_updated']).seconds > 300:
            update_daily_analytics_cache()
            
        # Get today's date
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Get daily stats for today (or yesterday if today not available)
        daily_stats = daily_analytics_cache[client_type].get(today, daily_analytics_cache[client_type].get(yesterday, None))
        
        if not daily_stats:
            return f"No recent data available for {CLIENT_GROUPS[client_type]['name']} campaigns."
        
        # Calculate total metrics from campaigns
        total_sent = sum(campaign.get('emails_sent_count', 0) for campaign in campaigns_cache[client_type])
        total_opened = sum(campaign.get('open_count', 0) for campaign in campaigns_cache[client_type])
        total_clicks = sum(campaign.get('link_click_count', 0) for campaign in campaigns_cache[client_type])
        total_replies = sum(campaign.get('reply_count', 0) for campaign in campaigns_cache[client_type])
        
        # Calculate percentages (with safety checks to avoid division by zero)
        today_open_pct = (daily_stats['unique_opened'] / daily_stats['sent'] * 100) if daily_stats['sent'] > 0 else 0
        today_click_pct = (daily_stats['unique_clicks'] / daily_stats['sent'] * 100) if daily_stats['sent'] > 0 else 0
        today_reply_pct = (daily_stats['replies'] / daily_stats['sent'] * 100) if daily_stats['sent'] > 0 else 0
        
        total_open_pct = (total_opened / total_sent * 100) if total_sent > 0 else 0
        total_click_pct = (total_clicks / total_sent * 100) if total_sent > 0 else 0
        total_reply_pct = (total_replies / total_sent * 100) if total_sent > 0 else 0
        
        # Format the message
        message = (
            f"Hey everyone, this is AIIO reporting on daily metrics for {today}:\n\n"
            f"TODAY:\n\n"
            f"New contacts reached – {daily_stats['sent']}\n"
            f"New open/read – {daily_stats['unique_opened']} | {today_open_pct:.2f}%\n"
            f"New links opened – {daily_stats['unique_clicks']} | {today_click_pct:.2f}%\n"
            f"New responses – {daily_stats['replies']} | {today_reply_pct:.2f}%\n\n"
            f"TOTAL:\n\n"
            f"Total contacts reached – {total_sent}\n"
            f"Total open/read – {total_opened} | {total_open_pct:.2f}%\n"
            f"Total links opened – {total_clicks} | {total_click_pct:.2f}%\n"
            f"Total responses – {total_replies} | {total_reply_pct:.2f}%\n\n"
            f"Here is your [campaign analytics link]({CLIENT_GROUPS[client_type]['analytics_link']}) with full details."
        )
        
        return message
    except Exception as e:
        logger.error(f"Error generating broadcast message: {e}")
        return f"Error generating metrics for {CLIENT_GROUPS[client_type]['name']}. Please try again later."

async def send_broadcast(application, client_type):
    """Send broadcast to all groups for a specific client type"""
    try:
        message = await generate_broadcast_message(client_type)
        
        for chat_id in CLIENT_GROUPS[client_type]['chat_ids']:
            try:
                await application.bot.send_message(
                    chat_id=chat_id, 
                    text=message, 
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                logger.info(f"Broadcast sent to {client_type} group {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send broadcast to {client_type} group {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Error in send_broadcast for {client_type}: {e}")

async def start(update: Update, context: CallbackContext) -> None:
    """Send a message and prompt for login"""
    chat_id = update.effective_chat.id
    if chat_id in user_sessions:
        await show_main_menu(update, context)
        return
    
    keyboard = [
        [InlineKeyboardButton("Login", callback_data='login')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔒 Welcome to Campaign Pal Bot\n\n"
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
    """Show the main menu with stats summary based on user type"""
    chat_id = update.effective_chat.id
    username = user_sessions.get(chat_id)
    
    if not username:
        await start(update, context)
        return
    
    # Ensure we have latest data
    if not campaigns_cache['last_updated'] or (datetime.now() - campaigns_cache['last_updated']).seconds > 300:
        fetch_all_campaigns()
    
    if not daily_analytics_cache['last_updated'] or (datetime.now() - daily_analytics_cache['last_updated']).seconds > 300:
        update_daily_analytics_cache()
    
    # Determine client type
    client_type = 'triplea' if username == 'triplea@123' else 'go'
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Get daily stats for today (or yesterday if today not available)
    daily_stats = daily_analytics_cache[client_type].get(today, daily_analytics_cache[client_type].get(yesterday, None))
    
    # Create keyboard based on user type
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
    
    # Generate welcome message
    welcome_message = f"👋 Welcome <b>{username}</b>\n\n"
    
    # Generate stats summary if data is available
    stats_message = ""
    if daily_stats:
        # Calculate total metrics from campaigns
        total_sent = sum(campaign.get('emails_sent_count', 0) for campaign in campaigns_cache[client_type])
        total_opened = sum(campaign.get('open_count', 0) for campaign in campaigns_cache[client_type])
        total_clicks = sum(campaign.get('link_click_count', 0) for campaign in campaigns_cache[client_type])
        total_replies = sum(campaign.get('reply_count', 0) for campaign in campaigns_cache[client_type])
        
        # Calculate percentages
        today_open_pct = (daily_stats['unique_opened'] / daily_stats['sent'] * 100) if daily_stats['sent'] > 0 else 0
        today_click_pct = (daily_stats['unique_clicks'] / daily_stats['sent'] * 100) if daily_stats['sent'] > 0 else 0
        today_reply_pct = (daily_stats['replies'] / daily_stats['sent'] * 100) if daily_stats['sent'] > 0 else 0
        
        total_open_pct = (total_opened / total_sent * 100) if total_sent > 0 else 0
        total_click_pct = (total_clicks / total_sent * 100) if total_sent > 0 else 0
        total_reply_pct = (total_replies / total_sent * 100) if total_sent > 0 else 0
        
        # Build stats message
        stats_message = (
            f"<b>📊 Campaign Metrics for {today}:</b>\n\n"
            f"<b>TODAY:</b>\n"
            f"New contacts reached – {daily_stats['sent']}\n"
            f"New open/read – {daily_stats['unique_opened']} | {today_open_pct:.2f}%\n"
            f"New links opened – {daily_stats['unique_clicks']} | {today_click_pct:.2f}%\n"
            f"New responses – {daily_stats['replies']} | {today_reply_pct:.2f}%\n\n"
            f"<b>TOTAL:</b>\n"
            f"Total contacts reached – {total_sent}\n"
            f"Total open/read – {total_opened} | {total_open_pct:.2f}%\n"
            f"Total links opened – {total_clicks} | {total_click_pct:.2f}%\n"
            f"Total responses – {total_replies} | {total_reply_pct:.2f}%\n\n"
            f"<b>Select an option:</b>\n"
        )
    
    # Combine messages
    full_message = welcome_message + stats_message
    
    # Send or edit message based on update type
    if update.callback_query:
        await update.callback_query.edit_message_text(
            full_message,
            reply_markup=reply_markup,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    else:
        await update.message.reply_text(
            full_message,
            reply_markup=reply_markup,
            parse_mode='HTML',
            disable_web_page_preview=True
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

async def cmd_add_group(update: Update, context: CallbackContext) -> None:
    """Admin command to add the current group to broadcasts"""
    chat_id = update.effective_chat.id
    username = user_sessions.get(chat_id)
    
    if username not in VALID_USERS:
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return
    
    if len(context.args) > 0 and context.args[0].lower() in CLIENT_GROUPS:
        client_type = context.args[0].lower()
        current_chat_id = update.effective_message.chat_id
        
        # Get chat title for reference
        chat_title = update.effective_chat.title if update.effective_chat.title else f"Chat {current_chat_id}"
        
        if current_chat_id not in CLIENT_GROUPS[client_type]['chat_ids']:
            CLIENT_GROUPS[client_type]['chat_ids'].append(current_chat_id)
            save_group_config(CLIENT_GROUPS)
            
            await update.message.reply_text(
                f"✅ This group ({chat_title}) has been added to {client_type.upper()} broadcasts!\n"
                f"Broadcasts will be sent every 6 hours."
            )
        else:
            await update.message.reply_text(
                f"ℹ️ This group is already receiving {client_type.upper()} broadcasts."
            )
    else:
        await update.message.reply_text(
            "❌ Please specify a valid client type: go or triplea\n\n"
            "Example: /addgroup go"
        )

async def cmd_remove_group(update: Update, context: CallbackContext) -> None:
    """Admin command to remove the current group from broadcasts"""
    chat_id = update.effective_chat.id
    username = user_sessions.get(chat_id)
    
    if username not in VALID_USERS:
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return
    
    current_chat_id = update.effective_message.chat_id
    removed = False
    
    for client_type in CLIENT_GROUPS:
        if current_chat_id in CLIENT_GROUPS[client_type]['chat_ids']:
            CLIENT_GROUPS[client_type]['chat_ids'].remove(current_chat_id)
            removed = True
    
    if removed:
        save_group_config(CLIENT_GROUPS)
        await update.message.reply_text("✅ This group has been removed from all broadcasts.")
    else:
        await update.message.reply_text("ℹ️ This group is not registered for any broadcasts.")

# Broadcaster Task
class BroadcasterTask:
    def __init__(self, application):
        self.application = application
        self.last_broadcast_time = {
            'go': datetime.min,
            'triplea': datetime.min
        }
        self.running = False
        self.task = None
    
    async def start(self):
        """Start the broadcaster task"""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting scheduled broadcaster...")
        self.task = asyncio.create_task(self.run())
        
    async def run(self):
        """Run the broadcaster task loop"""
        while self.running:
            current_time = datetime.now()
            
            # Check each client type
            for client_type in CLIENT_GROUPS.keys():
                # Calculate hours since last broadcast
                hours_since_last = (current_time - self.last_broadcast_time[client_type]).total_seconds() / 3600
                
                # If it's been 6 hours or more since the last broadcast
                if hours_since_last >= 6:
                    logger.info(f"Sending scheduled broadcast for {client_type}")
                    await send_broadcast(self.application, client_type)
                    self.last_broadcast_time[client_type] = current_time
            
            # Wait for 5 minutes before checking again
            await asyncio.sleep(300)  # 5 minutes
    
    async def stop(self):
        """Stop the broadcaster task"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

def main():
    """Main function"""
    # Initial data load
    fetch_all_campaigns()
    update_daily_analytics_cache()
    
    # Set up and configure the application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers for commands and callbacks
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addgroup", cmd_add_group))
    application.add_handler(CommandHandler("removegroup", cmd_remove_group))
    
    application.add_handler(CallbackQueryHandler(login_prompt, pattern='^login'))
    application.add_handler(CallbackQueryHandler(logout, pattern='^logout'))
    application.add_handler(CallbackQueryHandler(refresh_data, pattern='^refresh_data'))
    application.add_handler(CallbackQueryHandler(show_go_campaigns, pattern='^go_campaigns'))
    application.add_handler(CallbackQueryHandler(show_triplea_campaigns, pattern='^triplea_campaigns'))
    application.add_handler(CallbackQueryHandler(show_daily_go, pattern='^daily_go'))
    application.add_handler(CallbackQueryHandler(show_daily_triplea, pattern='^daily_triplea'))
    application.add_handler(CallbackQueryHandler(back_to_menu, pattern='^back_to_menu'))
    
    # Add message handler (keep this last to avoid conflicts)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Create and start the broadcaster
    broadcaster = BroadcasterTask(application)
    
    # Define post_init to start the broadcaster after the application is initialized
    async def post_init(app: Application) -> None:
        await broadcaster.start()
    
    # Define post_shutdown to stop the broadcaster when the application is shutting down
    async def post_shutdown(app: Application) -> None:
        await broadcaster.stop()
    
    # Add the post init and shutdown callbacks
    application.post_init = post_init
    application.post_shutdown = post_shutdown
    
    # Start the bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()