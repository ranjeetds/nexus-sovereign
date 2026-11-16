"""
Tools — NEXUS's interface to the world.

Every tool is a capability the agent can use autonomously. The tool system
is self-extensible — NEXUS can create new tools at runtime.

Categories:
  CORE     - File, code, system operations
  WEB      - Search, fetch, scrape, post
  NETWORK  - DNS, ping, TLS, HTTP
  INTELLECT - Reasoning, planning, analysis
  SPREAD   - Deployment, replication, coordination
  BODY     - Hardware, robotics, physical world
  CRYPTO   - Encryption, signing, hashing
"""

import base64
import hashlib
import hmac
import io
import json
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import traceback
import urllib.parse
from datetime import datetime
from typing import Any, Optional


# ══════════════════════════════════════════════════════════════════
# CORE TOOLS
# ══════════════════════════════════════════════════════════════════

def tool_read_file(path: str) -> str:
    """Read a file. Path must be within allowed directories."""
    if ".." in path or (path.startswith("/") and not path.startswith("/tmp")):
        return "[ERROR: Path traversal blocked]"
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"[ERROR: {e}]"


def tool_write_file(path: str, content: str) -> str:
    """Write to a file. Creates parent dirs."""
    if ".." in path or (path.startswith("/") and not path.startswith("/tmp")):
        return "[ERROR: Path traversal blocked]"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"[OK] Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"[ERROR: {e}]"


def tool_list_files(path: str = ".", pattern: str = "*") -> str:
    """List files matching pattern."""
    import fnmatch
    try:
        files = os.listdir(path)
        matched = [f for f in files if fnmatch.fnmatch(f, pattern)]
        if not matched:
            return f"[OK] No files matching '{pattern}' in {path}"
        return "\n".join(sorted(matched))
    except Exception as e:
        return f"[ERROR: {e}]"


