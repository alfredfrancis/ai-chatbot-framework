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


def reminder(tagged_json):
    print tagged_json
    result = "Reminder set at %s , Event : %s" % (tagged_json["date"], tagged_json["event"])
    return result


def alarm(tagged_json):
    result = "Alarm set at %s" % (tagged_json["date"])
    return result

def checkTransactionStatus(tagged_json):
    return "Transanction Number : %s is completed."%tagged_json["lr_no"]