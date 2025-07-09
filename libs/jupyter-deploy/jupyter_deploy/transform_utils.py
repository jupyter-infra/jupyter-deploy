from collections.abc import Callable
from typing import Any

from jupyter_deploy import str_utils
from jupyter_deploy.enum import TransformType


def _no_transform_fn(value: Any) -> Any:
    return value


def _comma_sep_str_to_list_str(value: str) -> list[str]:
    return str_utils.to_list_str(value, sep=",")


_TRANSFORM_FN_MAP: dict[TransformType, Callable] = {
    TransformType.NO_TRANSFORM: _no_transform_fn,
    TransformType.COMMA_SEPARATED_STR_TO_LIST_STR: _comma_sep_str_to_list_str,
}


def get_transform_fn(transform: TransformType) -> Callable:
    """Return the transform function."""
    return _TRANSFORM_FN_MAP[transform]
