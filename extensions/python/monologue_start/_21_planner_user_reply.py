import os
import json
from helpers.extension import Extension
from agent import LoopData

PLAN_DIR = os.path.join("work", "plans")


def _load(chat_id: str) -> dict:
    path = os.path.join(PLAN_DIR, f"{chat_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"status": "none"}


class PlannerUserReply(Extension):
    """
    When status=awaiting_approval and a new user message arrives,
    pre-parse 'approve' or 'revise: ...' and inject a pinpoint directive
    so the agent calls the correct planner action immediately.
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
        if data.get("status") != "awaiting_approval":
            return

        user_msg = ""
        if loop_data.user_message:
            user_msg = loop_data.user_message.output_text().strip()

        if not user_msg:
            return

        u_lower = user_msg.lower()
        if u_lower.startswith("approve"):
            loop_data.extras_persistent["planner_reply_directive"] = (
                "## ✅ User Approved the Plan\n"
                "Call `planner` with `action=approve` as your FIRST action. "
                "After that, proceed to create the todo list with `todo_manager`."
            )
        elif u_lower.startswith("revise"):
            if ":" in user_msg:
                feedback = user_msg.split(":", 1)[1].strip()
            else:
                parts = user_msg.split(None, 1)
                feedback = parts[1].strip() if len(parts) > 1 else user_msg
            loop_data.extras_persistent["planner_reply_directive"] = (
                f"## 🔄 User Requested Plan Revision\n"
                f"Feedback: '{feedback}'\n"
                "Call `planner` with `action=revise`, `feedback=<exact feedback>` as your FIRST action."
            )
