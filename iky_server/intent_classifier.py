# scikit-learn
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.svm import LinearSVC
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.multiclass import OneVsRestClassifier
from sklearn import preprocessing
from sklearn.externals import joblib

from bson.json_util import loads,dumps
import mongo

class Intent_classifier(object):
	def __init__(self):
		self.lb = preprocessing.MultiLabelBinarizer()
		self.labeled_stories = mongo._retrieve("labled_queries",{"user_id":"1"})
		
		y_train_text =[]

		for story in self.labeled_stories:
			y_train_text.append([story['story_id']])
		
		self.Y = self.lb.fit_transform(y_train_text)

	def context_train(self):	
		x_train = []

		for story in self.labeled_stories:
			lq = ""
			for i,token in enumerate(loads(story["item"])):
				if i != 0:
					lq += " "+token[0]
				else:
					lq = token[0]
			x_train.append(lq)
			
		self.X_train = np.array(x_train)

		classifier = Pipeline([
		    ('vectorizer', CountVectorizer()),
		    ('tfidf', TfidfTransformer()),
		    ('clf', OneVsRestClassifier(LinearSVC()))])

		classifier.fit(self.X_train, self.Y)

		# dump generated model to file
		joblib.dump(classifier, 'models/intent.pkl', compress=3)
		return "Done"

	def context_check(self,user_say):
		try:
			#Prediction using Model
			classifier = joblib.load('models/intent.pkl')
		except IOError:
			return False

		predicted = classifier.predict([user_say])

		if predicted.any():
			all_labels = self.lb.inverse_transform(predicted)
			return all_labels[0][0]
		else:
			return False