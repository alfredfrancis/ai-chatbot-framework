from iky_server import app
import requests
import actions
import json
import re

def execute_action(action_type,action,parameters):
	types = {
				0 : python_function,
				1 : sql_query,
				2 : rest_api,
				3 : custom_message
			}
	return types[int(action_type)](action,parameters)

def python_function(action,parameters):
	#result = globals()["action"](parameters)
	result = getattr(actions, action)(parameters)
	return result

def sql_query(action,parameters):
 	output = re.sub(r'\{([a-z_0-9]*)\}',lambda m:'"'+parameters[m.group(1)]+'"',action)
	return output

def rest_api(action,parameters):
	result = requests.get(action, data=parameters)
	return result.text

def custom_message(action,parameters):
	output = re.sub(r'\{([a-z_0-9]*)\}',lambda m:parameters[m.group(1)],action)
	return output

"""import re
>>> str = "<20"
>>> output = re.sub(r'<(?=\d)', r'\r\n<', str)
"""