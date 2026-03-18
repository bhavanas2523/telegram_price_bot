import os
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

headers = {"User-Agent": "Mozilla/5.0"}

# Store user data
user_data = {}

# ---------------- LIVE SCRAPER ----------------
def get_live_price(product):
    try:
        url = f"https://www.flipkart.com/search?q={product}"
        r = requests.get(url, headers=headers, timeout=10)

        soup = BeautifulSoup(r.text, "html.parser")
        price = soup.find("div", {"class": "_30jeq3"})

        if price:
            return int("".join(filter(str.isdigit, price.text)))
    except:
        return None

    return None


# ---------------- FALLBACK ----------------
def get_fallback(product):
    demo_data = {
        "iphone": 50000,
        "shoes": 2000,
        "laptop": 60000,
        "shirt": 1500,
    }

    for key in demo_data:
        if key in product.lower():
            return demo_data[key]

    return 3000


# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send product and target price\nExample: iphone 45000"
    )


# ---------------- TRACK ----------------
async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.split()

    if len(text) < 2:
        await update.message.reply_text(
            "❗ Format: product target_price\nExample: iphone 45000"
        )
        return

    product = text[0]
    target_price = int(text[1])
    chat_id = update.message.chat_id

    product_query = product.replace(" ", "+")

    live_price = get_live_price(product_query)

    if live_price:
        price = live_price
        source = "Live"
    else:
        price = get_fallback(product)
        source = "Fallback"

    # Save data
    user_data[chat_id] = {
        "product": product_query,
        "target": target_price,
        "last_price": price,
    }

    # Buy Now button (safe link)
    link = f"https://www.flipkart.com/search?q={product_query}"

    button = [[InlineKeyboardButton("🛒 Buy Now", url=link)]]
    reply_markup = InlineKeyboardMarkup(button)

    await update.message.reply_text(
        f"📊 Tracking Started\nProduct: {product}\nCurrent Price: ₹{price}\nTarget: ₹{target_price}\nSource: {source}",
        reply_markup=reply_markup,
    )


# ---------------- CHECK PRICE ----------------
async def check_price(context: ContextTypes.DEFAULT_TYPE):
    for chat_id, data in user_data.items():
        product = data["product"]
        old_price = data["last_price"]
        target_price = data["target"]

        new_price = get_live_price(product)

        # If scraping fails → use last known
        if not new_price:
            new_price = old_price

        # 🔔 Target reached
        if new_price <= target_price:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🎯 Target Reached!\nPrice: ₹{new_price}",
            )

        # 🔔 Price dropped
        elif new_price < old_price:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📉 Price Dropped!\nOld: ₹{old_price}\nNew: ₹{new_price}",
            )

        # Update last price
        user_data[chat_id]["last_price"] = new_price


# ---------------- STOP ----------------
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    if chat_id in user_data:
        del user_data[chat_id]
        await update.message.reply_text("❌ Tracking stopped")
    else:
        await update.message.reply_text("No active tracking")


# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track))

    app.job_queue.run_repeating(check_price, interval=60, first=10)

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()