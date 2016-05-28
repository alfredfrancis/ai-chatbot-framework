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
from sklearn.externals import joblib

import json	
import mongo

lb = preprocessing.MultiLabelBinarizer()

def context_train():
	labeled_stories = json.loads(mongo._retrieve("labled_queries",{"user_id":"1"}))
	x_train = []
	y_train_text =[]
	for story in labeled_stories:
		lq = ""
		for i,token in enumerate(json.loads(story["item"])):
			if i != 0:
				lq += " "+token[0]
			else:
				lq = token[0]
		x_train.append(lq)
		y_train_text.append([story['story_id']])

	X_train = np.array(x_train)

 	lb = preprocessing.MultiLabelBinarizer()
	Y = lb.fit_transform(y_train_text)

	classifier = Pipeline([
	    ('vectorizer', CountVectorizer()),
	    ('tfidf', TfidfTransformer()),
	    ('clf', OneVsRestClassifier(LinearSVC()))])

	classifier.fit(X_train, Y)

	# dump generated model to file
	joblib.dump(classifier, 'models/intent.pkl', compress=3)
	return "Done"

def context_check(user_say):
	#Prediction using Model
	classifier = joblib.load('models/intent.pkl')
	predicted = classifier.predict([user_say])

	if predicted.any():
		all_labels = lb.inverse_transform(predicted)
		return all_labels[0][0]
	else:
		return False

context_train()
while True:
	result = context_check(raw_input())
	print(result)