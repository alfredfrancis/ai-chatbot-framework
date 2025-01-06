from app.main import spacy_tokenizer

def pos_tagger(sentence):
    """
    perform POS tagging on a given sentence
    :param sentence:
    :return:
    """
    doc = spacy_tokenizer(sentence)
    taged_sentance = []
    for token in doc:
        taged_sentance.append((token.text, token.tag_))
    return taged_sentance


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
    doc = spacy_tokenizer(sentences)
    words = [token.text for token in doc]
    return " ".join(words)
