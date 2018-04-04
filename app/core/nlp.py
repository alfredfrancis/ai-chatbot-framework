from nltk.tag.perceptron import PerceptronTagger
from nltk import word_tokenize

# Load and initialize Perceptron tagger
tagger = PerceptronTagger()


def pos_tagger(sentence):
    """
    perform POS tagging on a given sentence
    :param sentence:
    :return:
    """
    tokenized_sentence = word_tokenize(sentence)
    pos_tagged_sentence = tagger.tag(tokenized_sentence)
    return pos_tagged_sentence


def pos_tag_and_label(sentence):
    """
    Perform POS tagging and BIO labeling on given sentence
    :param sentence:
    :return:
    """
    tagged_sentence = pos_tagger(sentence)
    tagged_sentence_json = []
    for token, postag in tagged_sentence:
        tagged_sentence_json.append([token, postag, "O"])
    return tagged_sentence_json


def sentence_tokenize(sentences):
    """
    Sentence tokenizer
    :param sentences:
    :return:
    """
    tokenized_sentences = word_tokenize(sentences)
    return " ".join(tokenized_sentences)
