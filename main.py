import os
import time
import requests
import re
import logging
from web3 import Web3
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Configuration
INFURA_PROJECT_ID = os.getenv('INFURA_PROJECT_ID')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
ADDRESSES_TO_MONITOR = os.getenv('ADDRESSES_TO_MONITOR')
ADDRESS_NAMES = os.getenv('ADDRESS_NAMES')
SEND_TELEGRAM_MESSAGES = True  # Set to False to temporarily disable sending Telegram messages

# Ensure required environment variables are set
if ADDRESSES_TO_MONITOR is None or ADDRESS_NAMES is None:
    logging.error("ADDRESSES_TO_MONITOR or ADDRESS_NAMES environment variable is not set")
    exit()

# Convert the addresses and names to lists
ADDRESSES_TO_MONITOR = [addr.strip().lower() for addr in ADDRESSES_TO_MONITOR.split(',')]
ADDRESS_NAMES = [name.strip() for name in ADDRESS_NAMES.split(',')]

# Create a dictionary mapping addresses to names
ADDRESS_MAP = dict(zip(ADDRESSES_TO_MONITOR, ADDRESS_NAMES))

# Initialize web3 with Infura
web3 = Web3(Web3.HTTPProvider(f'https://mainnet.infura.io/v3/{INFURA_PROJECT_ID}'))

if not web3.is_connected():
    logging.error("Failed to connect to Infura")
    exit()

logging.info(f"Connected to Infura. Monitoring transactions for addresses: {ADDRESS_MAP}")

def send_telegram_message(message):
    """
    Sends a message to the configured Telegram chat.
    """
    if not SEND_TELEGRAM_MESSAGES:
        logging.info("Sending Telegram messages is disabled.")
        logging.info(f"Message that would be sent: {message}")
        return
    
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'MarkdownV2'
    }
    response = requests.post(url, data=data)
    logging.info(f"Telegram response: {response.json()}")
    return response.json()

def clean_html(raw_html):
    """
    Removes HTML tags and extra spaces from a raw HTML string.
    """
    clean_text = re.sub('<.*?>', ' ', raw_html)
    clean_text = re.sub('\s+', ' ', clean_text).strip()
    return clean_text

def extract_token_link(action_line):
    """
    Extracts the token link and its text from the action line if present.
    """
    token_link = None
    token_text = None
    if '/token/' in action_line:
        match = re.search(r'/token/0x[0-9a-fA-F]{40}', action_line)
        if match:
            token_link = f"https://etherscan.io{match.group()}"
            start_idx = action_line.find('>', match.end()) + 1
            end_idx = action_line.find('</a>', start_idx)
            token_text = action_line[start_idx:end_idx].strip()
    return token_link, token_text

def get_transaction_action(tx_hash):
    """
    Fetches the transaction action from Etherscan and returns a cleaned version of it.
    """
    etherscan_url = f'https://etherscan.io/tx/{tx_hash}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    
    response = requests.get(etherscan_url, headers=headers)
    if response.status_code == 200:
        logging.info("Successfully fetched the Etherscan page.")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Read the HTML content and search for 'Transaction Action:'
        for line in response.text.split('\n'):
            if 'Transaction Action:' in line:
                logging.info(f"Found 'Transaction Action:' line: {line.strip()}")
                action_line = line.strip().replace('Transaction Action:', '').strip()
                cleaned_action = clean_html(action_line)
                
                # Extract token link and text
                token_link, token_text = extract_token_link(action_line)
                if token_link and token_text:
                    cleaned_action = cleaned_action.replace(token_text, f"[{token_text}]({token_link})")
                
                return cleaned_action
        
        logging.info("Could not find 'Transaction Action:' section in the HTML.")
    else:
        logging.error(f"Failed to fetch the Etherscan page. Status code: {response.status_code}")
    return "No ACTION info available"

def handle_event(tx):
    """
    Handles an event and sends a Telegram message if the transaction involves a monitored address.
    """
    from_address = tx['from'].lower()
    to_address = tx['to'].lower() if tx['to'] else None
    value = web3.from_wei(tx['value'], 'ether')
    tx_hash = tx['hash'].hex()

    from_name = ADDRESS_MAP.get(from_address, from_address)
    to_name = ADDRESS_MAP.get(to_address, to_address)

    if from_address in ADDRESSES_TO_MONITOR:
        action_text = get_transaction_action(tx_hash)
        message = (
            f'⭐ *{from_name}: OUTGOING* 💵\n\n'
            f'*Transaction Hash:* {tx_hash}\n\n'
            f'*Action:* {action_text}'
        )
        send_telegram_message(message)

    if to_address in ADDRESSES_TO_MONITOR:
        message = (
            f'⭐ *{to_name}: INCOMING* 💵\n'
            f'*Value:* {value} ETH\n'
            f'*From:* {from_address}\n'
            f'*To:* {to_address}\n'
            f'*Transaction Hash:* {tx_hash}\n'
        )
        send_telegram_message(message)

def log_loop(poll_interval):
    """
    Main loop that polls for new blocks and handles transactions in those blocks.
    """
    latest_block = web3.eth.block_number
    logging.info(f"Starting to monitor from block {latest_block}")
    while True:
        logging.info("Checking for new events...")
        current_block = web3.eth.block_number
        if current_block > latest_block:
            for block_num in range(latest_block + 1, current_block + 1):
                block = web3.eth.get_block(block_num, full_transactions=True)
                for tx in block.transactions:
                    handle_event(tx)
            latest_block = current_block
        time.sleep(poll_interval)

def test_transaction(tx_hash):
    """
    Tests a specific transaction by hash.
    """
    try:
        tx = web3.eth.get_transaction(tx_hash)
        handle_event(tx)
    except Exception as e:
        logging.error(f"Error fetching transaction: {e}")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Wallet Tracing Bot")
    parser.add_argument('--test-tx', type=str, help='Test a specific transaction hash')
    args = parser.parse_args()

    if args.test_tx:
        test_transaction(args.test_tx)
    else:
        log_loop(10)
