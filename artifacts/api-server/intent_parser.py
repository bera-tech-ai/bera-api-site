"""
Natural language intent parser for Bruce Bera AI API.
Detects whether a message needs AI answering, SSH actions, or both.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedIntent:
    needs_ai: bool = False
    needs_ssh: bool = False
    ssh_commands: list = field(default_factory=list)
    ai_query: Optional[str] = None


# ─── SSH action pattern registry ────────────────────────────────────────────

_SSH_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Directory creation
    (re.compile(r"(?:create|make|mkdir)\s+(?:a\s+)?(?:folder|directory|dir)\s+(?:called\s+|named\s+)?['\"]?(\S+)['\"]?", re.I), "create_folder"),
    # File writing
    (re.compile(r"(?:write|create|make)\s+(?:a\s+)?file\s+(?:called\s+|named\s+)?['\"]?(\S+)['\"]?(?:\s+with\s+(?:content\s+)?(.+))?", re.I), "write_file"),
    # List / show files
    (re.compile(r"(?:list|show|ls)\s+(?:(?:the\s+)?(?:files|contents?|dir|directory)(?:\s+(?:in\s+)?(?:here|current|this))?|(?:current\s+)?(?:directory|folder))", re.I), "list_files"),
    # Read file
    (re.compile(r"(?:read|cat|show|display|print)\s+(?:the\s+)?(?:file\s+)?['\"]?([^\s]+\.[a-zA-Z0-9]+)['\"]?", re.I), "read_file"),
    # Delete
    (re.compile(r"(?:delete|remove|rm)\s+(?:the\s+)?(?:folder|directory|dir|file)?\s*['\"]?(\S+)['\"]?", re.I), "delete"),
    # Run npm install
    (re.compile(r"(?:run\s+)?npm\s+install", re.I), "npm_install"),
    # Create React app
    (re.compile(r"create\s+(?:a\s+)?(?:new\s+)?react\s+app\s+(?:called\s+|named\s+)?['\"]?(\S+)['\"]?", re.I), "create_react_app"),
    # Python venv
    (re.compile(r"(?:set\s+up|create|make)\s+(?:a\s+)?(?:python\s+)?(?:virtual\s+env(?:ironment)?|venv)", re.I), "create_venv"),
    # System info
    (re.compile(r"(?:show|display|get|what(?:'s|\s+is))\s+(?:me\s+)?(?:system\s+info(?:rmation)?|disk\s+(?:space|usage)|memory\s+(?:usage|info)|cpu\s+info)", re.I), "system_info"),
    # Port check
    (re.compile(r"(?:what(?:'s|\s+is)\s+)?(?:using|running\s+on)\s+port\s+(\d+)", re.I), "check_port"),
    # Restart nginx / apache / service
    (re.compile(r"restart\s+(?:the\s+)?(\S+)", re.I), "restart_service"),
    # Install package
    (re.compile(r"install\s+(?:the\s+)?(?:package\s+)?['\"]?(\S+)['\"]?", re.I), "install_package"),
    # Run command
    (re.compile(r"run\s+(?:the\s+)?(?:command\s+)?['\"]?(.+)['\"]?", re.I), "run_command"),
]

# Keywords that strongly indicate an SSH intent
_SSH_KEYWORDS = [
    "server", "terminal", "ssh", "bash", "shell", "command", "execute",
    "folder", "directory", "file", "files", "mkdir", "ls", "cd", "rm",
    "install", "npm", "pip", "apt", "yum", "restart", "nginx", "apache",
    "python", "node", "venv", "deploy", "port", "process", "systemctl",
]

# Security blacklist (regex patterns that map to dangerous commands)
_BLOCKED_PATTERNS = [
    re.compile(r"rm\s+-rf\s+/\s*$", re.I),
    re.compile(r"rm\s+-rf\s+/\*", re.I),
    re.compile(r"chmod\s+777\s+/", re.I),
    re.compile(r"dd\s+if=/dev/zero", re.I),
    re.compile(r":\(\)\s*\{\s*:\|:", re.I),  # fork bomb
    re.compile(r"mkfs\.", re.I),
    re.compile(r"\bfdisk\b", re.I),
    re.compile(r"format\s+[a-zA-Z]:", re.I),
]


def is_blocked_command(cmd: str) -> bool:
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(cmd):
            return True
    return False


def _build_ssh_command(action: str, message: str) -> Optional[str]:
    """Map a detected action + message to an actual shell command."""
    if action == "create_folder":
        m = re.search(
            r"(?:folder|directory|dir)\s+(?:called\s+|named\s+)?['\"]?(\S+)['\"]?",
            message, re.I,
        )
        name = m.group(1).strip("\"'") if m else "new_folder"
        return f"mkdir -p ~/{name}"

    if action == "write_file":
        m = re.search(
            r"file\s+(?:called\s+|named\s+)?['\"]?(\S+)['\"]?(?:\s+with\s+(?:content\s+)?(.+))?",
            message, re.I,
        )
        if m:
            fname = m.group(1).strip("\"'")
            content = (m.group(2) or "").strip().strip("\"'") or ""
            return f"echo {repr(content)} > ~/{fname}"
        return None

    if action == "list_files":
        return "ls -la"

    if action == "read_file":
        m = re.search(r"['\"]?([^\s]+\.[a-zA-Z0-9]+)['\"]?", message, re.I)
        fname = m.group(1).strip("\"'") if m else "file"
        return f"cat ~/{fname}"

    if action == "delete":
        # Extract target name, only allow non-root paths
        m = re.search(
            r"(?:delete|remove|rm)\s+(?:the\s+)?(?:folder|directory|file)?\s*['\"]?(\S+)['\"]?",
            message, re.I,
        )
        target = (m.group(1) if m else "").strip("\"'/")
        if not target or target in ("/", "/*", "."):
            return None
        return f"rm -rf ~/{target}"

    if action == "npm_install":
        return "npm install"

    if action == "create_react_app":
        m = re.search(
            r"react\s+app\s+(?:called\s+|named\s+)?['\"]?(\S+)['\"]?", message, re.I
        )
        name = m.group(1).strip("\"'") if m else "my-app"
        return f"npx create-react-app {name}"

    if action == "create_venv":
        return "python3 -m venv venv"

    if action == "system_info":
        return "df -h && echo '---' && free -m && echo '---' && top -bn1 | head -20"

    if action == "check_port":
        m = re.search(r"port\s+(\d+)", message, re.I)
        port = m.group(1) if m else "80"
        return f"lsof -i :{port}"

    if action == "restart_service":
        m = re.search(r"restart\s+(?:the\s+)?(\S+)", message, re.I)
        svc = m.group(1) if m else "nginx"
        return f"sudo systemctl restart {svc}"

    if action == "install_package":
        m = re.search(r"install\s+(?:package\s+)?['\"]?(\S+)['\"]?", message, re.I)
        pkg = m.group(1).strip("\"'") if m else None
        if pkg:
            # Guess package manager context
            if any(w in message.lower() for w in ["pip", "python"]):
                return f"pip install {pkg}"
            elif any(w in message.lower() for w in ["npm", "node", "javascript"]):
                return f"npm install {pkg}"
            elif any(w in message.lower() for w in ["apt"]):
                return f"sudo apt-get install -y {pkg}"
            else:
                return f"pip install {pkg}"

    if action == "run_command":
        m = re.search(r"run\s+(?:command\s+)?['\"]?(.+)['\"]?", message, re.I)
        if m:
            cmd = m.group(1).strip("\"'")
            return cmd

    return None


def _has_ssh_keyword(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in _SSH_KEYWORDS)


def _is_question(message: str) -> bool:
    """Heuristic: does the message ask for information / knowledge?"""
    question_words = [
        "what", "how", "why", "when", "who", "where", "explain",
        "tell me", "describe", "define", "meaning", "difference between",
        "is it", "are they", "can you explain",
    ]
    lower = message.lower()
    if message.strip().endswith("?"):
        return True
    for qw in question_words:
        if lower.startswith(qw) or f" {qw} " in lower:
            return True
    return False


def parse_intent(message: str) -> ParsedIntent:
    """
    Analyse the user message and return a ParsedIntent.
    Both needs_ai and needs_ssh can be True for mixed messages.
    """
    intent = ParsedIntent()
    commands: list[str] = []

    lower = message.lower()

    # Detect SSH actions via pattern registry
    for pattern, action in _SSH_PATTERNS:
        if pattern.search(message):
            cmd = _build_ssh_command(action, message)
            if cmd and not is_blocked_command(cmd):
                commands.append(cmd)
            break  # one primary action per message (they can chain multiple requests)

    # Also pick up multi-action phrases (e.g. "create X AND tell me about Y")
    # by scanning the full message for multiple action words
    if not commands and _has_ssh_keyword(lower):
        # Try to identify a generic command request
        for pattern, action in _SSH_PATTERNS:
            if pattern.search(message):
                cmd = _build_ssh_command(action, message)
                if cmd and not is_blocked_command(cmd):
                    commands.append(cmd)

    intent.needs_ssh = bool(commands)
    intent.ssh_commands = commands

    # Determine if an AI knowledge query is also needed
    # Heuristic: has question words, or has "and" / "also" followed by a question
    has_question = _is_question(message)
    has_explain = any(
        kw in lower
        for kw in ["explain", "what is", "what are", "tell me about", "how does",
                   "define", "describe", "meaning of"]
    )
    has_both_keywords = re.search(r"\b(and|also|plus)\b", lower) is not None

    if has_question or has_explain:
        intent.needs_ai = True
    elif not intent.needs_ssh:
        # Default: treat as AI query
        intent.needs_ai = True
    elif has_both_keywords and has_question:
        intent.needs_ai = True

    # If pure SSH (e.g. "create folder X"), don't call AI
    if intent.needs_ssh and not has_question and not has_explain:
        intent.needs_ai = False

    # Extract the AI query portion (strip SSH-specific parts)
    if intent.needs_ai:
        # Remove common SSH-specific phrases to leave the AI question
        ai_q = re.sub(
            r"(?:create|make|mkdir)\s+(?:a\s+)?(?:folder|directory)[^\n.,;]*",
            "", message, flags=re.I,
        ).strip(" ,and")
        ai_q = ai_q if ai_q else message
        intent.ai_query = ai_q

    return intent
