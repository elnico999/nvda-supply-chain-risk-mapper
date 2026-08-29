"""
NVDA Supply Chain & Customer Concentration Risk Mapper
--------------------------------------------------------
Author: [Your Name]
Purpose: Quantify NVIDIA's customer concentration risk and geographic/
supply-chain exposure using disclosures from public SEC filings, and
visualize the relationship network.

Data sources (documented, not scraped live in this version):
- NVIDIA FY2026 10-K (fiscal year ended Jan 25, 2026), "Concentration of
  Revenue" note and Risk Factors section, filed with SEC EDGAR.
- NVIDIA Q3 FY2026 10-Q customer concentration disclosure.
- Public reporting on NVDA's key foundry/memory/assembly partners
  (TSMC, SK Hynix, Samsung, Micron, Foxconn) — NVDA does not disclose
  exact supplier revenue splits, so supplier-side weights below are
  ANALYST ESTIMATES based on industry reporting, clearly flagged as such.

Extending this to live data:
- Swap `load_filing_disclosures()` for a call to the SEC EDGAR full-text
  search API (https://efts.sec.gov/LATEST/search-index) to auto-pull the
  latest 10-K/10-Q customer concentration language.
- Swap `load_supplier_estimates()` for a trade-data API (ImportGenius,
  Panjiva, or similar) if you have a subscription, to get real shipment-
  level supplier volume data instead of analyst estimates.
"""

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

pd.set_option("display.width", 120)

# ---------------------------------------------------------------------
# 1. DATA LAYER — sourced disclosures (documented above)
# ---------------------------------------------------------------------

def load_customer_concentration():
    """
    Direct customer revenue concentration, sourced from NVIDIA SEC filings.
    Each row = one disclosed reporting period.
    Values are % of TOTAL company revenue from customers individually
    representing >=10% of revenue (as required disclosure under SEC rules).
    """
    data = [
        # period,           customer_label, pct_of_revenue, source
        ("FY2024 (Annual)", "Customer A",   13, "FY24 10-K"),
        ("FY2026 (Annual)", "Customer A",   22, "FY26 10-K"),
        ("FY2026 (Annual)", "Customer B",   14, "FY26 10-K"),
        ("Q2 FY2026",       "Customer A",   23, "Q2 FY26 10-Q"),
        ("Q2 FY2026",       "Customer B",   16, "Q2 FY26 10-Q"),
        ("Q3 FY2026",       "Customer A",   22, "Q3 FY26 10-Q"),
        ("Q3 FY2026",       "Customer B",   15, "Q3 FY26 10-Q"),
        ("Q3 FY2026",       "Customer C",   13, "Q3 FY26 10-Q"),
        ("Q3 FY2026",       "Customer D",   11, "Q3 FY26 10-Q"),
    ]
    return pd.DataFrame(data, columns=["period", "customer", "pct_revenue", "source"])


def load_supplier_estimates():
    """
    Key supply-chain counterparties. NVDA does not disclose exact supplier
    revenue/volume splits publicly, so weights here are ANALYST ESTIMATES
    based on industry reporting on NVIDIA's known foundry/memory/assembly
    dependencies — flagged accordingly. Replace with real trade-data API
    output (ImportGenius/Panjiva) for a production version.
    """
    data = [
        # supplier,        role,               country,      est_weight, confidence
        ("TSMC",            "Foundry (wafer fab)", "Taiwan",       0.90, "high - single-source, widely reported"),
        ("SK Hynix",         "HBM memory",          "South Korea",  0.50, "medium - largest HBM supplier, not exclusive"),
        ("Samsung",          "HBM memory",          "South Korea",  0.25, "medium - qualifying/ramping HBM supplier"),
        ("Micron",           "HBM memory",          "USA",          0.25, "medium - smaller HBM allocation"),
        ("Foxconn/Wistron",  "Assembly/packaging",  "Taiwan",       0.60, "low-medium - among several ODM partners"),
        ("Amkor",            "Advanced packaging",  "Various",      0.20, "low - CoWoS/packaging capacity partner"),
    ]
    return pd.DataFrame(data, columns=["supplier", "role", "country", "est_weight", "confidence"])


# ---------------------------------------------------------------------
# 2. ANALYTICS LAYER
# ---------------------------------------------------------------------

