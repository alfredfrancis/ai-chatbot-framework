from flask_script import Manager
from app import create_app

app = create_app()
manager = Manager(app)

@manager.command
def migrate():
    from app.agents.models import Bot
    from app.intents.controllers import import_json
    from app.nlu.tasks import train_models

    # Create default bot
    try:
        bot = Bot()
        bot.name = "default"
        bot.save()
        print("Created default bot")
    except Exception as e:
        print(f"Default bot creation failed or already exists: {e}")

    # Import default intents
    try:
        with open("examples/default_intents.json", "r") as json_file:
            stories = import_json(json_file)
            print(f"Imported {len(stories)} Stories")
    except FileNotFoundError:
        print("Error: 'examples/default_intents.json' file not found.")
    except Exception as e:
        print(f"Failed to import intents: {e}")

    # Train models
    try:
        print("Training models..")
        train_models()
        print("Training models finished.")
    except Exception as e:
        error_message = str(e)
        if error_message == "NO_DATA":
            error_message = "Load data first into MongoDB. Refer to the README."
        print(f"Could not train models: {error_message}")

if __name__ == "__main__":
    manager.run()

