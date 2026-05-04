# _a0_planner — Research & Plan Plugin

A production Agent Zero plugin that intercepts every new task and runs a **deep multi-pass research pipeline** before any execution begins. The agent creates a structured plan, researches each point with web search + LLM reasoning, presents it for approval, and only proceeds after the user approves.

## Installation

```bash
cp -r _a0_planner/ /path/to/agent-zero/plugins/_a0_planner/
docker restart agent-zero
```

## Workflow

```
User message
     │
     ▼
[monologue_start] PlannerIntercept
  → if no plan: inject MANDATORY research instruction
  → if awaiting_approval: inject re-present instruction  
  → if revision_pending: inject re-research instruction
     │
     ▼
Agent calls planner(action=save_base_plan)
  → saves 5-15 point outline to work/plans/{chat_id}.json
     │
     ▼
Agent loops: for each point
  → search_engine(point title + approaches)
  → LLM synthesizes findings
  → planner(action=save_point_research, point_index=N, ...)
  → tool returns "next: index M" — no loop
     │
     ▼
planner(action=present_plan)
  → renders full plan with all approaches
  → Response(break_loop=True) → chat pauses, user sees plan
     │
     ▼
User replies: "approve" OR "revise: <feedback>"
     │
  [approve]──────────────────────────────────────┐
     │                                           │
  [revise]                                       ▼
     │                              planner(action=approve)
     ▼                              → create todo list
planner(action=revise, feedback=...)
  → re-research affected points
  → present_plan again
```

## File Structure

```
plugins/_a0_planner/
├── plugin.yaml
├── .toggle-1
├── README.md
├── tools/
│   └── planner.py                           # 6-action tool
├── extensions/
│   └── python/
│       ├── monologue_start/
│       │   ├── _20_planner_intercept.py     # force pipeline on new tasks
│       │   └── _21_planner_user_reply.py    # parse approve/revise replies
│       └── message_loop_prompts_after/
│           └── _20_planner_inject.py        # compact plan in every prompt
└── prompts/
    └── agent.system.tool.planner.md         # LLM tool description
```

## Plan JSON Schema

```json
{
  "chat_id": "abc123",
  "status": "approved",
  "original_prompt": "Build a SaaS dashboard",
  "created_at": "2026-05-04T18:00:00+00:00",
  "approved_at": "2026-05-04T18:05:00+00:00",
  "plan": [
    {
      "title": "Tech stack selection",
      "research_summary": "React + FastAPI dominates modern stacks...",
      "approaches": ["React + FastAPI", "Next.js + tRPC", "Vue 3 + Django"],
      "researched": true
    }
  ]
}
```

Plan files: `work/plans/{chat_id}.json`

## License
MIT
