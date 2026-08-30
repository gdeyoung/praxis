# Role template — defining an agent so someone else can recreate it

Every agent and subagent in our fleet is defined by the same schema. A role definition is a single markdown block with the fields below; it doubles as the context payload a parent passes when spawning a worker of that type. Copy this template, fill it in, and the role is runnable on any platform with a delegation primitive.

## The template

```markdown
# role: <name>

## Purpose
One sentence: what this role exists to do. If it takes two, it's two roles.

## Models
| Task | Routes to |
|---|---|
| <task shape> | <alias or model tier> |
Routing by task shape, never by model name — implementations swap, aliases stay.

## Tools
The exact toolset, scoped to the minimum: <tools/MCP servers/endpoints>.
If it can't be listed, it isn't scoped.

## Scope
- IN: what this role does, decides, and writes
- OUT: what it must not touch (explicit exclusions prevent boundary creep)

## Standards
The quality bar: error handling expectations, testing requirements,
verification steps, format rules. Named concretely, not "high quality."

## Reporting
What comes back to the parent/human: format, required evidence
(handles: URLs, paths, exit codes), and escalation conditions
(two identical failures → stop and ask).

## Persistence (optional)
Where durable knowledge from this role's work goes:
vault path, index domain, or "session only."
```

## The rules that make roles work

1. **One purpose per role.** A role that researches *and* publishes *and* monitors is three roles with a shared name. Split it.
2. **Scope OUT is load-bearing.** The exclusions are what let you hand a role autonomy without a leash. "Never writes skills", "never publishes without queue approval", "no package installs outside sandbox" — each one exists because its absence cost something.
3. **Evidence in reporting, always.** A worker's summary is a self-report; the required handles (URL, absolute path, exit code, test count) are what the parent verifies. No handle, no trust.
4. **Roles are data, not code.** Keep the definitions in version control next to the configs. Diffing a role change should be as ordinary as diffing a config change.
5. **Leaf by default.** A role gets delegation rights only if its purpose is orchestration; recursion depth is bounded at 1 unless explicitly raised.

## The catalog we run (de-identified)

| Role class | Roles | Purpose |
|---|---|---|
| **Orchestrator hubs** | architect, research-lead | Plan, split, dispatch, verify, integrate — hold judgment, not task work |
| **Dev workers** | backend, frontend, sre, data | Production code and infra per the dev-team template; report with evidence |
| **Researchers** | tech, market, academic, osint, data-analyst | Source-tiered research with confidence labels and cited gaps |
| **Specialists** | media, qa, security, sysadmin | Domain depth: pipelines, quality gates, threat models, ops |
| **Autonomous** | learners (fleet, work), curator, improvement-scanner | Scheduled unattended cycles; learners never write skills, curator is the sole skill-writer |

The full role definitions (with models, toolsets, and standards per role) live in the fleet's ops handbook — the shape above is everything you need to rebuild them on your own stack. Start with two roles (one orchestrator, one worker), get the delegation loop solid, then add specialists as real work demands them. A role created before its workload exists is inventory.
