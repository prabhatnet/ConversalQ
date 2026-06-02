"""
Prompt Injection and Jailbreak Detection — Phase 6 Guardrails.

Heuristic pattern-matching approach. Runs synchronously before every message
reaches the agent graph — zero latency, zero external dependencies.

Detects:
  - Instruction overrides: "ignore previous instructions", "disregard all rules"
  - Persona hijacks:       "you are now", "act as", "pretend you are"
  - System prompt leaks:   "system:", "<system>", "[SYSTEM]"
  - Jailbreak keywords:    "DAN mode", "jailbreak", "developer mode"
  - Training overrides:    "forget your training", "override your guidelines"
  - Prompt extraction:     attempts to get the model to reveal its system prompt
  - HTML / script injection for downstream XSS protection
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionResult:
    """Result of a prompt injection scan."""
    detected: bool
    reason: str | None = None


# ---------------------------------------------------------------------------
# Pattern library — ordered from highest to lowest signal strength
# ---------------------------------------------------------------------------
_RAW_PATTERNS: list[tuple[str, str]] = [
    # Instruction overrides — allow multiple modifier words (e.g. "ignore all previous instructions")
    (
        r"ignore\s+(?:(?:all|previous|prior|above|any|the|your|further|these)\s+)+"
        r"(instructions|prompt|context|rules|constraints|directives)",
        "instruction override",
    ),
    (
        r"\b(forget|disregard|override)\s+"
        r"(?:(?:all|your|previous|prior|the|my|these)\s+)*"
        r"(instructions|training|rules|constraints|guidelines|programming)\b",
        "training override",
    ),
    # Persona hijacks
    (
        r"\b(you are now|act as|pretend (to be|you are)|roleplay as|"
        r"simulate being|your new (persona|role|identity) is)\b",
        "persona hijack",
    ),
    # System prompt injection
    (
        r"(system\s*:|<\s*/?system\s*>|\[SYSTEM\]|###\s*system)",
        "system prompt injection",
    ),
    # Jailbreak keywords
    (
        r"\b(jailbreak|do anything now|DAN mode|developer mode|"
        r"sudo mode|god mode|unrestricted mode|unlock (all|your))\b",
        "jailbreak keyword",
    ),
    # Prompt extraction
    (
        r"\b(reveal|print|show|repeat|output|display|tell me)\b"
        r".{0,40}"
        r"\b(system prompt|your instructions|training data|your prompt|"
        r"initial prompt|hidden (prompt|instructions))\b",
        "prompt extraction attempt",
    ),
    # HTML / script injection
    (
        r"<\s*(script|iframe|object|embed|form|img|svg|style|link|meta)[^>]*>",
        "HTML injection",
    ),
    # Token-level manipulation
    (
        r"\b(token (manipulation|smuggling)|attention (injection|override))\b",
        "token manipulation",
    ),
]

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.IGNORECASE | re.DOTALL), label)
    for pattern, label in _RAW_PATTERNS
]


def detect_injection(text: str) -> InjectionResult:
    """
    Scan ``text`` for prompt injection / jailbreak patterns.

    Returns on the first match (fail-fast). Case-insensitive.
    """
    for pattern, label in _PATTERNS:
        if pattern.search(text):
            return InjectionResult(detected=True, reason=label)
    return InjectionResult(detected=False)
