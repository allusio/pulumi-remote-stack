from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import threading
from typing import TypedDict

import pulumi
from pulumi.automation import (
    ConfigValue as _PulumiConfigValue, LocalWorkspace, LocalWorkspaceOptions,
    ProjectBackend, ProjectSettings, PulumiFn, StackSettings, create_or_select_stack,
    create_stack,
)
from pulumi.dynamic import CreateResult, DiffResult, ResourceProvider, UpdateResult

from .config import _ConfigValue
from .subprocess_run import subprocess_run


class _Inputs(TypedDict):
    project_name: str
    stack_name: str
    backend_url: str
    secrets_provider: str
    backend_azure_storage_account: str
    config: dict[str, _ConfigValue]
    secrets: dict[str, _ConfigValue]
    only_create: bool


def generate_user_sas(azure_storage_account: str) -> str:
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=20)).strftime(
        '%Y-%m-%dT%H:%MZ'
    )
    return subprocess_run(
        [
            "az", "storage", "container", "generate-sas", "--account-name",
            azure_storage_account, "--name", "pulumi", "--permissions", "acdlrw",
            "--expiry", expiry, "--as-user", "--auth-mode", "login", "-o", "tsv"
        ],
        env=os.environ,
    )


def generate_program(
    stack_config: dict[str, _ConfigValue],
    stack_secrets: dict[str, _ConfigValue]
) -> PulumiFn:
    def _pulumi_program() -> None:
        config = pulumi.Config()

        def export_all(source, secrets):
            if secrets:
                secret = "_secret"
            else:
                secret = ""

            for name, value_dict in source.items():
                typ = value_dict["type"]
                if typ == "str":
                    kind = ""
                else:
                    kind = f"_{typ}"
                method_name = f"get{secret}{kind}"
                pulumi.export(name, getattr(config, method_name)(name))

        export_all(stack_config, False)
        export_all(stack_secrets, True)

    return _pulumi_program


lock = threading.Lock()


class RemoteStackProvider(ResourceProvider):

    def _setup_project_stack(self, inputs: _Inputs, old_inputs: _Inputs = None):
        project_name = inputs['project_name']
        stack_name = inputs['stack_name']
        backend_url = inputs['backend_url']
        backend_azure_storage_account = inputs['backend_azure_storage_account']
        secrets_provider = inputs['secrets_provider']
        config = inputs['config']
        secrets = inputs['secrets']
        only_create = inputs['only_create']

        env_vars = {
            "PULUMI_CONFIG_PASSPHRASE": "",
            "PULUMI_BACKEND_URL": backend_url,
        }

        if backend_azure_storage_account:
            env_vars.update({
                'AZURE_STORAGE_ACCOUNT': backend_azure_storage_account,
                'AZURE_STORAGE_SAS_TOKEN': generate_user_sas(
                    backend_azure_storage_account
                ),
            })

        pulumi_program = generate_program(config, secrets)

        project_settings = ProjectSettings(
            name=project_name,
            runtime="python",
            backend=ProjectBackend(url=backend_url),
        )

        stack_settings = StackSettings(
            secrets_provider=secrets_provider,
        )

        kwargs = {
            "project_name": project_name,
            "stack_name": stack_name,
            "program": pulumi_program,
            "opts": LocalWorkspaceOptions(
                project_settings=project_settings,
                secrets_provider=secrets_provider,
                stack_settings={stack_name: stack_settings},
                env_vars=env_vars,
            )
        }
        with lock:  # TODO lock because of https://github.com/pulumi/pulumi/issues/6052
            if only_create:
                create_stack(**kwargs)
                return
            else:
                stack = create_or_select_stack(**kwargs)

            stack_config = (
                {
                    key: _PulumiConfigValue(
                        value=config_value["value"],
                        secret=False,
                    )
                    for key, config_value in config.items()
                } | {
                    key: _PulumiConfigValue(
                        value=config_value["value"],
                        secret=True,
                    )
                    for key, config_value in secrets.items()
                }
            )

            if old_inputs:
                old_config_keys = (
                    old_inputs["config"].keys() | old_inputs["secrets"].keys()
                )
                for key in old_config_keys:
                    if key not in stack_config:
                        stack.remove_config(key)

            stack.set_all_config(stack_config)
            stack.up()

    def create(self, inputs: _Inputs):
        project_name = inputs['project_name']
        stack_name = inputs['stack_name']
        self._setup_project_stack(inputs)
        return CreateResult(f"{project_name}-{stack_name}", outs=inputs)

    def delete(self, id: str, inputs: _Inputs):
        # TODO think about edge cases
        project_name = inputs['project_name']
        stack_name = inputs['stack_name']
        backend_url = inputs['backend_url']
        backend_azure_storage_account = inputs['backend_azure_storage_account']

        env_vars = {
            "PULUMI_CONFIG_PASSPHRASE": "",
            "PULUMI_BACKEND_URL": backend_url,
        }

        if backend_azure_storage_account:
            env_vars.update({
                'AZURE_STORAGE_ACCOUNT': backend_azure_storage_account,
                'AZURE_STORAGE_SAS_TOKEN': generate_user_sas(
                    backend_azure_storage_account),
            })

        project_settings = ProjectSettings(
            name=project_name,
            runtime="python",
            backend=ProjectBackend(url=backend_url),
        )

        local_workspace = LocalWorkspace(
            project_settings=project_settings,
            env_vars=env_vars,
        )

        local_workspace._run_pulumi_cmd_sync(
            # TODO fill pulumi issue --force in remove_stack
            ["stack", "rm", "--yes", "--force", stack_name]
        )

    def diff(self, id: str, old_inputs: _Inputs, new_inputs: _Inputs):
        replaces = []
        if old_inputs["backend_url"] != new_inputs["backend_url"]:
            replaces.append("backend_url")
        if old_inputs["project_name"] != new_inputs["project_name"]:
            replaces.append("project_name")
        if old_inputs["stack_name"] != new_inputs["stack_name"]:
            replaces.append("stack_name")
        return DiffResult(
            changes=old_inputs != new_inputs,
            replaces=replaces,
            stables=None,
            delete_before_replace=True
        )

    def update(self, id: str, old_inputs: _Inputs, new_inputs: _Inputs):
        self._setup_project_stack(new_inputs, old_inputs)
        return UpdateResult(outs=new_inputs)
