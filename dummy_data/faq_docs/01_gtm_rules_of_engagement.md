---
document_id: DOC-GOV-001
title: SailPoint GTM Rules of Engagement & Account Ownership Policy
category: Governance & Policy
target_roles:
  - Sales Manager
  - Regional Vice President (RVP)
  - Account Executive (AE)
  - Sales Development Representative (SDR)
last_updated: 2026-08-15
effective_fiscal_year: FY26-FY27
security_classification: Confidential - Internal Sales Only
---

# 1. Account Ownership & Assignment Framework

## 1.1 Named Accounts vs. Non-Named Accounts
- **Named Accounts**: Accounts explicitly allocated to a designated enterprise Account Executive (AE) during annual fiscal planning.
  - Designated in Salesforce (SFDC) by the boolean field `Is_Named_Account__c = TRUE`.
  - Once finalized at the start of the fiscal year, Named Account lists are frozen for a minimum of 12 months.
  - Named AE retains exclusive rights to all pipeline generation, cross-sell, and upsell within the defined parent entity and eligible subsidiaries.
- **Non-Named Accounts (Territory / Commercial)**: Accounts within a geographic territory that are not explicitly assigned to a Named AE list.
  - Designated by `Is_Named_Account__c = FALSE`.
  - Assigned dynamically by geography, postal code mapping, or industry vertical through round-robin or DSR routing.

## 1.2 Headquarters (HQ) Rule
- Account assignment is strictly governed by the **Global Corporate Headquarters** billing location recorded in SFDC (`Account.BillingCountry`, `Account.BillingState`).
- Subsidiaries and branch offices located in other geographies roll up to the primary parent account owner unless an explicit territory carve-out or split agreement has been formally documented and approved by the corresponding RVPs.

## 1.3 Lead Routing & Poaching Rules
- Working an inbound Marketing Qualified Lead (MQL) or SDR-sourced contact does not grant ownership over an account that belongs to another AE's named territory.
- Any inbound inquiry associated with a Named Account must be reassigned to the Named AE within **24 business hours**.
- If an AE knowingly opens or progresses an opportunity in another rep's named account ("poaching"), the opportunity will be reassigned immediately with **0% commission credit** to the originating rep.

---

# 2. Split Credit & Co-Selling Governance

## 2.1 Standard Inter-Territory Split Rules
When deal execution requires material co-selling between two geographic regions (e.g., procurement and executive sponsor in North America, technical rollout and local budget in EMEA):
- **Eligibility**: Both reps must actively participate in discovery, proof of value (POV), or commercial negotiations.
- **Approval Path**: Requires written concurrence from both direct Sales Managers and approval from the respective RVPs in Rev Intel / SFDC.
- **Standard Ratio**: 50% / 50% ARR quota retirement and commission credit. Alternate ratios (e.g., 70/30, 60/40) require Regional VP of Sales Operations sign-off.

## 2.2 Overlay & Specialist Quota Retirement
- **Modernization Overlay Representatives**: When converting legacy on-premises IdentityIQ (IIQ) customers to Identity Security Cloud (ISC), overlay specialists receive overlay quota credit without reducing the core AE's 100% ARR base quota retirement.
- **Product Specialists (e.g., NERM, DAS)**: Product-specific overlay credit applies in addition to the territory AE credit on deals where the specialist led technical discovery and sizing.

---

# 3. Holdover & Grace Period Policy

## 3.1 Account Transition Holdover
- If a rep is transitioned off an account during territory re-alignments:
  - Opportunities in **Stage SS40 (Proposal / Business Justification)** or higher closing within **60 calendar days** of territory handover remain eligible for full commission credit to the departing AE.
  - Opportunities in **Stage SS02 or SS20** transition to the new account owner immediately with 0% holdover credit to the previous AE.

## 3.2 Rep Departure & Abandoned Pipeline
- When an AE departs the company, pipeline is immediately assigned to the First-Line Sales Manager (`ManagerId`) as interim custodian until reassigned to an active rep.
- The interim manager must reallocate open opportunities within **14 business days**.

---

# 4. Dispute Resolution & Escalation Matrix

1. **Tier 1 (Direct Managers)**: Originating AE manager and contested AE manager must convene within 3 business days to reach mutual agreement.
2. **Tier 2 (Regional VP / Sales Operations)**: Unresolved disputes escalate to Regional Sales Operations for factual CRM audit (timeline of creation, touchpoints, Outreach activity).
3. **Tier 3 (SVP Worldwide Sales)**: Final, non-appealable arbitration.
