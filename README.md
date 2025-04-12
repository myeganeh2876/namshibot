# NamshiBot

A Telegram bot that extracts product information from Namshi website URLs.

## Features

- Extract product images, name, price, and available sizes from Namshi product URLs
- Download and send images to the user
- Display product details in a formatted message

## Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your Telegram bot token:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```

3. Run the bot:
   ```
   python bot.py
   ```

## Usage

1. Start a chat with the bot
2. Send a Namshi product URL (e.g., https://www.namshi.com/uae-en/buy-product-name/product-id/p/)
3. The bot will extract and send the product information

## Requirements

- Python 3.7+
- Telegram bot token (obtained from BotFather)
