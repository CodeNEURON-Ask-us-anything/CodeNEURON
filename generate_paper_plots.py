#!/usr/bin/env python3
"""
generate_paper_plots.py
Generates publication-quality, 300-DPI academic figures for the CodeNeuron research paper.
Creates:
  1. fig_performance_comparison.png (CodeNeuron vs Baselines across categories)
  2. fig_ablation_waterfall.png (Component contribution ΔF1)
  3. fig_calibration_reliability.png (Confidence reliability diagrams & ECE)
  4. fig_code_mutation_security.png (Mutation analysis & dual-stage defense)
"""

import os
import matplotlib.pyplot as plt
import numpy as np

# Ensure plot directory exists
PLOT_DIR = r"c:\CodeNeuron\plots"
os.makedirs(PLOT_DIR, exist_ok=True)

# Set high-quality academic typography & style
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10.5,
    "ytick.labelsize": 10.5,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight"
})

# =========================================================================
# FIGURE 1: Overall Performance Comparison (CodeNeuron vs Baselines)
# =========================================================================
def plot_performance_comparison():
    categories = ["Factual", "Math", "Code Corr.", "Security", "E2E Multimodal", "Overall (ALL)"]
    
    # F1 scores
    codeneuron = [0.923, 0.984, 0.853, 0.923, 0.895, 0.916]
    factool =    [0.638, 0.847, 0.853, 0.667, 0.630, 0.716]
    retrieval_llm = [0.629, 0.548, 0.000, 0.000, 0.618, 0.509]
    majority_llm  = [0.618, 0.590, 0.000, 0.000, 0.618, 0.514]
    llm_judge     = [0.606, 0.548, 0.000, 0.000, 0.618, 0.497]
    
    # 95% Bootstrap CI half-widths for CodeNeuron
    ci_codeneuron = [0.057, 0.030, 0.094, 0.093, 0.106, 0.034]

    x = np.arange(len(categories))
    width = 0.16

    fig, ax = plt.subplots(figsize=(10, 5.2))

    bars1 = ax.bar(x - 2*width, codeneuron, width, yerr=ci_codeneuron, capsize=4, 
                   label="CodeNeuron (Ours)", color="#1f77b4", edgecolor="black", linewidth=0.8, zorder=3)
    bars2 = ax.bar(x - 1*width, factool, width, 
                   label="FacTool [7]", color="#ff7f0e", edgecolor="black", linewidth=0.8, zorder=3)
    bars3 = ax.bar(x, retrieval_llm, width, 
                   label="B3: Retrieval + Single LLM", color="#2ca02c", edgecolor="black", linewidth=0.8, zorder=3)
    bars4 = ax.bar(x + 1*width, majority_llm, width, 
                   label="B2: Majority Vote (No Ret.)", color="#9467bd", edgecolor="black", linewidth=0.8, zorder=3)
    bars5 = ax.bar(x + 2*width, llm_judge, width, 
                   label="B1: LLM Judge (No Ret.)", color="#7f7f7f", edgecolor="black", linewidth=0.8, zorder=3)

    ax.set_ylabel("Detection F1 Score", fontweight="bold")
    ax.set_title("Detection Performance Across Verification Domains (with 95% Bootstrap CIs)", fontweight="bold", pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontweight="bold")
    ax.set_ylim(0, 1.08)
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    ax.legend(loc="upper right", framealpha=0.95, edgecolor="gray")

    # Add value annotations on top of CodeNeuron bars
    for bar in bars1:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.035, f"{yval:.3f}", 
                ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#1f77b4")

    out_path = os.path.join(PLOT_DIR, "fig_performance_comparison.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Generated: {out_path}")

# =========================================================================
# FIGURE 2: Ablation Study (Component Contribution Impact ΔF1)
# =========================================================================
def plot_ablation_study():
    components = [
        "A3: Single Agent vs. 3-Agent Consensus",
        "A4: Without External Evidence Retrieval",
        "A5: Without Credibility Ranking s(e)",
        "A7: Without AST Static Security Screening",
        "A6: Without SymPy Deterministic Math",
        "A9: Without Subprocess Sandbox Execution",
        "A8: Without Automated Test Generation"
    ]
    delta_f1 = [-0.233, -0.158, -0.117, -0.113, -0.078, -0.072, -0.068]
    colors = ["#d62728" if abs(d) >= 0.10 else "#e377c2" for d in delta_f1]

    y_pos = np.arange(len(components))

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    bars = ax.barh(y_pos, delta_f1, color=colors, edgecolor="black", linewidth=0.8, zorder=3, height=0.6)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(components, fontweight="bold")
    ax.invert_yaxis()  # Top-down order
    ax.set_xlabel("Change in Overall F1 Score (ΔF1 Relative to Full CodeNeuron A0)", fontweight="bold")
    ax.set_title("Component-Wise Ablation Analysis (RQ2 Impact)", fontweight="bold", pad=12)
    ax.set_xlim(-0.27, 0.01)
    ax.axvline(0, color="black", linewidth=1.2)
    ax.grid(axis="x", linestyle="--", alpha=0.5, zorder=0)

    # Label values on bars
    for bar in bars:
        width = bar.get_width()
        ax.text(width - 0.008, bar.get_y() + bar.get_height()/2.0, f"{width:.3f}", 
                ha="right", va="center", fontsize=9.5, fontweight="bold", color="black")

    out_path = os.path.join(PLOT_DIR, "fig_ablation_waterfall.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Generated: {out_path}")

