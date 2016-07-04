from __future__ import print_function

import requests
import json

def hello(entities):
    return "hello"
def statusDescription(statusDesc):
    return {
        'POSTED_TO_BANK': 'posted to bank',
        'FOR_BIC_APPROVAL': 'pending for BICs Approavl'
    }.get(statusDesc, 'Pass')

def checkTransactionStatus(entities):
    url = "http://172.30.10.119:7004/remit/txn/10/146281095932945"
    parameters = {"txnno": entities['txnNo']}
    response = requests.get(url, params=parameters)
    json_dict = json.loads(response.content)
    statusDesc = (json_dict['statusDesc'])
    ##print ('The Transaction number %s is %s'%(entities['txnNo'],statusDescription(statusDesc)))
    ##return('The Transaction number %s is %s'%(entities['txnNo'],statusDescription(statusDesc)))
    return [statusDescription(statusDesc)]

def addEventToGoogleCalender(tagged_json):
    from apiclient.discovery import build
    from httplib2 import Http
    from oauth2client import file, client, tools
    from datetime import datetime, timedelta

    try:
        import argparse

        flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()

    except ImportError:
        flags = Nones

    SCOPES = 'https://www.googleapis.com/auth/calendar'
    store = file.Storage('storage.json')
    creds = store.get()

    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('ikyWebServer/client_secret.json', SCOPES)
        creds = tools.run_flow(flow, store, flags) \
            if flags else tools.run(flow, store)

    CAL = build('calendar', 'v3', http=creds.authorize(Http()))

    GMT_OFF = '+05:30'  # GMT for india
    date_time_object = datetime.strptime(tagged_json["date"], '%Y-%m-%d %H:%M:%S')
    START_DATE = date_time_object.strftime("%Y-%m-%dT%H:%M:%S"+GMT_OFF)
    END_DATE = (date_time_object + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S"+GMT_OFF)
    EVENT = {
        'summary': tagged_json["event"],
        'start': {'dateTime': START_DATE},
        'end': {'dateTime': END_DATE},
    }

    e = CAL.events().insert(calendarId='primary',
                            sendNotifications=True, body=EVENT).execute()

    return ('''added Event : %r,
            at: %s''' % (e['summary'].encode('utf-8'),
                         e['start']['dateTime']))