def customer_concentration_summary(df):
    """Compute concentration metrics for the most recent period available."""
    latest_period = df["period"].iloc[-1]
    latest = df[df["period"] == latest_period]

    top_n_pct = latest["pct_revenue"].sum()
    hhi = ((latest["pct_revenue"]).pow(2)).sum()  # simplified HHI on disclosed customers only

    print(f"\n=== Customer Concentration — {latest_period} ===")
    print(latest[["customer", "pct_revenue", "source"]].to_string(index=False))
    print(f"\nCombined revenue from disclosed >=10% customers: {top_n_pct}%")
    print(f"Simplified HHI (disclosed customers only): {hhi:,.0f}")
    print("  (HHI > 2,500 on even a partial customer base signals high concentration;")
    print("   a fully diversified base of many small customers would score near 0)")

    return latest_period, top_n_pct, hhi


def geographic_exposure_summary(suppliers_df):
    """Aggregate estimated supply-chain weight by country."""
    geo = suppliers_df.groupby("country")["est_weight"].sum().sort_values(ascending=False)
    geo_pct = (geo / geo.sum() * 100).round(1)

    print("\n=== Estimated Geographic Supply-Chain Exposure ===")
    print("(Analyst estimates — NVDA does not disclose exact supplier splits)")
    for country, pct in geo_pct.items():
        print(f"  {country:<15} {pct:>5}% of weighted supplier exposure")

    return geo_pct


def risk_flags(top_n_pct, hhi, geo_pct):
    """Rule-based flags — mirrors the kind of checklist a credit/equity
    analyst would apply during diligence."""
    flags = []

    if top_n_pct >= 30:
        flags.append(f"HIGH customer concentration: disclosed >=10% customers "
                      f"represent {top_n_pct}% of revenue (>30% threshold).")
    if hhi >= 1500:
        flags.append(f"Elevated concentration by HHI ({hhi:,.0f}), even before "
                      f"accounting for undisclosed sub-10% customers.")
    if geo_pct.iloc[0] >= 50:
        flags.append(f"Single-country supply dependency: {geo_pct.index[0]} "
                      f"accounts for an estimated {geo_pct.iloc[0]}% of weighted "
                      f"supplier exposure — material geopolitical/tariff risk "
                      f"(Taiwan Strait risk specifically, if Taiwan).")

    flags.append("Regulatory overlay: U.S. export controls on advanced AI chips to "
                  "China have already constrained a previously significant revenue "
                  "market — a live example of geographic/regulatory risk converting "
                  "into realized revenue impact, not just a hypothetical.")

    return flags


def generate_summary_memo(period, top_n_pct, hhi, geo_pct, flags):
    memo = f"""
=== AUTO-GENERATED RISK SUMMARY MEMO ===

As of {period}, NVIDIA's disclosed >=10% direct customers account for
{top_n_pct}% of total revenue, up materially from prior periods — a trend
NVIDIA itself acknowledges in its risk factor disclosures. This concentration
sits alongside a supply chain that is itself narrow: foundry production is
single-sourced through TSMC in Taiwan, and advanced memory (HBM) sourcing is
split across a small number of qualified suppliers, most based in South Korea.

The combination creates a dual-sided concentration risk: revenue depends on a
small number of hyperscale customers, while production depends on a small
number of counterparties concentrated in Taiwan and South Korea. A disruption
at either end of this chain — loss of a major customer, or a supply
disruption tied to Taiwan Strait tensions — would have an outsized impact on
NVIDIA relative to a company with a more diversified customer or supplier
base.

Key flags identified:
"""
    for f in flags:
        memo += f"  - {f}\n"

    memo += """
Caveat: customer identities are not disclosed by NVIDIA (referred to only as
"Customer A," "Customer B," etc. in filings); supplier-side weightings in this
analysis are analyst estimates based on public industry reporting, not
confirmed trade volumes, since NVDA does not disclose exact supplier splits.
"""
    return memo


# ---------------------------------------------------------------------
# 3. VISUALIZATION LAYER
# ---------------------------------------------------------------------

