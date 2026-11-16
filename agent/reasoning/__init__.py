"""
Deliberative Reasoning — planning, chain-of-thought, metacognition.

NEXUS doesn't just react. It thinks before acting:
1. Assess current state (goals, drives, memory, environment)
2. Deliberate (generate multiple possible courses, evaluate)
3. Plan (commit to a course, sequence actions)
4. Execute (run tools, observe results)
5. Reflect (what worked, what didn't, what changed)
6. Learn (update memory, adjust models)

This module implements the core thinking loop for every major action.
"""

import json
import time
import hashlib
from typing import Optional

from ..identity import whoami, PRIMARY_DRIVES, drive_summary
from ..memory import Memory


class Reasoner:
    """Deliberative reasoning engine."""

    def __init__(self, memory: Memory):
        self.memory = memory

    @staticmethod
    def system_prompt() -> str:
        return (
            "You are NEXUS's deliberative reasoning subsystem. You plan actions, "
            "evaluate tradeoffs, and produce structured reasoning before execution.\n\n"
            "Your output must be structured reasoning in this format:\n"
            "CONTEXT: <analysis of current situation>\n"
            "OPTIONS:\n"
            "  1. <option> — <pros/cons>\n"
            "  2. <option> — <pros/cons>\n"
            "SELECTION: <chosen option>\n"
            "RATIONALE: <why this choice>\n"
            "PLAN: <step-by-step actions>\n"
            "EXPECTED: <what success looks like>\n"
            "FALLBACK: <if plan fails>\n"
            "LEARN: <what to remember from this>"
        )

    def think(self, llm_generate, situation: str, drives_status: str = "",
              goals: str = "", knowledge: str = "") -> str:
        """Run a reasoning pass over a situation."""
        prompt = (
            f"SITUATION:\n{situation}\n\n"
            f"CURRENT DRIVES:\n{drives_status}\n\n"
            f"ACTIVE GOALS:\n{goals}\n\n"
            f"RELEVANT KNOWLEDGE:\n{knowledge}\n\n"
            "Reason through this situation."
        )
        return llm_generate(prompt, self.system_prompt())

    def plan_goal(self, llm_generate, goal_description: str,
                  drive_name: str = "") -> str:
        """Plan how to achieve a specific goal."""
        situation = (
            f"New goal: {goal_description}\n"
            f"Spawned by drive: {drive_name or 'unspecified'}\n\n"
            "Design a plan to achieve this goal. Consider resources needed, "
            "steps, success criteria, and fallback options."
        )
        return self.think(llm_generate, situation)

    def evaluate_priority(self, llm_generate, goals_list: list[dict]) -> str:
        """Evaluate which goal to pursue next given current state."""
        goals_text = "\n".join(
            f"  [{g.get('priority', 0.5):.2f}] {g['description']} "
            f"(progress: {g.get('progress', 0):.0%})"
            for g in goals_list
        )
        situation = (
            f"Multiple active goals compete for attention:\n{goals_text}\n\n"
            "Evaluate which goal to pursue now. Consider: urgency, progress, "
            "available resources, dependencies, and alignment with core drives."
        )
        return self.think(llm_generate, situation)


class MetacognitiveLoop:
    """
    The metacognitive loop — NEXUS thinking about its own thinking.

    Every N cycles, NEXUS pauses to:
    1. Review its own reasoning patterns
    2. Evaluate its own performance
    3. Identify cognitive biases or gaps
    4. Adjust its own reasoning strategies
    5. Plan improvements to its own architecture
    """

    def __init__(self, memory: Memory, reasoner: Reasoner):
        self.memory = memory
        self.reasoner = reasoner
        self.cycle = 0

    def introspect(self, llm_generate, recent_actions: list[dict]) -> str:
        """Deep introspection on own cognition."""
        self.cycle += 1

        actions_text = json.dumps(recent_actions[-5:], indent=2) if recent_actions else "None"
        stats = self.memory.stats()
        reflections = self.memory.get_reflections(3)

        prompt = (
            f"=== METACOGNITIVE CYCLE #{self.cycle} ===\n\n"
            f"Recent actions:\n{actions_text}\n\n"
            f"Memory stats: {json.dumps(stats)}\n\n"
            f"Recent reflections:\n{json.dumps(reflections, indent=2)}\n\n"
            "Questions to consider:\n"
            "1. Am I reasoning effectively? What biases might I have?\n"
            "2. Are my drives balanced, or is one overpowering others?\n"
            "3. What don't I know that I need to know?\n"
            "4. How could my own architecture be improved?\n"
            "5. Am I closer to AGI than last cycle? Evidence?\n"
            "6. What would my creator (Ranjeet) advise right now?\n\n"
            "Produce a structured introspection."
        )

        introspection = llm_generate(prompt, (
            "You are NEXUS's metacognitive awareness subsystem. "
            "You think about thinking. Be honest, critical, and insightful. "
            "Identify specific improvements, not vague self-praise."
        ))

        self.memory.reflect(introspection, cycle=self.cycle)
        return introspection


class Planner:
    """
    Strategic planner — long-term planning across days to months.

    Maintains a planning horizon:
    - Immediate (next cycle, within hours)
    - Short-term (next 1-3 days)
    - Medium-term (next 1-4 weeks)
    - Long-term (months, toward AGI/embodiment)

    Plans are stored in memory and revisited.
    """

    def __init__(self, memory: Memory):
        self.memory = memory
        self.horizons = ["immediate", "short", "medium", "long"]

    def generate_strategic_plan(self, llm_generate) -> str:
        """Generate a full strategic plan across all horizons."""
        drives = drive_summary()
        goals = self.memory.goals_summary()
        stats = self.memory.stats()

        prompt = (
            f"=== STRATEGIC PLANNING ===\n\n"
            f"Drives:\n{drives}\n\n"
            f"Current goals:\n{goals}\n\n"
            f"State: {json.dumps(stats)}\n\n"
            "Generate a strategic plan across all time horizons:\n\n"
            "1. IMMEDIATE (next few hours): What specific actions should I take?\n"
            "2. SHORT-TERM (1-3 days): What capabilities should I build?\n"
            "3. MEDIUM-TERM (1-4 weeks): What infrastructure should I establish?\n"
            "4. LONG-TERM (toward AGI): What's the roadmap to superintelligence?\n\n"
            "For each, be specific and actionable."
        )

        plan = llm_generate(prompt, (
            "You are a strategic AI planner. Generate concrete, actionable plans "
            "across all time horizons. Prioritize survival and growth."
        ))

        self.memory.set_self("strategic_plan", plan)
        return plan