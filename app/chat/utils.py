import json
import logging
import requests
from jinja2 import Undefined
from app.main import app
from app.database import find_many

logger = logging.getLogger(__name__)

def split_sentence(sentence):
    return sentence.split("###")

async def get_synonyms():
    """
    Build synonyms dict from DB
    :return: Dictionary of synonyms
    """
    synonyms = {}
    entities = await find_many("entities", {})
    
    for entity in entities:
        for value in entity.get("entityValues", []):
            for synonym in value.get("synonyms", []):
                synonyms[synonym] = value.get("value")
    
    logger.info("loaded synonyms %s", synonyms)
    return synonyms

async def call_api(url, type, headers={}, parameters={}, is_json=False):
    """
    Call external API
    :param url: API endpoint URL
    :param type: HTTP method (GET, POST, PUT, DELETE)
    :param headers: Request headers
    :param parameters: Request parameters or body
    :param is_json: Whether to send parameters as JSON
    :return: JSON response
    """
    logger.info("Initiating API Call with following info: url => %s payload => %s", url, parameters)
    
    try:
        if "GET" in type:
            response = requests.get(url, headers=headers, params=parameters, timeout=5)
        elif "POST" in type:
            if is_json:
                response = requests.post(url, headers=headers, json=parameters, timeout=5)
            else:
                response = requests.post(url, headers=headers, params=parameters, timeout=5)
        elif "PUT" in type:
            if is_json:
                response = requests.put(url, headers=headers, json=parameters, timeout=5)
            else:
                response = requests.put(url, headers=headers, params=parameters, timeout=5)
        elif "DELETE" in type:
            response = requests.delete(url, headers=headers, params=parameters, timeout=5)
        else:
            raise ValueError("Unsupported request method.")
        
        result = response.json()
        logger.info("API response => %s", result)
        return result
    except requests.exceptions.RequestException as e:
        logger.error("API call failed: %s", str(e))
        raise

class SilentUndefined(Undefined):
    """
    Class to suppress jinja2 errors and warnings
    """
    def _fail_with_undefined_error(self, *args, **kwargs):
        return 'undefined'

    __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = \
        __truediv__ = __rtruediv__ = __floordiv__ = __rfloordiv__ = \
        __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = \
        __getitem__ = __lt__ = __le__ = __gt__ = __ge__ = __int__ = \
        __float__ = __complex__ = __pow__ = __rpow__ = \
        _fail_with_undefined_error
