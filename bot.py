# bot.py
import json
import os
import re
import time
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import schedule
import threading

from config import BOT_TOKEN, CHANNEL_ID, ADMIN_ID, CHECK_INTERVAL_HOURS
from decoder import extract_moviesmod_files
from pastes import create_paste, format_episode_list, format_batch_list

# ========== DATABASE FUNCTIONS ==========
DB_FILE = "database.json"

def load_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({"posts": [], "last_check": None}, f)
        return {"posts": [], "last_check": None}
    
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

def is_post_exists(url):
    db = load_db()
    for post in db["posts"]:
        if post["url"] == url:
            return True
    return False

def add_post(title, url, data):
    db = load_db()
    db["posts"].append({
        "title": title,
        "url": url,
        "data": data,
        "date": datetime.now().isoformat()
    })
    save_db(db)

def search_posts(query):
    db = load_db()
    query_lower = query.lower()
    results = []
    for post in db["posts"]:
        if query_lower in post["title"].lower():
            results.append(post)
    return results

# ========== TELEGRAM MESSAGE FORMATTER ==========
def format_movie_message(title, qualities):
    """
    qualities: {"480p": "url", "720p": "url"}
    """
    msg = f"🎬 {title}\n\n"
    for quality, url in qualities.items():
        msg += f"{quality}\n🔗 {url}\n\n"
    return msg

def format_single_season_message(title, season, qualities_data):
    """
    qualities_data: {
        "480p": {"single_paste": "url", "batch_paste": "url"},
        "720p": {"single_paste": "url", "batch_paste": "url"}
    }
    """
    msg = f"📺 {title}\n\n"
    
    for quality, data in qualities_data.items():
        msg += f"🎬 {quality}\n"
        if data.get("single_paste"):
            msg += f"[📌 Single Episodes]({data['single_paste']})"
        if data.get("batch_paste"):
            msg += f" {' ' * 10} [📦 Batch/Zip]({data['batch_paste']})\n\n"
        else:
            msg += "\n\n"
    
    return msg

def format_multi_season_message(title, seasons_data):
    """
    seasons_data: {
        "S01": {"480p": {...}, "720p": {...}},
        "S02": {...}
    }
    """
    msg = f"📺 {title}\n\n"
    
    for season, qualities in seasons_data.items():
        msg += f"━━━ {season} ━━━\n\n"
        for quality, data in qualities.items():
            msg += f"🎬 {quality}\n"
            if data.get("single_paste"):
                msg += f"[📌 Single]({data['single_paste']})"
            if data.get("batch_paste"):
                msg += f" {' ' * 10} [📦 Batch]({data['batch_paste']})\n\n"
            else:
                msg += "\n\n"
        msg += "\n"
    
    msg += "👇 Click any link to open"
    return msg

