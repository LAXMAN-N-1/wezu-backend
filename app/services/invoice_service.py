"""
Invoice Generation Service
Generate PDF invoices for orders and rentals
"""
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime
from typing import Optional
from sqlmodel import Session
from app.models.catalog import CatalogOrder, CatalogOrderItem
from app.models.rental import Rental
from app.models.user import User
import logging

logger = logging.getLogger(__name__)

class InvoiceService:
    """Invoice generation service"""
    
    @staticmethod
    def generate_order_invoice(order_id: int, session: Session) -> Optional[BytesIO]:
        """
        Generate PDF invoice for order
        
        Args:
            order_id: Order ID
            session: Database session
            
        Returns:
            BytesIO buffer with PDF or None
        """
        try:
            # Get order details
            order = session.get(CatalogOrder, order_id)
            if not order:
                return None
            
            # Get user
            user = session.get(User, order.user_id)
            
            # Get order items
            from sqlmodel import select
            items = session.exec(
                select(CatalogOrderItem).where(CatalogOrderItem.order_id == order_id)
            ).all()
            
            # Create PDF buffer
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []
            
            # Styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a73e8'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            # Company header
            elements.append(Paragraph("WEZU Energy", title_style))
            elements.append(Paragraph("Battery Rental & Sales", styles['Normal']))
            elements.append(Paragraph("GST: 27XXXXX1234X1ZX", styles['Normal']))
            elements.append(Spacer(1, 0.3*inch))
            
            # Invoice details
            elements.append(Paragraph(f"<b>INVOICE</b>", styles['Heading2']))
            invoice_data = [
                ['Invoice Number:', order.order_number],
                ['Invoice Date:', order.created_at.strftime('%d-%m-%Y')],
                ['Payment Status:', order.payment_status],
                ['Payment Method:', order.payment_method]
            ]
            invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
            invoice_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(invoice_table)
            elements.append(Spacer(1, 0.3*inch))
            
            # Customer details
            elements.append(Paragraph("<b>Bill To:</b>", styles['Heading3']))
            customer_data = [
                [user.full_name if user else 'N/A'],
                [user.email if user else 'N/A'],
                [order.shipping_address],
                [f"{order.shipping_city}, {order.shipping_state} - {order.shipping_pincode}"],
                [f"Phone: {order.shipping_phone}"]
            ]
            for line in customer_data:
                elements.append(Paragraph(line[0], styles['Normal']))
            elements.append(Spacer(1, 0.3*inch))
            
            # Items table
            elements.append(Paragraph("<b>Order Items:</b>", styles['Heading3']))
            items_data = [['#', 'Product', 'SKU', 'Qty', 'Unit Price', 'Total']]
            
            for idx, item in enumerate(items, 1):
                items_data.append([
                    str(idx),
                    item.product_name,
                    item.sku,
                    str(item.quantity),
                    f"₹{item.unit_price:.2f}",
                    f"₹{item.total_price:.2f}"
                ])
            
            items_table = Table(items_data, colWidths=[0.5*inch, 2.5*inch, 1.2*inch, 0.6*inch, 1*inch, 1*inch])
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(items_table)
            elements.append(Spacer(1, 0.3*inch))
            
            # Totals
            totals_data = [
                ['Subtotal:', f"₹{order.subtotal:.2f}"],
                ['GST (18%):', f"₹{order.tax_amount:.2f}"],
                ['Shipping:', f"₹{order.shipping_fee:.2f}"],
                ['<b>Total Amount:</b>', f"<b>₹{order.total_amount:.2f}</b>"]
            ]
            totals_table = Table(totals_data, colWidths=[4.5*inch, 2*inch])
            totals_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(totals_table)
            elements.append(Spacer(1, 0.5*inch))
            
            # Footer
            elements.append(Paragraph("<b>Terms & Conditions:</b>", styles['Heading4']))
            elements.append(Paragraph("1. Warranty as per product specifications", styles['Normal']))
            elements.append(Paragraph("2. Goods once sold cannot be returned", styles['Normal']))
            elements.append(Paragraph("3. Subject to Mumbai jurisdiction", styles['Normal']))
            elements.append(Spacer(1, 0.3*inch))
            elements.append(Paragraph("Thank you for your business!", styles['Normal']))
            
            # Build PDF
            doc.build(elements)
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            logger.error(f"Failed to generate invoice: {str(e)}")
            return None
    
    @staticmethod
    def generate_rental_invoice(rental_id: int, session: Session) -> Optional[BytesIO]:
        """Generate PDF invoice for rental"""
        try:
            rental = session.get(Rental, rental_id)
            if not rental:
                return None
            
            user = session.get(User, rental.user_id)
            
            # Create PDF buffer
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []
            
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a73e8'),
                alignment=TA_CENTER
            )
            
            # Header
            elements.append(Paragraph("WEZU Energy", title_style))
            elements.append(Paragraph("Battery Rental Invoice", styles['Heading2']))
            elements.append(Spacer(1, 0.3*inch))
            
            # Rental details
            rental_data = [
                ['Rental ID:', str(rental.id)],
                ['Start Date:', rental.start_time.strftime('%d-%m-%Y %H:%M')],
                ['End Date:', rental.end_time.strftime('%d-%m-%Y %H:%M') if rental.end_time else 'Active'],
                ['Duration:', f"{int(((rental.end_time or rental.expected_end_time) - rental.start_time).total_seconds() / 3600)} hours" if rental.start_time else 'N/A'],
                ['Daily Rate:', f"₹{rental.daily_rate:.2f}"],
                ['Total Amount:', f"₹{rental.total_amount:.2f}"],
                ['Status:', rental.status]
            ]
            
            rental_table = Table(rental_data, colWidths=[2*inch, 3*inch])
            rental_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ]))
            elements.append(rental_table)
            elements.append(Spacer(1, 0.3*inch))
            
            # Customer details
            elements.append(Paragraph("<b>Customer Details:</b>", styles['Heading3']))
            elements.append(Paragraph(user.full_name if user else 'N/A', styles['Normal']))
            elements.append(Paragraph(user.email if user else 'N/A', styles['Normal']))
            
            doc.build(elements)
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            logger.error(f"Failed to generate rental invoice: {str(e)}")
            return None
