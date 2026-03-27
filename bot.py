import os
import time
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

tracked_products = []

# 🔹 SCRAPER (Flipkart search)
def get_price(product):
    url = f"https://www.flipkart.com/search?q={product}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")

        price = soup.select_one("div._30jeq3")
        link = soup.select_one("a._1fQZEK")

        if price and link:
            price_value = int(price.text.replace("₹", "").replace(",", ""))
            product_url = "https://www.flipkart.com" + link.get("href")
            return price_value, product_url
    except:
        pass

    return None, None


# 🔹 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send product and target price\nExample:\nlenovo laptop 60000"
    )


# 🔹 HANDLE INPUT
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global tracked_products

    user_input = update.message.text.strip().lower()
    parts = user_input.split()

    if len(parts) < 2 or not parts[-1].isdigit():
        await update.message.reply_text(
            "❌ Format:\nproduct_name target_price\nExample: laptop 50000"
        )
        return

    target_price = int(parts[-1])
    product = " ".join(parts[:-1])

    price, url = get_price(product)

    if not price:
        await update.message.reply_text("⚠️ Could not fetch price. Try again.")
        return

    tracked_products.append({
        "product": product,
        "target": target_price,
        "url": url,
        "last_alert": 0,
        "alert_count": 0,
        "deal_active": False,
        "user_id": update.message.chat_id
    })

    await update.message.reply_text(
        f"🔍 Tracking started\n📦 {product}\n🎯 Target: ₹{target_price}"
    )


# 🔹 BACKGROUND CHECK
async def check_price(context: ContextTypes.DEFAULT_TYPE):
    global tracked_products

    for item in tracked_products:
        price, _ = get_price(item["product"])

        if not price:
            continue

        current_time = time.time()

        # 🚨 PRICE DROPPED
        if price <= item["target"]:
            if item["alert_count"] < 3:
                if current_time - item["last_alert"] > 3600:

                    keyboard = [[InlineKeyboardButton("🛒 Buy Now", url=item["url"])]]

                    await context.bot.send_message(
                        chat_id=item["user_id"],
                        text=f"🚨 Price Dropped!\n📦 {item['product']}\n💰 Now: ₹{price}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

                    item["last_alert"] = current_time
                    item["alert_count"] += 1
                    item["deal_active"] = True

        # ⚠️ DEAL ENDED
        elif item["deal_active"]:
            await context.bot.send_message(
                chat_id=item["user_id"],
                text=f"⚠️ Deal Ended!\n📦 {item['product']}\nPrice increased above target."
            )
            item["deal_active"] = False


# 🔹 STOP COMMAND
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global tracked_products
    tracked_products = []
    await update.message.reply_text("🛑 All tracking stopped!")


# 🔹 STATUS COMMAND
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not tracked_products:
        await update.message.reply_text("📭 No active tracking.")
        return

    message = "📊 Active Tracking:\n\n"

    for item in tracked_products:
        message += f"📦 {item['product']}\n🎯 Target: ₹{item['target']}\n\n"

    await update.message.reply_text(message)


# 🔹 MAIN
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ⏱️ Check every 2 minutes
    app.job_queue.run_repeating(check_price, interval=120, first=10)

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
