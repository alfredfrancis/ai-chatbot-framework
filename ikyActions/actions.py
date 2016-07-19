from __future__ import print_function
import requests
import json
import re
from datetime import datetime,timedelta
def hello(entities):
    return "hello"

def calculateOutTime(entities):
    userId = "356000199"
    password = "lulu@123"
    if not userId or not password:
        return "username or password cant be empty"

    URL = 'http://172.30.15.124:2020/HRMS/j_acegi_security_check'
    session = requests.session()

    login_data = {
        'j_username': userId,
        'j_password': password,
        'Submit.x': '50',
        'Submit.y': '12',
    }
    headers = {
        "Referer": "http://172.30.15.124:2020/HRMS/login.do",
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:47.0) Gecko/20100101 Firefox/47.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        r = session.post(URL, data=login_data, headers=headers)
        if "incorrect" in r.text:
            return "username or password incorrect"
    except:
        return "Server can't be reached"

    post_data = {
        'attendancedate': '19 Jul 2016',
        'dummyattendancedate': '19 Jul 2016'
    }
    attendence_url = 'http://172.30.15.124:2020/HRMS/attendance/swipeinfo.do?action=show'
    r = session.post(attendence_url, post_data)
    result = re.findall(r'<td nowrap="true">.*&nbsp;(.*?)</td>', r.text)
    inTime = datetime.strptime(result[0], '%I:%M').time()
    defaultTime = datetime.strptime("9:30", '%I:%M').time()

    if (inTime <= defaultTime):
        #outTime = (defaultTime + timedelta(hours=8, minutes=30)).strftime('%I:%M')
        outTime = (datetime.combine(datetime.today(),defaultTime) + timedelta(hours=8, minutes=30))
    else:
        outTime = (datetime.combine(datetime.today(),inTime)  + timedelta(hours=8, minutes=30))

    now = datetime.now() + timedelta(hours=5, minutes=30)
    print (now)

    if now.time() >= outTime.time() :
        result = "You can leave now. Have a nice time ahead :)"
    elif now.time() < outTime.time():
        diff = "%s hours and %s Minutes"%(str(outTime - now).split(":")[0],str(outTime - now).split(":")[1])
        result = "No. You punched in at %s, You can leave at %s ( %s more)"%(inTime,outTime.time(),diff)

    return result

def checkH2HTransactionStatus(entities):
    url ="http://172.30.10.141:8094/callyourpartner/%s"%(entities["routingKey"])
    data={"txnType": "2O", "method": "enquiryTxn", "txnRefNum": entities["txnNo"]}
    try:
        response = requests.get(url,data)
        json_dict = json.loads(response.content)
        if "statusDescription" not in json_dict:
            return "Status not available in Red currant."
        else:
            json_dict["statusDescription"]
    except:
        return "Red currant Not avilable"

def checkTransactionStatus(entities):
    url = "http://172.30.10.119:7003/customer/enquiry/10/146281095932945"
    parameters = {"txnno": entities['txnNo']}
    if not entities['txnNo']:
        return "Empty or Invalid Transaction number"
    try:
        response = requests.get(url, params=parameters)
        json_dict = json.loads(response.content)
        statusDesc = json_dict['statusDesc']
        if not (statusDesc):
            return "Status not available in YOM"
        else:
            return ("Your transaction no :%s is %s") % (entities['txnNo'],statusDesc)
    except Exception as e:
        return "Server Error,Please try again later."


def addEventToGoogleCalender(entities):
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
    store = file.Storage('ikyActions/Zstorage.json')
    creds = store.get()

    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('ikyActions/client_secret.json', SCOPES)
        creds = tools.run_flow(flow, store, flags) \
            if flags else tools.run(flow, store)

    CAL = build('calendar', 'v3', http=creds.authorize(Http()))

    GMT_OFF = '+05:30'  # GMT for india
    date_time_object = datetime.strptime(entities["date"], '%Y-%m-%d %H:%M:%S')
    START_DATE = date_time_object.strftime("%Y-%m-%dT%H:%M:%S"+GMT_OFF)
    END_DATE = (date_time_object + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S"+GMT_OFF)
    EVENT = {
        'summary': entities["event"],
        'start': {'dateTime': START_DATE},
        'end': {'dateTime': END_DATE},
    }

    e = CAL.events().insert(calendarId='primary',
                            sendNotifications=True, body=EVENT).execute()

    return ('''added Event : %r,
            at: %s''' % (e['summary'].encode('utf-8'),
                         e['start']['dateTime']))
