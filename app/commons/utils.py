from datetime import datetime
import parsedatetime as pdt
from typing import Dict, Any, List

def date_from_string(time_string: str) -> str:
    """Convert a string time to datetime string"""
    cal = pdt.Calendar()
    now = datetime.now()
    result = str(cal.parseDT(time_string.strip(), now)[0])
    return result

def prepare_document(data_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare a dictionary for MongoDB document insertion/update
    """
    # Convert _id to id if present
    if "_id" in data_dict:
        data_dict["id"] = data_dict.pop("_id")
    
    # Handle nested dictionaries and lists
    for key, value in data_dict.items():
        if isinstance(value, dict):
            data_dict[key] = prepare_document(value)
        elif isinstance(value, list):
            data_dict[key] = [
                prepare_document(item) if isinstance(item, dict) else item
                for item in value
            ]
    
    return data_dict

def is_list_empty(in_list: List[Any]) -> bool:
    """Check if a list or nested list is empty"""
    if isinstance(in_list, list):
        return all(map(is_list_empty, in_list))
    return False

def serialize_object_id(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB ObjectId to string in document"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "_id":
                obj[key] = str(value)
            elif isinstance(value, (dict, list)):
                obj[key] = serialize_object_id(value)
    elif isinstance(obj, list):
        return [serialize_object_id(item) for item in obj]
    return obj
