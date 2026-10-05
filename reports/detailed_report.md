# Tax Analysis & GST Compliance — Detailed Project Report

**Project**: Automated GST Compliance & Tax Leakage Audit Pipeline  
**Author**: Chetan | Data Analyst  
**Date**: October 2024  
**Dataset**: 50,000+ B2B Invoices & 500 Vendor Profiles  
**Time Period**: January 2023 – September 2024  

---

## Executive Summary

Goods and Services Tax (GST) compliance in India is a major operational challenge for medium-to-large enterprises due to multi-tiered tax slabs (0%, 5%, 12%, 18%, 28%), distinct destination-based tax rules (IGST for inter-state vs CGST+SGST for intra-state), and stringent GSTR-2B Input Tax Credit (ITC) reconciliation mandates. 

This project establishes an **automated GST audit and tax leakage analytics pipeline** analyzing 50,000 B2B invoices and 500 supplier entities. The pipeline surfaced **₹2.31 Crores in net tax leakage** and uncovered **₹87 Lakhs in unclaimed eligible Input Tax Credit (ITC)**. By instituting a 6-rule automated audit verification engine, the business can mitigate tax non-compliance penalties, recover working capital, and streamline quarterly vendor reconciliation cycles.

---

## Problem Statement

Indian enterprises routinely lose substantial revenue and incur statutory penalties due to several systemic invoice processing errors:

1. **IGST vs CGST/SGST Misclassification**: ERP systems or billing vendors frequently charge CGST+SGST on inter-state shipments instead of IGST (or vice versa), creating invalid tax invoices that fail automated GST portal reconciliation.
2. **HSN Code Rate Inconsistencies**: Over 10% of invoices reflect applied GST rates divergent from prescribed HSN master schedules, resulting in either under-collection liabilities or buyer disputes.
3. **Buyer GSTIN Invalidation & Missing ITC**: Approximately 5% of vendor invoices contain malformed or inactive buyer GSTINs, preventing legitimate ITC claims under Section 16(2) of the CGST Act.
4. **Delayed & Forfeited ITC Claims**: Strict statutory timelines (Section 16(4)) dictate that unclaimed ITC within 180 days results in permanent cash loss.
5. **Vendor Risk Blindspots**: In the absence of quantifiable vendor compliance scoring, chronic non-compliant suppliers continue to pass on reconciliation burdens to the accounts payable team.

---

## Data Architecture & Scope

| Table | Records | Key Fields | Purpose |
|---|---|---|---|
| `invoices.csv` | 50,000 | `invoice_id`, `supplier_gstin`, `buyer_gstin`, `transaction_type`, `hsn_code`, `taxable_value_inr`, `igst_charged_inr`, `cgst_charged_inr`, `sgst_charged_inr`, `tax_leakage_inr`, `itc_eligible`, `audit_risk_score` | Core transactional tax records |
| `vendors.csv` | 500 | `vendor_id`, `vendor_name`, `gstin`, `state`, `compliance_rate_pct`, `avg_itc_delay_days`, `vendor_risk_category` | Vendor compliance master |

- **Tax Framework**: Indian Dual GST System (Central GST, State GST, Integrated GST)
- **HSN Coverage**: Key industrial sectors including Steel (7204), IT & Electronics (8471, 8516, 8517), Pharmaceuticals (3004), Apparel (6101), Automotive (8703), and FMCG.
- **Geography**: 18 major Indian state jurisdictions (Maharashtra, Karnataka, Tamil Nadu, Delhi, Gujarat, etc.).

---

## Automated GST Audit Rules Applied

The pipeline evaluates every transaction against 6 core audit checks:

```
[Invoice Ingestion] 
       │
       ├── Rule 1: Place of Supply & IGST Misclassification Check
       ├── Rule 2: HSN Schedule & Applied GST Rate Validation
       ├── Rule 3: 15-Digit Regex GSTIN Format & State Code Match
       ├── Rule 4: GSTR-2B Eligibility & Unclaimed ITC Recovery Detection
       ├── Rule 5: Rolling Vendor Compliance Scoring & Risk Tiering
       └── Rule 6: High-Value (>₹5 Lakh) Audit Priority Trigger
```

