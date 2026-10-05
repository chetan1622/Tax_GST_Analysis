# =============================================================================
# PROJECT  : Tax Analysis & GST Compliance
# SCRIPT   : 01_data_generation.py
# AUTHOR   : Chetan
# DESC     : Generates 50,000+ realistic Indian GST invoices
#            with deliberate compliance errors for audit analysis
# =============================================================================

import pandas as pd
import numpy as np
from faker import Faker
import random
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

fake = Faker('en_IN')
np.random.seed(42)
random.seed(42)

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'raw')
os.makedirs(RAW_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# INDIAN GST MASTER DATA
# ─────────────────────────────────────────────────────────────
STATE_CODES = {
    'Jammu & Kashmir': '01', 'Haryana': '06', 'Delhi': '07',
    'Rajasthan': '08', 'Uttar Pradesh': '09', 'Bihar': '10',
    'West Bengal': '19', 'Jharkhand': '20', 'Odisha': '21',
    'Maharashtra': '27', 'Karnataka': '29', 'Kerala': '32',
    'Tamil Nadu': '33', 'Telangana': '36', 'Andhra Pradesh': '37',
    'Gujarat': '24', 'Punjab': '03', 'Madhya Pradesh': '23',
}
STATES = list(STATE_CODES.keys())

# HSN Code → (description, GST rate %)
HSN_MAP = {
    '7204': ('Steel Scrap',         18),
    '8471': ('Computers & Laptops', 18),
    '3004': ('Pharmaceutical Drugs', 12),
    '6101': ('Clothing & Apparel',   5),
    '2709': ('Crude Petroleum',      5),
    '8703': ('Motor Cars',          28),
    '0901': ('Coffee & Tea',         5),
    '5208': ('Cotton Fabric',        5),
    '9403': ('Furniture',           18),
    '8516': ('Electronic Appliances',18),
    '2204': ('Wine & Alcohol',       28),
    '3304': ('Cosmetics',            18),
    '8517': ('Telecom Equipment',    18),
    '4901': ('Books & Journals',      0),
    '1905': ('Bakery Products',      18),
}
HSN_CODES = list(HSN_MAP.keys())

GST_RATES = [0, 5, 12, 18, 28]

COMPANY_NAMES = [
    'Reliance Industries', 'Tata Steel', 'Mahindra Logistics', 'Infosys BPO',
    'Wipro Enterprises', 'HDFC Trade', 'Bajaj Industries', 'Asian Paints Supply',
    'Adani Logistics', 'Birla Corp', 'Godrej Distribution', 'ITC Trading',
    'HUL Supply Chain', 'Dabur India', 'Marico Distribution', 'Hero Motors',
    'Larsen & Toubro', 'Sun Pharma', 'Dr Reddy Chemicals', 'Cipla Pharma',
]


def generate_gstin(state_code):
    """Generate realistic GSTIN format: 2-digit state + 10-char PAN + 1 + Z + 1"""
    pan = (''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=5)) +
           ''.join(random.choices('0123456789', k=4)) +
           random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    return f"{state_code}{pan}{random.randint(1,9)}Z{random.randint(1,9)}"


# ─────────────────────────────────────────────────────────────
# TABLE 1: VENDORS (500 vendors)
# ─────────────────────────────────────────────────────────────
def generate_vendors(n=500):
    print(f"Generating {n} vendors...")
    rows = []
    for i in range(1, n + 1):
        state = random.choice(STATES)
        sc = STATE_CODES[state]
        compliance = round(random.uniform(60, 99), 2)
        rows.append({
            'vendor_id':            f'VND-{i:03d}',
            'vendor_name':          random.choice(COMPANY_NAMES) + f' {fake.last_name()} & Co',
            'gstin':                generate_gstin(sc),
            'state':                state,
            'state_code':           sc,
            'city':                 fake.city(),
            'contact_email':        fake.email(),
            'total_invoices':       random.randint(10, 500),
            'compliance_rate_pct':  compliance,
            'avg_itc_delay_days':   random.randint(0, 90),
            'vendor_risk_category': 'Low' if compliance >= 90 else ('Medium' if compliance >= 75 else 'High'),
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RAW_DIR, 'vendors.csv'), index=False)
    print(f"  ✓ vendors.csv — Shape: {df.shape}")
    return df


