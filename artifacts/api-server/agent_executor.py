"""
Bera AI Agent Executor
Executes real file system, bash, and GitHub operations on the server.
"""
import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

WORKSPACE_DIR = Path(os.getenv("AGENT_WORKSPACE", "/tmp/bera-workspace"))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

GITHUB_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN", "")

BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/[^t]",
    r":(){ :|:& };:",
    r"dd\s+if=",
    r"mkfs\.",
    r">\s*/dev/sda",
    r"chmod\s+-R\s+777\s+/",
    r"shutdown",
    r"reboot",
    r"halt",
    r"init\s+0",
]

MAX_OUTPUT = 4000
CMD_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "30"))


def _is_blocked(cmd: str) -> bool:
    for pat in BLOCKED_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return True
    return False


def _truncate(s: str, n: int = MAX_OUTPUT) -> str:
    if len(s) <= n:
        return s
    return s[:n] + f"\n... [truncated — {len(s) - n} chars omitted]"


def _safe_path(rel: str) -> Path:
    """Resolve a path relative to workspace, preventing directory traversal."""
    base = WORKSPACE_DIR.resolve()
    target = (base / rel.lstrip("/")).resolve()
    if not str(target).startswith(str(base)):
        raise PermissionError(f"Access denied: {rel} is outside the workspace")
    return target


class ActionResult:
    def __init__(self, success: bool, output: str, action: str):
        self.success = success
        self.output = output
        self.action = action

    def to_dict(self):
        return {"success": self.success, "output": self.output, "action": self.action}


# ── File & Folder Operations ────────────────────────────────────────────────

async def create_directory(path: str) -> ActionResult:
    try:
        p = _safe_path(path)
        p.mkdir(parents=True, exist_ok=True)
        return ActionResult(True, f"✅ Directory created: {p.relative_to(WORKSPACE_DIR)}", "mkdir")
    except Exception as e:
        return ActionResult(False, f"❌ mkdir failed: {e}", "mkdir")


async def delete_path(path: str) -> ActionResult:
    try:
        p = _safe_path(path)
        if not p.exists():
            return ActionResult(False, f"❌ Not found: {path}", "delete")
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return ActionResult(True, f"✅ Deleted: {path}", "delete")
    except Exception as e:
        return ActionResult(False, f"❌ delete failed: {e}", "delete")


async def write_file(path: str, content: str) -> ActionResult:
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        size = len(content.encode())
        return ActionResult(True, f"✅ File written: {path} ({size} bytes)", "write_file")
    except Exception as e:
        return ActionResult(False, f"❌ write_file failed: {e}", "write_file")


async def read_file(path: str) -> ActionResult:
    try:
        p = _safe_path(path)
        if not p.exists():
            return ActionResult(False, f"❌ File not found: {path}", "read_file")
        content = p.read_text(encoding="utf-8", errors="replace")
        return ActionResult(True, _truncate(content), "read_file")
    except Exception as e:
        return ActionResult(False, f"❌ read_file failed: {e}", "read_file")


async def list_directory(path: str = ".") -> ActionResult:
    try:
        p = _safe_path(path)
        if not p.exists():
            return ActionResult(False, f"❌ Path not found: {path}", "ls")
        items = []
        for item in sorted(p.iterdir()):
            icon = "📁" if item.is_dir() else "📄"
            size = f" ({item.stat().st_size}B)" if item.is_file() else ""
            items.append(f"  {icon} {item.name}{size}")
        if not items:
            return ActionResult(True, f"📂 {path} (empty)", "ls")
        return ActionResult(True, f"📂 {path}:\n" + "\n".join(items), "ls")
    except Exception as e:
        return ActionResult(False, f"❌ ls failed: {e}", "ls")


# ── Bash Command Execution ──────────────────────────────────────────────────

