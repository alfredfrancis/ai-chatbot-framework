from flask_script import Manager

from app import app

manager = Manager(app)

@manager.command
def migrate():
    from app.agents.models import Bot

    try:
        # create default bot
        bot = Bot()
        bot.name = "default"
        bot.save()
        print("Created default bot")
    except:
        print("Default agent exists.. skipping..")


    # import some default intents
    from app.intents.controllers import import_json
    json_file = open("examples/default_intents.json", "r+")
    stories = import_json(json_file)
    print("Imported {} Stories".format(len(stories)))

    try:
        print("Training models..")
        from app.nlu.tasks import train_models
        train_models()
        print("Training models finished..")
    except Exception as e:
        e = str(e)
        if e == "NO_DATA":
            e = "load Data first into mongodb. Reffer Readme."
        print("Could not train models..skipping.. (reason: {})".format(e))


if __name__ == "__main__":
    manager.run()
