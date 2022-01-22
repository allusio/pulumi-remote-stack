from __future__ import annotations

from functools import singledispatch
import json
from typing import Literal, TypedDict, Union

import pulumi
from pulumi import Output

_ConfigType = Literal["object", "str"]


class _ConfigValue(TypedDict):
    value: str
    type: _ConfigType


@singledispatch
def _config_value(value: Union[dict, list, int, bool]) -> _ConfigValue:
    return {
        "value": json.dumps(value),
        "type": "object",
    }


@_config_value.register
def _config_value_str(value: str) -> _ConfigValue:
    return {"value": value, "type": "str"}


ConfigValue = Union[dict, list, int, bool, str]


def config_value(value: ConfigValue) -> pulumi.Output[_ConfigValue]:
    return Output.from_input(value).apply(
        lambda val:
        _config_value(val)
    )
