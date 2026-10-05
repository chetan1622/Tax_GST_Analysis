# =============================================================================
# PROJECT  : Tax Analysis & GST Compliance
# SCRIPT   : 04_visualization.py
# AUTHOR   : Chetan
# DESC     : 8-panel GST Compliance Dashboard
#            Output: reports/gst_compliance_dashboard.png (300 DPI)
# =============================================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import os
import warnings
warnings.filterwarnings('ignore')

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
REPORTS_DIR   = os.path.join(BASE_DIR, 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

C_RED    = '#E53935'
C_GREEN  = '#43A047'
C_BLUE   = '#1E88E5'
C_ORANGE = '#FB8C00'
C_PURPLE = '#8E24AA'
C_TEAL   = '#00897B'


def load_data():
    inv = pd.read_csv(os.path.join(PROCESSED_DIR, 'cleaned_invoices.csv'), parse_dates=['invoice_date'])
    vnd = pd.read_csv(os.path.join(PROCESSED_DIR, 'cleaned_vendors.csv'))
    return inv, vnd


def create_dashboard():
    inv, vnd = load_data()

    sns.set_style('whitegrid')
    fig, axes = plt.subplots(4, 2, figsize=(22, 28))
    fig.patch.set_facecolor('#F5F5F5')

    fig.suptitle(
        'GST Tax Compliance & ITC Recovery Analytics Dashboard  |  FY 2023–24\nAuthor: Chetan  |  Tax Analysis Portfolio Project',
        fontsize=18, fontweight='bold', y=0.98, color='#B71C1C'
    )

    # ── PANEL 1: Monthly Tax Leakage Trend ───────────────────
    ax = axes[0, 0]
    monthly_leak = inv.groupby('invoice_month')['tax_leakage_inr'].sum().reset_index()
    monthly_leak = monthly_leak.sort_values('invoice_month')
    monthly_leak['leakage_lakhs'] = monthly_leak['tax_leakage_inr'] / 1e5
    ax.bar(monthly_leak['invoice_month'], monthly_leak['leakage_lakhs'],
           color=C_RED, edgecolor='white', alpha=0.85)
    ax.plot(monthly_leak['invoice_month'], monthly_leak['leakage_lakhs'],
            color='darkred', linewidth=2, marker='D', markersize=5)
    ax.axhline(monthly_leak['leakage_lakhs'].mean(), color='orange', linestyle='--',
               linewidth=1.5, label=f'Avg ₹{monthly_leak["leakage_lakhs"].mean():.1f}L')
    ax.set_title('Monthly Tax Leakage Trend (₹ Lakhs)', fontweight='bold', fontsize=12)
    ax.set_xlabel('Month')
    ax.set_ylabel('Tax Leakage (₹ Lakhs)')
    ax.tick_params(axis='x', rotation=45, labelsize=7)
    ax.legend(fontsize=9)

    # ── PANEL 2: Compliance Status Distribution (Donut) ──────
    ax = axes[0, 1]
    status_counts = inv['compliance_status'].value_counts()
    colors_p2 = [C_GREEN if s == 'Compliant' else
                 (C_RED if 'Misclass' in s else
                  (C_ORANGE if 'Rate' in s else C_PURPLE)) for s in status_counts.index]
    wedges, texts, autotexts = ax.pie(
        status_counts.values, labels=status_counts.index,
        autopct='%1.1f%%', colors=colors_p2, startangle=90,
        pctdistance=0.75, wedgeprops={'width': 0.55, 'edgecolor': 'white', 'linewidth': 2}
    )
    for at in autotexts:
        at.set_fontsize(9); at.set_fontweight('bold')
    ax.set_title('Invoice Compliance Status Distribution', fontweight='bold', fontsize=12)
    total_inv = len(inv)
    ax.text(0, 0, f'{total_inv:,}\nInvoices', ha='center', va='center',
            fontsize=11, fontweight='bold', color='#333')

    # ── PANEL 3: Top 10 States by Tax Non-Compliance ─────────
    ax = axes[1, 0]
    state_leak = inv[inv['compliance_status'] != 'Compliant'].groupby('supplier_state')['tax_leakage_inr'].sum()
    state_leak = state_leak.nlargest(10) / 1e5
    bar_colors = [C_RED if v > state_leak.mean() else C_ORANGE for v in state_leak.values]
    bars = ax.barh(state_leak.index, state_leak.values, color=bar_colors, edgecolor='white')
    ax.set_xlabel('Tax Leakage (₹ Lakhs)', fontsize=10)
    ax.set_title('Top 10 States by Tax Non-Compliance (₹ Lakhs)', fontweight='bold', fontsize=12)
    for bar, val in zip(bars, state_leak.values):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f'₹{val:.1f}L', va='center', fontsize=9, fontweight='bold')
    ax.tick_params(axis='y', labelsize=9)

    # ── PANEL 4: GST Rate-wise Invoice Count & Leakage ───────
    ax = axes[1, 1]
    rate_grp = inv.groupby('applicable_gst_rate').agg(
        count=('invoice_id', 'count'),
        leakage=('tax_leakage_inr', 'sum')
    ).reset_index()
    x = np.arange(len(rate_grp))
    w = 0.4
    ax2 = ax.twinx()
    ax.bar(x - w/2, rate_grp['count'], width=w, color=C_BLUE, label='Invoice Count', alpha=0.85)
    ax2.bar(x + w/2, rate_grp['leakage'] / 1e5, width=w, color=C_ORANGE, label='Tax Leakage (₹L)', alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r}%" for r in rate_grp['applicable_gst_rate']])
    ax.set_xlabel('GST Rate', fontsize=10)
    ax.set_ylabel('Invoice Count', color=C_BLUE, fontsize=10)
    ax2.set_ylabel('Tax Leakage (₹ Lakhs)', color=C_ORANGE, fontsize=10)
    ax.set_title('GST Rate-wise: Invoice Count vs Tax Leakage', fontweight='bold', fontsize=12)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8, loc='upper left')

    # ── PANEL 5: Inter-State vs Intra-State by Month ─────────
    ax = axes[2, 0]
    tx_monthly = inv.groupby(['invoice_month', 'transaction_type']).size().unstack(fill_value=0)
    tx_monthly = tx_monthly.sort_index()
    months = tx_monthly.index.tolist()
    x = np.arange(len(months))
    inter = tx_monthly.get('Inter-State', pd.Series(0, index=tx_monthly.index)).values
    intra = tx_monthly.get('Intra-State', pd.Series(0, index=tx_monthly.index)).values
    ax.bar(x, inter, label='Inter-State (IGST)', color=C_BLUE, edgecolor='white')
    ax.bar(x, intra, bottom=inter, label='Intra-State (CGST+SGST)', color=C_GREEN, edgecolor='white')
    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=45, ha='right', fontsize=7)
    ax.set_ylabel('Invoice Count')
    ax.set_title('Monthly Transaction Mix: Inter-State vs Intra-State', fontweight='bold', fontsize=12)
    ax.legend(fontsize=9)

    # ── PANEL 6: State-wise Tax Collection: IGST vs CGST+SGST ─
    ax = axes[2, 1]
    state_tax = inv.groupby('supplier_state').agg(
        igst_total=('igst_charged_inr', 'sum'),
        cgst_sgst_total=('cgst_charged_inr', 'sum'),
    ).reset_index()
    state_tax['cgst_sgst_combined'] = state_tax['cgst_sgst_total'] * 2
    state_tax = state_tax.nlargest(12, 'igst_total')
    x = np.arange(len(state_tax))
    ax.bar(x - 0.2, state_tax['igst_total'] / 1e7, width=0.4, label='IGST (₹ Cr)', color=C_BLUE)
    ax.bar(x + 0.2, state_tax['cgst_sgst_combined'] / 1e7, width=0.4, label='CGST+SGST (₹ Cr)', color=C_GREEN)
    ax.set_xticks(x)
    ax.set_xticklabels(state_tax['supplier_state'], rotation=45, ha='right', fontsize=7)
    ax.set_ylabel('Tax Amount (₹ Crores)')
    ax.set_title('Top 12 States: IGST vs CGST+SGST Collection', fontweight='bold', fontsize=12)
    ax.legend(fontsize=9)

    # ── PANEL 7: Scatter — Invoice Value vs Tax Leakage ──────
    ax = axes[3, 0]
    sample = inv.sample(min(3000, len(inv)), random_state=42)
    sc = ax.scatter(
        sample['taxable_value_inr'] / 1000,
        sample['tax_leakage_inr'],
        c=sample['audit_risk_score'], cmap='RdYlGn_r',
        alpha=0.4, s=20, edgecolors='none'
    )
    plt.colorbar(sc, ax=ax, label='Audit Risk Score')
    ax.axhline(0, color='black', linewidth=1, linestyle='--', alpha=0.5)
    ax.set_xlabel('Taxable Value (₹ Thousands)')
    ax.set_ylabel('Tax Leakage (₹)')
    ax.set_title('Invoice Value vs Tax Leakage (Colored by Risk Score)', fontweight='bold', fontsize=12)

    # ── PANEL 8: ITC Claim Delay Distribution ────────────────
    ax = axes[3, 1]
    inv_claimed = inv[(inv['itc_eligible'] == 1) & (inv['itc_claimed_inr'] > 0)].copy()
    inv_claimed['itc_claim_date'] = pd.to_datetime(inv_claimed['itc_claim_date'], errors='coerce')
    inv_claimed['delay_days'] = (inv_claimed['itc_claim_date'] - inv_claimed['invoice_date']).dt.days
    inv_claimed['delay_bucket'] = pd.cut(
        inv_claimed['delay_days'],
        bins=[0, 30, 60, 90, float('inf')],
        labels=['0-30 days', '31-60 days', '61-90 days', '>90 days']
    )
    bucket_counts = inv_claimed['delay_bucket'].value_counts().sort_index()
    bucket_colors = [C_GREEN, C_TEAL, C_ORANGE, C_RED]
    bars = ax.bar(bucket_counts.index, bucket_counts.values, color=bucket_colors, edgecolor='white')
    ax.set_xlabel('ITC Claim Delay')
    ax.set_ylabel('Invoice Count')
    ax.set_title('ITC Claim Delay Distribution (Days from Invoice Date)', fontweight='bold', fontsize=12)
    for bar, val in zip(bars, bucket_counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                f'{val:,}', ha='center', fontsize=10, fontweight='bold')

    # ── Save ──────────────────────────────────────────────────
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out_path = os.path.join(REPORTS_DIR, 'gst_compliance_dashboard.png')
    plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='#F5F5F5')
    plt.close()
    print(f"✓ Dashboard saved → {out_path}")


if __name__ == '__main__':
    print("=" * 65)
    print("  GST TAX COMPLIANCE — DASHBOARD GENERATION")
    print("=" * 65)
    create_dashboard()
    print("✓ All panels generated successfully!")
