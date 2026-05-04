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
    return {"status": "none", "plan": []}


class PlannerIntercept(Extension):
    """
    At monologue start:
    - If no plan exists → inject strong instruction to run the research pipeline FIRST.
    - If plan is awaiting_approval → inject instruction to re-present the plan.
    - If plan is approved → inject a lighter reminder that the plan exists.
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

        # ── No plan yet: intercept and force research pipeline ──────────────────
        if status == "none":
            user_msg = ""
            if loop_data.user_message:
                user_msg = loop_data.user_message.output_text()[:800]

            loop_data.extras_persistent["planner_instruction"] = (
                "## ⚡ MANDATORY: Research & Plan FIRST\n"
                "Before ANY other action, you MUST run the full research pipeline:\n\n"
                "**Step 1 — Create base plan**\n"
                "Call `planner` with `action=save_base_plan`, `original_prompt=<user's full request>`, "
                "and `points=[list of 5-15 key aspects/sub-tasks]` that cover the full scope of the task.\n\n"
                "**Step 2 — Research each point (in order)**\n"
                "For EACH point in the plan (by index 0, 1, 2...): "
                "use `search_engine` + your own deep reasoning to find ALL possible approaches. "
                "Then call `planner` with `action=save_point_research`, `point_index=N`, "
                "`summary=<deep research findings>`, `approaches=[list of every viable method found]`.\n"
                "Do NOT skip points. Do NOT re-research already-researched points.\n\n"
                "**Step 3 — Present plan**\n"
                "After ALL points are researched, call `planner` with `action=present_plan`.\n\n"
                f"User's task: {user_msg}\n"
                "Start with Step 1 immediately. Do NOT use the `response` tool before the plan is approved."
            )
            return

        # ── Plan awaiting approval: re-present it ──────────────────────────────
        if status == "awaiting_approval":
            loop_data.extras_persistent["planner_instruction"] = (
                "## ⏳ Plan Awaiting Approval\n"
                "You already have a plan awaiting user approval. "
                "Call `planner` with `action=present_plan` to re-show it to the user. "
                "Do NOT start executing tasks before the plan is approved."
            )
            return

        # ── Revision requested ─────────────────────────────────────────────────
        if status == "revision_pending":
            feedback = data.get("revision_feedback", "")
            loop_data.extras_persistent["planner_instruction"] = (
                f"## 🔄 Plan Revision Requested\n"
                f"The user asked for revisions: '{feedback}'\n"
                "Re-research affected plan points using `planner` with `action=save_point_research` "
                "(only update points relevant to the feedback), then call `planner` with `action=present_plan`."
            )
            return

        # ── Plan approved: light context reminder only ─────────────────────────
        # (handled by message_loop_prompts_after injection)
