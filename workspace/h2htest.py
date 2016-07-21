import requests
import json


# {"txnType":"2O","method":"enquiryTxn","txnRefNum":"0116016120126679"}

def checkH2HTransactionStatus(entities):
    url = "http://172.30.10.119:8094/callyourpartner/YOM/%s" % entities["routingKey"]
    payload = {
        "txnType": "2O",
        "method": "enquiryTxn",
        "txnRefNum": entities["txnNo"],
        "serviceProviderCode": "LULUXAE#####",
        "uploadDate": "20-07-2016"
    }
    try:
        response = requests.post(url, payload)
        responseDict = json.loads(response.text)
        print (responseDict)
        if "statusDescription" not in responseDict:
            return "Status not available in Red currant."
        else:
            return responseDict["statusDescription"]
    except:
        return "Red currant Not avilable"


def checkTransactionStatus(entities):

    routingKeyMatchTable = {
        4564: "DIBHH",
        6594: "ICICIHH"

    }

    url = "http://10.45.0.171:7003/customer/enquiry/10/1232"
    parameters = {"txnno": entities['txnNo']}
    if not entities['txnNo']:
        return "Empty or Invalid Transaction number"
    try:
        response = requests.get(url, params=parameters)
        responseDict = json.loads(response.text)
        statusDesc = responseDict.get('statusDesc')
        if not (statusDesc):
            result = "Status not available in YOM"
        elif "Transmitted" in statusDesc:
            entities["routingKey"] = responseDict.get('beneficiary').get('draweeBankId')
            result = checkH2HTransactionStatus(entities)
        else:
            result = statusDesc
        return ("Transaction no :%s, %s") % (entities['txnNo'], result)
    except Exception as e:
        return "Server Error,Please try again later."


print (checkTransactionStatus({"txnNo": "0105216101749320", "routingKey": "DIBHH"}))
