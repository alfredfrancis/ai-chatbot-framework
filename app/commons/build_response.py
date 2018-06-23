import json

from flask import Response


def build_json(result):
    return Response(response=json.dumps(result),
                    status=200,
                    mimetype="application/json")


def sent_json(result):
    return Response(response=result,
                    status=200,
                    mimetype="application/json")


def sent_ok():
    return Response(response=json.dumps({"result": True}),
                    status=200,
                    mimetype="application/json")


def sent_plain_text(result):
    return Response(response=result.strip(), status=200, mimetype="text")
