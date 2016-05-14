from pymongo import MongoClient

# Initialize MongoDb client with default local server
client = MongoClient()

iky = client.iky


def _insert_user(name,email,level):
	users = iky.users
	user_info = {
	"uname":name,
	"email":email,
	"level":"admin",
	"stories":[]
	}
	user_id = users.insert_one().inserted_id
	return user_id

def _insert_tagged(labeled_info):
	"""
	labeled_info = {
	"token":name,
	"postag":email,
	"label":"admin",
	"story_id":""
	}
	"""
	labled_queries = iky.labled_queries
	post_id = labled_queries.insert_one(data).inserted_id
	return post_id
def _get_tagged(query=None):
    query = {"name" : "SP"}
        try:
            cursor = hcoll.find(query)
        except Exception as e:
            print "Unexpected error:", type(e), e
        return cursor 