from __future__ import print_function
from apiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from datetime import datetime,timedelta

try:
    import argparse

    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()

except ImportError:
    flags = Nones

SCOPES = 'https://www.googleapis.com/auth/calendar'
store = file.Storage('storage.json')
creds = store.get()
tagged_json = {"date" :"2016-06-25 10:00:00",
               "event" : "Call mom"}
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('client_secret.json', SCOPES)
    creds = tools.run_flow(flow, store, flags) \
        if flags else tools.run(flow, store)

CAL = build('calendar', 'v3', http=creds.authorize(Http()))

GMT_OFF = '+05:30'  # GMT for india
date_time_object = datetime.strptime(tagged_json["date"], '%Y-%m-%d %H:%M:%S')
START_DATE = date_time_object.strftime("%Y-%m-%dT%H:%M:%S-05:30")
END_DATE = (date_time_object + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S-05:30")
EVENT = {
    'summary': tagged_json["event"],
    'start': {'dateTime': '2016-06-24T15:00:00+05:30'},
    'end': {'dateTime': '2016-06-24T16:00:00+05:30'},
}

e = CAL.events().insert(calendarId='primary',
                        sendNotifications=True, body=EVENT).execute()

print ('''*** %r event added:
        at: %s''' % (e['summary'].encode('utf-8'),
                     e['start']['dateTime']))
