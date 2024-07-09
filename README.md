# Moneytree Tracking Bot

The Moneytree Tracking Bot is a Python-based tool that monitors Ethereum blockchain transactions for specific addresses. It sends transaction details to a designated Telegram chat. The bot can detect and report on transactions involving monitored addresses, including transaction actions such as token swaps.

![MTP](images/MTB.png)

## Features

- Monitors Ethereum transactions for specified addresses.
- Sends transaction details to a Telegram chat.
- Detects and reports transaction actions, including token swaps.
- Configurable via environment variables.

## Requirements

- Python 3.x
- An Infura project ID
- A Telegram bot token
- A Telegram chat ID

## Setup

1. **Clone the repository:**

   ```sh
   git clone <repository-url>
   cd Moneytree-Tracking-Bot
   ```

2. **Create a virtual environment and install dependencies:**

   ```sh
   python -m venv venv
   source venv/bin/activate   # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

3. **Create a `.env` file:**

   Copy the example `.env_example` file and rename it to `.env`. Set the environment variables in the `.env` file:

   ```sh
   cp .env_example .env
   ```

   Edit the `.env` file to include your configuration:

   ```ini
   INFURA_PROJECT_ID=your_infura_project_id
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   CHAT_ID=your_telegram_chat_id
   ADDRESSES_TO_MONITOR=address1,address2,address3
   ADDRESS_NAMES=name1,name2,name3
   ```

4. **Get Your Telegram Chat ID:**

   Use the provided `get_chat_id.py` script to get your Telegram chat ID. Run the following command:

   ```sh
   python get_chat_id.py
   ```

   This script will print the chat ID of the group or individual chat where the bot received the most recent message. Use this chat ID in your `.env` file.

5. **Run the bot:**

   ```sh
   python main.py
   ```

6. **(Optional) Test a specific transaction:**

   ```sh
   python main.py --test-tx <transaction_hash>
   ```

## Configuration

The bot is configured using environment variables. These should be set in a `.env` file in the project directory:

- `INFURA_PROJECT_ID`: Your Infura project ID.
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token.
- `CHAT_ID`: The ID of the Telegram chat where messages will be sent.
- `ADDRESSES_TO_MONITOR`: A comma-separated list of Ethereum addresses to monitor.
- `ADDRESS_NAMES`: A comma-separated list of names corresponding to the addresses to monitor.

## How It Works

1. **Initialize and Connect:**
   The bot initializes by loading environment variables and connecting to the Ethereum blockchain via Infura.

2. **Monitor Transactions:**
   It monitors transactions involving the specified addresses. If a transaction involves one of these addresses, it fetches the transaction details from Etherscan.

3. **Parse and Send Details:**
   The bot parses the transaction details, including detecting any token swap actions. It formats these details and sends them to the designated Telegram chat.

## Example Output

The bot sends a message to the Telegram chat with details about the transaction. Here is an example message:

    ⭐ name: OUTGOING 💵

    Transaction Hash: 0x1234567890abcdef

    Action: Swap 0.1 ETH for 1000 TOKEN — TOKEN LINK

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
