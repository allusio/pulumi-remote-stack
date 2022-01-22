from __future__ import annotations

import subprocess

import pulumi


def subprocess_run(args, cwd=None, env=None):
    try:
        return subprocess.run(
            args,
            check=True,
            text=True,
            capture_output=True,
            cwd=cwd,
            env=env or {},
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        cmd = ' '.join(args)
        error = exc.stderr.strip()
        ls = subprocess.run(
            "ls",
            check=True,
            text=True,
            capture_output=True,
            cwd=cwd,
        ).stdout.strip()
        pulumi.error(f"{cmd}:\n{error}\n\nls:\n{ls}")
        raise
