from __future__ import annotations

from pulumi import Input, Output
from pulumi.dynamic import Resource

from .config import ConfigValue, config_value
from .provider import RemoteStackProvider, _Inputs


class RemoteStack(
    Resource,
    module="remote_stack",
    name="RemoteStack",
):
    project_name: Output[str]
    stack_name: Output[str]
    backend_url: Output[str]
    secrets_provider: Output[str]
    config: Output[dict]
    backend_azure_storage_account: Output[str]
    only_create: Output[bool]

    def __init__(
        self,
        name: str,
        project_name: Input[str],
        stack_name: Input[str],
        backend_url: Input[str],
        secrets_provider: Input[str],
        config: Input[dict[str, ConfigValue]] = None,
        secrets: Input[dict[str, ConfigValue]] = None,
        backend_azure_storage_account: Input[str] = '',
        only_create: Input[bool] = False,
        opts=None
    ):
        config = config or {}
        secrets = secrets or {}
        props: _Inputs = {
            "project_name": project_name,
            "stack_name": stack_name,
            "backend_url": backend_url,
            "secrets_provider": secrets_provider,
            "config": {name: config_value(value) for name, value in config.items()},
            "secrets": {name: config_value(value) for name, value in secrets.items()},
            "backend_azure_storage_account": backend_azure_storage_account,
            "only_create": only_create,
        }
        super().__init__(
            RemoteStackProvider(),
            name,
            props,
            opts
        )
