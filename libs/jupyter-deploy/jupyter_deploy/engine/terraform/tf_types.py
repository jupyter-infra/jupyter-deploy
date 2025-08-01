from enum import Enum


class TerraformType(str, Enum):
    """The 'type' attribute in the variables.tf file as surfaced by python-hcl2."""

    STRING = "string"
    NUMBER = "number"
    BOOL = "bool"
    LIST_STR = "${list(string)}"
    MAP_STR = "${map(string)}"
    LIST_MAP_STR = "${list(map(string))}"
