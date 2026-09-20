# Next actions

Keep the architecture: **orchestrator → Sales Manager specialists
(`single_turn` tools + structured output) → synthesis**. The manager never
selects a specialist and synthesis always writes the final briefing.

## Product direction

1. Keep the linked JSON fixtures as the source of truth while specialist
   contracts stabilize.
2. Expand routing evals for cross-team asks and explicit follow-ups.
3. Add real CRM, forecasting, enablement, and policy connectors only after the
   deterministic mock workflows are stable.

## Definition of done for each specialist

- `mode="single_turn"`, transfer disabled, and a typed output schema.
- Tool calls against grounded records; unknown scope returns an explicit error.
- Registry entry, routing hints, task-menu prompt, and progress copy.
- Synthesis remains last and never exposes internal agent or table names.
- Unit tests plus at least one routing-eval case.
