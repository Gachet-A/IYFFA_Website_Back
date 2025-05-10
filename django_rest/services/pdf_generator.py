from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os
from django.conf import settings

class DonationReceiptGenerator:
    # Association information
    ASSOCIATION_NAME = "IYFFA"
    ASSOCIATION_ADDRESS = "Boulevard carl-vogt, 1205 Genève"  
    ASSOCIATION_CONTACT = "contact@iyffa.org"  

    # PDF Layout constants
    PAGE_WIDTH, PAGE_HEIGHT = A4
    MARGIN = 2 * cm
    CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Setup custom styles for the PDF"""
        self.styles.add(ParagraphStyle(
            name='ReceiptTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1  # Center alignment
        ))
        
        self.styles.add(ParagraphStyle(
            name='ReceiptSubTitle',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=20,
            alignment=1
        ))

        self.styles.add(ParagraphStyle(
            name='ReceiptNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=12
        ))

    def generate_receipt(self, payment_data):
        """
        Generate a donation receipt PDF
        
        Args:
            payment_data (dict): Dictionary containing payment information
                Required keys:
                - amount: float
                - currency: str
                - payment_method: str
                - donor_name: str
                - donor_address: str
                - payment_date: datetime
                - transaction_id: str
        
        Returns:
            str: Path to the generated PDF file
        """
        # Create the PDF file path
        filename = f"receipt_{payment_data['transaction_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(settings.MEDIA_ROOT, 'receipts', filename)
        
        # Ensure the receipts directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Create the PDF document
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=self.MARGIN,
            leftMargin=self.MARGIN,
            topMargin=self.MARGIN,
            bottomMargin=self.MARGIN
        )
        
        # Build the PDF content
        story = []
        
        # Add title
        story.append(Paragraph("DONATION RECEIPT", self.styles['ReceiptTitle']))
        story.append(Spacer(1, 20))
        
        # Add date
        story.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", self.styles['ReceiptNormal']))
        story.append(Spacer(1, 20))
        
        # Add association information
        story.append(Paragraph("Association Information:", self.styles['ReceiptSubTitle']))
        story.append(Paragraph(f"Name: {self.ASSOCIATION_NAME}", self.styles['ReceiptNormal']))
        story.append(Paragraph(f"Address: {self.ASSOCIATION_ADDRESS}", self.styles['ReceiptNormal']))
        story.append(Paragraph(f"Contact: {self.ASSOCIATION_CONTACT}", self.styles['ReceiptNormal']))
        story.append(Spacer(1, 20))
        
        # Add donor information
        story.append(Paragraph("Donor Information:", self.styles['ReceiptSubTitle']))
        story.append(Paragraph(f"Name: {payment_data['donor_name']}", self.styles['ReceiptNormal']))
        story.append(Paragraph(f"Address: {payment_data['donor_address']}", self.styles['ReceiptNormal']))
        story.append(Spacer(1, 20))
        
        # Add donation details
        story.append(Paragraph("Donation Details:", self.styles['ReceiptSubTitle']))
        story.append(Paragraph(f"Amount: {payment_data['amount']} {payment_data['currency']}", self.styles['ReceiptNormal']))
        story.append(Paragraph(f"Payment Method: {payment_data['payment_method']}", self.styles['ReceiptNormal']))
        story.append(Paragraph(f"Date: {payment_data['payment_date'].strftime('%Y-%m-%d')}", self.styles['ReceiptNormal']))
        story.append(Paragraph(f"Transaction ID: {payment_data['transaction_id']}", self.styles['ReceiptNormal']))
        story.append(Spacer(1, 20))
        
        # Add declaration of consent
        story.append(Paragraph("Declaration of Consent:", self.styles['ReceiptSubTitle']))
        consent_text = """
        I hereby declare that this donation is made voluntarily and without any expectation of gain or benefit. 
        This donation is made for the purpose of supporting the activities and mission of IYFFA.
        """
        story.append(Paragraph(consent_text, self.styles['ReceiptNormal']))
        story.append(Spacer(1, 40))
        
        # Add signature line
        story.append(Paragraph("_________________________", self.styles['ReceiptNormal']))
        story.append(Paragraph("Signature", self.styles['ReceiptNormal']))
        
        # Build the PDF
        doc.build(story)
        
        return filepath 