async def run_bash(command: str, cwd: Optional[str] = None) -> ActionResult:
    if _is_blocked(command):
        return ActionResult(False, f"❌ Blocked command: {command}", "bash")
    work_dir = str(WORKSPACE_DIR)
    if cwd:
        try:
            work_dir = str(_safe_path(cwd))
        except Exception:
            pass
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=work_dir,
            env={**os.environ, "HOME": str(WORKSPACE_DIR)},
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=CMD_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            return ActionResult(False, f"❌ Command timed out after {CMD_TIMEOUT}s", "bash")
        output = stdout.decode("utf-8", errors="replace").strip()
        success = proc.returncode == 0
        prefix = "✅" if success else "❌"
        return ActionResult(success, f"{prefix} $ {command}\n{_truncate(output) if output else '(no output)'}", "bash")
    except Exception as e:
        return ActionResult(False, f"❌ bash error: {e}", "bash")


# ── GitHub Operations ────────────────────────────────────────────────────────

async def github_create_repo(name: str, description: str = "", private: bool = False) -> ActionResult:
    if not GITHUB_TOKEN:
        return ActionResult(False, "❌ GITHUB_PERSONAL_ACCESS_TOKEN not set", "github_create_repo")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                "https://api.github.com/user/repos",
                headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={"name": name, "description": description, "private": private, "auto_init": True},
            )
            if r.status_code in (200, 201):
                data = r.json()
                return ActionResult(True, f"✅ Repo created: {data['html_url']}", "github_create_repo")
            elif r.status_code == 422:
                data = r.json()
                return ActionResult(False, f"❌ Repo creation failed: {data.get('message', 'already exists?')}", "github_create_repo")
            else:
                return ActionResult(False, f"❌ GitHub API error {r.status_code}: {r.text[:200]}", "github_create_repo")
    except Exception as e:
        return ActionResult(False, f"❌ GitHub error: {e}", "github_create_repo")


async def github_list_repos() -> ActionResult:
    if not GITHUB_TOKEN:
        return ActionResult(False, "❌ GITHUB_PERSONAL_ACCESS_TOKEN not set", "github_list_repos")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                "https://api.github.com/user/repos?per_page=20&sort=updated",
                headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            r.raise_for_status()
            repos = r.json()
            lines = [f"  {'🔒' if repo['private'] else '🌐'} {repo['full_name']} — {repo.get('description') or 'no description'}" for repo in repos]
            return ActionResult(True, f"📦 Your repos ({len(repos)}):\n" + "\n".join(lines), "github_list_repos")
    except Exception as e:
        return ActionResult(False, f"❌ GitHub error: {e}", "github_list_repos")