# ========== PROCESS AND CREATE PASTES ==========
async def process_page(url, title_hint=None):
    """
    Process a MoviesMod page and create pastes
    Returns formatted message and data
    """
    print(f"Processing: {url}")
    
    # Tumhara decoder call karo
    data = extract_moviesmod_files(url)
    
    if not data:
        return None, None
    
    page_title = data.get("title", title_hint or "Unknown")
    page_type = data.get("type", "movie")
    
    if page_type == "movie":
        # Movie: direct links, no paste
        qualities = {}
        for quality, links in data.get("qualities", {}).items():
            if links:
                qualities[quality] = links[0] if isinstance(links, list) else links
        
        if qualities:
            msg = format_movie_message(page_title, qualities)
            return msg, data
    
    elif page_type == "single_season":
        # Single season: create pastes for each quality
        season = data.get("season", "S01")
        qualities_data = {}
        
        for quality, q_data in data.get("qualities", {}).items():
            quality_data = {}
            
            # Single episodes paste
            if q_data.get("single") and len(q_data["single"]) > 0:
                single_content = format_episode_list(q_data["single"], f"{page_title} - {quality}")
                single_title = f"{page_title}_{quality}_single".replace(" ", "_").replace(".", "")
                single_url = create_paste(single_title, single_content)
                if single_url:
                    quality_data["single_paste"] = single_url
            
            # Batch paste
            if q_data.get("batch"):
                batch_content = format_batch_list(q_data["batch"]["name"], q_data["batch"]["url"])
                batch_title = f"{page_title}_{quality}_batch".replace(" ", "_").replace(".", "")
                batch_url = create_paste(batch_title, batch_content)
                if batch_url:
                    quality_data["batch_paste"] = batch_url
            
            if quality_data:
                qualities_data[quality] = quality_data
        
        if qualities_data:
            msg = format_single_season_message(page_title, season, qualities_data)
            return msg, data
    
    elif page_type == "multi_season":
        # Multi season: create pastes for each season + quality
        seasons_data = {}
        
        for season, qualities in data.get("seasons", {}).items():
            seasons_data[season] = {}
            
            for quality, q_data in qualities.items():
                quality_data = {}
                
                if q_data.get("single") and len(q_data["single"]) > 0:
                    single_content = format_episode_list(q_data["single"], f"{page_title} {season} - {quality}")
                    single_title = f"{page_title}_{season}_{quality}_single".replace(" ", "_")
                    single_url = create_paste(single_title, single_content)
                    if single_url:
                        quality_data["single_paste"] = single_url
                
                if q_data.get("batch"):
                    batch_content = format_batch_list(q_data["batch"]["name"], q_data["batch"]["url"])
                    batch_title = f"{page_title}_{season}_{quality}_batch".replace(" ", "_")
                    batch_url = create_paste(batch_title, batch_content)
                    if batch_url:
                        quality_data["batch_paste"] = batch_url
                
                if quality_data:
                    seasons_data[season][quality] = quality_data
        
        if seasons_data:
            msg = format_multi_season_message(page_title, seasons_data)
            return msg, data
    
    return None, None

# ========== AUTO DETECT NEW POSTS ==========
def check_for_new_posts():
    """
    Check MoviesMod for new posts (sitemap or homepage)
    """
    print(f"[{datetime.now()}] Checking for new posts...")
    
    try:
        # Try sitemap first
        sitemap_url = "https://moviesmod.money/sitemap.xml"
        response = requests.get(sitemap_url, timeout=15)
        
        if response.status_code == 200:
            # Parse sitemap for latest URLs
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            urls = []
            for loc in root.findall('.//ns:loc', namespaces):
                url = loc.text
                if '/download-' in url or '/movie-' in url:
                    urls.append(url)
            
            # Check first 5 latest URLs (usually sorted by date)
            new_posts = []
            for url in urls[:10]:
                if not is_post_exists(url):
                    new_posts.append(url)
            
            if new_posts:
                print(f"Found {len(new_posts)} new posts!")
                
                # Process each new post and send to channel
                asyncio.run(send_new_posts_to_channel(new_posts))
                
                # Update last check
                db = load_db()
                db["last_check"] = datetime.now().isoformat()
                save_db(db)
            
            return
    
    except Exception as e:
        print(f"Sitemap check failed: {e}")
    
    # Fallback: Check homepage for new links
    try:
        response = requests.get("https://moviesmod.money/", timeout=15)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find article links (adjust selector as per MoviesMod structure)
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/download-' in href or '/movie-' in href:
                if href.startswith('/'):
                    href = f"https://moviesmod.money{href}"
                if not is_post_exists(href):
                    links.append(href)
        
        # Take first 5 new links
        new_posts = links[:5]
        
        if new_posts:
            print(f"Found {len(new_posts)} new posts!")
            asyncio.run(send_new_posts_to_channel(new_posts))
            
            db = load_db()
            db["last_check"] = datetime.now().isoformat()
            save_db(db)
    
    except Exception as e:
        print(f"Homepage check failed: {e}")

