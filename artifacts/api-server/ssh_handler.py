"""
Async SSH connection and command execution for Bruce Bera AI API.
Uses paramiko in a thread-pool to keep FastAPI async-friendly.
"""
import asyncio
import io
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import paramiko

logger = logging.getLogger(__name__)

SSH_TIMEOUT = int(os.getenv("SSH_TIMEOUT", "10"))
COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "60"))


@dataclass
class SshResult:
    stdout: str
    stderr: str
    exit_code: int
    command: str
    success: bool


def _sync_run_ssh(
    host: str,
    port: int,
    username: str,
    password: Optional[str],
    private_key: Optional[str],
    commands: list[str],
) -> list[SshResult]:
    """
    Synchronous SSH execution (runs in a thread via asyncio.run_in_executor).
    Returns one SshResult per command.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict = {
        "hostname": host,
        "port": port,
        "username": username,
        "timeout": SSH_TIMEOUT,
        "banner_timeout": SSH_TIMEOUT,
        "auth_timeout": SSH_TIMEOUT,
        "allow_agent": False,
        "look_for_keys": False,
    }

    if private_key:
        try:
            key_obj = paramiko.RSAKey.from_private_key(io.StringIO(private_key))
        except paramiko.ssh_exception.SSHException:
            try:
                key_obj = paramiko.Ed25519Key.from_private_key(io.StringIO(private_key))
            except Exception:
                raise ValueError("Could not parse the provided private key. Ensure it is PEM or OpenSSH format.")
        connect_kwargs["pkey"] = key_obj
    elif password:
        connect_kwargs["password"] = password
    else:
        raise ValueError("Either password or private_key must be provided for SSH authentication.")

    client.connect(**connect_kwargs)

    results: list[SshResult] = []
    for cmd in commands:
        logger.info("SSH [%s@%s:%s] > %s", username, host, port, cmd)
        _, stdout_ch, stderr_ch = client.exec_command(cmd, timeout=COMMAND_TIMEOUT)

        # Wait for channel with timeout
        deadline = time.time() + COMMAND_TIMEOUT
        while not stdout_ch.channel.exit_status_ready():
            if time.time() > deadline:
                stdout_ch.channel.close()
                break
            time.sleep(0.1)

        stdout_text = stdout_ch.read().decode("utf-8", errors="replace").strip()
        stderr_text = stderr_ch.read().decode("utf-8", errors="replace").strip()
        exit_code = stdout_ch.channel.recv_exit_status()

        results.append(
            SshResult(
                stdout=stdout_text,
                stderr=stderr_text,
                exit_code=exit_code,
                command=cmd,
                success=(exit_code == 0),
            )
        )

    client.close()
    return results


async def run_ssh_commands(
    host: str,
    port: int,
    username: str,
    password: Optional[str],
    private_key: Optional[str],
    commands: list[str],
) -> list[SshResult]:
    """
    Async wrapper around _sync_run_ssh.
    Runs in the default thread-pool executor.
    """
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(
        None,
        _sync_run_ssh,
        host,
        port,
        username,
        password,
        private_key,
        commands,
    )
    return results


def format_ssh_results(results: list[SshResult]) -> str:
    """Format SSH results into a human-readable string for the chat response."""
    parts: list[str] = []
    for r in results:
        if r.success:
            output = r.stdout or "(no output)"
            parts.append(f"✅ `{r.command}`\n```\n{output}\n```")
        else:
            error = r.stderr or r.stdout or f"Exit code {r.exit_code}"
            parts.append(f"❌ `{r.command}` failed\n```\n{error}\n```")
    return "\n\n".join(parts)