# ─────────────────────────────────────────────────────────────
# TABLE 2: INVOICES (50,000 invoices)
# ─────────────────────────────────────────────────────────────
def generate_invoices(vendors_df, n=50000):
    print(f"\nGenerating {n} GST invoices...")
    start_date = datetime(2023, 1, 1)
    end_date   = datetime(2024, 9, 30)
    date_range = (end_date - start_date).days

    rows = []
    for i in range(1, n + 1):
        # Supplier details
        sup_state      = random.choice(STATES)
        sup_state_code = STATE_CODES[sup_state]
        sup_gstin      = generate_gstin(sup_state_code)

        # Buyer details
        buyer_state      = random.choice(STATES)
        buyer_state_code = STATE_CODES[buyer_state]
        # 5% missing/invalid GSTIN
        if random.random() < 0.05:
            buyer_gstin = 'INVALID' if random.random() < 0.5 else ''
            compliance_issue = 'Missing GSTIN'
        else:
            buyer_gstin = generate_gstin(buyer_state_code)
            compliance_issue = None

        inv_date    = start_date + timedelta(days=random.randint(0, date_range))
        is_interstate = (sup_state != buyer_state)
        transaction_type = 'Inter-State' if is_interstate else 'Intra-State'

        hsn = random.choice(HSN_CODES)
        hsn_desc, std_rate = HSN_MAP[hsn]

        qty        = random.randint(1, 1000)
        unit_price = round(random.uniform(50, 50000), 2)
        taxable    = round(qty * unit_price, 2)

        # Determine correct tax
        correct_igst  = round(taxable * std_rate / 100, 2) if is_interstate else 0.0
        correct_cgst  = round(taxable * std_rate / 200, 2) if not is_interstate else 0.0
        correct_sgst  = correct_cgst
        correct_total = round(correct_igst + correct_cgst + correct_sgst, 2)

        # Introduce errors
        applied_rate = std_rate
        error_type   = compliance_issue

        # Error 1: IGST misclassification (15% of inter-state): charged CGST+SGST instead
        if is_interstate and random.random() < 0.15 and error_type is None:
            # Wrong: used CGST+SGST for inter-state
            charged_igst = 0.0
            charged_cgst = round(taxable * std_rate / 200, 2)
            charged_sgst = charged_cgst
            error_type   = 'IGST Misclassification'

        # Error 2: Wrong GST rate (10% of invoices)
        elif random.random() < 0.10 and error_type is None:
            other_rates  = [r for r in GST_RATES if r != std_rate]
            applied_rate = random.choice(other_rates)
            error_type   = 'Rate Error'
            if is_interstate:
                charged_igst = round(taxable * applied_rate / 100, 2)
                charged_cgst = 0.0; charged_sgst = 0.0
            else:
                charged_igst = 0.0
                charged_cgst = round(taxable * applied_rate / 200, 2)
                charged_sgst = charged_cgst

        else:
            # Correct classification
            if is_interstate:
                charged_igst = correct_igst; charged_cgst = 0.0; charged_sgst = 0.0
            else:
                charged_igst = 0.0; charged_cgst = correct_cgst; charged_sgst = correct_sgst
            if error_type is None:
                error_type = 'Compliant'

        charged_total = round(charged_igst + charged_cgst + charged_sgst, 2)
        tax_leakage   = round(correct_total - charged_total, 2)
        tax_error_flag = 1 if abs(tax_leakage) > 100 else 0

        # ITC
        itc_eligible = 1 if (buyer_gstin not in ['INVALID', ''] and random.random() < 0.80) else 0
        if itc_eligible:
            # 8% chance ITC not claimed despite eligibility
            itc_claimed = 0.0 if random.random() < 0.08 else charged_total
            claim_date  = inv_date + timedelta(days=random.randint(30, 90))
        else:
            itc_claimed = 0.0
            claim_date  = None

        # Audit risk score
        risk = 0
        if error_type != 'Compliant': risk += 40
        if abs(tax_leakage) > 50000:  risk += 30
        if taxable > 500000:          risk += 20
        if itc_eligible and itc_claimed == 0: risk += 10
        audit_risk = min(risk + random.randint(0, 20), 100)

        rows.append({
            'invoice_id':          f'INV-{inv_date.year}-{i:06d}',
            'invoice_date':        inv_date.strftime('%Y-%m-%d'),
            'supplier_gstin':      sup_gstin,
            'buyer_gstin':         buyer_gstin,
            'supplier_state':      sup_state,
            'supplier_state_code': sup_state_code,
            'buyer_state':         buyer_state,
            'buyer_state_code':    buyer_state_code,
            'transaction_type':    transaction_type,
            'hsn_code':            hsn,
            'item_description':    hsn_desc,
            'quantity':            qty,
            'unit_price_inr':      unit_price,
            'taxable_value_inr':   taxable,
            'applicable_gst_rate': applied_rate,
            'standard_gst_rate':   std_rate,
            'igst_charged_inr':    charged_igst,
            'cgst_charged_inr':    charged_cgst,
            'sgst_charged_inr':    charged_sgst,
            'total_tax_charged_inr': charged_total,
            'correct_igst_inr':    correct_igst,
            'correct_cgst_inr':    correct_cgst,
            'correct_sgst_inr':    correct_sgst,
            'correct_total_tax_inr': correct_total,
            'tax_error_flag':      tax_error_flag,
            'tax_leakage_inr':     tax_leakage,
            'compliance_status':   error_type,
            'itc_eligible':        itc_eligible,
            'itc_claimed_inr':     itc_claimed,
            'itc_claim_date':      claim_date.strftime('%Y-%m-%d') if claim_date else None,
            'audit_risk_score':    audit_risk,
        })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RAW_DIR, 'invoices.csv'), index=False)
    print(f"  ✓ invoices.csv — Shape: {df.shape}")
    print(f"\n  Compliance Status Distribution:")
    print(df['compliance_status'].value_counts().to_string())
    print(f"\n  Total Tax Leakage : ₹{df['tax_leakage_inr'].sum():,.0f}")
    print(f"  Avg Audit Risk    : {df['audit_risk_score'].mean():.1f}/100")
    return df


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 65)
    print("  TAX ANALYSIS & GST COMPLIANCE — DATA GENERATION")
    print("=" * 65)

    vendors  = generate_vendors(500)
    invoices = generate_invoices(vendors, 50000)

    total = len(vendors) + len(invoices)
    print("\n" + "=" * 65)
    print(f"  DATA GENERATION COMPLETE!")
    print(f"  Total records : {total:,}")
    print(f"  Saved to      : {RAW_DIR}")
    print("=" * 65)
