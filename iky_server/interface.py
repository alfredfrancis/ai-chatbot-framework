from iky_server import app
import requests
import actions
import json
import re


# ORACLE database connection
# import cx_Oracle
def execute_action(action_type, action, parameters):
    types = {
        0: python_function,
        1: sql_query,
        2: rest_api,
        3: custom_message
    }
    return types[int(action_type)](action, parameters)


def python_function(action, parameters):
    # result = globals()["action"](parameters)
    result = getattr(actions, action)(parameters)
    return result


def sql_query(action, parameters):
    _query = re.sub(r'\{([a-z_0-9]*)\}', lambda m: "'" + parameters[m.group(1)] + "'", action)
    print(_query)
    connstr = 'mambo/luexmambo@172.30.13.201/EXCHDB'
    conn = cx_Oracle.connect(connstr)
    curs = conn.cursor()
    try:
        curs.execute(_query)
        return str(curs.fetchall())
    except:
        return "Sql Error"


def rest_api(action, parameters):
    result = requests.get(action, data=parameters)
    return result.text


def custom_message(action, parameters):
    output = re.sub(r'\{([a-z_0-9]*)\}', lambda m: parameters[m.group(1)], action)
    return output
