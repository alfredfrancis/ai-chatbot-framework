from nltk.tag.perceptron import PerceptronTagger
from nltk import word_tokenize

# Load and initialize Perceptron tagger
tagger = PerceptronTagger()


def posTagger(sentence):
    tokenizedSentence = word_tokenize(sentence)
    posTaggedSentence = tagger.tag(tokenizedSentence)
    return posTaggedSentence


def posTagAndLabel(sentence):
    taggedSentence = posTagger(sentence)
    taggedSentenceJson = []
    for token, postag in taggedSentence:
        taggedSentenceJson.append([token, postag, "O"])
    return taggedSentenceJson


def sentenceTokenize(sentences):
    tokenizedSentences = word_tokenize(sentences)
    tokenizedSentencesPlainText = ""
    for t in tokenizedSentences:
        tokenizedSentencesPlainText += " " + t
    return tokenizedSentencesPlainText
