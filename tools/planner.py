import json
import os
from datetime import datetime, timezone
from helpers.tool import Tool, Response

PLAN_DIR = os.path.join("work", "plans")


def _plan_path(chat_id: str) -> str:
    os.makedirs(PLAN_DIR, exist_ok=True)
    return os.path.join(PLAN_DIR, f"{chat_id}.json")


def _load(chat_id: str) -> dict:
    path = _plan_path(chat_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"chat_id": chat_id, "status": "none", "plan": [], "original_prompt": "", "created_at": "", "approved_at": ""}


def _save(data: dict) -> None:
    with open(_plan_path(data["chat_id"]), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _render_plan(data: dict) -> str:
    plan = data.get("plan", [])
    if not plan:
        return "No plan yet."
    status = data.get("status", "")
    lines = [f"**Research Plan** (status: {status})\n"]
    for i, point in enumerate(plan, 1):
        title = point.get("title", "")
        summary = point.get("research_summary", "")
        approaches = point.get("approaches", [])
        lines.append(f"### {i}. {title}")
        if summary:
            lines.append(f"{summary}")
        if approaches:
            lines.append("**Possible approaches:**")
            for a in approaches:
                lines.append(f"  - {a}")
        lines.append("")
    return "\n".join(lines)


class Planner(Tool):
    """Research & planning tool. Runs deep research pipeline and manages plan lifecycle."""

    async def execute(self, **kwargs) -> Response:
        action = (self.args.get("action") or "").strip().lower()
        chat_id = self._chat_id()
        data = _load(chat_id)

        # ── save_base_plan ──────────────────────────────────────────────────────
        if action == "save_base_plan":
            points = self.args.get("points", [])
            prompt = self.args.get("original_prompt", "")
            if not isinstance(points, list) or not points:
                return Response(message="Provide a non-empty 'points' list.", break_loop=False)
            data["original_prompt"] = prompt
            data["status"] = "researching"
            data["created_at"] = _now()
            data["plan"] = [
                {"title": str(p).strip(), "research_summary": "", "approaches": [], "researched": False}
                for p in points[:20]
            ]
            _save(data)
            return Response(
                message=f"Base plan saved with {len(data['plan'])} points. Now research each point.",
                break_loop=False,
            )

        # ── save_point_research ────────────────────────────────────────────────
        elif action == "save_point_research":
            idx = int(self.args.get("point_index", -1))
            summary = (self.args.get("summary") or "").strip()
            approaches = self.args.get("approaches", [])
            if idx < 0 or idx >= len(data.get("plan", [])):
                return Response(message=f"Invalid point_index {idx}.", break_loop=False)
            point = data["plan"][idx]
            if point.get("researched"):
                return Response(
                    message=f"Point {idx} already researched. Move to next unresearched point.",
                    break_loop=False,
                )
            point["research_summary"] = summary
            point["approaches"] = [str(a).strip() for a in (approaches or [])]
            point["researched"] = True
            _save(data)
            # Tell agent what to do next — prevents loop
            remaining = [i for i, p in enumerate(data["plan"]) if not p.get("researched")]
            if remaining:
                nxt = data["plan"][remaining[0]]
                return Response(
                    message=f"Point {idx} saved. Next unresearched: index {remaining[0]} — '{nxt['title']}'. Research it now.",
                    break_loop=False,
                )
            else:
                return Response(
                    message="All points researched. Call planner with action=present_plan now.",
                    break_loop=False,
                )

        # ── present_plan ───────────────────────────────────────────────────────
        elif action == "present_plan":
            if data["status"] not in ("researching", "revision_pending"):
                return Response(message="No active plan to present.", break_loop=False)
            data["status"] = "awaiting_approval"
            _save(data)
            rendered = _render_plan(data)
            msg = (
                f"{rendered}\n\n"
                "---\n"
                "**Reply with one of:**\n"
                "- `approve` — to approve this plan and begin execution\n"
                "- `revise: <your suggestions>` — to request specific improvements\n"
            )
            # break_loop=True: ends monologue, chat stays open, waits for user reply
            return Response(message=msg, break_loop=True)

        # ── approve ────────────────────────────────────────────────────────────
        elif action == "approve":
            data["status"] = "approved"
            data["approved_at"] = _now()
            _save(data)
            return Response(
                message="Plan approved. Proceed with execution — create the todo list next.",
                break_loop=False,
            )

        # ── revise ─────────────────────────────────────────────────────────────
        elif action == "revise":
            feedback = (self.args.get("feedback") or "").strip()
            if not feedback:
                return Response(message="Provide 'feedback' for revision.", break_loop=False)
            data["status"] = "revision_pending"
            data["revision_feedback"] = feedback
            _save(data)
            return Response(
                message=f"Revision noted: '{feedback}'. Re-research affected points and call present_plan again.",
                break_loop=False,
            )

        # ── get ────────────────────────────────────────────────────────────────
        elif action == "get":
            return Response(message=_render_plan(data), break_loop=False)

        else:
            return Response(
                message="Valid actions: save_base_plan, save_point_research, present_plan, approve, revise, get.",
                break_loop=False,
            )

    def _chat_id(self) -> str:
        return str(
            getattr(self.agent, "chat_id", None)
            or getattr(self.agent.context, "id", None)
            or "default"
        )
