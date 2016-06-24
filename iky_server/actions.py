from __future__ import print_function

def buy_pizza(tagged_json):
    return "function buy_pizza(%s)" % (tagged_json)


def book_ticket(tagged_json):
    return "Flight from %s to %s on %s.Done!" % (tagged_json['FROM'], tagged_json['TO'], tagged_json['DATE'])


def create_user(tagged_json):
    return "function create_user(%s)" % (tagged_json)


def getMyTxnCount(tagged_json):
    return "function getMyTxnCount(%s)" % (tagged_json)


def check_status(tagged_json):
    return "function check_status(%s)" % (tagged_json)

def alarm(tagged_json):
    result = "Alarm set at %s" % (tagged_json["date"])
    return result


def checkTransactionStatus(tagged_json):
    return "Transanction Number : %s is completed." % tagged_json["lr_no"]

def reminder(tagged_json):
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
        flow = client.flow_from_clientsecrets('iky_server/client_secret.json', SCOPES)
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

