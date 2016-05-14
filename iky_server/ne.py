from iky_server import app

from itertools import chain
import nltk
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import LabelBinarizer
import sklearn
import pycrfsuite


# NER support functions for Feature extration

def _word2features(sent, i):
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
        word1 = sent[i-1][0]
        postag1 = sent[i-1][1]
        features.extend([
            '-1:word.lower=' + word1.lower(),
            '-1:word.istitle=%s' % word1.istitle(),
            '-1:word.isupper=%s' % word1.isupper(),
            '-1:postag=' + postag1,
            '-1:postag[:2]=' + postag1[:2],
        ])
    else:
        features.append('BOS')
        
    if i < len(sent)-1:
        word1 = sent[i+1][0]
        postag1 = sent[i+1][1]
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


def _sent2features(sent):
    return [_word2features(sent, i) for i in range(len(sent))]

def _sent2labels(sent):
    return [label for token, postag, label in sent]

def _sent2tokens(sent):
    return [token for token, postag, label in sent] 

	X_train = [_sent2features(s) for s in train_sents]
	y_train = [_sent2labels(s) for s in train_sents]

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

# Manual tag text chunks

@app.route('/train', methods=['POST'])
def train():
	train_sents = [
					[('send', 'NN', 'O'),
					('sms', 'NNS', 'B-TSK'),
					('to', 'TO', 'O'),
					('8714349616', 'CD', 'B-MOB'),
					('saying', 'VBG', 'O'),
					('hello', 'NN', 'B-MSG')],
					[('sms', 'NNS', 'B-TSK'), 
					('9446623306', 'CD', 'B-MOB'), 
					('haai', 'NN', 'B-MSG')],
					[('sms', 'NNS', 'B-TSK'),
					('9446623306', 'CD', 'B-MOB'),
					('haai', 'NN', 'B-MSG'),
					('how', 'WRB', 'I-MSG'),
					('are', 'VBP', 'I-MSG'),
					('you', 'PRP', 'I-MSG')]
					]
	trainer.params()

	trainer.train('iky.model.crfsuite')

@app.route('/predict', methods=['GET'])
def predict():
	query = request.args.get('query')
	tagger = pycrfsuite.Tagger()
	tagger.open('iky.model.crfsuite')
	print("Predicted:", ' '.join(tagger.tag(_sent2features(example_sent))))

@app.route('/pos_tag',methods=['GET'])
def pos_tag():
		text = request.args.get('text')
		token_text  = nltk.word_tokenize(text)
		tagged_token = nltk.pos_tag(token_text)
		return str(tagged_token)