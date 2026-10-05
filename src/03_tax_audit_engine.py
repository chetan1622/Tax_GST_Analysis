# =============================================================================
# PROJECT  : Tax Analysis & GST Compliance
# SCRIPT   : 03_tax_audit_engine.py
# AUTHOR   : Chetan
# DESC     : Rule-based GST Compliance Audit Engine
#            6 Audit Rules: IGST Misclassification, HSN Rates,
#            Missing GSTIN, ITC Recovery, Vendor Compliance, High-Value Alerts
# =============================================================================

import pandas as pd
import numpy as np
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
REPORTS_DIR   = os.path.join(BASE_DIR, 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

report_lines = []

def rprint(line=""):
    print(line)
    report_lines.append(str(line))

HSN_RATES = {
    '7204': 18, '8471': 18, '3004': 12, '6101': 5,  '2709': 5,
    '8703': 28, '0901': 5,  '5208': 5,  '9403': 18, '8516': 18,
    '2204': 28, '3304': 18, '8517': 18, '4901': 0,  '1905': 18,
}


def load_data():
    inv = pd.read_csv(os.path.join(PROCESSED_DIR, 'cleaned_invoices.csv'), parse_dates=['invoice_date'])
    vnd = pd.read_csv(os.path.join(PROCESSED_DIR, 'cleaned_vendors.csv'))
    rprint(f"  Invoices loaded : {len(inv):,}")
    rprint(f"  Vendors loaded  : {len(vnd):,}")
    return inv, vnd


def rule1_igst_misclassification(inv):
    """Rule 1: Inter-state invoices must use IGST, NOT CGST+SGST."""
    rprint("\n" + "-" * 60)
    rprint("  RULE 1 — IGST Misclassification Check")
    rprint("-" * 60)

    flagged = inv[
        (inv['transaction_type'] == 'Inter-State') &
        ((inv['cgst_charged_inr'] > 0) | (inv['sgst_charged_inr'] > 0))
    ].copy()

    flagged['correct_igst_owed'] = flagged['taxable_value_inr'] * flagged['standard_gst_rate'] / 100
    flagged['igst_leakage_inr']  = flagged['correct_igst_owed'] - flagged['igst_charged_inr']
    total_leakage = flagged['igst_leakage_inr'].sum()

    rprint(f"  Inter-state invoices flagged : {len(flagged):,}")
    rprint(f"  As % of all inter-state      : {len(flagged) / len(inv[inv['transaction_type']=='Inter-State']) * 100:.1f}%")
    rprint(f"  Total IGST Leakage           : ₹{total_leakage:,.0f}")
    rprint(f"  Avg Leakage per Invoice      : ₹{flagged['igst_leakage_inr'].mean():,.0f}")
    rprint(f"\n  Top 5 States with highest IGST misclassification:")
    top_states = flagged.groupby('supplier_state')['igst_leakage_inr'].sum().nlargest(5)
    rprint(top_states.to_string())
    return flagged, total_leakage


def rule2_hsn_rate_validation(inv):
    """Rule 2: Applied GST rate must match HSN code standard rate."""
    rprint("\n" + "-" * 60)
    rprint("  RULE 2 — HSN Code Rate Validation")
    rprint("-" * 60)

    flagged = inv[inv['rate_error_flag'] == 1].copy()
    flagged['over_under'] = np.where(
        flagged['applicable_gst_rate'] > flagged['standard_gst_rate'],
        'Over-Charged', 'Under-Charged'
    )
    flagged['rate_diff_leakage'] = (
        (flagged['standard_gst_rate'] - flagged['applicable_gst_rate']) / 100 *
        flagged['taxable_value_inr']
    )

    rprint(f"  Invoices with rate errors : {len(flagged):,}")
    rprint(f"  Over-Charged invoices     : {(flagged['over_under']=='Over-Charged').sum():,}")
    rprint(f"  Under-Charged invoices    : {(flagged['over_under']=='Under-Charged').sum():,}")
    rprint(f"  Net Rate Error Leakage    : ₹{flagged['rate_diff_leakage'].sum():,.0f}")

    rprint(f"\n  HSN-wise rate errors:")
    hsn_errors = flagged.groupby(['hsn_code', 'item_description']).agg(
        count=('invoice_id', 'count'),
        total_leakage=('rate_diff_leakage', 'sum')
    ).sort_values('count', ascending=False).head(8)
    rprint(hsn_errors.to_string())
    return flagged, flagged['rate_diff_leakage'].sum()


def rule3_missing_gstin(inv):
    """Rule 3: Missing/invalid buyer GSTIN — ITC cannot be claimed."""
    rprint("\n" + "-" * 60)
    rprint("  RULE 3 — Missing / Invalid GSTIN Detection")
    rprint("-" * 60)

    flagged = inv[~inv['buyer_gstin_valid']].copy()
    itc_loss = flagged['total_tax_charged_inr'].sum()

    rprint(f"  Invoices with invalid buyer GSTIN : {len(flagged):,}")
    rprint(f"  ITC Loss to Buyer (cannot claim)  : ₹{itc_loss:,.0f}")
    rprint(f"  States most affected:")
    top_states = flagged.groupby('buyer_state').size().nlargest(5)
    rprint(top_states.to_string())
    return flagged, itc_loss


def rule4_itc_recovery(inv):
    """Rule 4: Eligible invoices where ITC was NOT claimed."""
    rprint("\n" + "-" * 60)
    rprint("  RULE 4 — ITC Recovery Opportunity")
    rprint("-" * 60)

    unclaimed = inv[(inv['itc_eligible'] == 1) & (inv['itc_claimed_inr'] == 0)].copy()
    total_itc  = unclaimed['total_tax_charged_inr'].sum()

    rprint(f"  Invoices with unclaimed ITC : {len(unclaimed):,}")
    rprint(f"  Total Recoverable ITC       : ₹{total_itc:,.0f}")
    rprint(f"\n  State-wise unclaimed ITC (Top 5):")
    state_itc = unclaimed.groupby('buyer_state')['total_tax_charged_inr'].sum().nlargest(5)
    rprint(state_itc.to_string())
    rprint(f"\n  HSN-wise unclaimed ITC (Top 5):")
    hsn_itc = unclaimed.groupby(['hsn_code', 'item_description'])['total_tax_charged_inr'].sum().nlargest(5)
    rprint(hsn_itc.to_string())
    return unclaimed, total_itc


def rule5_vendor_compliance(inv, vnd):
    """Rule 5: Vendor-level compliance scoring — flag <80% compliant vendors."""
    rprint("\n" + "-" * 60)
    rprint("  RULE 5 — Vendor Compliance Scoring")
    rprint("-" * 60)

    # Match invoices to vendors by supplier GSTIN
    # Use supplier_state to approximate
    vendor_flags = inv.groupby('supplier_state').agg(
        total_invoices   = ('invoice_id', 'count'),
        compliant        = ('compliance_status', lambda x: (x == 'Compliant').sum()),
        total_leakage    = ('tax_leakage_inr', 'sum'),
        total_tax_value  = ('total_tax_charged_inr', 'sum'),
    ).reset_index()
    vendor_flags['compliance_rate'] = (vendor_flags['compliant'] / vendor_flags['total_invoices'] * 100).round(2)
    vendor_flags['risk_flag'] = vendor_flags['compliance_rate'].apply(
        lambda x: 'NON-COMPLIANT ❌' if x < 80 else 'COMPLIANT ✅')

    non_compliant = vendor_flags[vendor_flags['risk_flag'] == 'NON-COMPLIANT ❌']
    rprint(f"  States with <80% compliance : {len(non_compliant)}")
    rprint(f"  Total tax exposure (non-compliant states) : ₹{non_compliant['total_leakage'].sum():,.0f}")
    rprint(f"\n  State compliance breakdown:")
    rprint(vendor_flags.sort_values('compliance_rate').to_string(index=False))
    return vendor_flags, non_compliant['total_leakage'].sum()


def rule6_high_value_audit_triggers(inv):
    """Rule 6: High-value invoices (>₹5L) with any compliance error — priority audit."""
    rprint("\n" + "-" * 60)
    rprint("  RULE 6 — High-Value Invoice Audit Trigger List")
    rprint("-" * 60)

    high_value = inv[
        (inv['taxable_value_inr'] > 500000) &
        (inv['compliance_status'] != 'Compliant')
    ].sort_values('audit_risk_score', ascending=False)

    rprint(f"  High-value non-compliant invoices : {len(high_value):,}")
    rprint(f"  Total Tax Leakage (these)         : ₹{high_value['tax_leakage_inr'].sum():,.0f}")
    rprint(f"\n  TOP 10 PRIORITY AUDIT INVOICES:")
    rprint(high_value[['invoice_id', 'invoice_date', 'taxable_value_inr', 'tax_leakage_inr',
                        'compliance_status', 'audit_risk_score']].head(10).to_string(index=False))
    return high_value


def print_master_report(inv, r1_leak, r2_leak, r3_itc, r4_itc):
    total = len(inv)
    compliant = (inv['compliance_status'] == 'Compliant').sum()
    non_compliant = total - compliant

    rprint("\n")
    rprint("=" * 65)
    rprint("  GST COMPLIANCE AUDIT REPORT")
    rprint(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    rprint("=" * 65)
    rprint(f"  Total Invoices Analyzed        : {total:,}")
    rprint(f"  Compliant Invoices             : {compliant:,} ({compliant/total*100:.1f}%)")
    rprint(f"  Non-Compliant Invoices         : {non_compliant:,} ({non_compliant/total*100:.1f}%)")
    rprint("")
    rprint("  TAX LEAKAGE SUMMARY:")
    rprint(f"    IGST Misclassification       : ₹{r1_leak:,.0f}")
    rprint(f"    Wrong Rate Applied           : ₹{abs(r2_leak):,.0f}")
    rprint(f"    Net Total Tax Leakage        : ₹{inv['tax_leakage_inr'].sum():,.0f}")
    rprint("")
    rprint("  ITC RECOVERY OPPORTUNITY:")
    rprint(f"    Unclaimed ITC Amount         : ₹{r4_itc:,.0f}")
    rprint(f"    Invalid GSTIN ITC Loss       : ₹{r3_itc:,.0f}")
    rprint(f"    Total Recoverable            : ₹{r3_itc + r4_itc:,.0f}")
    rprint("")
    rprint(f"  HIGH RISK Invoices (score>70)  : {(inv['audit_risk_score']>70).sum():,}")
    rprint(f"  Priority Audit Invoices (>5L)  : {((inv['taxable_value_inr']>500000)&(inv['compliance_status']!='Compliant')).sum():,}")
    rprint("=" * 65)


if __name__ == '__main__':
    rprint("=" * 65)
    rprint("  GST TAX COMPLIANCE AUDIT ENGINE — STARTING")
    rprint("=" * 65)

    inv, vnd = load_data()

    r1_flagged, r1_leak  = rule1_igst_misclassification(inv)
    r2_flagged, r2_leak  = rule2_hsn_rate_validation(inv)
    r3_flagged, r3_itc   = rule3_missing_gstin(inv)
    r4_unclaimed, r4_itc = rule4_itc_recovery(inv)
    vendor_df, _         = rule5_vendor_compliance(inv, vnd)
    hv_df                = rule6_high_value_audit_triggers(inv)

    print_master_report(inv, r1_leak, r2_leak, r3_itc, r4_itc)

    # Save report
    report_path = os.path.join(REPORTS_DIR, 'audit_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    print(f"\n✓ Audit report saved → {report_path}")
