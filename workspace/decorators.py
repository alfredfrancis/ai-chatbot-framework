import time
import logging
import random
from datetime import datetime as dt
from functools import wraps

logging.basicConfig(format='[%(asctime)s](%(filename)s#%(lineno)d)%(levelname)-7s %(message)s',
                    level=logging.NOTSET)


def intercept_me(intercepted_function):
    @wraps(intercepted_function)
    def hello(*args, **kwargs):
        '''*args and **kwargs are the parametrs that are supplied to our original function'''
        # get our actual function name
        function_name = intercepted_function.func_name()
        actual_result = intercepted_function(*args, **kwargs)
        return actual_result

    # return our inner function which will intercept the call
    return hello


@intercept_me
def some_slow_function():
    logging.info("Will sleep a bit..")
    time.sleep(1 + int((random.random() * 10) % 5))
    return 'boohoo'


for i in range(0, 10):
    logging.info("{0} Starting iter {1}{0}".format(20 * "=", i + 1))
    logging.info(some_slow_function())