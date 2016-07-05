import re

from datetime import datetime
import parsedatetime as pdt


def reCheck(userQuery):
    actions = ['call', 'wake', 'mail', 'kick', 'wish']
    patterns = [
        re.compile(r'.*(' + "|".join(actions[:]) + ').+in\s(\d+)\s(min|sec)'),
        re.compile(r'(sms)\s([0-9]{10})\s(.+)'),
        re.compile(r'(i am|my name|im)\s([a-zA-Z]+)'),
        re.compile(r'(turn)\s(on|off)\s([a-zA-Z]+[0-9]*)'),
        re.compile(r'(transfer)\s([0-9]+)\sto\s([0-9]+)'),
        re.compile(r'(convert)\s([0-9]+)\s(dollar|inr)\sto\s(inr|dollar)')
    ]
    for p in patterns:
        result = p.findall(userQuery)
        if result:
            return result
    return False


def dateFromString(timeString):
    cal = pdt.Calendar()
    now = datetime.now()
    result = str(cal.parseDT(timeString.strip(), now)[0])
    return result
