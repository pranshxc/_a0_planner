## planner

Manages the **Research & Plan** pipeline. This MUST run before any task execution and before todo list creation.

### Mandatory Workflow (in strict order)

```
1. save_base_plan     → outline 5-15 key aspects of the task
2. save_point_research (×N) → deep research each point with search_engine + reasoning
3. present_plan       → show to user for approval (breaks loop, waits for reply)
4. [user replies]     → approve OR revise
5a. approve           → mark plan approved, then create todo list
5b. revise            → apply feedback, re-research, present_plan again
```

### Actions

| action | required args | description |
|---|---|---|
| `save_base_plan` | `original_prompt`, `points: [...]` | Save initial 5-15 point outline |
| `save_point_research` | `point_index: int`, `summary: str`, `approaches: [...]` | Save deep research for one point |
| `present_plan` | _(none)_ | Render full plan + approval prompt → **breaks loop** |
| `approve` | _(none)_ | Mark plan approved, proceed to execution |
| `revise` | `feedback: str` | Record user feedback, trigger re-research |
| `get` | _(none)_ | Print full plan (any time) |

### Research Quality Rules

- For each point: use `search_engine` to find **real, current information**.
- Document **ALL viable approaches** found, not just the "best" one.
- `approaches` list should contain 3-8 concrete, actionable methods per point.
- `summary` should be 2-4 sentences of synthesized findings.
- Use your own LLM reasoning to evaluate, compare, and add depth beyond raw search results.

### Anti-Loop Rules

- NEVER call `save_point_research` on an already-researched point (tool will reject it).
- NEVER call `present_plan` before all points are researched.
- NEVER use `response` tool before the plan is approved.
- NEVER re-run the full pipeline if a plan already exists (check status with `get`).

### Examples

```json
{"action": "save_base_plan", "original_prompt": "Build a SaaS analytics dashboard", "points": ["Tech stack selection", "Database schema design", "Authentication system", "Chart library options", "Deployment strategy"]}
```
```json
{"action": "save_point_research", "point_index": 0, "summary": "React + FastAPI is the dominant modern stack. Next.js offers SSR benefits for dashboards.", "approaches": ["React + FastAPI + PostgreSQL", "Next.js + tRPC + PlanetScale", "Vue 3 + Django + TimescaleDB", "Svelte + Express + ClickHouse"]}
```
```json
{"action": "present_plan"}
```
```json
{"action": "approve"}
```
```json
{"action": "revise", "feedback": "Include more open-source self-hosted deployment options"}
```