async def send_new_posts_to_channel(urls):
    """
    Process new posts and send to Telegram channel
    """
    for url in urls:
        try:
            msg, data = await process_page(url)
            if msg and data:
                # Send to channel
                app = Application.builder().token(BOT_TOKEN).build()
                await app.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=f"📺 **NEW UPLOAD**\n\n{msg}",
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                
                # Add to database
                title = data.get("title", url.split("/")[-2])
                add_post(title, url, data)
                
                print(f"Posted to channel: {title}")
            
            time.sleep(2)  # Delay between posts
            
        except Exception as e:
            print(f"Failed to process {url}: {e}")

def start_scheduler():
    """
    Start background scheduler for auto checking
    """
    schedule.every(CHECK_INTERVAL_HOURS).hours.do(check_for_new_posts)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# ========== TELEGRAM BOT COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *MoviesMod Download Bot*\n\n"
        "Commands:\n"
        "/search <title> - Search for a show/movie\n"
        "/add <url> - Add new URL (Admin only)\n"
        "/latest - Show latest 5 posts\n"
        "/help - Show help\n\n"
        "Or simply send me a MoviesMod URL!",
        parse_mode="Markdown"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /search <show name>")
        return
    
    query = " ".join(context.args)
    results = search_posts(query)
    
    if not results:
        await update.message.reply_text(f"No results found for '{query}'")
        return
    
    msg = f"🔍 Results for '{query}':\n\n"
    for i, post in enumerate(results[:10], 1):
        msg += f"{i}. {post['title']}\n{post['url']}\n\n"
    
    await update.message.reply_text(msg, disable_web_page_preview=True)

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    posts = db["posts"][-5:][::-1]  # Last 5, newest first
    
    if not posts:
        await update.message.reply_text("No posts in database yet.")
        return
    
    msg = "📺 *Latest 5 Posts*\n\n"
    for post in posts:
        msg += f"• {post['title']}\n{post['url']}\n\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

async def add_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin only
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /add <moviesmod_url>")
        return
    
    url = context.args[0]
    
    if is_post_exists(url):
        await update.message.reply_text("URL already exists in database.")
        return
    
    msg = await update.message.reply_text("Processing URL... Please wait ⏳")
    
    try:
        result_msg, data = await process_page(url)
        
        if result_msg and data:
            title = data.get("title", url.split("/")[-2])
            add_post(title, url, data)
            await msg.edit_text(f"✅ Added successfully!\n\n{result_msg[:500]}")
        else:
            await msg.edit_text("❌ Failed to process URL.")
    
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)[:100]}")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if 'moviesmod.money' not in url:
        await update.message.reply_text("❌ Please send a valid MoviesMod URL")
        return
    
    msg = await update.message.reply_text("🔄 Processing... Please wait ⏳")
    
    try:
        # Check if already in database
        if is_post_exists(url):
            db = load_db()
            for post in db["posts"]:
                if post["url"] == url:
                    # Reuse existing data
                    # Need to reformat message from stored data
                    await msg.edit_text("✅ Found in database!\n\nUse /latest to see all posts.")
                    return
        
        # Process new URL
        result_msg, data = await process_page(url)
        
        if result_msg and data:
            title = data.get("title", url.split("/")[-2])
            add_post(title, url, data)
            await msg.edit_text(result_msg, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await msg.edit_text("❌ No download links found on this page.")
    
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)[:100]}\n\nTry again later.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How to use:*\n\n"
        "*Commands:*\n"
        "/start - Start bot\n"
        "/search <title> - Search for show/movie\n"
        "/latest - Show latest posts\n"
        "/add <url> - Add URL (Admin)\n\n"
        "*Direct URL:*\n"
        "Send any MoviesMod URL directly\n\n"
        "*Auto Post:*\n"
        f"Bot checks every {CHECK_INTERVAL_HOURS} hours for new posts\n"
        f"New posts auto-posted to {CHANNEL_ID}",
        parse_mode="Markdown"
    )

# ========== MAIN ==========
async def main():
    # Create bot application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("latest", latest))
    app.add_handler(CommandHandler("add", add_url))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    
    print(f"🤖 Bot is running...")
    print(f"   Auto check every {CHECK_INTERVAL_HOURS} hours")
    print(f"   Channel: {CHANNEL_ID}")
    
    # Start polling
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
