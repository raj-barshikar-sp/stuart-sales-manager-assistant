# Sales Manager prompt catalog

Paste these into the workspace or ADK Web. The manager always talks to `central_orchestrator`; matching specialists query grounded records, then `synthesis` writes one briefing.

## Forecasting

- “Review deal and forecast risks for east.” → `forecast_modeling_specialist`
- “Run the Sales Stage Validator for 0068b00001Deal002 and list every failed rule.” → `crm_intelligence_specialist`

## Forecast inspection

- “Review Salesforce forecast activity for east.”
- “Compare opportunity activity to the CRM deal roll-up for east.”
- “Show pipeline coverage for east.”
- “Which large deals lack a backup opportunity?”
- “Show CRM scores for this quarter and flag weak deals.”
- “Are reps pacing to the call based on conversion rates?”
- “Which deals lack a current weekly update or next step?”

These split across `crm_intelligence_specialist`,
`activity_engagement_specialist`, and `forecast_modeling_specialist` according
to the evidence requested.

## Rep participation

- “Which reps need help based on participation and productivity?”
- “Prepare the coaching-meeting queue for my team.”
- “Which deals require manager oversight?”
- “Show productivity gaps against minimum expectations.”

All four route to `rep_performance_specialist`.

## Future quarter pipeline overview

- “Which future-quarter deals are stagnated?”
- “Model the Q+1 and Q+2 forecast separately.”
- “Show future-quarter pipeline risks, coverage gaps, and assumptions.”

All three route to `forecast_modeling_specialist`.

## Manager policy & knowledge

- “What are the rules of engagement?” → `knowledge_base_rag`
- “Who approves a 22% ISC discount?” → `knowledge_base_rag`
- “Explain the modernization SPIF.” → `knowledge_base_rag`
- “Compare ISC Business and Business Plus.” → `knowledge_base_rag`
- “How should I handle the Okta governance objection?” → `knowledge_base_rag`

The standalone FAQ agent retrieves from allowlisted Confluence spaces only
and keeps source metadata internal. If Confluence does not support the
question, it reports an explicit grounded-data error.

## Multi-specialist asks

- “Validate a deal’s stage and tell me whether its rep needs coaching.” → `crm_intelligence_specialist` + `rep_performance_specialist`
- “Compare the call to roll-up and model Q+1/Q+2.” → `activity_engagement_specialist` + `crm_intelligence_specialist` + `forecast_modeling_specialist`

## No specialists

- “hello” → direct greeting
- “thanks” / “okay great” → direct acknowledgment
- Off-topic chat → direct scope reminder

## Routing eval cases

The routing eval set covers the five legal specialist IDs plus direct and
multi-specialist cases. Operational cases expect `synthesis` last; knowledge
cases expect `policy_answer` and skip synthesis.
