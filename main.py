import asyncio
import yaml
import os
from src.bot import IBKRBot
from src.telegram_bot import TelegramBot
from src.utils import setup_logger

async def main():
    logger = setup_logger("Main", "main.log")
    logger.info("Starting the IBKR Scalping Bot application...")

    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)

    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config.yaml not found. Please create one based on the template.")
        return

    ibkr_bot = IBKRBot(config_path="config.yaml")
    
    # The IBKRBot constructor now initializes all its sub-modules internally.
    # We just need to ensure the TelegramBot gets the correct references.
    # The TelegramBot is already initialized within IBKRBot, so we can access it directly.
    telegram_bot = ibkr_bot.telegram_bot

    # Start Telegram bot polling in a separate task
    telegram_task = asyncio.create_task(telegram_bot.run())

    # Start IBKR bot
    await ibkr_bot.start_bot()

    # Wait for telegram task to finish (e.g., if bot is stopped)
    await telegram_task

if __name__ == "__main__":
    asyncio.run(main())
