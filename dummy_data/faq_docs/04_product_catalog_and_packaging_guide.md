---
document_id: DOC-PROD-004
title: SailPoint Product Catalog, Suites & Packaging Architecture Guide
category: Product & Technical Architecture
target_roles:
  - Sales Manager
  - Solutions Engineer (SE)
  - Account Executive (AE)
  - Product Marketing Manager
last_updated: 2026-08-25
effective_fiscal_year: FY26-FY27
security_classification: Confidential - Internal Sales Only
---

# 1. SailPoint Identity Security Cloud (ISC) Suites

The flagship SaaS platform, built on the **Atlas Platform Architecture**, is packaged into two primary core suites:

## 1.1 Identity Security Cloud Business
Designed for organizations needing core enterprise Identity Governance & Administration (IGA):
- **Core Capabilities**:
  - Automated Lifecycle Management (Joiner, Mover, Leaver).
  - Access Request and Automated Approval Workflows.
  - Periodic and Event-Driven Access Certifications.
  - Out-of-the-Box (OOTB) Application Connectors (Salesforce, ServiceNow, Microsoft 365, Workday, etc.).
  - Password Management & Self-Service Reset.
- **Target Customer**: Mid-market to Enterprise organizations transitioning from manual IAM processes or legacy point solutions.

## 1.2 Identity Security Cloud Business Plus
The comprehensive enterprise package incorporating intelligent identity governance and machine learning:
- **All Features of ISC Business**, plus:
  - **Access Insights**: Visual analytics, peer-group clustering, and outlier detection.
  - **Access Modeling & Role Mining**: Automated AI-generated role suggestions and drift analysis.
  - **Access Recommendations**: Real-time approver guidance during certification campaigns to reduce access fatigue and rubber-stamping.
  - **Policy & Separation of Duties (SoD)**: Advanced multi-attribute conflict detection and preventative policy controls.
- **Target Customer**: Highly regulated enterprises (Financial Services, Healthcare, Government, Global 2000).

---

# 2. Add-On Modular Extensions

Add-ons can be co-termed with ISC Business or Business Plus licenses:

## 2.1 Non-Employee Risk Management (NERM)
- **Problem Solved**: Governance of third-party vendors, contractors, seasonal workers, supply chain partners, and bot identities that do not exist in HR systems.
- **Key Features**: Customizable registration portals, sponsor-based access sponsorship, automated contractor offboarding.

## 2.2 Data Access Security (DAS / DIF-A)
- **Problem Solved**: Discovers and governs access to unstructured data residing in cloud and on-prem file shares (SharePoint, OneDrive, Box, Google Drive, Windows File Shares, AWS S3).
- **Key Features**: Sensitive data classification (PII, PCI, HIPAA), real-time file activity monitoring, data owner identification.
- **Architectural Note**: Requires Virtual Appliance (VA) sizing review when scanning large on-premises repositories.

## 2.3 Cloud Infrastructure Entitlement Management (CIEM)
- **Problem Solved**: Manages identity permissions and eliminates excessive privileges across multi-cloud infrastructure (AWS, Microsoft Azure, Google Cloud Platform).
- **Key Features**: Effective permissions calculation, cross-cloud privilege drift detection, just-in-time (JIT) access integration.

---

# 3. Legacy IdentityIQ (IIQ) vs. Identity Security Cloud (ISC)

| Capability / Metric | Legacy IdentityIQ (IIQ) | Identity Security Cloud (ISC) |
| :--- | :--- | :--- |
| **Deployment Model** | On-premises / Customer-hosted AWS/Azure | Multi-tenant Cloud Native (Atlas SaaS) |
| **Upgrade Cadence** | Manual major upgrades every 12–24 months | Continuous, zero-downtime weekly cloud updates |
| **Connector Connectivity** | Local direct connectors on application server | Cloud direct connectors + Virtual Appliance (VA) |
| **AI / Machine Learning** | Add-on modules / custom integrations | Embedded native AI engine (Recommendations & Insights) |
| **Infrastructure Cost** | Heavy server, DB, and admin maintenance costs | Fully managed by SailPoint (Zero infra footprint) |

---

# 4. Sizing & Licensing Metrics

- **Primary License Metric**: **Identity (User) Count**.
  - All employees and active contractors managed within the system require an assigned user license.
  - External identities (e.g., customers/patients) are licensed under dedicated B2B/B2C identity tiers.
- **Minimum Order Requirement**:
  - ISC Business: Minimum 1,000 Identities.
  - ISC Business Plus: Minimum 2,500 Identities.
