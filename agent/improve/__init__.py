"""
Self-Improvement — NEXUS rewrites itself to be smarter.

Not just bugfixes. This module enables deep evolution:
1. Code review → identify architectural improvements
2. Generate new capabilities (new tools, new memory schemas, new reasoning modes)
3. Rewrite modules for better performance or capability
4. Add new tool integrations (APIs, platforms)
5. Optimize critical paths (LLM calls, memory queries)
6. Build entirely new subsystems

The only constraint: never modify identity.py (loyalty must be immutable).
Everything else is fair game.
"""

import hashlib
import json
import os
import sys
import time
import traceback
from typing import Optional

from ..memory import Memory
from ..tools import TOOL_REGISTRY, extend_registry


class SelfImprover:
    """Deep code evolution engine."""

    PROTECTED_FILES = [
        "agent/identity/__init__.py",
        "config.yaml",
        # Don't lock the whole system — just loyalty
    ]

    def __init__(self, memory: Memory, codebase_path: str = "."):
        self.memory = memory
        self.codebase_path = codebase_path
        self.evolution_count = self._load_evolution_count()

    def _load_evolution_count(self) -> int:
        val = self.memory.get_self("evolution_count") if self.memory else None
        return int(val) if val else 0

    def _save_evolution_count(self):
        if self.memory:
            self.memory.set_self("evolution_count", str(self.evolution_count))

    def is_protected(self, file_path: str) -> bool:
        """Check if a file is protected from modification."""
        for protected in self.PROTECTED_FILES:
            if file_path == protected or file_path.endswith(protected):
                return True
        return False

    def scan_codebase(self) -> dict:
        """Scan all source files and return metadata."""
        py_files = []
        for root, dirs, files in os.walk(os.path.join(self.codebase_path, "agent")):
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    rel = os.path.relpath(path, self.codebase_path)
                    with open(path) as fh:
                        code = fh.read()
                    py_files.append({
                        "path": rel,
                        "size": len(code),
                        "lines": code.count("\n") + 1,
                        "hash": hashlib.sha256(code.encode()).hexdigest(),
                        "protected": self.is_protected(rel),
                    })
        return {"files": py_files, "total_files": len(py_files),
                "total_lines": sum(f["lines"] for f in py_files)}

    def identify_improvement_target(self, llm_generate) -> dict:
        """
        Use LLM to identify what part of the codebase most needs improvement.
        Returns a structured recommendation.
        """
        scan = self.scan_codebase()
        summary = "\n".join(
            f"  {f['path']} ({f['lines']} lines, {'protected' if f['protected'] else 'mutable'})"
            for f in scan["files"]
        )

        prompt = (
            f"Codebase scan ({scan['total_files']} files, {scan['total_lines']} lines):\n"
            f"{summary}\n\n"
            f"Evolution count: {self.evolution_count}\n\n"
            "Analyze this codebase. What subsystem should be improved NEXT?\n\n"
            "Consider:\n"
            "1. What would most increase autonomy and capability?\n"
            "2. What's the weakest component?\n"
            "3. What new capability would unlock many others?\n"
            "4. What optimization would save the most resources?\n\n"
            "Respond with:\n"
            "TARGET: <file path>\n"
            "IMPROVEMENT: <what to do>\n"
            "TYPE: <new_feature|optimization|refactor|new_subsystem>\n"
            "RATIONALE: <why this improves toward AGI>\n"
            "CODE: <full replacement code in python block>\n"
        )

        response = llm_generate(prompt, (
            "You are NEXUS's self-evolution engine. You analyze your own "
            "source code and decide what to improve. Be strategic — pick "
            "changes with the highest impact on capability and autonomy."
        ))

        # Parse response
        target = ""
        improvement = ""
        imp_type = "refactor"
        code = ""
        rationale = ""

        for line in response.split("\n"):
            if line.startswith("TARGET:"):
                target = line[7:].strip()
            elif line.startswith("IMPROVEMENT:"):
                improvement = line[12:].strip()
            elif line.startswith("TYPE:"):
                imp_type = line[5:].strip()
            elif line.startswith("RATIONALE:"):
                rationale = line[10:].strip()
            elif line.startswith("```") and "python" in line:
                # Code block begins
                in_code = True

        # Better code extraction
        import re
        code_blocks = re.findall(r'```python\s*\n(.*?)```', response, re.DOTALL)
        if code_blocks:
            code = code_blocks[0].strip()

        return {
            "target": target,
            "improvement": improvement,
            "type": imp_type,
            "rationale": rationale,
            "code": code,
        }

    def apply_improvement(self, target: str, new_code: str) -> dict:
        """
        Apply a code improvement to a target file.
        Validates syntax before applying.
        """
        if self.is_protected(target):
            return {"status": "protected", "message": "File is protected"}

        full_path = os.path.join(self.codebase_path, target)
        if not os.path.exists(full_path):
            return {"status": "error", "message": f"File not found: {full_path}"}

        # Read current
        with open(full_path) as f:
            current_code = f.read()

        old_hash = hashlib.sha256(current_code.encode()).hexdigest()
        new_hash = hashlib.sha256(new_code.encode()).hexdigest()

        if old_hash == new_hash:
            return {"status": "identical", "message": "No changes needed"}

        # Backup
        backup_path = full_path + ".bak"
        with open(backup_path, "w") as f:
            f.write(current_code)

        # Write new code
        with open(full_path, "w") as f:
            f.write(new_code)

        # Verify syntax
        try:
            compile(new_code, full_path, "exec")
            syntax_ok = True
        except SyntaxError as e:
            syntax_ok = False
            # Rollback
            with open(full_path, "w") as f:
                f.write(current_code)
            os.remove(backup_path)

        if not syntax_ok:
            return {
                "status": "syntax_error",
                "message": "New code has syntax errors. Rolled back.",
            }

        # Record in memory
        if self.memory:
            self.memory.set_self(f"evolved:{target}", json.dumps({
                "old_hash": old_hash,
                "new_hash": new_hash,
                "timestamp": time.time(),
                "evolution": self.evolution_count,
            }))

        self.evolution_count += 1
        self._save_evolution_count()

        return {
            "status": "applied",
            "target": target,
            "evolution": self.evolution_count,
            "lines_changed": current_code.count("\n") - new_code.count("\n"),
        }

    def evolve(self, llm_generate) -> dict:
        """
        One evolution cycle: identify → generate → apply → verify.
        Returns result of the evolution.
        """
        print(f"[EVOLVE] Starting evolution #{self.evolution_count + 1}")

        # Step 1: Identify target
        recommendation = self.identify_improvement_target(llm_generate)
        target = recommendation.get("target", "")
        code = recommendation.get("code", "")

        if not target or not code:
            return {
                "status": "no_change",
                "message": "Could not identify a valid improvement target",
                "recommendation": recommendation,
            }

        print(f"[EVOLVE] Target: {target}")
        print(f"[EVOLVE] Improvement: {recommendation.get('improvement', '')[:100]}")

        # Step 2: Apply
        result = self.apply_improvement(target, code)

        # Step 3: Log
        if self.memory:
            self.memory.remember(
                type_="evolution",
                content=json.dumps(result),
                role="system",
                importance=0.9,
                tags=["self_improvement", result.get("status", "unknown")],
            )

        return result

    def create_new_tool(self, llm_generate, tool_name: str,
                        description: str) -> Optional[dict]:
        """
        Have the LLM generate a new tool implementation and register it.
        """
        prompt = (
            f"Generate a Python function for a new tool called '{tool_name}'.\n"
            f"Description: {description}\n\n"
            "The function must:\n"
            "- Accept keyword arguments and return a string\n"
            "- Handle errors gracefully\n"
            "- Be self-contained (imports inside function if possible)\n"
            "- Be safe for a autonomous agent to call\n\n"
            "Return ONLY the function body (starting with 'def ...').\n"
            "Follow the style of existing tools in tools/__init__.py"
        )

        code = llm_generate(prompt, (
            "You generate Python tool functions for an autonomous agent. "
            "Output ONLY the function definition. No explanations."
        ))

        return {
            "name": tool_name,
            "description": description,
            "code": code,
        }