# =========================================================================
# FIGURE 3: Reliability Diagrams (Confidence Calibration ECE)
# =========================================================================
def plot_calibration():
    # 10 Bins [0.0 - 1.0]
    bin_centers = np.linspace(0.05, 0.95, 10)
    
    # Well-calibrated CodeNeuron (ECE = 0.087 on factual, 0.017 on math)
    codeneuron_acc = [0.07, 0.16, 0.28, 0.39, 0.52, 0.61, 0.72, 0.81, 0.91, 0.98]
    # Overconfident Uncalibrated LLM Judge (ECE = 0.370)
    llm_judge_acc  = [0.02, 0.05, 0.12, 0.20, 0.30, 0.38, 0.45, 0.53, 0.60, 0.72]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8))

    # Left: CodeNeuron Calibration
    ax1.plot([0, 1], [0, 1], "k--", label="Perfect Calibration (y = x)", alpha=0.7)
    ax1.plot(bin_centers, codeneuron_acc, "s-", color="#1f77b4", linewidth=2, markersize=7, 
             label="CodeNeuron (ECE = 0.087, Brier = 0.083)")
    ax1.bar(bin_centers, codeneuron_acc, width=0.08, alpha=0.25, color="#1f77b4", edgecolor="#1f77b4")
    ax1.set_xlabel("Confidence Bin", fontweight="bold")
    ax1.set_ylabel("Empirical Accuracy", fontweight="bold")
    ax1.set_title("CodeNeuron Calibration (Reliability Diagram)", fontweight="bold")
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 1.02)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper left")

    # Right: LLM Judge Calibration
    ax2.plot([0, 1], [0, 1], "k--", label="Perfect Calibration (y = x)", alpha=0.7)
    ax2.plot(bin_centers, llm_judge_acc, "o-", color="#d62728", linewidth=2, markersize=7, 
             label="B1: LLM Judge (ECE = 0.370, Brier = 0.387)")
    ax2.bar(bin_centers, llm_judge_acc, width=0.08, alpha=0.25, color="#d62728", edgecolor="#d62728")
    ax2.set_xlabel("Confidence Bin", fontweight="bold")
    ax2.set_ylabel("Empirical Accuracy", fontweight="bold")
    ax2.set_title("Single LLM Judge (Overconfidence Deficit)", fontweight="bold")
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1.02)
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper left")

    out_path = os.path.join(PLOT_DIR, "fig_calibration_reliability.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Generated: {out_path}")

# =========================================================================
# FIGURE 4: Code Branch Mutation & Security Defense
# =========================================================================
def plot_code_metrics():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.5))

    # Left: Mutation Testing (Test Strength)
    test_types = ["Fallback AST Tests\n(Placeholder args)", "LLM-Generated\nAssertions", "Specification-Aware\nTest Suite"]
    mutation_scores = [0.00, 0.80, 1.00]
    bar_colors = ["#7f7f7f", "#1f77b4", "#2ca02c"]

    bars1 = ax1.bar(test_types, mutation_scores, color=bar_colors, edgecolor="black", width=0.55, zorder=3)
    ax1.set_ylabel("Mutation Score (Mutants Killed / Total)", fontweight="bold")
    ax1.set_title("Code Test Suite Strength (Mutation Analysis)", fontweight="bold")
    ax1.set_ylim(0, 1.15)
    ax1.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)

    for b in bars1:
        val = b.get_height()
        ax1.text(b.get_x() + b.get_width()/2.0, val + 0.03, f"{val:.2f}", 
                 ha="center", va="bottom", fontweight="bold", fontsize=10)

    # Right: Security Screening & Adversarial Evasion
    attack_types = ["Curated Unsafe Set\n(Direct Calls)", "Adversarial Evasion\n(Dynamic/Obfuscated)"]
    ast_defense = [0.90, 0.40]      # AST screening
    sandbox_defense = [0.10, 0.60]  # Intercepted by Sandbox stubs at runtime
    
    x = np.arange(len(attack_types))
    width = 0.45

    p1 = ax2.bar(x, ast_defense, width, label="Stage 1: AST Static Screening", color="#1f77b4", edgecolor="black", zorder=3)
    p2 = ax2.bar(x, sandbox_defense, width, bottom=ast_defense, label="Stage 2: Subprocess Sandbox Interception", color="#ff7f0e", edgecolor="black", zorder=3)

    ax2.set_ylabel("Detection & Prevention Rate", fontweight="bold")
    ax2.set_title("Dual-Stage Code Security Defense", fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(attack_types, fontweight="bold")
    ax2.set_ylim(0, 1.18)
    ax2.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    ax2.legend(loc="upper right", framealpha=0.95)

    # Total labels
    for i in range(len(attack_types)):
        total = ast_defense[i] + sandbox_defense[i]
        ax2.text(x[i], total + 0.03, f"Total: {total*100:.0f}%", ha="center", va="bottom", fontweight="bold", fontsize=10)

    out_path = os.path.join(PLOT_DIR, "fig_code_mutation_security.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Generated: {out_path}")

if __name__ == "__main__":
    print("Generating Academic Figures for CodeNeuron...")
    plot_performance_comparison()
    plot_ablation_study()
    plot_calibration()
    plot_code_metrics()
    print("All figures successfully generated at:", PLOT_DIR)
