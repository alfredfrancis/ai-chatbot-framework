from datetime import datetime
import parsedatetime as pdt


def dateFromString(timeString):
    cal = pdt.Calendar()
    now = datetime.now()
    result = str(cal.parseDT(timeString.strip(), now)[0])
    return result
