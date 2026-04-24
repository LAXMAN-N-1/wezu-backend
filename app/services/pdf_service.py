from __future__ import annotations
from fpdf import FPDF
import os

class PDFService:
    @staticmethod
    def generate_invoice(invoice_data: dict) -> str:
        # Use FPDF or ReportLab
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=15)
        pdf.cell(200, 10, txt="Invoice", ln=1, align="C")
        
        pdf.set_font("Arial", size=10)
        for key, value in invoice_data.items():
             pdf.cell(200, 10, txt=f"{key}: {value}", ln=1, align="L")
             
        # Save
        filename = f"invoice_{invoice_data.get('invoice_number', 'temp')}.pdf"
        path = f"uploads/invoices/{filename}"
        os.makedirs("uploads/invoices", exist_ok=True)
        pdf.output(path)
        return f"/static/{path}"
