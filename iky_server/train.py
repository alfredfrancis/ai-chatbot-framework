from itertools import chain
import nltk
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import LabelBinarizer
import sklearn
import pycrfsuite


# NER support functions for Feature extration
def word2features(sent, i):
    word = sent[i][0]
    postag = sent[i][1]
    print(word, postag)
    features = [
        'bias',
        'word.lower=' + word.lower(),
        'word[-3:]=' + word[-3:],
        'word[-2:]=' + word[-2:],
        'word.isupper=%s' % word.isupper(),
        'word.istitle=%s' % word.istitle(),
        'word.isdigit=%s' % word.isdigit(),
        'postag=' + postag,
        'postag[:2]=' + postag[:2],
    ]
    if i > 0:
        word1 = sent[i - 1][0]
        postag1 = sent[i - 1][1]
        features.extend([
            '-1:word.lower=' + word1.lower(),
            '-1:word.istitle=%s' % word1.istitle(),
            '-1:word.isupper=%s' % word1.isupper(),
            '-1:postag=' + postag1,
            '-1:postag[:2]=' + postag1[:2],
        ])
    else:
        features.append('BOS')

    if i < len(sent) - 1:
        word1 = sent[i + 1][0]
        postag1 = sent[i + 1][1]
        features.extend([
            '+1:word.lower=' + word1.lower(),
            '+1:word.istitle=%s' % word1.istitle(),
            '+1:word.isupper=%s' % word1.isupper(),
            '+1:postag=' + postag1,
            '+1:postag[:2]=' + postag1[:2],
        ])
    else:
        features.append('EOS')

    return features


def sent2features(sent):
    print(sent)
    return [word2features(sent, i) for i in range(len(sent))]


def sent2labels(sent):
    return [label for token, postag, label in sent]


def sent2tokens(sent):
    return [token for token, postag, label in sent]

train_sents = [u'[["send","NN","O"],["sms","NNS","O"],["to","TO","O"],["alfred","VB","B-PER"],["saying","VBG","O"],["hello","NN","B-MSG"]]',
               u'[["please","VB","O"],["send","VB","O"],["sms","NNS","B-TSK"],["to","TO","O"],["alfred","VB","B-PER"],["saying","VBG","O"],["how","WRB","B-MSG"],["are","VBP","I-MSG"],["you","PRP","I-MSG"]]',
               u'[["please","VB","O"],["send","VB","O"],["a","DT","O"],["sms","NN","B-TSK"],["to","TO","O"],["alfred","VB","B-PER"],["saying","VBG","O"],["goodbye","NN","B-MSG"]]',
               u'[["please","VB","O"],["send","VB","O"],["a","DT","O"],["sms","NN","B-TSK"],["to","TO","O"],["alfred","VB","B-PER"],["saying","VBG","O"],["goodbye","NN","B-MSG"]]',
               u'[["please","VB","O"],["send","VB","O"],["a","DT","O"],["sms","NN","B-TSK"],["to","TO","O"],["alfred","VB","B-PER"],["saying","VBG","O"],["goodbye","NN","B-MSG"]]',
               u'[["please","VB","O"],["send","VB","O"],["a","DT","O"],["sms","NN","B-TSK"],["to","TO","O"],["alfred","VB","B-PER"],["saying","VBG","O"],["goodbye","NN","B-MSG"]]',
               u'[["please","VB","O"],["send","VB","O"],["a","DT","O"],["sms","NN","B-TSK"],["to","TO","O"],["alfred","VB","B-PER"],["saying","VBG","O"],["goodbye","NN","B-MSG"]]',
               u'[["sms","NNS","B-TSK"],["alfred","VBD","B-PERSON"],["hello","NN","B-MSG"]]',
               u'[["sms","NNS","B-TSK"],["alfred","VBD","B-PERSON"],["hello","NN","B-MSG"]]',
               u'[["sms","NNS","B-TSK"],["alfred","VBD","B-PERSON"],["hello","NN","B-MSG"]]',
               u'[["sms","NNS","B-TSK"],["alfred","VBD","B-PERSON"],["hello","NN","B-MSG"]]',
               u'[["sms","NNS","B-TSK"],["alfred","VBD","B-PERSON"],["hello","NN","B-MSG"]]']

X_train = [sent2features(s) for s in train_sents]
y_train = [sent2labels(s) for s in train_sents]

trainer = pycrfsuite.Trainer(verbose=False)

for xseq, yseq in zip(X_train, y_train):
    trainer.append(xseq, yseq)

trainer.set_params({
    'c1': 1.0,   # coefficient for L1 penalty
    'c2': 1e-3,  # coefficient for L2 penalty
    'max_iterations': 50,  # stop earlier

    # include transitions that are possible, but not observed
    'feature.possible_transitions': True
})
trainer.params()

trainer.train('iky.model.crfsuite')


query = "hello how are you"
token_text = nltk.word_tokenize(query)
tagged_token = nltk.pos_tag(token_text)
tagger = pycrfsuite.Tagger()
tagger.open('iky.model.crfsuite')
print("Predicted:", ' '.join(tagger.tag(sent2features(tagged_token))))
