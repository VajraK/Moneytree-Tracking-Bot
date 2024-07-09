import requests
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

def get_updates():
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates'
    response = requests.get(url)
    return response.json()

updates = get_updates()
for result in updates['result']:
    print(result)
    if 'message' in result:
        print('Chat ID:', result['message']['chat']['id'])
        break
