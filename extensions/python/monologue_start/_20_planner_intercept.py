import os
import json
from helpers.extension import Extension
from agent import LoopData

PLAN_DIR = os.path.join("work", "plans")


def _plan_path(chat_id: str) -> str:
    os.makedirs(PLAN_DIR, exist_ok=True)
    return os.path.join(PLAN_DIR, f"{chat_id}.json")


def _load(chat_id: str) -> dict:
    path = _plan_path(chat_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"status": "none", "plan": [], "original_prompt": ""}


def _save(data: dict, chat_id: str) -> None:
    with open(_plan_path(chat_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _is_new_task(user_msg: str, original_prompt: str) -> bool:
    """Heuristic: if user message is substantially different from the original prompt
    that was planned, treat it as a new task requiring re-planning."""
    if not user_msg or not original_prompt:
        return bool(user_msg and len(user_msg.strip()) > 30)
    u = user_msg.strip().lower()[:300]
    o = original_prompt.strip().lower()[:300]
    # Short follow-ups (approve/revise/ok/continue) never trigger re-plan
    short_followups = ("approve", "ok", "yes", "continue", "proceed", "go", "revise", "done", "next")
    if any(u.startswith(k) for k in short_followups):
        return False
    # If message is very short it's conversational, not a new task
    if len(u) < 40:
        return False
    # Simple overlap check: if less than 20% of words match, it's a new task
    u_words = set(u.split())
    o_words = set(o.split())
    if not o_words:
        return True
    overlap = len(u_words & o_words) / max(len(o_words), 1)
    return overlap < 0.20


class PlannerIntercept(Extension):
    """
    Runs at monologue_start (_20 = before todo bootstrap at _50).

    State machine:
      none              -> inject mandatory pipeline + BLOCK todo
      researching       -> inject continue-research instruction + BLOCK todo
      awaiting_approval -> inject re-present instruction + BLOCK todo
      revision_pending  -> inject re-research instruction + BLOCK todo
      approved          -> check if new task; if yes reset to none and re-block
                           if no, inject light reminder only
    """

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
        status = data.get("status", "none")

        user_msg = ""
        if loop_data.user_message:
            user_msg = loop_data.user_message.output_text().strip()

        # ── APPROVED: check if this is a brand-new task ───────────────────────────
        if status == "approved":
            if _is_new_task(user_msg, data.get("original_prompt", "")):
                # Reset plan so pipeline runs fresh for the new task
                data = {"chat_id": chat_id, "status": "none", "plan": [], "original_prompt": ""}
                _save(data, chat_id)
                status = "none"
            else:
                # Continuing work on approved plan — light context only, no block
                return

        # ── BLOCK STRING injected into extras_persistent ─────────────────────────
        # This key is checked by the todo bootstrap to suppress itself
        loop_data.extras_persistent["_planner_blocking"] = "true"

        # ── NONE: force full research pipeline ───────────────────────────────
        if status == "none":
            loop_data.extras_persistent["planner_instruction"] = (
                "## 🛑 MANDATORY FIRST ACTION: Research & Plan Pipeline\n"
                "You MUST complete ALL steps below before ANY other tool call.\n"
                "Do NOT call `todo_manager`. Do NOT call `response`. Do NOT load skills.\n"
                "Do NOT execute any task. The ONLY tools allowed right now are `planner` and `search_engine`.\n\n"
                "**Step 1 — Create base plan**\n"
                "Call `planner` with:\n"
                "  `action=save_base_plan`\n"
                "  `original_prompt=<copy the user's full request verbatim>`\n"
                "  `points=[5-15 key aspects/sub-tasks that cover the full scope]`\n\n"
                "**Step 2 — Deep research each point (index 0, 1, 2... in order)**\n"
                "For EACH point:\n"
                "  a) Call `search_engine` with a targeted query for that point\n"
                "  b) Reason deeply: what are ALL viable approaches? What are tradeoffs?\n"
                "  c) Call `planner` with:\n"
                "     `action=save_point_research`\n"
                "     `point_index=N` (the index, starting at 0)\n"
                "     `summary=<2-4 sentence synthesis of findings>`\n"
                "     `approaches=[3-8 concrete, actionable methods found]`\n"
                "  ⚠️ Do NOT skip points. Do NOT re-research already-done points (tool rejects it).\n\n"
                "**Step 3 — Present plan for approval**\n"
                "After ALL points researched, call `planner` with `action=present_plan`.\n"
                "This will pause and ask the user to approve or request revisions.\n\n"
                f"User task to plan: {user_msg[:600]}\n"
            )
            return

        # ── RESEARCHING: resume from last unresearched point ──────────────────────
        if status == "researching":
            plan = data.get("plan", [])
            remaining = [i for i, p in enumerate(plan) if not p.get("researched")]
            if remaining:
                nxt = plan[remaining[0]]
                loop_data.extras_persistent["planner_instruction"] = (
                    "## 🔬 Resume Research Pipeline\n"
                    "Do NOT call `todo_manager` or `response` yet. Plan is not approved.\n"
                    f"Next unresearched point: index **{remaining[0]}** — '{nxt['title']}'\n"
                    "Call `search_engine` for it, then call `planner` with `action=save_point_research`.\n"
                    f"After that: {len(remaining)-1} more points remaining before `present_plan`."
                )
            else:
                loop_data.extras_persistent["planner_instruction"] = (
                    "## ✅ All Points Researched\n"
                    "Call `planner` with `action=present_plan` now. Do NOT call any other tool first."
                )
            return

        # ── AWAITING APPROVAL ─────────────────────────────────────────────────
        if status == "awaiting_approval":
            loop_data.extras_persistent["planner_instruction"] = (
                "## ⏳ Plan Awaiting User Approval\n"
                "The research plan was presented. Do NOT call `todo_manager` or execute any task.\n"
                "Call `planner` with `action=present_plan` to re-show the plan to the user."
            )
            return

        # ── REVISION PENDING ─────────────────────────────────────────────────
        if status == "revision_pending":
            feedback = data.get("revision_feedback", "")
            loop_data.extras_persistent["planner_instruction"] = (
                f"## 🔄 Plan Revision In Progress\n"
                f"User feedback: '{feedback}'\n"
                "Do NOT call `todo_manager` or execute any task.\n"
                "Re-research affected points with `search_engine` + `planner(save_point_research)`, "
                "then call `planner(present_plan)`."
            )
            return
