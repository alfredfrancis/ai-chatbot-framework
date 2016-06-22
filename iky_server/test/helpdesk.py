import requests
import json
payload = {
    "OPERATION_NAME":"ADD_REQUEST",
    "TECHNICIAN_KEY":"A2D2DEFC-C3BB-4F17-AB79-3215CAA07E34",
    "INPUT_DATA": {
        "operation":
            {
            "details":
                    {
                        "from": "0",
                        "limit": "50",
                        "filterby": "All_Requests"
                    }
            }
        }
    }

url = "http://172.30.10.101:/sdpapi/request"
response = requests.post(url, data=json.dumps(payload))

print response
print(response.content)
