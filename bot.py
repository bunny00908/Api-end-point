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

# Monitoring targets
CARD_CHECK_BOT_ID = 5366864997  # The bot that checks cards
SOURCE_GROUPS = [-4759483285]  # Your source group ID(s)
TARGET_CHANNELS = ["@hybuabu"]  # Your channel(s)

# Track processed messages
processed_ids = set()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ======================

app = Client("card_tracker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def get_bin_data(bin_code):
    """Enhanced BIN lookup with better error handling"""
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
                logging.warning(f"BIN API responded with status {resp.status}")
    except Exception as e:
        logging.error(f"BIN lookup failed: {str(e)}")
    return [bin_code, "Unknown", "Unknown", "Unknown", "Unknown"]

def parse_message(text):
    """Parse card check results from both bots and groups"""
    try:
        # Extract CC information (multiple formats)
        cc_match = re.search(
            r'(?:Card|CC):?\s*(\d{13,19})[| ](\d{1,2})[| ](\d{2,4})[| ](\d{3,4})', 
            text
        )
        if not cc_match:
            return None
        
        # Extract status and response (multiple formats)
        status = "N/A"
        response = "N/A"
        
        status_match = re.search(r'Status:\s*(.+?)(?:\s|$)', text, re.IGNORECASE)
        if status_match:
            status = status_match.group(1).strip()
            
        response_match = re.search(r'Response:\s*(.+?)(?:\s|$)', text, re.IGNORECASE)
        if response_match:
            response = response_match.group(1).strip()
        
        # Extract other details (if available)
        bank = re.search(r'Bank:\s*(.+?)(?:\s|$)', text, re.IGNORECASE)
        country = re.search(r'Country:\s*(.+?)(?:\s|$)', text, re.IGNORECASE)
        level = re.search(r'Level:\s*(.+?)(?:\s|$)', text, re.IGNORECASE)
        took = re.search(r'Took:\s*([\d.]+)', text, re.IGNORECASE)
        
        return {
            "cc": cc_match.group(1),
            "month": cc_match.group(2),
            "year": cc_match.group(3),
            "cvv": cc_match.group(4),
            "status": status,
            "response": response,
            "bank": bank.group(1) if bank else "Unknown",
            "country": country.group(1) if country else "Unknown",
            "level": level.group(1) if level else "Unknown",
            "took": f"{took.group(1)}s" if took else "N/A"
        }
    except Exception as e:
        logging.error(f"Error parsing message: {str(e)}")
        return None

def should_forward(response):
    """Determine if we should forward this card"""
    response = (response or "").upper()
    return any(keyword in response for keyword in ["CHARGED", "APPROVED", "SUCCESS", "LIVE"])

async def send_to_channels(formatted_text):
    """Handle sending to all channels with error handling"""
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
            logging.info(f"Successfully sent to {channel}")
            return True
        except Exception as e:
            logging.error(f"Failed to send to {channel}: {str(e)}")
    return False

@app.on_message(
    (filters.user(CARD_CHECK_BOT_ID) | filters.chat(SOURCE_GROUPS)) & 
    ~filters.edited
)
async def handle_card_messages(client, message: Message):
    try:
        # Skip if we've already processed this message
        if message.id in processed_ids:
            return
        
        text = message.text or message.caption or ""
        logging.info(f"Processing message from {message.chat.id}: {text[:100]}...")
        
        # Skip "wait" or "checking" messages
        if any(x in text.lower() for x in ["wait", "checking", "processing"]):
            logging.debug("Skipping processing message")
            return
        
        # Parse the message
        card_data = parse_message(text)
        if not card_data:
            logging.debug("Message doesn't contain valid card info")
            return
        
        # Check if we should forward this card
        if not should_forward(card_data["response"]):
            logging.debug(f"Skipping card with response: {card_data['response']}")
            return
        
        # Get BIN info
        bin_info = await get_bin_data(card_data["cc"][:6])
        
        # Format the message
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
        
        # Send to channels
        if await send_to_channels(formatted_text):
            processed_ids.add(message.id)
            logging.info("Card successfully processed and forwarded")
        else:
            logging.error("Failed to send to all channels")
            
    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")

# === START BOT ===
logging.info("Starting Card Tracker Bot...")
print("✅ Bot is now running and monitoring:")
print(f"- Card Check Bot ID: {CARD_CHECK_BOT_ID}")
print(f"- Source Groups: {SOURCE_GROUPS}")
print(f"- Target Channels: {TARGET_CHANNELS}")
app.run()
