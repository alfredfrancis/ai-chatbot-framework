from iky_server import app

# Regular expression
import re

# scikit-learn
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.svm import LinearSVC
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.multiclass import OneVsRestClassifier
from sklearn import preprocessing
from datetime import datetime
import parsedatetime as pdt 


def re_check(user_say):
	actions=['call','wake','mail','kick','wish']
	patterns = [
					re.compile(r'.*('+"|".join(actions[:])+').+in\s(\d+)\s(min|sec)'),
					re.compile(r'(sms)\s([0-9]{10})\s(.+)'),
					re.compile(r'(i am|my name|im)\s([a-zA-Z]+)'),
					re.compile(r'(turn)\s(on|off)\s([a-zA-Z]+[0-9]*)'),
					re.compile(r'(transfer)\s([0-9]+)\sto\s([0-9]+)'),
					re.compile(r'(convert)\s([0-9]+)\s(dollar|inr)\sto\s(inr|dollar)')
				]
	for p in patterns:
		result =p.findall(user_say) 
		if result:
				return result
	return False

@app.route('/context_check', methods=['POST'])
def context_check(user_say):
	X_train = np.array(["set up a meeting with alfred",
                    "initiate new transaction",
                    "invite joe for a meeting",
                    "meet joe at restorent",
                    "send 100 rupees to rahul",
                    "trasact 100 rupees from 43845793 to 329572357",
                    "set up a meeting with tina",
                    "ask teena wheather she is avilable for tommorrow's meeting"])

	y_train_text = [["meeting"],["transaction"],["meeting"],["meeting"],["transaction"],
	                ["transaction"],["meeting"],["meeting"]]

	lb = preprocessing.MultiLabelBinarizer()
	Y = lb.fit_transform(y_train_text)

	classifier = Pipeline([
	    ('vectorizer', CountVectorizer()),
	    ('tfidf', TfidfTransformer()),
	    ('clf', OneVsRestClassifier(LinearSVC()))])

	classifier.fit(X_train, Y)

	predicted = classifier.predict([user_say])
	if predicted.any():
		all_labels = lb.inverse_transform(predicted)
		return "query context : "+all_labels[0][0]
	else:
		return false

def extract_chunks(tagged_sent, chunk_type):
    grp1, grp2, chunk_type = [], [], "-" + chunk_type
    for ind, (s, tp) in enumerate(tagged_sent):
        if tp.endswith(chunk_type):
            if not tp.startswith("B"):
                grp2.append(str(ind))
                grp1.append(s)
            else:
                if grp1:
                    yield " ".join(grp1), "-".join(grp2)
                grp1, grp2 = [s], [str(ind)]
    yield " ".join(grp1), "-".join(grp2)


def datefromstring(time_string):
	cal = pdt.Calendar()
	now = datetime.now()
	return str(cal.parseDT(time_string, now)[0])










"""
In [2]: l = [('The', 'B-NP'), ('Mitsubishi', 'I-NP'), ('Electric', 'I-NP'), ('Company', 'I-NP'), ('Managing', 'B-NP'),
   ...:                ('Director', 'I-NP'), ('ate', 'B-VP'), ('ramen', 'B-NP')]

In [3]: list(extract_chunks(l, "NP"))
Out[3]: 
[('The Mitsubishi Electric Company', '0-1-2-3'),
 ('Managing Director', '4-5'),
 ('ramen', '7')]

In [4]: l = [('What', 'B-NP'), ('is', 'B-VP'), ('the', 'B-NP'), ('airspeed', 'I-NP'), ('of', 'B-PP'), ('an', 'B-NP'), ('unladen', 'I-NP'), ('swallow', 'I-NP'), ('?', 'O')]

In [5]: list(extract_chunks(l, "NP"))
Out[5]: [('What', '0'), ('the airspeed', '2-3'), ('an unladen swallow', '5-6-7')]
"""