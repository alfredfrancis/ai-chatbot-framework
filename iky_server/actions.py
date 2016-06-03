def buy_pizza(tagged_json):
	return "function buy_pizza(%s)"%(tagged_json)

def book_ticket(tagged_json):
	return "Flight from %s to %s on %s.Done!"%(tagged_json['FROM'],tagged_json['TO'],tagged_json['DATE'])

def google_search(tagged_json):
	return 'Wait a sec, Let me redirect you..<meta http-equiv="refresh" content="1;url=http://google.com/search?q=%s" />'%tagged_json['QUERY']

def create_user(tagged_json):
	return "function create_user(%s)"%(tagged_json)

def getMyTxnCount(tagged_json):
	return "function getMyTxnCount(%s)"%(tagged_json)

def check_status(tagged_json):
	return "function check_status(%s)"%(tagged_json)

def reminder(tagged_json):
	return "function reminder(%s)"%(tagged_json)