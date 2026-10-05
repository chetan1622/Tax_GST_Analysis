# =============================================================================
# PROJECT  : Tax Analysis & GST Compliance
# SCRIPT   : 02_data_cleaning.py
# AUTHOR   : Chetan
# DESC     : Loads raw GST invoice data, validates GSTIN format,
#            detects misclassifications, computes risk tiers,
#            saves cleaned data to data/processed/
# =============================================================================

import pandas as pd
import numpy as np
import re
import os
import warnings
warnings.filterwarnings('ignore')

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR       = os.path.join(BASE_DIR, 'data', 'raw')
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
os.makedirs(PROCESSED_DIR, exist_ok=True)

VALID_GSTIN_PATTERN = re.compile(r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d{1}Z\d{1}$')

HSN_RATES = {
    '7204': 18, '8471': 18, '3004': 12, '6101': 5,  '2709': 5,
    '8703': 28, '0901': 5,  '5208': 5,  '9403': 18, '8516': 18,
    '2204': 28, '3304': 18, '8517': 18, '4901': 0,  '1905': 18,
}


def validate_gstin(gstin_str):
    """Returns True if GSTIN matches Indian format."""
    if pd.isna(gstin_str) or gstin_str == '':
        return False
    return bool(VALID_GSTIN_PATTERN.match(str(gstin_str)))


def load_raw():
    print("Loading raw data...")
    invoices = pd.read_csv(os.path.join(RAW_DIR, 'invoices.csv'))
    vendors  = pd.read_csv(os.path.join(RAW_DIR, 'vendors.csv'))
    print(f"  invoices.csv : {invoices.shape}")
    print(f"  vendors.csv  : {vendors.shape}")
    return invoices, vendors


def clean_invoices(df):
    print("\n── Cleaning: invoices ──")
    before_rows = len(df)

    # Fix dtypes
    df['invoice_date']    = pd.to_datetime(df['invoice_date'])
    df['itc_claim_date']  = pd.to_datetime(df['itc_claim_date'], errors='coerce')

    # Remove exact duplicates
    df.drop_duplicates(subset='invoice_id', inplace=True)
    print(f"  Duplicates removed : {before_rows - len(df)}")

    # ── GSTIN Validation ──────────────────────────────────────
    df['supplier_gstin_valid'] = df['supplier_gstin'].apply(validate_gstin)
    df['buyer_gstin_valid']    = df['buyer_gstin'].apply(validate_gstin)
    invalid_buyer  = (~df['buyer_gstin_valid']).sum()
    invalid_supplier = (~df['supplier_gstin_valid']).sum()
    print(f"  Invalid Buyer GSTIN    : {invalid_buyer:,}")
    print(f"  Invalid Supplier GSTIN : {invalid_supplier:,}")

    # ── Tax Consistency Check ─────────────────────────────────
    # For inter-state: IGST should be charged, NOT CGST/SGST
    df['igst_misclassification_flag'] = (
        (df['transaction_type'] == 'Inter-State') &
        ((df['cgst_charged_inr'] > 0) | (df['sgst_charged_inr'] > 0))
    ).astype(int)

    # For intra-state: CGST+SGST should be charged, NOT IGST
    df['intrastate_igst_flag'] = (
        (df['transaction_type'] == 'Intra-State') &
        (df['igst_charged_inr'] > 0)
    ).astype(int)

    # ── HSN Rate Validation ───────────────────────────────────
    df['expected_gst_rate'] = df['hsn_code'].astype(str).map(HSN_RATES)
    df['rate_error_flag'] = (
        df['applicable_gst_rate'] != df['expected_gst_rate']
    ).astype(int)

    # ── Net Tax Leakage ───────────────────────────────────────
    df['net_tax_leakage_inr'] = (df['correct_total_tax_inr'] - df['total_tax_charged_inr']).round(2)
    df['leakage_direction'] = df['net_tax_leakage_inr'].apply(
        lambda x: 'Under-Charged' if x > 0 else ('Over-Charged' if x < 0 else 'Correct'))

    # ── Risk Tier ─────────────────────────────────────────────
    df['risk_tier'] = pd.cut(
        df['audit_risk_score'],
        bins=[-1, 39, 69, 100],
        labels=['Low Risk', 'Medium Risk', 'High Risk']
    )

    # ── ITC Gap ───────────────────────────────────────────────
    df['itc_gap_inr'] = (
        (df['itc_eligible'] == 1) &
        (df['itc_claimed_inr'] == 0)
    ).astype(int) * df['total_tax_charged_inr']

    # ── Derived Time Fields ───────────────────────────────────
    df['invoice_month']   = df['invoice_date'].dt.to_period('M').astype(str)
    df['invoice_year']    = df['invoice_date'].dt.year
    df['invoice_quarter'] = df['invoice_date'].dt.quarter.map({1:'Q1',2:'Q2',3:'Q3',4:'Q4'})

    # ── Fill Nulls ────────────────────────────────────────────
    df['itc_claimed_inr'] = df['itc_claimed_inr'].fillna(0)
    df['tax_leakage_inr'] = df['tax_leakage_inr'].fillna(0)

    return df


def clean_vendors(df):
    print("\n── Cleaning: vendors ──")
    df.drop_duplicates(subset='vendor_id', inplace=True)
    df['compliance_rate_pct'] = df['compliance_rate_pct'].fillna(df['compliance_rate_pct'].median())
    df['gstin_valid'] = df['gstin'].apply(validate_gstin)
    df['vendor_risk_category'] = df['compliance_rate_pct'].apply(
        lambda x: 'Low' if x >= 90 else ('Medium' if x >= 75 else 'High'))
    return df


def print_data_quality_report(invoices):
    total = len(invoices)
    print("\n" + "=" * 65)
    print("  GST DATA QUALITY & COMPLIANCE REPORT")
    print("=" * 65)
    print(f"  Total Invoices Processed       : {total:,}")
    print(f"  Compliant Invoices             : {(invoices['compliance_status']=='Compliant').sum():,} "
          f"({(invoices['compliance_status']=='Compliant').sum()/total*100:.1f}%)")
    print(f"  IGST Misclassified             : {invoices['igst_misclassification_flag'].sum():,} "
          f"({invoices['igst_misclassification_flag'].sum()/total*100:.1f}%)")
    print(f"  GST Rate Errors                : {invoices['rate_error_flag'].sum():,}")
    print(f"  Invalid Buyer GSTINs           : {(~invoices['buyer_gstin_valid']).sum():,}")
    print(f"\n  FINANCIAL IMPACT:")
    print(f"  Total Tax Leakage (Under-Charged) : ₹{invoices[invoices['net_tax_leakage_inr']>0]['net_tax_leakage_inr'].sum():,.0f}")
    print(f"  Total Tax Over-Charged            : ₹{abs(invoices[invoices['net_tax_leakage_inr']<0]['net_tax_leakage_inr'].sum()):,.0f}")
    print(f"  Net Tax Leakage                   : ₹{invoices['net_tax_leakage_inr'].sum():,.0f}")
    print(f"  Unclaimed ITC Amount              : ₹{invoices['itc_gap_inr'].sum():,.0f}")
    print(f"\n  RISK DISTRIBUTION:")
    print(invoices['risk_tier'].value_counts().to_string())
    print("=" * 65)


def save_cleaned(invoices, vendors):
    invoices.to_csv(os.path.join(PROCESSED_DIR, 'cleaned_invoices.csv'), index=False)
    vendors.to_csv(os.path.join(PROCESSED_DIR, 'cleaned_vendors.csv'), index=False)
    print("\n✓ cleaned_invoices.csv saved")
    print("✓ cleaned_vendors.csv saved")


if __name__ == '__main__':
    print("=" * 65)
    print("  TAX ANALYSIS — DATA CLEANING PIPELINE")
    print("=" * 65)

    invoices, vendors = load_raw()
    invoices = clean_invoices(invoices)
    vendors  = clean_vendors(vendors)
    print_data_quality_report(invoices)
    save_cleaned(invoices, vendors)
    print("\n✓ Data cleaning complete!")
