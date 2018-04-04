from nltk.tag.perceptron import PerceptronTagger
from nltk import word_tokenize

# Load and initialize Perceptron tagger
tagger = PerceptronTagger()


def posTagger(sentence):
    """
    perform POS tagging on a given sentence
    :param sentence:
    :return:
    """
    tokenizedSentence = word_tokenize(sentence)
    posTaggedSentence = tagger.tag(tokenizedSentence)
    return posTaggedSentence


def posTagAndLabel(sentence):
    """
    Perform POS tagging and BIO labeling on given sentence
    :param sentence:
    :return:
    """
    taggedSentence = posTagger(sentence)
    taggedSentenceJson = []
    for token, postag in taggedSentence:
        taggedSentenceJson.append([token, postag, "O"])
    return taggedSentenceJson


def sentenceTokenize(sentences):
    """
    Sentence tokenizer
    :param sentences:
    :return:
    """
    tokenizedSentences = word_tokenize(sentences)
    return " ".join(tokenizedSentences)
