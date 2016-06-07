#date parsing
from datetime import datetime
import parsedatetime as pdt

def parsedate(time_string):
	cal = pdt.Calendar()
	now = datetime.now()
	return cal.parseDT(time_string, now)[0]
while True:
	print(parsedate(raw_input("\n\nEnter date:\t")))