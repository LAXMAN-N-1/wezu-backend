from __future__ import annotations
from fpdf import FPDF
from datetime import datetime
import os

class ReceiptService:
    @staticmethod
    def generate_receipt_pdf(transaction: dict, user_name: str) -> str:
        """Generate a simple PDF receipt for a transaction"""
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, "WEZU ENERGY - RECEIPT", ln=True, align='C')
        pdf.ln(10)
        
        # Details
        pdf.set_font("Arial", size=12)
        pdf.cell(100, 10, f"Customer: {user_name}")
        pdf.cell(90, 10, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='R')
        pdf.ln(5)
        
        pdf.cell(190, 10, f"Transaction ID: {transaction['id']}", ln=True)
        pdf.cell(190, 10, f"Type: {transaction['type'].replace('_', ' ').title()}", ln=True)
        pdf.cell(190, 10, f"Status: {transaction['status'].title()}", ln=True)
        pdf.ln(5)
        
        # Amount
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(100, 10, "Total Amount:")
        pdf.cell(90, 10, f"{transaction['currency']} {transaction['amount']}", ln=True, align='R')
        
        pdf.ln(20)
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(190, 10, "Thank you for using WEZU Energy!", ln=True, align='C')
        
        # Save
        receipt_dir = "uploads/receipts"
        os.makedirs(receipt_dir, exist_ok=True)
        file_name = f"receipt_{transaction['id']}.pdf"
        file_path = f"{receipt_dir}/{file_name}"
        pdf.output(file_path)
        
        return f"/static/{file_path}"
