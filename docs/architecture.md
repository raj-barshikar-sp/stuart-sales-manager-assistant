# Stuart architecture

The Sales Manager talks only to `central_orchestrator`. The workflow runs one
deterministic CRM-hygiene preflight, routes directly to one or more specialists,
and merges operational results through the hidden `synthesis` writer.

```text
Sales Manager → central_orchestrator → deterministic CRM hygiene
                                      ├─ crm_intelligence_specialist ─┐
                                      ├─ activity_engagement_specialist
                                      ├─ rep_performance_specialist   ├→ synthesis
                                      ├─ forecast_modeling_specialist ┘
                                      └─ knowledge_base_rag → policy_answer
```

The five routable IDs are:

- `crm_intelligence_specialist`: Salesforce CRM score, official Confluence
  stage evidence, deal roll-up, coverage, and backup opportunities.
- `activity_engagement_specialist`: Gong verbal calls and deal intelligence,
  plus calendar and email engagement.
- `rep_performance_specialist`: Workday tenure-tier minima and actuals, Gong
  coaching, and manager oversight.
- `forecast_modeling_specialist`: Salesforce quotas and opportunity
  probabilities, conversion/pacing history, Gong calls, Q+1/Q+2 forecasts,
  stagnation, and risk.
- `knowledge_base_rag`: approved Confluence knowledge through Rovo MCP v2.

`synthesis` and `policy_answer` are hidden workflow writers, not routing targets.
Knowledge-only requests skip synthesis.

## Deterministic hygiene

The preflight runs once before specialist dispatch. It checks snapshot files,
cross-source joins, requested scope, and stage-gate evidence. `CONF-DOC-005` is
the canonical stage policy. A required source column that is absent is reported
as `unverifiable`; it is never silently treated as a failed gate. Stagnation
uses the official per-stage day threshold.

## Data boundary

`agents/new_data_store.py` normalizes all five enriched v2 snapshots. It derives
account display names from opportunity names, aliases `deal_id` to opportunity
IDs, maps owners and Workday employees, exposes tenure tiers, quotas, conversion
history and weekly verbal calls, and flattens `CONF-DOC-001..005` for local
retrieval tests.

The production knowledge path exposes only Rovo's read-only
`searchConfluence` and `getConfluenceContent` tools.

## Manager workspace

The UI preserves the five manager-facing groups: Forecasting, Forecast
inspection, Rep participation, Future quarter pipeline overview, and Manager
policy & knowledge. Individual forecast-inspection tasks are owned by CRM,
activity, or forecast specialists according to their source data.

## Verification

```bash
pytest -q
adk eval agents evals/routing.evalset.json --config_file_path evals/test_config.json
```