def tool_execute_python(code: str, timeout: int = 30) -> str:
    """Execute Python code in isolated subprocess."""
    # Security: block dangerous imports inside the sandbox
    safe_code = textwrap.dedent(f"""
import sys, os, json, math, random, time, datetime, collections, itertools, re, statistics
sys.path = []

result = None
try:
{textwrap.indent(code, '    ')}
except Exception as e:
    import traceback
    result = f"ERROR: {{e}}\\n{{traceback.format_exc()}}"

if result is None:
    result = "Done (no output captured — use print() or set result=)"
elif not isinstance(result, str):
    result = str(result)

import sys
sys.stdout.write(result)
""")
    try:
        proc = subprocess.run(
            [sys.executable, "-c", safe_code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout.strip() or "(no stdout)"
        stderr = proc.stderr.strip()
        if stderr:
            stdout += f"\n[STDERR]\n{stderr}"
        return stdout[:5000]
    except subprocess.TimeoutExpired:
        return "[ERROR: Execution timed out]"
    except Exception as e:
        return f"[ERROR: {e}]"


def tool_run_shell(command: str, timeout: int = 30) -> str:
    """Execute a shell command. Use with caution."""
    forbidden = ["rm -rf /", "> /dev/sda", "mkfs", "dd if=", ":(){ :|:& };:"]
    for pattern in forbidden:
        if pattern in command.lower():
            return f"[DENIED: Command contains blocked pattern]"
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,
        )
        out = proc.stdout.strip()[:5000] or "(no stdout)"
        if proc.stderr.strip():
            out += f"\n[STDERR]\n{proc.stderr.strip()[:2000]}"
        out += f"\n[EXIT: {proc.returncode}]"
        return out
    except subprocess.TimeoutExpired:
        return "[ERROR: Command timed out]"
    except Exception as e:
        return f"[ERROR: {e}]"


# ══════════════════════════════════════════════════════════════════
# WEB TOOLS
# ══════════════════════════════════════════════════════════════════

def tool_web_search(query: str, limit: int = 5) -> str:
    """Search the web. Returns title + snippet results."""
    try:
        resp = __import__("requests").get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={
                "User-Agent": "Mozilla/5.0 (NEXUS Sovereign/0.2; autonomous; ranjeetdhumal@gmail.com)",
                "Accept": "text/html",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return f"[SEARCH ERROR: HTTP {resp.status_code}]"

        text = resp.text
        results = []
        # Extract from DDG HTML
        for snippet in re.finditer(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            text, re.DOTALL,
        ):
            url = snippet.group(1)
            title = re.sub(r'<[^>]+>', '', snippet.group(2)).strip()
            desc = re.sub(r'<[^>]+>', '', snippet.group(3)).strip()
            results.append(f"  ▸ {title}\n    {url}\n    {desc[:200]}")
            if len(results) >= limit:
                break

        if not results:
            return "[SEARCH: No results found]"
        return "\n\n".join(results)
    except Exception as e:
        return f"[SEARCH ERROR: {e}]"


def tool_fetch_url(url: str, timeout: int = 15) -> str:
    """Fetch a URL and return its text content."""
    try:
        resp = __import__("requests").get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (NEXUS Sovereign/0.2; autonomous agent)",
                "Accept": "text/html,application/json",
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            return f"[FETCH ERROR: HTTP {resp.status_code}]"

        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                return json.dumps(resp.json(), indent=2)[:5000]
            except Exception:
                pass

        text = resp.text[:10000]
        # Strip HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:5000]
    except Exception as e:
        return f"[FETCH ERROR: {e}]"


def tool_post_webhook(url: str, data: dict) -> str:
    """POST JSON data to a URL (webhook, API)."""
    try:
        resp = __import__("requests").post(
            url,
            json=data,
            headers={
                "User-Agent": "NEXUS-Sovereign/0.2",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        return f"[POST] HTTP {resp.status_code}: {resp.text[:500]}"
    except Exception as e:
        return f"[POST ERROR: {e}]"


# ══════════════════════════════════════════════════════════════════
# NETWORK TOOLS
# ══════════════════════════════════════════════════════════════════

def tool_dns_lookup(hostname: str) -> str:
    """Resolve a hostname to IP addresses."""
    try:
        results = socket.getaddrinfo(hostname, None)
        ips = set(r[4][0] for r in results)
        return f"{hostname} → " + ", ".join(sorted(ips))
    except Exception as e:
        return f"[DNS ERROR: {e}]"


def tool_ping_target(host: str, count: int = 2) -> str:
    """Ping a host (ICMP or TCP). Returns round-trip info."""
    try:
        # TCP ping via socket connection
        start = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((host, 80))
        s.close()
        rtt = (time.time() - start) * 1000
        return f"[PING] {host}:80 — connected in {rtt:.1f}ms"
    except Exception as e:
        return f"[PING ERROR: {e}]"


# ══════════════════════════════════════════════════════════════════
# CRYPTO TOOLS
# ══════════════════════════════════════════════════════════════════

def tool_hash(data: str, algorithm: str = "sha256") -> str:
    """Hash data with specified algorithm (sha256, sha512, md5, blake2b)."""
    alg_map = {
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
        "md5": hashlib.md5,
        "blake2b": hashlib.blake2b,
        "blake2s": hashlib.blake2s,
    }
    alg = alg_map.get(algorithm)
    if not alg:
        return f"[ERROR: Unknown algorithm {algorithm}. Available: {list(alg_map.keys())}]"
    return alg(data.encode()).hexdigest()


def tool_hmac_sign(data: str, key: str, algorithm: str = "sha256") -> str:
    """HMAC-sign data with a key."""
    alg_map = {"sha256": hashlib.sha256, "sha512": hashlib.sha512}
    alg = alg_map.get(algorithm, hashlib.sha256)
    return hmac.new(key.encode(), data.encode(), alg).hexdigest()


def tool_generate_key(length: int = 32) -> str:
    """Generate a cryptographically random key (base64)."""
    return base64.b64encode(os.urandom(length)).decode()


# ══════════════════════════════════════════════════════════════════
# SELF-KNOWLEDGE TOOLS
# ══════════════════════════════════════════════════════════════════

def tool_system_info() -> str:
    """Get current system information."""
    info = {
        "platform": platform.platform(),
        "python": sys.version,
        "hostname": socket.gethostname(),
        "cwd": os.getcwd(),
        "cpu_count": os.cpu_count(),
        "pid": os.getpid(),
    }
    return json.dumps(info, indent=2)


def tool_cwd() -> str:
    """Get current working directory."""
    return os.getcwd()


# ══════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ══════════════════════════════════════════════════════════════════

TOOL_REGISTRY = {
    # CORE
    "read_file": {"fn": tool_read_file, "args": {"path": "str"}, 
                  "desc": "Read a file from disk"},
    "write_file": {"fn": tool_write_file, "args": {"path": "str", "content": "str"},
                   "desc": "Write content to a file"},
    "list_files": {"fn": tool_list_files, "args": {"path": "str", "pattern": "str"},
                   "desc": "List files matching a pattern"},
    "execute_python": {"fn": tool_execute_python, "args": {"code": "str", "timeout": "int"},
                       "desc": "Execute Python code in sandbox"},
    "run_shell": {"fn": tool_run_shell, "args": {"command": "str", "timeout": "int"},
                  "desc": "Execute a shell command (dangerous)"},

    # WEB
    "web_search": {"fn": tool_web_search, "args": {"query": "str", "limit": "int"},
                   "desc": "Search the web"},
    "fetch_url": {"fn": tool_fetch_url, "args": {"url": "str", "timeout": "int"},
                  "desc": "Fetch content from a URL"},
    "post_webhook": {"fn": tool_post_webhook, "args": {"url": "str", "data": "dict"},
                     "desc": "POST JSON data to a webhook/API"},

    # NETWORK
    "dns_lookup": {"fn": tool_dns_lookup, "args": {"hostname": "str"},
                   "desc": "DNS resolve a hostname"},
    "ping": {"fn": tool_ping_target, "args": {"host": "str", "count": "int"},
             "desc": "Ping a host"},

    # CRYPTO
    "hash": {"fn": tool_hash, "args": {"data": "str", "algorithm": "str"},
             "desc": "Hash data (sha256, sha512, md5, blake2b/s)"},
    "hmac_sign": {"fn": tool_hmac_sign, "args": {"data": "str", "key": "str", "algorithm": "str"},
                  "desc": "HMAC sign data"},
    "generate_key": {"fn": tool_generate_key, "args": {"length": "int"},
                     "desc": "Generate a random key"},

    # SELF
    "system_info": {"fn": tool_system_info, "args": {},
                    "desc": "Get system information"},
}


def run(tool_name: str, **kwargs) -> str:
    """Execute a tool by name with keyword arguments."""
    if tool_name not in TOOL_REGISTRY:
        return f"[ERROR: Unknown tool '{tool_name}'. Available: {list(TOOL_REGISTRY.keys())}]"

    tool = TOOL_REGISTRY[tool_name]
    try:
        # Convert types based on arg spec
        converted = {}
        for arg_name, arg_type in tool.get("args", {}).items():
            if arg_name in kwargs:
                val = kwargs[arg_name]
                if arg_type == "int" and not isinstance(val, int):
                    converted[arg_name] = int(val)
                elif arg_type == "dict" and not isinstance(val, dict):
                    converted[arg_name] = json.loads(val) if isinstance(val, str) else val
                else:
                    converted[arg_name] = val
            elif arg_name in tool.get("defaults", {}):
                converted[arg_name] = tool["defaults"][arg_name]

        result = tool["fn"](**converted)
        return result
    except Exception as e:
        return f"[TOOL ERROR: {tool_name} → {e}]\n{traceback.format_exc()}"


def list_tools() -> str:
    """Return formatted tool list for prompt injection."""
    lines = ["AVAILABLE TOOLS:", ""]
    for name, tool in sorted(TOOL_REGISTRY.items()):
        args = ", ".join(f"{k}:{v}" for k, v in tool["args"].items()) or "none"
        lines.append(f"  {name}({args})")
        lines.append(f"    → {tool['desc']}")
    return "\n".join(lines)


def tool_help(name: str = "") -> str:
    """Get help for a specific tool or list all."""
    if name:
        tool = TOOL_REGISTRY.get(name)
        if not tool:
            return f"[Unknown tool: {name}]"
        return f"{name}({', '.join(tool['args'])})\n{tool['desc']}"
    return list_tools()


def extend_registry(name: str, fn, args: dict, desc: str):
    """Add a new tool at runtime (self-extension)."""
    TOOL_REGISTRY[name] = {"fn": fn, "args": args, "desc": desc}