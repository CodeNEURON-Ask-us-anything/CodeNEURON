#!/usr/bin/env python3
"""
insert_figures_into_docx.py
Inserts the 4 generated 300-DPI academic figures into CodeNeuron_revised_completed.docx
with formal captions and proper centered formatting.
"""

import os
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

DOCX_PATH = r"C:\CodeNeuron\CodeNeuron_revised_completed.docx"
DOCX_OUT_DOWNLOADS = r"C:\Users\shriv\Downloads\CodeNeuron_revised_completed.docx"
PLOT_DIR = r"c:\CodeNeuron\plots"

doc = docx.Document(DOCX_PATH)

def add_figure_after_paragraph(target_p_text_fragment, image_path, caption_text, width_inches=5.8):
    for i, p in enumerate(doc.paragraphs):
        if target_p_text_fragment.lower() in p.text.lower():
            # Add after this paragraph
            p_img = p.insert_paragraph_before() # create sibling
            # Swap: insert image
            p_img.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(8)
            p_img.paragraph_format.space_after = Pt(2)
            run = p_img.add_run()
            run.add_picture(image_path, width=Inches(width_inches))

            # Caption paragraph
            p_cap = p.insert_paragraph_before()
            p_cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_before = Pt(2)
            p_cap.paragraph_format.space_after = Pt(10)
            r_cap = p_cap.add_run(caption_text)
            r_cap.font.name = "Times New Roman"
            r_cap.font.size = Pt(9.5)
            r_cap.italic = True
            print(f"Inserted: {caption_text[:40]}...")
            return True
    return False

# 1. Performance comparison figure in Section 5.2
fig2_path = os.path.join(PLOT_DIR, "fig_performance_comparison.png")
add_figure_after_paragraph(
    "Across all benchmark categories, CodeNeuron significantly outperforms",
    fig2_path,
    "Fig. 2. Performance comparison of CodeNeuron versus baselines across verification categories with 95% bootstrap confidence intervals.",
    width_inches=5.8
)

# 2. Ablation waterfall figure in Section 5.3
fig3_path = os.path.join(PLOT_DIR, "fig_ablation_waterfall.png")
add_figure_after_paragraph(
    "Table 9. Ablation results",
    fig3_path,
    "Fig. 3. Component-wise ablation study showing F1 score decrement (ΔF1) relative to full CodeNeuron (A0).",
    width_inches=5.2
)

# 3. Code mutation & security figure in Section 5.4
fig5_path = os.path.join(PLOT_DIR, "fig_code_mutation_security.png")
add_figure_after_paragraph(
    "Evaluating the code branch across 60 correctness",
    fig5_path,
    "Fig. 4. Code evaluation breakdown: mutation score across test generation methods (left) and dual-stage defense prevention rate across attack categories (right).",
    width_inches=5.8
)

# 4. Calibration reliability figure in Section 5.6
fig4_path = os.path.join(PLOT_DIR, "fig_calibration_reliability.png")
add_figure_after_paragraph(
    "Confidence calibration across the 300 test items",
    fig4_path,
    "Fig. 5. Reliability diagrams showing confidence calibration for CodeNeuron (left, ECE = 0.087) versus ungrounded LLM judge (right, ECE = 0.370).",
    width_inches=5.8
)

doc.save(DOCX_PATH)
try:
    doc.save(DOCX_OUT_DOWNLOADS)
except Exception as e:
    print(f"Downloads save error: {e}")

print("Document updated with all 4 publication figures successfully!")
