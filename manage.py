import typer
import asyncio
from json import loads
from pymongo.errors import DuplicateKeyError
from app.main import app
import logging
cli = typer.Typer()

logger = logging.getLogger(__name__)

@cli.command()
def migrate():
    async def async_migrate():
        from app.admin.bots.schemas import Bot
        from app.admin.bots.store import add_bot
        from app.admin.bots.store import import_bot

        try:
            default_bot = Bot(name="default",config={"confidence_threshold": 0.85})
            await add_bot(default_bot.model_dump())
            logger.info("Created default bot")
        except DuplicateKeyError:
            logger.info("Default bot already exists")

        try:
            with open("migrations/default_intents.json", "r") as json_file:
                json_data = loads(json_file.read())
                imported_intents = await import_bot("default", json_data)
                logger.info(f"Imported {imported_intents.get('num_intents_created')} intents for default bot")
        except FileNotFoundError:
            logger.error("Error: 'migrations/default_intents.json' file not found.")


    asyncio.run(async_migrate())

@cli.command()
def train():
    async def async_train():
        from app.bot.nlu.training import train_pipeline
        logger.info("Training models...")
        await train_pipeline(app)
        logger.info("Training models finished.")
    asyncio.run(async_train())

if __name__ == "__main__":
    cli()
