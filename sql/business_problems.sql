-- ============================================================
-- PROJECT  : Tax Analysis & GST Compliance
-- AUTHOR   : Chetan
-- DATABASE : gst_compliance_db
-- DESC     : 10 Real Business Problems solved using MySQL
--            Tables: invoices (50,000), vendors (500)
--            Time Period: Jan 2023 – Sep 2024
--            Context: Indian GST framework (IGST/CGST/SGST)
-- ============================================================

CREATE DATABASE IF NOT EXISTS gst_compliance_db;
USE gst_compliance_db;

-- ============================================================
-- PROBLEM 1: Overall GST Compliance Health Dashboard
-- Business Use: One-screen KPI view for CFO and tax team —
--               total tax collected, leakage, and ITC status.
-- ============================================================
SELECT
    COUNT(*)                                               AS Total_Invoices,
    ROUND(SUM(taxable_value_inr) / 1e7, 2)                AS Total_Taxable_Value_Crores,
    ROUND(SUM(total_tax_charged_inr) / 1e7, 2)            AS Total_Tax_Collected_Crores,
    ROUND(SUM(correct_total_tax_inr) / 1e7, 2)            AS Total_Correct_Tax_Crores,
    ROUND(SUM(tax_leakage_inr) / 1e5, 2)                  AS Net_Tax_Leakage_Lakhs,
    ROUND(SUM(CASE WHEN compliance_status = 'Compliant' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2)
                                                           AS Compliance_Rate_Pct,
    ROUND(SUM(itc_claimed_inr) / 1e5, 2)                  AS Total_ITC_Claimed_Lakhs,
    SUM(CASE WHEN itc_eligible = 1 AND itc_claimed_inr = 0 THEN 1 ELSE 0 END)
                                                           AS Unclaimed_ITC_Invoices
FROM invoices;
-- Expected: ~75-80% compliance, ₹20-30Cr total tax, significant ITC unclaimed


-- ============================================================
-- PROBLEM 2: IGST Misclassification — Core Tax Leakage Driver
-- Business Use: Quantify how much revenue is lost because
--               inter-state transactions used CGST+SGST wrongly.
-- ============================================================
SELECT
    supplier_state,
    buyer_state,
    COUNT(*)                                               AS Misclassified_Invoices,
    ROUND(SUM(taxable_value_inr) / 1e5, 2)                AS Taxable_Value_Lakhs,
    ROUND(SUM(igst_charged_inr), 0)                        AS IGST_Actually_Charged,
    ROUND(SUM(correct_igst_inr), 0)                        AS IGST_Should_Have_Been,
    ROUND(SUM(correct_igst_inr) - SUM(igst_charged_inr), 0)
                                                           AS IGST_Leakage_INR
FROM invoices
WHERE transaction_type = 'Inter-State'
  AND (cgst_charged_inr > 0 OR sgst_charged_inr > 0)
GROUP BY supplier_state, buyer_state
ORDER BY IGST_Leakage_INR DESC
LIMIT 15;
-- Expected: Maharashtra→Karnataka, Delhi→UP corridors have highest misclassification


-- ============================================================
-- PROBLEM 3: Vendor Compliance Ranking
-- Business Use: Identify top and bottom vendors for
--               compliance review, blacklisting, or rewarding.
-- ============================================================
WITH vendor_stats AS (
    SELECT
        supplier_gstin,
        supplier_state,
        COUNT(*)                                           AS Total_Invoices,
        SUM(CASE WHEN compliance_status = 'Compliant' THEN 1 ELSE 0 END)
                                                           AS Compliant_Count,
        ROUND(SUM(CASE WHEN compliance_status='Compliant' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2)
                                                           AS Compliance_Rate_Pct,
        ROUND(SUM(tax_leakage_inr), 0)                    AS Total_Leakage_INR,
        ROUND(SUM(taxable_value_inr) / 1e5, 2)            AS Total_Value_Lakhs
    FROM invoices
    GROUP BY supplier_gstin, supplier_state
    HAVING Total_Invoices >= 5
)
SELECT
    supplier_gstin,
    supplier_state,
    Total_Invoices,
    Compliance_Rate_Pct,
    Total_Leakage_INR,
    Total_Value_Lakhs,
    CASE
        WHEN Compliance_Rate_Pct >= 95 THEN 'GOLD Vendor ⭐'
        WHEN Compliance_Rate_Pct >= 85 THEN 'STANDARD Vendor ✅'
        WHEN Compliance_Rate_Pct >= 70 THEN 'AT-RISK Vendor 🔶'
        ELSE 'BLACKLIST Candidate ❌'
    END                                                    AS Vendor_Classification
FROM vendor_stats
ORDER BY Compliance_Rate_Pct ASC
LIMIT 20;
-- Expected: ~5% vendors qualify as Blacklist Candidates


-- ============================================================
-- PROBLEM 4: HSN Code-wise Tax Collection vs Expected
-- Business Use: Which product categories drive the most
--               tax disputes? Useful for GST audit prioritization.
-- ============================================================
SELECT
    hsn_code,
    item_description,
    standard_gst_rate                                      AS Correct_GST_Rate_Pct,
    COUNT(*)                                               AS Total_Invoices,
    ROUND(SUM(taxable_value_inr) / 1e5, 2)                AS Taxable_Value_Lakhs,
    ROUND(SUM(total_tax_charged_inr) / 1e5, 2)            AS Tax_Charged_Lakhs,
    ROUND(SUM(correct_total_tax_inr) / 1e5, 2)            AS Correct_Tax_Lakhs,
    ROUND(SUM(tax_leakage_inr) / 1e5, 2)                  AS Net_Leakage_Lakhs,
    SUM(CASE WHEN rate_error_flag = 1 THEN 1 ELSE 0 END)  AS Rate_Error_Count,
    ROUND(SUM(CASE WHEN rate_error_flag=1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2)
                                                           AS Rate_Error_Rate_Pct
FROM invoices
GROUP BY hsn_code, item_description, standard_gst_rate
ORDER BY Net_Leakage_Lakhs DESC;
-- Expected: HSN 8703 (Cars, 28%) and 8471 (Computers, 18%) show most errors


-- ============================================================
-- PROBLEM 5: Monthly ITC Claim Trend with Rolling Average
-- Business Use: Track if ITC recovery is improving or
--               declining month-over-month.
-- ============================================================
WITH monthly_itc AS (
    SELECT
        DATE_FORMAT(invoice_date, '%Y-%m')                 AS invoice_month,
        ROUND(SUM(itc_claimed_inr) / 1e5, 2)              AS itc_claimed_lakhs,
        ROUND(SUM(CASE WHEN itc_eligible=1 THEN total_tax_charged_inr ELSE 0 END) / 1e5, 2)
                                                           AS itc_eligible_lakhs,
        COUNT(CASE WHEN itc_eligible=1 AND itc_claimed_inr=0 THEN 1 END)
                                                           AS unclaimed_count
    FROM invoices
    GROUP BY DATE_FORMAT(invoice_date, '%Y-%m')
)
SELECT
    invoice_month,
    itc_claimed_lakhs,
    itc_eligible_lakhs,
    ROUND(itc_claimed_lakhs / NULLIF(itc_eligible_lakhs, 0) * 100, 2)
                                                           AS ITC_Claim_Rate_Pct,
    unclaimed_count,
    ROUND(AVG(itc_claimed_lakhs) OVER (
        ORDER BY invoice_month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2)                                                  AS Rolling_3M_Avg_ITC_Claimed
FROM monthly_itc
ORDER BY invoice_month;
-- Expected: ITC claim rate improves as companies get compliant over time


-- ============================================================
-- PROBLEM 6: State-to-State Trade Flow & Tax Value
-- Business Use: Which inter-state corridors drive the most
--               IGST revenue? Useful for policy and audit targeting.
-- ============================================================
SELECT
    supplier_state,
    buyer_state,
    COUNT(*)                                               AS Total_Transactions,
    ROUND(SUM(taxable_value_inr) / 1e7, 2)                AS Trade_Value_Crores,
    ROUND(SUM(igst_charged_inr) / 1e5, 2)                 AS IGST_Collected_Lakhs,
    ROUND(SUM(tax_leakage_inr) / 1e5, 2)                  AS Tax_Leakage_Lakhs
FROM invoices
WHERE transaction_type = 'Inter-State'
GROUP BY supplier_state, buyer_state
HAVING Total_Transactions >= 50
ORDER BY Trade_Value_Crores DESC
LIMIT 20;
-- Expected: Maharashtra↔Karnataka, Delhi↔UP are top trade corridors


-- ============================================================
-- PROBLEM 7: Priority Audit List — High-Value Non-Compliant
-- Business Use: Generate a ranked list of invoices for
--               immediate human audit review, sorted by risk score.
-- ============================================================
SELECT
    invoice_id,
    invoice_date,
    supplier_state,
    buyer_state,
    hsn_code,
    item_description,
    ROUND(taxable_value_inr, 0)                            AS Taxable_Value_INR,
    ROUND(total_tax_charged_inr, 0)                        AS Tax_Charged_INR,
    ROUND(correct_total_tax_inr, 0)                        AS Correct_Tax_INR,
    ROUND(tax_leakage_inr, 0)                              AS Tax_Leakage_INR,
    compliance_status,
    audit_risk_score,
    CASE
        WHEN audit_risk_score >= 80 THEN 'IMMEDIATE AUDIT 🚨'
        WHEN audit_risk_score >= 60 THEN 'PRIORITY REVIEW 🔶'
        ELSE 'STANDARD REVIEW 📋'
    END                                                    AS Audit_Priority
FROM invoices
WHERE taxable_value_inr > 500000
  AND compliance_status != 'Compliant'
ORDER BY audit_risk_score DESC, tax_leakage_inr DESC
LIMIT 25;
-- Expected: 150-250 invoices with ₹5L+ taxable value flagged for audit


-- ============================================================
-- PROBLEM 8: ITC Recovery Opportunity by State and HSN
-- Business Use: Where should the tax team focus to recover
--               maximum unclaimed ITC?
-- ============================================================
SELECT
    buyer_state,
    hsn_code,
    item_description,
    COUNT(*)                                               AS Eligible_Unclaimed_Invoices,
    ROUND(SUM(total_tax_charged_inr) / 1e5, 2)            AS Recoverable_ITC_Lakhs,
    ROUND(AVG(total_tax_charged_inr), 0)                   AS Avg_ITC_Per_Invoice
FROM invoices
WHERE itc_eligible = 1
  AND itc_claimed_inr = 0
GROUP BY buyer_state, hsn_code, item_description
ORDER BY Recoverable_ITC_Lakhs DESC
LIMIT 20;
-- Expected: Maharashtra and Karnataka have highest unclaimed ITC in Electronics


-- ============================================================
-- PROBLEM 9: Vendor Risk Segmentation with INR Exposure
-- Business Use: Classify vendors into risk tiers with
--               financial exposure — input for procurement policy.
-- ============================================================
SELECT
    CASE
        WHEN compliance_rate_pct >= 95 THEN 'Tier 1 — Low Risk'
        WHEN compliance_rate_pct >= 80 THEN 'Tier 2 — Medium Risk'
        WHEN compliance_rate_pct >= 65 THEN 'Tier 3 — High Risk'
        ELSE 'Tier 4 — Critical / Blacklist'
    END                                                    AS Risk_Tier,
    COUNT(*)                                               AS Vendor_Count,
    ROUND(AVG(compliance_rate_pct), 2)                     AS Avg_Compliance_Rate
FROM vendors
GROUP BY Risk_Tier
ORDER BY Avg_Compliance_Rate DESC;
-- Expected: 80/20 rule — 80% vendors are Tier1/2, 20% cause 80% of issues


-- ============================================================
-- PROBLEM 10: Year-over-Year Comparison 2023 vs 2024
-- Business Use: Has GST compliance improved YoY?
--               Are we recovering more ITC? Is tax leakage reducing?
-- ============================================================
SELECT
    invoice_year,
    COUNT(*)                                               AS Total_Invoices,
    ROUND(SUM(taxable_value_inr) / 1e7, 2)                AS Taxable_Value_Crores,
    ROUND(SUM(total_tax_charged_inr) / 1e7, 2)            AS Tax_Collected_Crores,
    ROUND(SUM(tax_leakage_inr) / 1e5, 2)                  AS Tax_Leakage_Lakhs,
    ROUND(SUM(itc_claimed_inr) / 1e5, 2)                  AS ITC_Claimed_Lakhs,
    ROUND(SUM(CASE WHEN compliance_status='Compliant' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2)
                                                           AS Compliance_Rate_Pct,
    ROUND(SUM(CASE WHEN compliance_status='IGST Misclassification' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2)
                                                           AS IGST_Misclass_Rate_Pct,
    SUM(CASE WHEN itc_eligible=1 AND itc_claimed_inr=0 THEN 1 ELSE 0 END)
                                                           AS Unclaimed_ITC_Invoices
FROM invoices
WHERE invoice_year IN (2023, 2024)
GROUP BY invoice_year
ORDER BY invoice_year;
-- Expected: 2024 shows higher compliance rate and more ITC claimed vs 2023