1. **Rule 1 (IGST Misclassification)**: Assesses `supplier_state != buyer_state`. If CGST or SGST > 0, flags as statutory misclassification and computes IGST liability.
2. **Rule 2 (HSN Rate Match)**: Validates applied rate against master HSN tariff. Segregates into under-charge (liability) vs over-charge (commercial dispute).
3. **Rule 3 (GSTIN Integrity Check)**: Enforces regex pattern `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$` and matches first two digits against state identifier.
4. **Rule 4 (ITC Recovery Check)**: Filters eligible B2B invoices with unfiled ITC past standard credit cycles (>60 days).
5. **Rule 5 (Vendor Performance Index)**: Tracks historical invoice acceptance rate per vendor; groups suppliers into Gold (≥95%), Standard (85-94%), At-Risk (70-84%), and Blacklist (<70%).
6. **Rule 6 (High-Value Exposure Flag)**: Elevates invoices exceeding ₹5,00,000 taxable value containing any error directly to executive audit queues.

---

## Key Findings & Business Impact

### 1. IGST Misclassification: ₹1.43 Cr Tax Exposure
- Out of 26,450 inter-state transactions, **15.0% (3,968 invoices)** incorrectly collected CGST + SGST.
- **Root Cause**: Billing systems defaulted to vendor home state rather than shipping destination (Place of Supply).
- **Impact**: ₹1.43 Cr in incorrectly deposited tax requiring refund applications (Form RFD-01) and re-payment under IGST to avoid interest under Section 50.

### 2. Unclaimed Input Tax Credit: ₹87 Lakhs Immediate Recovery
- **3,847 eligible B2B invoices** showed zero ITC claimed despite valid vendor invoices.
- Total recoverable working capital identified: **₹87.4 Lakhs**.
- **Action**: Automated generation of reconciliation report for bulk inclusion in monthly GSTR-3B filings.

### 3. Vendor Compliance Segmentation (80/20 Rule)
- 73 out of 500 vendors (14.6%) were classified as **At-Risk or Blacklist Candidates**, accounting for **64.2% of all audit discrepancies**.
- Top misclassifying corridors: Maharashtra ↔ Karnataka and Delhi ↔ Uttar Pradesh.

### 4. High-Value Priority Invoices
- **248 high-value invoices (>₹5L)** were flagged with audit risk scores > 75/100, representing **₹1.12 Cr of concentrated financial risk**.

---

## SQL Business Queries Summary

| Query # | Focus Area | Key Output & Insight |
|---|---|---|
| **SQL-01** | Executive KPI Summary | Overall compliance rate: 76.8%, Total tax: ₹28.4 Cr, Net leakage: ₹2.31 Cr |
| **SQL-02** | IGST Misclassification Matrix | Top corridor: MH → KA (₹18.4L leakage across 412 invoices) |
| **SQL-03** | Vendor Compliance Ranking | 23 vendors flagged for contractual review (<70% compliance) |
| **SQL-04** | HSN Tariff Discrepancy | HSN 8703 (Motor Vehicles, 28%) had highest rate deviation frequency |
| **SQL-05** | Monthly ITC Trend (Window Fn) | 3-month rolling average ITC claim improved by 14% over FY24 |
| **SQL-06** | State-to-State Trade Value | Maharashtra & Gujarat account for 41% of total B2B invoice volume |
| **SQL-07** | Priority Audit Trigger List | Ranked queue of top 25 high-value non-compliant invoices |
| **SQL-08** | Unclaimed ITC by HSN & State | Electronics (HSN 8471) in Karnataka holds largest unclaimed pool |
| **SQL-09** | Vendor Risk Segmentation | Automated tier classification with total INR risk exposure |
| **SQL-10** | YoY Compliance Comparison | FY24 demonstrated 4.7% higher compliance rate vs FY23 baseline |

---

## 30-60-90 Day Strategic Remediation Roadmap

- **Day 1 – 30**: File GSTR-3B amendments to recover ₹87 Lakhs in identified unclaimed ITC before fiscal cutoff; issue correction debit/credit notes for top 248 high-value invoices.
- **Day 31 – 60**: Integrate Rule 1 & Rule 3 validation logic into ERP pre-billing hooks to block invalid GSTINs and misclassified tax heads at generation time.
- **Day 61 – 90**: Implement automated vendor scorecard reviews and mandate compliance SLA clauses in vendor renewal contracts.

---

## Technical Stack & Architecture

- **Data Processing**: Python 3.9+, Pandas, NumPy
- **Validation Engine**: Regular Expressions (Regex), Rule-based decision heuristics
- **Data Warehousing & SQL**: MySQL 8.0 (Window Functions, CTEs, Aggregations)
- **Visualization**: Matplotlib, Seaborn (8-panel executive dashboard at 300 DPI)

---
*Report published as part of the Data Analyst Portfolio | Author: Chetan*
