from iky_server import app
from flask import request, jsonify, Response
import json
from sklearn import linear_model
from sklearn.externals import joblib

_model = joblib.load('models/' + request.args['device'] + '.pkl')

@app.route("/generate", methods=['GET'])
def generate():
	data = pd.read_csv('datasets/data.csv')

	# setting target value
	_bulb1 = data['bulb1']
	target = _bulb1.values

	# setting features for prediction
	numerical_features = data[['light', 'time', 'motion']]

	# converting into numpy arrays
	features_array = numerical_features.values

	# Create linear regression object
	regr = linear_model.LinearRegression()

	# Train the model using the training sets
	regr.fit(features_array, target)

	# dump generated model to file
	joblib.dump(regr, 'mis.pkl', compress=3)

	return 'Models Generated'

@app.route("/predict", methods = ['POST'])
def predict():
	# Bulding Features list
	if request.headers['Content-Type'] == 'application/json':
		features_set = json.dumps(request.json)

	#	Prediction using Model
	_model = joblib.load('mis.pkl')
	target_predicted = _model.predict(features_set)
	return jsonify(target_predicted)