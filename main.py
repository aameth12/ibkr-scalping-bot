import asyncio
import yaml
from src.bot import IBKRBot
from src.telegram_bot import TelegramBot
from src.utils import setup_logger

async def main():
    logger = setup_logger("Main", "main.log")
    logger.info("Starting the IBKR Scalping Bot application...")

    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config.yaml not found. Please create one based on the template.")
        return

    ibkr_bot = IBKRBot(config_path="config.yaml")
    telegram_bot = TelegramBot(config, ibkr_bot)
    ibkr_bot.set_telegram_bot(telegram_bot)

    # Start Telegram bot in a separate task
    telegram_task = asyncio.create_task(telegram_bot.run())

    # Start IBKR bot
    await ibkr_bot.start_bot()

    # Wait for telegram task to finish (e.g., if bot is stopped)
    await telegram_task

if __name__ == "__main__":
    asyncio.run(main())
