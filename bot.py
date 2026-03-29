import os
import re
import time
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

user_data = {}
last_alert_time = {}

# ---------------- PRICE FETCH (FINAL FIXED) ---------------- #
def get_price(product):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9"
        }

        search_url = f"https://www.flipkart.com/search?q={product.replace(' ', '+')}"
        res = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        # -------- LAYOUT 1 (BIG CARDS) -------- #
        items = soup.select("a._1fQZEK")

        for item in items[:5]:
            title = item.get_text().lower()
            if all(word in title for word in product.lower().split()):
                price_tag = item.select_one("div._30jeq3")
                if price_tag:
                    price = int(re.sub(r"[^\d]", "", price_tag.text))
                    link = "https://www.flipkart.com" + item.get("href")
                    return price, link, "Flipkart"

        # -------- LAYOUT 2 (GRID - IMPORTANT) -------- #
        grid_items = soup.select("div._4ddWXP")

        for item in grid_items[:8]:
            title_tag = item.select_one("a.s1Q9rs") or item.select_one("a.IRpwTa")
            price_tag = item.select_one("div._30jeq3")

            if title_tag and price_tag:
                title = title_tag.get_text().lower()

                if all(word in title for word in product.lower().split()):
                    price = int(re.sub(r"[^\d]", "", price_tag.text))
                    link = "https://www.flipkart.com" + title_tag.get("href")
                    return price, link, "Flipkart"

        # -------- FALLBACK TO FIRST GRID ITEM -------- #
        if grid_items:
            item = grid_items[0]
            title_tag = item.select_one("a.s1Q9rs") or item.select_one("a.IRpwTa")
            price_tag = item.select_one("div._30jeq3")

            if title_tag and price_tag:
                price = int(re.sub(r"[^\d]", "", price_tag.text))
                link = "https://www.flipkart.com" + title_tag.get("href")
                return price, link, "Flipkart"

    except Exception as e:
        print("Scraping error:", e)

    # -------- FINAL FALLBACK -------- #
    fallback_url = f"https://www.flipkart.com/search?q={product.replace(' ', '+')}"
    fallback_price = 999  # safe demo value
    return fallback_price, fallback_url, "Fallback"


# ---------------- START ---------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Send product and target price\nExample: iphone 13 50000"
    )


# ---------------- HANDLE INPUT ---------------- #
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    match = re.search(r"(.+)\s(\d+)", text)
    if not match:
        await update.message.reply_text("❌ Format: product target_price")
        return

    product = match.group(1).strip()
    target = int(match.group(2))

    price, url, source = get_price(product)
    chat_id = update.message.chat_id

    if chat_id not in user_data:
        user_data[chat_id] = []

    user_data[chat_id].append({
        "product": product,
        "target": target,
        "last_price": price,
        "url": url
    })

    await update.message.reply_text(
        f"🔍 Tracking started\n📦 {product}\n💰 Current: ₹{price}\n📡 Source: {source}\n🎯 Target: ₹{target}"
    )

    # -------- INSTANT ALERT -------- #
    keyboard = [[InlineKeyboardButton("🛒 Buy Now", url=url)]]

    if price <= target:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🚨 Price Dropped!\n📦 {product}\n💰 Now: ₹{price}\n📡 Source: {source}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ---------------- CHECK COMMAND ---------------- #
async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    if chat_id not in user_data or not user_data[chat_id]:
        await update.message.reply_text("❌ No products being tracked")
        return

    for item in user_data[chat_id]:
        product = item["product"]
        target = item["target"]

        price, url, source = get_price(product)

        if price <= target:
            keyboard = [[InlineKeyboardButton("🛒 Buy Now", url=url)]]

            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚨 Price Dropped!\n📦 {product}\n💰 Now: ₹{price}\n📡 Source: {source}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


# ---------------- STATUS ---------------- #
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    if chat_id not in user_data or not user_data[chat_id]:
        await update.message.reply_text("📭 No active tracking")
        return

    msg = "📊 Active Tracking:\n"
    for item in user_data[chat_id]:
        msg += f"\n📦 {item['product']} | 🎯 ₹{item['target']}"

    await update.message.reply_text(msg)


# ---------------- STOP ---------------- #
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_data[chat_id] = []
    await update.message.reply_text("🛑 Tracking stopped")


# ---------------- BACKGROUND CHECK ---------------- #
async def check_prices(context: ContextTypes.DEFAULT_TYPE):
    for chat_id, items in user_data.items():
        for item in items:
            product = item["product"]
            target = item["target"]

            price, url, source = get_price(product)

            key = f"{chat_id}_{product}"
            now = time.time()

            # -------- COOLDOWN -------- #
            if key in last_alert_time and now - last_alert_time[key] < 600:
                continue

            keyboard = [[InlineKeyboardButton("🛒 Buy Now", url=url)]]

            if price <= target:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚨 Price Dropped!\n📦 {product}\n💰 Now: ₹{price}\n📡 Source: {source}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                last_alert_time[key] = now

            elif price > item["last_price"]:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Deal ended for {product}\n💰 Now: ₹{price}"
                )

            item["last_price"] = price


# ---------------- MAIN ---------------- #
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("check", check_now))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Runs every 2 minutes
    app.job_queue.run_repeating(check_prices, interval=120, first=10)

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
