import nltk
import os

# Downloading necessary NLTK datasets
nltk.download("stopwords")
nltk.download("wordnet")
nltk.download('averaged_perceptron_tagger')
nltk.download('punkt')

# creating directory for storing chat logs
if not os.path.exists("logs"):
    os.makedirs("logs")

try:
    print("Training models..")
    from app.core.intentClassifier import IntentClassifier
    IntentClassifier().train()
    print("Training models finished..")
except Exception as e:
    e = str(e)
    if e == "NO_DATA":
        e = "load Data first into mongodb. Reffer Readme."
    print("Could not train models..skipping.. (reason: {})".format(e))
