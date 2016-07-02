import json
import requests
from bs4 import BeautifulSoup
import nltk
from nltk import word_tokenize
data = {
    "operation": {
        "details": {
            "from": "0",
            "limit": "10",
            "filterby": "All_Requests"
        }
    }
}

url = "http://172.30.10.101/sdpapi/request?OPERATION_NAME=GET_REQUESTS&" \
      "TECHNICIAN_KEY=268FBC4E-24AF-4712-8577-0B6AF96C117D" \
      "&format=json&INPUT_DATA=%s" % json.dumps(data)

response = requests.get(url)

parsed = json.loads(response.content)

for work in parsed["operation"]["details"]:

    data = {
        "operation": {
            "details": {
                "from": "0",
                "limit": "50",
                "filterby": "All_Requests"
            }
        }
    }

    url = "http://172.30.10.101/sdpapi/request/%s?OPERATION_NAME=GET_REQUEST_FIELDS&" \
          "TECHNICIAN_KEY=268FBC4E-24AF-4712-8577-0B6AF96C117D" \
          "&format=json"%work["WORKORDERID"]

    response = requests.get(url)
    print (response.content)

    parsed = json.loads(response.content)
    #data.write(soup.get_text().encode('ascii', 'ignore').decode('ascii'))
    #soup = BeautifulSoup(parsed["operation"]["details"][12]["VALUE"],"html.parser")
    #print(soup.get_text())
    #print(word_tokenize(soup.get_text()))
    #print ("\n\n\n")
