import typer
import asyncio
from json import loads
import logging
import spacy
from pymongo.errors import DuplicateKeyError
from app.main import app

cli = typer.Typer()

logger = logging.getLogger(__name__)


@cli.command()
def migrate():
    async def async_migrate():
        from app.admin.bots.store import ensure_default_bot, import_bot
        from app.admin.integrations.store import ensure_default_integrations
        from app.config import app_config

        try:
            await ensure_default_bot()
            logger.info("Created default bot")
        except DuplicateKeyError:
            logger.info("Default bot already exists")

        try:
            with open("migrations/default_intents.json", "r") as json_file:
                json_data = loads(json_file.read())
                imported_intents = await import_bot("default", json_data)
                logger.info(
                    f"Imported {imported_intents.get('num_intents_created')} intents for default bot"
                )
        except FileNotFoundError:
            logger.error("Error: 'migrations/default_intents.json' file not found.")

        await ensure_default_integrations()

        # ensure spacy language models are installed
        logger.info("Downloading spacy language models...")
        spacy.cli.download(app_config.SPACY_LANG_MODEL)

        logger.info("Migration finished.")

    asyncio.run(async_migrate())


@cli.command()
def train():
    async def async_train():
        from app.bot.nlu.pipeline_utils import train_pipeline

        logger.info("Training models...")
        await train_pipeline(app)
        logger.info("Training models finished.")

    asyncio.run(async_train())


if __name__ == "__main__":
    cli()
