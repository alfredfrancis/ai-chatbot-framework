import nltk
import os

# Downloading necessary NLTK datasets
nltk.download("stopwords")
nltk.download("wordnet")
nltk.download('averaged_perceptron_tagger')
nltk.download('punkt')

#creating directory for storing chat logs
if not os.path.exists("logs"):
    os.makedirs("logs")

try:
    from app.stories.models import Story, LabeledSentences

    # Setting up default intents
    newStory = Story()
    newStory.storyName = 'Default Fallback intent'
    newStory.intentName = 'fallback'
    newStory.speechResponse = "Sorry. I'm having trouble understanding you."
    newStory.apiTrigger = False
    newLabeledSentence = LabeledSentences()
    newLabeledSentence.data = [['', 'VB', 'O']]
    newStory.labeledSentences.append(newLabeledSentence)
    newStory.save()

    newStory = Story()
    newStory.storyName = 'cancel'
    newStory.intentName = 'cancel'
    newStory.speechResponse = "Ok. Canceled."
    newStory.apiTrigger = False
    newLabeledSentence = LabeledSentences()
    newLabeledSentence.data = [['cancel', 'VB', 'O'], ['close', 'VB', 'O']]
    newStory.labeledSentences.append(newLabeledSentence)
    newStory.save()

    newStory = Story()
    newStory.storyName = 'Welcome message'
    newStory.intentName = 'init_conversation'
    newStory.speechResponse = "Hi, What can i do for you ?"
    newStory.apiTrigger = False
    newLabeledSentence = LabeledSentences()
    newLabeledSentence.data = [[
        "init_conversation",
        "NN",
        "O"
    ]]
    newStory.labeledSentences.append(newLabeledSentence)
    newStory.save()
except:
    print("Stories already exists..skipping..")
    
try:
    print("Training models..")
    from app.core.intentClassifier import IntentClassifier
    IntentClassifier().train()
    print("Training models finished..")
except:
    print("Could train models..")
