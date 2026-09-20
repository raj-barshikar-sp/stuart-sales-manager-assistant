# Project Gru Sales Manager

A sales-manager assistant built on **Google ADK**. A manager talks to Stuart through one front door; Stuart runs deterministic CRM hygiene, routes directly to grounded specialists, and returns one briefing.

## Flow

```
Manager → central_orchestrator → CRM hygiene → specialist(s) → synthesis
                                             └→ knowledge_base_rag → policy_answer
```

Greetings, thanks, acknowledgments (`okay great`, `got it`), and off-topic chat never open specialists. Working context is reused only for an explicit Sales Manager follow-up.

| Agent | Model | Role |
|---|---|---|
| **central_orchestrator** | Gemini 3.6 Flash | Front door, one CRM-hygiene preflight, and direct multi-specialist routing |
| **crm_intelligence_specialist** | Gemini 3.6 Flash | CRM score, stage validation, roll-up, coverage, and backup |
| **activity_engagement_specialist** | Gemini 3.6 Flash | Gong verbal calls, calendar/email engagement, and weekly updates |
| **rep_performance_specialist** | Gemini 3.6 Flash | Workday minima/actuals, Gong coaching, and manager oversight |
| **forecast_modeling_specialist** | Gemini 3.6 Flash | Quotas, conversion/pacing, Q+1/Q+2 forecast, stagnation, and risk |
| **knowledge_base_rag** | Gemini 3.6 Flash + Rovo MCP v2 | Searches approved Atlassian knowledge for policy, product, compensation, and competitive guidance |
| **policy_answer** | Gemini 3.6 Flash | Writes the FAQ reply from retrieved sections; figures it cannot source are rejected |
| **synthesis** | Gemini 3.6 Flash | Structured merge; workflow renders Summary / Insights / Actions / Artifacts |

These five IDs are the current specialist allowlist. Operational specialists are `single_turn` children and use the enriched v2 Salesforce, Gong, calendar/email, Workday, and Confluence snapshots in `new_dummy_data/`. The knowledge specialist can only use Rovo's read-only `searchConfluence` and `getConfluenceContent` tools; the Confluence snapshot is used for local tests.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set GOOGLE_API_KEY or Vertex vars
python -m ui
```

### Rovo MCP v2 FAQ knowledge

Set these values in `.env`; never commit the token:

```bash
ROVO_MCP_URL=https://mcp.atlassian.com/v2/mcp
ROVO_MCP_API_KEY=replace-with-your-service-account-key
ROVO_MCP_EMAIL=
```

Service-account API keys use Bearer auth. For a personal API token, also set
`ROVO_MCP_EMAIL`; the app then uses Basic auth. The Atlassian admin must enable
API-token authentication and grant `search:rovo:agent-interface` plus
`read:confluence:agent-interface`. If Rovo is unavailable or cannot support the
question, the FAQ reports that instead of falling back to dummy files.

Open http://127.0.0.1:8080, then **Open workspace**. The task menu has exactly five groups: **Forecasting**, **Forecast inspection**, **Rep participation**, **Future quarter pipeline overview**, and **Manager policy & knowledge**. Specialists stay hidden.

The workspace keeps chats in the browser across refresh, offers dark mode, and copies a full briefing (plus individual paste lines). Stop only marks a reply cancelled when generation is still in flight.

Developer debug UI (optional): `adk web agents` then open http://localhost:8000 and select **agents**. Use `adk web agents` (not `adk web .`) — the project folder name has a hyphen.

## Try it

- *Review deal and forecast risks for east*
- *Run the Sales Stage Validator for 0068b00001Deal002*
- *Review CRM score and activity for east*
- *Which reps need coaching or manager oversight?*
- *Show stagnated deals and the Q+1/Q+2 modeled forecast*
- *What are the rules of engagement?*
- *How do pricing and quoting approvals work?*
- *Explain the commission plan and product portfolio*

After a briefing, *thanks* or *okay great* should acknowledge only — not reopen Meridian Bank, east, or another prior account.

## Guardrails (summary)

- The manager only chats with the orchestrator; specialists cannot transfer or take over.
- The orchestrator never answers book or policy questions itself; specialists fetch the consolidated snapshots.
- Acknowledgments and off-topic chat do not run a domain team.
- Specialists must tool-call first; never invent records or scores.
- Synthesis receives specialist JSON from code, not a paraphrased orchestrator prompt.
- Stage failures, productivity gaps, stagnation flags, and Q+1/Q+2 totals must cite grounded records. FAQ answers retain source metadata internally but do not show citations to the manager.
- Session memory: manager name, last account, last territory, last opportunity.

Prompt catalog (ask → agents): [docs/prompts.md](docs/prompts.md).

Architecture: [docs/architecture.md](docs/architecture.md).

Roadmap: [docs/next-actions.md](docs/next-actions.md).

## Tests & evals

```bash
pytest -q
adk eval agents evals/routing.evalset.json --config_file_path evals/test_config.json
```

Gates are name-level routing and four-section synthesis format, not exact tool-argument strings.

Optional runtime knobs in `.env`:

- `SELLER_COPILOT_MODEL` — default `gemini-3.6-flash`
- `SELLER_COPILOT_SYNTHESIS_MODEL` — default `gemini-3.6-flash`
- `SELLER_COPILOT_MOCK_LATENCY_SECONDS` — default `0`; set to `0.5` for a slower demo
- `BOB_LOG_LEVEL` — default `INFO`; use `DEBUG` for tool-level detail
- `BOB_LOG_FILE` — default `logs/bob.log`; set to `off` to skip the file

Developer activity (sessions, routing, specialists, errors) prints in the terminal and appends to `logs/bob.log`.