async def github_push_directory(local_dir: str, repo_full_name: str, commit_msg: str = "update") -> ActionResult:
    if not GITHUB_TOKEN:
        return ActionResult(False, "❌ GITHUB_PERSONAL_ACCESS_TOKEN not set", "github_push")
    try:
        p = _safe_path(local_dir)
        if not p.exists():
            return ActionResult(False, f"❌ Directory not found: {local_dir}", "github_push")

        # Set up git config + remote
        cmds = [
            "git config --global user.email 'bera-ai@bera-tech.dev'",
            "git config --global user.name 'Bera AI'",
        ]
        for c in cmds:
            proc = await asyncio.create_subprocess_shell(c, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()

        remote_url = f"https://{GITHUB_TOKEN}@github.com/{repo_full_name}.git"
        git_cmds = [
            f"git -C {p} init",
            f"git -C {p} add -A",
            f"git -C {p} commit -m '{commit_msg}' --allow-empty",
            f"git -C {p} branch -M main",
            f"git -C {p} remote remove origin 2>/dev/null; git -C {p} remote add origin {remote_url}",
            f"git -C {p} push -u origin main --force",
        ]
        output_lines = []
        for cmd in git_cmds:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            output_lines.append(out.decode("utf-8", errors="replace").strip())

        return ActionResult(True, f"✅ Pushed to https://github.com/{repo_full_name}\n\n" + "\n".join(output_lines[-3:]), "github_push")
    except Exception as e:
        return ActionResult(False, f"❌ git push error: {e}", "github_push")


# ── Intent Parser for Agent Mode ────────────────────────────────────────────

INTENT_PATTERNS = [
    # mkdir / create folder
    (r"(?:create|make|mkdir|new)\s+(?:a\s+)?(?:folder|directory|dir)\s+(?:called\s+|named\s+)?[\"']?([^\s\"']+)[\"']?", "mkdir"),
    # delete
    (r"(?:delete|remove|rm)\s+(?:the\s+)?(?:folder|directory|dir|file)?\s*[\"']?([^\s\"']+)[\"']?", "delete"),
    # write/create file
    (r"(?:create|write|make)\s+(?:a\s+)?file\s+(?:at\s+|called\s+|named\s+)?[\"']?([^\s\"']+)[\"']?(?:\s+with\s+content\s+(.+))?", "write_file"),
    # read file
    (r"(?:read|show|cat|view)\s+(?:the\s+)?file\s+[\"']?([^\s\"']+)[\"']?", "read_file"),
    # list
    (r"(?:list|ls|show)\s+(?:files|contents?)\s+(?:in\s+|of\s+)?[\"']?([^\s\"']*)[\"']?", "ls"),
    # run bash
    (r"(?:run|execute|bash|shell|cmd)\s*:?\s*(.+)", "bash"),
    # GitHub
    (r"(?:create|new)\s+(?:github\s+)?repo\s+(?:called\s+|named\s+)?[\"']?([^\s\"']+)[\"']?", "github_create_repo"),
    (r"(?:list|show)\s+(?:my\s+)?(?:github\s+)?repos?", "github_list_repos"),
    (r"(?:push|deploy)\s+(?:to\s+)?github\s+(?:repo\s+)?[\"']?([^\s\"']+)[\"']?", "github_push"),
]


async def execute_agent_task(task: str) -> list[ActionResult]:
    """
    Parse natural language task and execute real actions.
    Returns list of ActionResults.
    """
    task_lower = task.lower().strip()
    results = []

    for pattern, intent in INTENT_PATTERNS:
        m = re.search(pattern, task_lower, re.IGNORECASE | re.DOTALL)
        if m:
            groups = [g for g in m.groups() if g]
            if intent == "mkdir":
                path = groups[0] if groups else "new-folder"
                results.append(await create_directory(path))

            elif intent == "delete":
                path = groups[0] if groups else ""
                if path:
                    results.append(await delete_path(path))

            elif intent == "write_file":
                path = groups[0] if groups else "output.txt"
                content = groups[1] if len(groups) > 1 else ""
                results.append(await write_file(path, content))

            elif intent == "read_file":
                path = groups[0] if groups else ""
                if path:
                    results.append(await read_file(path))

            elif intent == "ls":
                path = groups[0] if groups else "."
                results.append(await list_directory(path or "."))

            elif intent == "bash":
                cmd = m.group(1).strip()
                results.append(await run_bash(cmd))

            elif intent == "github_create_repo":
                name = groups[0] if groups else "new-repo"
                results.append(await github_create_repo(name))

            elif intent == "github_list_repos":
                results.append(await github_list_repos())

            elif intent == "github_push":
                repo = groups[0] if groups else ""
                if repo:
                    results.append(await github_push_directory(".", repo))

            if results:
                return results

    # Fallback: try running as raw bash command if it looks like one
    if any(task.startswith(kw) for kw in ("ls", "mkdir", "touch", "cat", "echo", "cd", "npm", "node", "python", "git", "pip")):
        results.append(await run_bash(task))
        return results

    return []


async def push_project_to_github(local_path: str, repo_name: str, description: str = "") -> list[ActionResult]:
    """Helper: create GitHub repo and push local directory."""
    results = []
    create_result = await github_create_repo(repo_name, description)
    results.append(create_result)
    if create_result.success:
        # Get the authenticated username
        username = ""
        if GITHUB_TOKEN:
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.get("https://api.github.com/user", headers={"Authorization": f"token {GITHUB_TOKEN}"})
                    username = r.json().get("login", "")
            except Exception:
                pass
        if username:
            push_result = await github_push_directory(local_path, f"{username}/{repo_name}", f"Initial commit: {repo_name}")
            results.append(push_result)
    return results
