from itertools import chain
import nltk
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import LabelBinarizer
import sklearn
import pycrfsuite

def word2features(sent, i):
    word = sent[i][0]
    postag = sent[i][1]
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
    return [word2features(sent, i) for i in range(len(sent))]


def sent2labels(sent):
    return [label for token, postag, label in sent]


def sent2tokens(sent):
    return [token for token, postag, label in sent]

train_sents = [[["book","NN","O"],["me","PRP","O"],["a","DT","O"],["flight","NN","B-TSK"],["from","IN","O"],["abu","JJ","B-FROM"],["dhabi","JJ","I-FROM"],["to","TO","O"],["new","JJ","B-TO"],["york","NN","I-TO"],["on","IN","O"],["monday","NN","B-DATE"]],
                [["get","VB","O"],["me","PRP","O"],["a","DT","O"],["flight","NN","B-TSK"],["from","IN","O"],["usa","JJ","B-FROM"],["to","TO","O"],["india","VB","B-TO"],["on","IN","O"],["monday","NN","B-DATE"]]
            ]

def extract_chunks(tagged_sent):
    labeled = {}
    labels=[]
    for s, tp in tagged_sent:
        if tp != "O":
            label = tp[2:]
            if tp.startswith("B"):
                labeled[label] = s
            elif tp.startswith("I") and (label not in labels) :
                labels.append(label)
                labeled[label] = s
            elif (tp.startswith("I") and (label in labels)):
                labeled[label] += " %s"%s
    return labeled

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

trainer.train('iky.test.crfsuite')


query =raw_input("Enter : ")

token_text = nltk.word_tokenize(query)
tagged_token = nltk.pos_tag(token_text)
tagger = pycrfsuite.Tagger()
tagger.open('iky.test.crfsuite')

tagged = tagger.tag(sent2features(tagged_token))

print(zip(token_text,tagged))
bio_tagged = extract_chunks(zip(token_text,tagged))

print(str(bio_tagged))



"""
from collections import Counter
info = tagger.info()

def print_transitions(trans_features):
    for (label_from, label_to), weight in trans_features:
        print("%-6s -> %-7s %0.6f" % (label_from, label_to, weight))

print("Top likely transitions:")
print_transitions(Counter(info.transitions).most_common(15))

print("\nTop unlikely transitions:")
print_transitions(Counter(info.transitions).most_common()[-15:])
"""