from iky_server import app

def book_pizza(tagged_json):
	return "Ok,Ordering %s pizza from %s"%(tagged_json['QUANTITY'],tagged_json['STORE_NAME'])

def book_ticker(tagged_json):
	return "Flight from %s to %s on %s.Done!"%(tagged_json['FROM'],tagged_json['TO'],tagged_json['DATE'])

def google_search(tagged_json):
	return 'Wait a sec, Let me redirect you..<meta http-equiv="refresh" content="1;url=http://google.com/search?q=%s" />'%tagged_json['QUERY']
def create_user(tagged_json):
	return "executing create user function with following details " + str(tagged_json)