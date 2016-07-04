import re

from ikyActions import actions


# ORACLE database connection
# import cx_Oracle

def executeAction(actionType, action, parameters):
    types = {
        1: python_function,
        2: sql_query,
        3: rest_api,
        4: custom_message
    }
    return types[int(actionType)](action, parameters)


def python_function(action, parameters):
    # result = globals()["action"](parameters)
    result = getattr(actions, action)(parameters)
    return result


def sql_query(action, parameters):
    _query = re.sub(r'\{([a-z_0-9]*)\}', lambda m: "'" + parameters[m.group(1)] + "'", action)
    print(_query)
    connstr = 'mambo/luexmambo@172.30.13.172/mambodev'
    conn = cx_Oracle.connect(connstr)
    curs = conn.cursor()
    try:
        curs.execute(_query)
        return str(curs.fetchall())[0]
    except:
        return "Sql Error"


def rest_api(action, parameters):
    result = requests.get(action, data=parameters)
    return result.text


def custom_message(action, parameters):
    output = re.sub(r'\{([a-z_0-9]*)\}', lambda m: parameters[m.group(1)], action)
    return output
