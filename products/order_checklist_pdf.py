"""Generate order packing checklist PDF (aggregated by product, no payers/prices)."""

from collections import defaultdict
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FONTS_DIR = Path(__file__).resolve().parent / 'fonts'
_FONT_REGISTERED = False
_FONT_NAME = 'DejaVuSans'
_FONT_BOLD_NAME = 'DejaVuSans-Bold'


def _ensure_fonts():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return

    regular = _FONTS_DIR / 'DejaVuSans.ttf'
    bold = _FONTS_DIR / 'DejaVuSans-Bold.ttf'
    if not regular.is_file() or not bold.is_file():
        raise FileNotFoundError(
            f'Brak czcionek PDF w {_FONTS_DIR} (oczekiwano DejaVuSans.ttf i DejaVuSans-Bold.ttf)'
        )

    pdfmetrics.registerFont(TTFont(_FONT_NAME, str(regular)))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD_NAME, str(bold)))
    _FONT_REGISTERED = True


def _aggregate_order_items(order):
    """Group order items by product; sum quantities (one OrderItem = one unit)."""
    quantities = defaultdict(int)
    names = {}
    for item in order.items.select_related('product').all():
        product_id = item.product_id
        quantities[product_id] += 1
        names[product_id] = item.product.name

    rows = [
        {'product_id': product_id, 'product_name': names[product_id], 'quantity': qty}
        for product_id, qty in quantities.items()
    ]
    rows.sort(key=lambda row: (row['product_name'] or '').lower())
    return rows


def build_order_checklist_pdf(order):
    """
    Build a PDF checklist for the given Order.

    Returns:
        bytes: PDF file content
    """
    _ensure_fonts()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f'Lista kontrolna — zamówienie #{order.id}',
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ChecklistTitle',
        parent=styles['Heading1'],
        fontName=_FONT_BOLD_NAME,
        fontSize=16,
        leading=20,
        spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        'ChecklistMeta',
        parent=styles['Normal'],
        fontName=_FONT_NAME,
        fontSize=10,
        leading=14,
        spaceAfter=2,
    )
    cell_style = ParagraphStyle(
        'ChecklistCell',
        parent=styles['Normal'],
        fontName=_FONT_NAME,
        fontSize=10,
        leading=13,
    )
    header_cell_style = ParagraphStyle(
        'ChecklistHeaderCell',
        parent=styles['Normal'],
        fontName=_FONT_BOLD_NAME,
        fontSize=10,
        leading=13,
    )

    buyer_name = ''
    if order.buyer_id:
        buyer_name = (
            order.buyer.get_organization_name_or_full_name()
            or order.buyer.username
            or ''
        )

    created_label = ''
    if order.created_at:
        created_label = order.created_at.strftime('%d.%m.%Y %H:%M')

    story = [
        Paragraph(f'Lista kontrolna — zamówienie #{order.id}', title_style),
    ]
    if order.order_number:
        story.append(Paragraph(f'Numer: {order.order_number}', meta_style))
    if created_label:
        story.append(Paragraph(f'Data: {created_label}', meta_style))
    if buyer_name:
        story.append(Paragraph(f'Kupujący: {buyer_name}', meta_style))
    story.append(Spacer(1, 8 * mm))

    aggregated = _aggregate_order_items(order)
    table_data = [
        [
            Paragraph('☐', header_cell_style),
            Paragraph('Produkt', header_cell_style),
            Paragraph('Ilość', header_cell_style),
        ]
    ]
    for row in aggregated:
        table_data.append(
            [
                Paragraph('☐', cell_style),
                Paragraph(row['product_name'] or '—', cell_style),
                Paragraph(str(row['quantity']), cell_style),
            ]
        )

    if len(table_data) == 1:
        table_data.append(
            [
                Paragraph('', cell_style),
                Paragraph('Brak pozycji w zamówieniu.', cell_style),
                Paragraph('', cell_style),
            ]
        )

    table = Table(table_data, colWidths=[12 * mm, 130 * mm, 22 * mm])
    table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (-1, 0), _FONT_BOLD_NAME),
                ('FONTNAME', (0, 1), (-1, -1), _FONT_NAME),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.92, 0.92, 0.92)),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.Color(0.7, 0.7, 0.7)),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return buffer.getvalue()
