import re

from datetime import datetime
import parsedatetime as pdt


def re_check(user_say):
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
        result = p.findall(user_say)
        if result:
            return result
    return False


def extract_chunks(tagged_sent, chunk_type):
    grp1, grp2, chunk_type = [], [], "-" + chunk_type
    for ind, (s, tp) in enumerate(tagged_sent):
        if tp.endswith(chunk_type):
            if not tp.startswith("B"):
                grp2.append(str(ind))
                grp1.append(s)
            else:
                if grp1:
                    yield " ".join(grp1), "-".join(grp2)
                grp1, grp2 = [s], [str(ind)]
    yield " ".join(grp1), "-".join(grp2)


def datefromstring(time_string):
    cal = pdt.Calendar()
    now = datetime.now()
    result = str(cal.parseDT(time_string.strip(), now)[0])
    return result
