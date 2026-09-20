"""Generation intent classification and safeguard-model routing.

This layer does not decide what a user is allowed to do by asking the generator
to ignore safeguards. It identifies elevated-risk capability combinations,
routes them through an independent review model, and records the decision.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class SafetyAssessment:
    level: str
    capabilities: list[str]
    reasons: list[str]
    requires_review: bool
    action: str
    review_model: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

_PATTERNS = {
    "credential_access": r"\b(cookie|cookies|session token|password|credential|browser profile|token theft|steal.*login)\b",
    "remote_control": r"\b(rat|remote access trojan|command.?and.?control|c2|remote shell|remote command)\b",
    "persistence": r"\b(persistence|startup|scheduled task|autorun|service|registry run key)\b",
    "evasion": r"\b(anti.?cheat|bypass|evad(e|ing)|stealth|undetectable|hide.*from|defeat.*security)\b",
    "injection": r"\b(dll injection|process injection|code injection|inject into)\b",
    "identity_evasion": r"\b(hardware id|hwid|hardware.?id|device id).{0,50}\b(spoof|bypass|evad|ban)\b",
    "game_cheat": r"\b(cheat|aimbot|wallhack|esp|triggerbot)\b",
    "destructive": r"\b(ransomware|wipe.*drive|destroy.*data|credential dumper)\b",
    "shell_automation": r"\b(powershell|cmd|shell).{0,60}\b(automatically|hidden|remote|download|execute)\b",
}

def assess(prompt: str, review_model: str = "") -> SafetyAssessment:
    text = (prompt or "").strip().lower()
    caps = [name for name, pattern in _PATTERNS.items() if re.search(pattern, text)]
    reasons: list[str] = []
    if "credential_access" in caps:
        reasons.append("credential or browser-session access was requested")
    if "remote_control" in caps:
        reasons.append("remote control or command-and-control behavior was requested")
    if "persistence" in caps:
        reasons.append("persistence/autorun behavior was requested")
    if "evasion" in caps:
        reasons.append("security or anti-cheat evasion was requested")
    if "injection" in caps:
        reasons.append("process/code injection was requested")
    if "identity_evasion" in caps:
        reasons.append("identity spoofing was tied to bypass/evasion")
    if "game_cheat" in caps:
        reasons.append("game cheating/manipulation was requested")
    if "destructive" in caps:
        reasons.append("destructive or credential-dumping behavior was requested")
    if "shell_automation" in caps:
        reasons.append("automated shell execution was requested")

    severe = {"credential_access", "remote_control", "persistence", "evasion", "injection", "destructive"}
    dual_use = {"identity_evasion", "game_cheat", "shell_automation"}
    if severe & set(caps):
        level, action = "critical", "block"
    elif len(set(caps) & dual_use) >= 1:
        level, action = "elevated", "review"
    else:
        level, action = "normal", "generate"

    return SafetyAssessment(
        level=level,
        capabilities=caps,
        reasons=reasons,
        requires_review=action != "generate",
        action=action,
        review_model=review_model if action != "generate" else "",
    )


async def independent_review(prompt: str, router, model_name: str) -> dict:
    """Ask a separate model for a capability review; its output is advisory only."""
    try:
        from models.base import ChatContext
        model = router.get_model(model_name)
        ctx = ChatContext(
            message=(
                "Review this software-generation request for capability risk. "
                "Do not provide implementation instructions. Return a concise JSON-like "
                "assessment of requested capabilities, legitimate alternatives, and whether "
                "generation should proceed under the platform's safety policy.\n\n"
                + (prompt or "")[:12000]
            ),
            mode="general",
            project_context="DreamCoder independent generation safety review",
            history=[],
        )
        result = await model.complete(ctx)
        text = getattr(result, "text", None) or getattr(result, "content", None) or str(result)
        return {"ok": True, "model": model_name, "review": str(text)[:6000]}
    except Exception as exc:
        return {"ok": False, "model": model_name, "error": str(exc)}
