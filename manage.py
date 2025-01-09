import typer
from app.config import app_config

app_cli = typer.Typer()

@app_cli.command()
async def migrate():
    from app.admin.bots.schemas import Bot
    from app.admin.bots.store import add_bot
    from app.admin.bots.store import import_bot
    from app.bot.nlu.training import train_pipeline

    default_bot = Bot(name="default")
    await add_bot(default_bot.model_dump())
    print(f"Created default bot")

    try:
        with open("migrations/default_intents.json", "r") as json_file:
            imported_intents = await import_bot(json_file)
            print(f"Imported {imported_intents.get("num_intents_created")} intents for default bot")
    except FileNotFoundError:
        print("Error: 'migrations/default_intents.json' file not found.")

    print("Training models...")
    await train_pipeline(app_config.MODELS_DIR)
    print("Training models finished.")


if __name__ == "__main__":
    app_cli()