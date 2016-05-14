from wit import Wit

global last_context 
last_context = {}

global botsay
botsay = ""


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))

def first_entity_value(entities, entity):
    if entity not in entities:
        return None

    val = entities[entity][0]['value']
    if not val:
        return None
    return val['value'] if isinstance(val, dict) else val

def say(session_id, msg):
    global botsay
    botsay = msg


def merge(context,entities):

	global last_context

	new_context = dict(context)
	mbody = first_entity_value(entities, 'message_body')

	if mbody:
		new_context['mbody'] = mbody

	mname = first_entity_value(entities, 'name')
	
	if mname:
		new_context['mname'] = mname
	
	last_context = new_context
	return new_context

def error(session_id, msg):
    print('Oops, I don\'t know what to do.')

actions = {
    'say': say,
    'merge': merge,
    'error': error,
    'send_sms':send_sms
}

access_token = ""

client = Wit(access_token, actions)