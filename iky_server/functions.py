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
