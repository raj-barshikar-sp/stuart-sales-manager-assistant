---
document_id: DOC-DEAL-002
title: Deal Desk, Quoting Governance & Commercial Guardrails
category: Commercial & Operations
target_roles:
  - Sales Manager
  - Deal Desk Analyst
  - Pricing & Packaging Director
  - Regional Vice President (RVP)
last_updated: 2026-08-20
effective_fiscal_year: FY26-FY27
security_classification: Confidential - Internal Sales Only
---

# 1. Stage-Gated Quoting Governance

All opportunities in Salesforce CPQ must adhere to strict stage-gate requirements before advancing through the sales cycle:

| Opportunity Stage | CPQ Quoting Requirement | Required Approvals | Locking Conditions |
| :--- | :--- | :--- | :--- |
| **SS02 - Discovery** | No CPQ quote required. Estimated ARR amount only. | N/A | Open editing allowed. |
| **SS20 - Solution Validated** | **Draft Primary Quote** must be created in Salesforce CPQ with selected SKU package. | Sales Manager review | Line items editable, standard pricing. |
| **SS40 - Proposal / Justification** | **Approved Primary Quote** required. Discount thresholds validated. | Sales Manager & Deal Desk | Pricing, term length, and billing schedule locked. |
| **SS60 - Final Negotiation** | Legal & InfoSec approvals logged on Quote. Redlines attached. | Legal & Deal Desk | Only payment terms / minor language open. |
| **SS80 - Closed Pending** | Executed Order Form or Signed Agreement attached. | Finance & RevOps | Fully locked; no edits permitted. |

---

# 2. Discount Authorization Matrix (Delegation of Authority)

Discount calculations apply against standard List Price (ACV / ARR) in Salesforce CPQ:

## 2.1 Identity Security Cloud (ISC) Subscription SKUs
- **0% – 15% Discount**: **First-Line Sales Manager Approval** (Automatic approval routing in CPQ).
- **16% – 25% Discount**: **Regional Vice President (RVP) Approval** required.
- **26% – 35% Discount**: **SVP / Area Vice President + Deal Desk Lead** approval required.
- **> 35% Discount**: **Chief Revenue Officer (CRO) & Chief Financial Officer (CFO)** approval required.

## 2.2 Add-on Modules (NERM, DAS, CIEM) & Professional Services
- **NERM / DAS / CIEM**: Standard manager limit is capped at **10%**. Any discount > 20% requires Business Unit GM approval.
- **SailPoint Expert Services / Deployment Packages**: Maximum discretionary manager discount is **0%**. Any discount on fixed-scope packages requires Services VP approval.

---

# 3. Contract Terms & Non-Standard Guardrails

## 3.1 Multi-Year Commitments & Escalators
- **Standard Contract Term**: 36 months (3 Years), billed annually in advance.
- **Annual Price Escalator**:
  - Standard required escalator: **5% to 7% annual uplift** on Year 2 and Year 3.
  - Flat pricing (0% uplift across 36 months) requires RVP + Deal Desk approval.
  - Multi-year contracts < 36 months (e.g., 12 or 24 months) require Deal Desk approval and forfeit standard multi-year discount credits.

## 3.2 Payment Terms & Billing Schedules
- **Standard Payment Terms**: Net 30 days from invoice date; annual in advance.
- **Non-Standard Terms Requiring Finance Approval**:
  - Net 45 or Net 60 days.
  - Semi-annual or quarterly billing in advance (incurs a standard **3% finance surcharge**).
  - Billing in arrears (strictly prohibited without CFO written authorization).

---

# 4. Legacy Modernization (IIQ to SaaS) Carve-Out Policy

When migrating an existing on-premises IdentityIQ (IIQ) customer to Identity Security Cloud (ISC):
1. **Carve-Out Note Requirement**: The CPQ quote must specify the credit carve-out for remaining unamortized maintenance/support.
2. **Dual-Run Bridge Allowance**: Standard customer bridge period (running both IIQ and ISC simultaneously) is **up to 6 months** without additional maintenance penalties. Bridge periods beyond 6 months require Deal Desk & Services VP approval.
3. **Net New ARR Calculation**: Only incremental subscription revenue above the annualized maintenance baseline counts toward Net New ACV/ARR quota attainment.
