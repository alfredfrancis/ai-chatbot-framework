def is_list_empty(inList):
    if isinstance(inList, list):  # Is a list
        return all(map(is_list_empty, inList))
    return False  # Not a list
