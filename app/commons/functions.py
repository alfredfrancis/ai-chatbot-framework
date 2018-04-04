from datetime import datetime
import parsedatetime as pdt


def date_from_string(timeString):
    cal = pdt.Calendar()
    now = datetime.now()
    result = str(cal.parseDT(timeString.strip(), now)[0])
    return result
