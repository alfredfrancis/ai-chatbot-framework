import nltk

from app.core import Story, LabeledSentences

# Downloading necessary NLTK datasets

nltk.download("stopwords")
nltk.download("wordnet")
nltk.download('averaged_perceptron_tagger')
nltk.download('punkt')

# Setting up default intents

newStory = Story()
newStory.storyName = 'Default Fallback intent'
newStory.intentName = 'fallback'
newStory.speechResponse = "Sorry. I'm having trouble understanding you."
newLabeledSentence = LabeledSentences()
newLabeledSentence.data = [['', 'VB', 'O']]
newStory.labeledSentences.append(newLabeledSentence)
newStory.save()

newStory = Story()
newStory.storyName = 'cancel'
newStory.intentName = 'cancel'
newStory.speechResponse = "Ok. Canceled."
newLabeledSentence = LabeledSentences()
newLabeledSentence.data = [['cancel', 'VB', 'O'], ['close', 'VB', 'O']]
newStory.labeledSentences.append(newLabeledSentence)
newStory.save()

newStory = Story()
newStory.storyName = 'Welcome message'
newStory.intentName = 'init_conversation'
newStory.speechResponse = "Hi, What can i do for you ?"
newLabeledSentence = LabeledSentences()
newLabeledSentence.data = [[
    "init_conversation",
    "NN",
    "O"
]]
newStory.labeledSentences.append(newLabeledSentence)
newStory.save()
