import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fpdf import FPDF

def test_markdown():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    try:
        pdf.multi_cell(0, 10, "Este texto tem **negrito** e *itálico*.", markdown=True)
        pdf.output("test_markdown.pdf")
        print("markdown=True SUPPORTED!")
    except Exception as e:
        print(f"markdown=True FAILED: {e}")

if __name__ == "__main__":
    test_markdown()
