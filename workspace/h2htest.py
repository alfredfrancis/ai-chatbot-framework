import requests
import json


# {"txnType":"2O","method":"enquiryTxn","txnRefNum":"0116016120126679"}

def checkH2HTransactionStatus(entities):
    if not entities["routingKey"]:
        return "Routing key not supported."
    url = "http://172.30.10.119:8094/callyourpartner/YOM/%s"%entities["routingKey"]
    data = {"payload": json.dumps({
        "txnType":"2O",
        "method":"enquiryTxn",
        "txnRefNum":entities["txnNo"]}
    )}
    try:
        response = requests.post(url, data=data)
        responseDict = json.loads(response.text)
        if "statusDescription" not in responseDict:
            return "Status not available in Red currant."
        else:
            return responseDict["statusDescription"]
    except:
        return "Redcurrant Server Not avilable"


def checkTransactionStatus(entities):
    routingKeyMatchTable = {
        11667: "DIBHH"
    }
    url = "http://172.30.10.119:7027/rateboard/enquiry/10/146281095932945"
    parameters = {"txnno": entities['txnNo']}
    if not entities['txnNo']:
        return "Empty or Invalid Transaction number"
    try:
        response = requests.get(url, params=parameters)
        responseDict = json.loads(response.text)
        statusDesc = responseDict.get('statusDesc')
        rcResult=yomResult = "Not Avilable"
        if not (statusDesc):
            yomResult = "Status not available in YOM"
        elif "Transmitted" in statusDesc:
            yomResult = statusDesc
            entities["routingKey"] = routingKeyMatchTable.get(responseDict.get('beneficiary').get('beneficiaryBank').get('draweeBankId'))
            rcResult = checkH2HTransactionStatus(entities)
        else:
            yomResult = statusDesc
        return ("***Transaction no :%s ***YOM status :%s ***RedCurrant status: %s")%(entities['txnNo'],
                                                                            yomResult,rcResult)
    except Exception as e:
        return "Server Error,Please try again later."


print (checkTransactionStatus({"txnNo": "545454"}))