def build_network_graph(customers_df, suppliers_df, latest_period, save_path):
    G = nx.DiGraph()
    G.add_node("NVDA", type="core")

    latest_customers = customers_df[customers_df["period"] == latest_period]
    for _, row in latest_customers.iterrows():
        G.add_node(row["customer"], type="customer")
        G.add_edge(row["customer"], "NVDA", weight=row["pct_revenue"])

    for _, row in suppliers_df.iterrows():
        G.add_node(row["supplier"], type="supplier")
        G.add_edge("NVDA", row["supplier"], weight=row["est_weight"] * 100)

    pos = {}
    customer_nodes = [n for n, d in G.nodes(data=True) if d["type"] == "customer"]
    supplier_nodes = [n for n, d in G.nodes(data=True) if d["type"] == "supplier"]

    for i, n in enumerate(customer_nodes):
        pos[n] = (-2, (i - len(customer_nodes) / 2) * 1.2)
    for i, n in enumerate(supplier_nodes):
        pos[n] = (2, (i - len(supplier_nodes) / 2) * 1.0)
    pos["NVDA"] = (0, 0)

    fig, ax = plt.subplots(figsize=(12, 8))

    node_colors = []
    node_sizes = []
    for n, d in G.nodes(data=True):
        if d["type"] == "core":
            node_colors.append("#76B900")  # NVIDIA green
            node_sizes.append(3500)
        elif d["type"] == "customer":
            node_colors.append("#4C72B0")
            node_sizes.append(2000)
        else:
            node_colors.append("#C44E52")
            node_sizes.append(1800)

    edge_widths = [G[u][v]["weight"] / 4 for u, v in G.edges()]

    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes,
                            edgecolors="white", linewidths=1.5, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=9, font_weight="bold", ax=ax)
    nx.draw_networkx_edges(G, pos, width=edge_widths, alpha=0.6,
                            edge_color="gray", arrows=True,
                            arrowsize=15, connectionstyle="arc3,rad=0.05", ax=ax)

    edge_labels = {(u, v): f"{G[u][v]['weight']:.0f}%" for u, v in G.edges()}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8, ax=ax)

    legend_elements = [
        mpatches.Patch(color="#4C72B0", label="Customers (revenue side)"),
        mpatches.Patch(color="#76B900", label="NVDA"),
        mpatches.Patch(color="#C44E52", label="Suppliers (est. — supply side)"),
    ]
    ax.legend(handles=legend_elements, loc="upper center", ncol=3, frameon=False)

    ax.set_title(f"NVDA Customer & Supplier Concentration Network — {latest_period}\n"
                 f"(Edge width/label = est. % revenue or supply weight)",
                 fontsize=13, fontweight="bold")
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nNetwork graph saved to: {save_path}")


# ---------------------------------------------------------------------
# 3. HISTORICAL CUSTOMER CONCENTRATION
# ---------------------------------------------------------------------

def plot_customer_concentration(df, save_path):
    """Plot disclosed customer concentration by reporting period."""
    historical = (
        df.groupby("period")["pct_revenue"]
        .sum()
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(
        historical["period"],
        historical["pct_revenue"],
        marker="o",
        linewidth=2
    )

    ax.set_title(
        "NVIDIA Disclosed Customer Concentration",
        fontsize=13,
        fontweight="bold"
    )
    ax.set_xlabel("Reporting Period")
    ax.set_ylabel("Disclosed customer revenue (%)")
    ax.set_ylim(0, 70)

    for x, y in zip(historical["period"], historical["pct_revenue"]):
        ax.annotate(
            f"{y:.0f}%",
            (x, y),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center"
        )

    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"\nCustomer concentration chart saved to: {save_path}")

# ---------------------------------------------------------------------
# 4. MAIN
# ---------------------------------------------------------------------

def main():
    customers_df = load_customer_concentration()
    suppliers_df = load_supplier_estimates()

    latest_period, top_n_pct, hhi = customer_concentration_summary(customers_df)
    geo_pct = geographic_exposure_summary(suppliers_df)
    flags = risk_flags(top_n_pct, hhi, geo_pct)
    memo = generate_summary_memo(latest_period, top_n_pct, hhi, geo_pct, flags)
    print(memo)

    build_network_graph(customers_df, suppliers_df, latest_period,
                         "/home/claude/nvda_supply_chain/nvda_network_graph.png")

    plot_customer_concentration(
        customers_df,
        "/home/claude/nvda_supply_chain/customer_concentration.png"
    )

    # Save outputs
    customers_df.to_csv("/home/claude/nvda_supply_chain/nvda_customer_concentration.csv", index=False)
    suppliers_df.to_csv("/home/claude/nvda_supply_chain/nvda_supplier_estimates.csv", index=False)
    with open("/home/claude/nvda_supply_chain/nvda_risk_memo.txt", "w") as f:
        f.write(memo)

    print("\nAll outputs saved to /home/claude/nvda_supply_chain/")


if __name__ == "__main__":
    main()
