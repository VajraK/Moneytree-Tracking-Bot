import os
import time
import requests
import re
import logging
from web3 import Web3
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from retry import retry
import threading

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
TRADING_BOT_URL = 'http://localhost:5000/transaction'

SEND_TELEGRAM_MESSAGES = True  # Set to True to enable sending Telegram messages
ALLOW_SWAP_MESSAGES_ONLY = True # Set to True to enable swap messages only
ALLOW_AGGREGATED_MESSAGES_ALSO = True # Set to True to enable aggregated messages also
ALLOW_MONEYTREE_TRADING_BOT_INTERACTION = True # Set to True to enable interactions with the Moneytree Trading Bot

# Bypassing proxies in local environment
proxies = {
    "http": None,
    "https": None,
}

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
        'parse_mode': 'MarkdownV2',
        'disable_web_page_preview': True
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
    clean_text = clean_text.replace('(', '〈').replace(')', '〉')
    
    # Remove unwanted strings
    unwanted_strings = ['Click to show more', 'Click to show less']
    for unwanted in unwanted_strings:
        clean_text = clean_text.replace(unwanted, '')

    print(f"Extracted token text: {clean_text}")
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

def escape_markdown(text):
    """
    Escapes Markdown special characters in the given text.
    """
    escape_chars = r'\_*~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

@retry(tries=5, delay=2, backoff=2, jitter=(1, 3))
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
        with open("etherscan_page.html", "w", encoding="utf-8") as file:
            file.write(response.text)
        
        lines = response.text.split('\n')
        for i, line in enumerate(lines):
            if 'Transaction Action: ' in line:
                logging.info(f"Found 'Transaction Action: ' line: {line.strip()}")
                
                # Check if the line contains other non-HTML text
                clean_line = clean_html(line.strip().replace('Transaction Action: ', '').strip())
                if clean_line:
                    action_line = line.strip().replace('Transaction Action: ', '').strip()
                elif clean_html(lines[i + 1].strip()):
                    # Use the following line if it contains non-HTML text
                    action_line = lines[i + 1].strip()
                else:
                    # Look for the next occurrence of 'Sponsored:'
                    sponsored_index = next((j for j in range(i, len(lines)) if 'Sponsored:' in lines[j]), None)
                    if sponsored_index:
                        action_line = '\n'.join(lines[i+1:sponsored_index]).strip()
                    else:
                        action_line = "No ACTION info available"
                
                # Clean the action line
                cleaned_action = clean_html(action_line)
                
                # Extract token link and text
                token_link, token_text = extract_token_link(action_line)
                if token_link and token_text:
                    cleaned_action = cleaned_action.replace(token_text, f"[{token_text}]({token_link})")
                
                # Escape markdown special characters
                cleaned_action = escape_markdown(cleaned_action)
                
                return cleaned_action
        
        logging.info("Could not find 'Transaction Action:' section in the HTML.")
    else:
        logging.error(f"Failed to fetch the Etherscan page. Status code: {response.status_code}")
        response.raise_for_status()  # Raise an HTTPError if the status code is 4xx, 5xx
    return "No ACTION info available"

@retry(tries=5, delay=2, backoff=2, jitter=(1, 3))
def get_block_number():
    """
    Retrieves the latest block number from the Ethereum blockchain.
    """
    return web3.eth.block_number

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

    from_name_link = f"[{from_name}](https://etherscan.io/address/{from_address})"
    to_name_link = f"[{to_name}](https://etherscan.io/address/{to_address})"
    tx_hash_link = f"[{tx_hash}](https://etherscan.io/tx/{tx_hash})"

    if from_address in ADDRESSES_TO_MONITOR:
        time.sleep(5)
        action_text = get_transaction_action(tx_hash)
        
        if ALLOW_SWAP_MESSAGES_ONLY and not (action_text.startswith("Swap") or (ALLOW_AGGREGATED_MESSAGES_ALSO and action_text.startswith("Aggregated"))):
            return  # Skip non-swap and non-aggregated transactions if only swaps are allowed

        transaction_details = {
            'from_name': from_name,
            'tx_hash': tx_hash,
            'action_text': action_text,
        }
        if ALLOW_MONEYTREE_TRADING_BOT_INTERACTION:
            threading.Thread(target=notify_trading_bot, args=(transaction_details,)).start()

        token_action = ''
        if 'ETH For' in action_text:
            token_action += '⭐ *Token BUY* 💵\n\n'
        if 'ETH On' in action_text:
            token_action += '⭐ *Token SELL* 💵\n\n'

        message = (
            f'{token_action}'
            f'*Wallet:*\n{from_name_link}\n\n'
            f'*Transaction Hash:*\n{tx_hash_link}\n\n'
            f'*Action:*\n{action_text}'
        )
        send_telegram_message(message)

    if to_address in ADDRESSES_TO_MONITOR:
        time.sleep(5)
        if ALLOW_SWAP_MESSAGES_ONLY:
            return  # Skip incoming messages if only swaps are allowed
        message = (
            f'⭐ *{to_name_link}: INCOMING* 💵\n\n'
            f'*From:*\n{from_address}\n\n'
            f'*To:*\n{to_address}\n\n'
            f'*Transaction Hash:*\n{tx_hash_link}'
        )
        send_telegram_message(message)

def notify_trading_bot(transaction_details):
    """
    Sends the transaction details to the trading bot via HTTP POST request.
    """
    try:
        response = requests.post(TRADING_BOT_URL, json=transaction_details, proxies=proxies)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
        logging.info(f"Trading bot response: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending transaction details to trading bot: {e}")

def log_loop(poll_interval):
    """
    Main loop that polls for new blocks and handles transactions in those blocks.
    """
    latest_block = get_block_number()
    logging.info(f"Starting to monitor from block {latest_block}")
    while True:
        logging.info("Checking for new events...")
        current_block = get_block_number()
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
