def is_list_str_repr(arg: object) -> bool:
    """Return True if the argument is a list[str]."""
    return isinstance(arg, list) and len(arg) >= 2 and arg[0] == "list" and arg[1] in ["string", "str", "dynamic"]
