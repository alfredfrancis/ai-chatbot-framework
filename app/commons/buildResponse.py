from flask import Response
import json


def buildJson(result):
    return Response(response=json.dumps(result),
                    status=200,
                    mimetype="application/json")


def sentJson(result):
    return Response(response=result,
                    status=200,
                    mimetype="application/json")


def sentOk():
    return Response(response=json.dumps({"result": True}),
                    status=200,
                    mimetype="application/json")


def sentPlainText(result):
    return Response(response=result.strip(), status=200, mimetype="text")
