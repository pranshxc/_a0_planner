import os
import json
from helpers.extension import Extension
from agent import LoopData

PLAN_DIR = os.path.join("work", "plans")

STATUS_LABEL = {
    "none": "not started",
    "researching": "🔬 researching",
    "awaiting_approval": "⏳ awaiting user approval",
    "revision_pending": "🔄 revision requested",
    "approved": "✅ approved",
}


def _load(chat_id: str) -> dict:
    path = os.path.join(PLAN_DIR, f"{chat_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"status": "none", "plan": []}


def _compact(data: dict) -> str:
    plan = data.get("plan", [])
    if not plan:
        return ""
    status = STATUS_LABEL.get(data.get("status", "none"), data.get("status", ""))
    done = sum(1 for p in plan if p.get("researched"))
    lines = [f"<research_plan status='{status}' researched='{done}/{len(plan)}'>"]
    for i, p in enumerate(plan):
        r_flag = "✅" if p.get("researched") else "⬜"
        approaches_count = len(p.get("approaches", []))
        lines.append(f"  {r_flag} [{i}] {p['title']} ({approaches_count} approaches found)")
    lines.append("</research_plan>")
    return "\n".join(lines)


class PlannerInject(Extension):
    """Inject compact plan status into every prompt so agent always knows where it stands."""

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        agent = self.agent
        if not agent:
            return

        chat_id = str(
            getattr(agent, "chat_id", None)
            or getattr(agent.context, "id", None)
            or "default"
        )

        data = _load(chat_id)
        if data.get("status", "none") == "none":
            return

        compact = _compact(data)
        if not compact:
            return

        loop_data.extras_persistent["research_plan"] = (
            "## 📋 Current Research Plan\n"
            "This plan was created before execution. Use it to guide your work.\n"
            "If the plan is approved, follow it. To view full detail call `planner` with `action=get`.\n\n"
            + compact
        )
