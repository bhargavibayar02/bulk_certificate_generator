"""
Predefined Landscape A4 Certificate Template.

Defines the fixed visual layout, typography hierarchy, controlled border rendering,
and logo positioning for generated certificates.
"""
from datetime import date
from pathlib import Path
from typing import List, Optional
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen.canvas import Canvas

# Fixed Landscape A4 Dimensions
PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)  # 841.89 x 595.27 points

# Predefined Typography & Palette
PRIMARY_COLOR = colors.HexColor("#0F172A")       # Deep slate navy
ACCENT_COLOR = colors.HexColor("#C5A059")        # Elegant dark gold
MUTED_COLOR = colors.HexColor("#475569")         # Slate gray
BORDER_DEFAULT = colors.HexColor("#1E3A8A")      # Classic royal navy
SUBTEXT_COLOR = colors.HexColor("#64748B")       # Light slate


def draw_border(
    canvas: Canvas,
    style: str,
    color_hex: str,
    width: int
) -> None:
    """
    Renders controlled decorative borders based on the specified style:
    - none: No border drawn
    - single: One crisp outer border
    - double: Outer boundary border with parallel inner accent border
    - thick: Single prominent heavy-weight border
    """
    if style == "none":
        return

    try:
        border_color = colors.HexColor(color_hex)
    except Exception:
        border_color = BORDER_DEFAULT

    canvas.saveState()
    canvas.setStrokeColor(border_color)

    if style == "single":
        canvas.setLineWidth(width)
        margin = 24
        canvas.rect(margin, margin, PAGE_WIDTH - 2 * margin, PAGE_HEIGHT - 2 * margin)

    elif style == "double":
        # Outer border
        canvas.setLineWidth(width)
        outer_m = 22
        canvas.rect(outer_m, outer_m, PAGE_WIDTH - 2 * outer_m, PAGE_HEIGHT - 2 * outer_m)

        # Inner fine accent border
        inner_width = max(1.0, width * 0.5)
        canvas.setLineWidth(inner_width)
        inner_m = 28
        canvas.rect(inner_m, inner_m, PAGE_WIDTH - 2 * inner_m, PAGE_HEIGHT - 2 * inner_m)

        # Subtle corner flourishes (small gold squares in the four corners)
        canvas.setFillColor(ACCENT_COLOR)
        canvas.setStrokeColor(ACCENT_COLOR)
        flourish_size = 4
        corners = [
            (inner_m - flourish_size, inner_m - flourish_size),
            (PAGE_WIDTH - inner_m, inner_m - flourish_size),
            (inner_m - flourish_size, PAGE_HEIGHT - inner_m),
            (PAGE_WIDTH - inner_m, PAGE_HEIGHT - inner_m),
        ]
        for cx, cy in corners:
            canvas.rect(cx, cy, flourish_size, flourish_size, fill=1, stroke=0)

    elif style == "thick":
        thick_width = max(width * 2.0, 4.0)
        canvas.setLineWidth(thick_width)
        margin = 24
        canvas.rect(margin, margin, PAGE_WIDTH - 2 * margin, PAGE_HEIGHT - 2 * margin)

    canvas.restoreState()


def draw_logos(canvas: Canvas, logo_paths: Optional[List[Path]]) -> None:
    """
    Renders between 0 and 10 logos at the top of the certificate:
    - 0 logos: logo section skipped
    - 1 logo: perfectly centered
    - 2 logos: left and right placement
    - 3-10 logos: evenly distributed across top horizontal band
    Preserves aspect ratio without stretching and handles bad files gracefully.
    """
    if not logo_paths:
        return

    # Filter only existing and valid files up to 10
    valid_paths: List[Path] = []
    for p in logo_paths[:10]:
        if p and p.is_file():
            valid_paths.append(p)

    count = len(valid_paths)
    if count == 0:
        return

    # Top logo bounding box parameters
    top_y = PAGE_HEIGHT - 85  # baseline for logo box
    max_logo_w = 70.0
    max_logo_h = 42.0

    # Calculate X positions for logos
    x_positions: List[float] = []
    if count == 1:
        x_positions = [PAGE_WIDTH / 2.0]
    elif count == 2:
        x_positions = [120.0, PAGE_WIDTH - 120.0]
    else:
        # Distribute evenly across margins [100, PAGE_WIDTH - 100]
        left_bound = 100.0
        right_bound = PAGE_WIDTH - 100.0
        step = (right_bound - left_bound) / (count - 1)
        x_positions = [left_bound + i * step for i in range(count)]

    for path, center_x in zip(valid_paths, x_positions):
        try:
            with Image.open(path) as img:
                orig_w, orig_h = img.size
                if orig_w <= 0 or orig_h <= 0:
                    continue
                scale = min(max_logo_w / orig_w, max_logo_h / orig_h)
                draw_w = orig_w * scale
                draw_h = orig_h * scale

                x = center_x - (draw_w / 2.0)
                y = top_y + ((max_logo_h - draw_h) / 2.0)

                canvas.drawImage(
                    str(path),
                    x,
                    y,
                    width=draw_w,
                    height=draw_h,
                    mask="auto",
                    preserveAspectRatio=True
                )
        except Exception:
            # Handle corrupt/invalid image file gracefully without crashing
            continue


def render_certificate(
    canvas: Canvas,
    recipient_name: str,
    event_name: str,
    event_date: date,
    cert_id: int,
    border_style: str = "double",
    border_color: str = "#1E3A8A",
    border_width: int = 2,
    logo_paths: Optional[List[Path]] = None,
) -> None:
    """
    Renders the complete predefined certificate on the given ReportLab Canvas.
    """
    center_x = PAGE_WIDTH / 2.0

    # 1. Draw decorative background border
    draw_border(canvas, border_style, border_color, border_width)

    # 2. Draw optional top logos
    draw_logos(canvas, logo_paths)

    # Shift content down slightly if logos are present
    has_logos = bool(logo_paths and any(p and p.is_file() for p in logo_paths[:10]))
    base_shift = -10 if has_logos else 0

    # 3. Certificate Title
    canvas.saveState()
    canvas.setFillColor(PRIMARY_COLOR)
    canvas.setFont("Helvetica-Bold", 26)
    title_y = 455 + base_shift
    canvas.drawCentredString(center_x, title_y, "CERTIFICATE OF PARTICIPATION")

    # Decorative accent line below title
    canvas.setStrokeColor(ACCENT_COLOR)
    canvas.setLineWidth(2)
    line_w = 160
    canvas.line(center_x - line_w / 2, title_y - 12, center_x + line_w / 2, title_y - 12)
    canvas.restoreState()

    # 4. Presentation statement
    canvas.saveState()
    canvas.setFillColor(MUTED_COLOR)
    canvas.setFont("Helvetica", 14)
    canvas.drawCentredString(
        center_x,
        405 + base_shift,
        "This certificate is proudly presented to"
    )
    canvas.restoreState()

    # 5. Recipient Name (Prominently displayed)
    canvas.saveState()
    canvas.setFillColor(PRIMARY_COLOR)
    # Adjust font size dynamically for unusually long names to prevent overflow
    font_size = 32
    if len(recipient_name) > 30:
        font_size = 24
    elif len(recipient_name) > 22:
        font_size = 28
    canvas.setFont("Helvetica-Bold", font_size)
    name_y = 345 + base_shift
    canvas.drawCentredString(center_x, name_y, recipient_name)

    # Subtle underline under recipient name
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.setLineWidth(1)
    name_line_w = min(400, max(220, len(recipient_name) * 12))
    canvas.line(center_x - name_line_w / 2, name_y - 10, center_x + name_line_w / 2, name_y - 10)
    canvas.restoreState()

    # 6. Participation statement
    canvas.saveState()
    canvas.setFillColor(MUTED_COLOR)
    canvas.setFont("Helvetica", 13)
    canvas.drawCentredString(
        center_x,
        290 + base_shift,
        "for successfully participating in"
    )
    canvas.restoreState()

    # 7. Event Name
    canvas.saveState()
    canvas.setFillColor(colors.HexColor(border_color if border_color else "#1E3A8A"))
    event_font_size = 20
    if len(event_name) > 40:
        event_font_size = 16
    canvas.setFont("Helvetica-Bold", event_font_size)
    canvas.drawCentredString(center_x, 250 + base_shift, event_name)
    canvas.restoreState()

    # 8. Event Date
    formatted_date = event_date.strftime("%B %d, %Y")
    canvas.saveState()
    canvas.setFillColor(MUTED_COLOR)
    canvas.setFont("Helvetica", 12)
    canvas.drawCentredString(
        center_x,
        215 + base_shift,
        f"held on {formatted_date}."
    )
    canvas.restoreState()

    # 9. Signatures and Official Marks
    sig_y = 105
    sig_line_len = 160

    # Left Signature Line: Authorized Signatory
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#94A3B8"))
    canvas.setLineWidth(1)
    left_x = 180
    canvas.line(left_x - sig_line_len / 2, sig_y + 25, left_x + sig_line_len / 2, sig_y + 25)
    canvas.setFillColor(PRIMARY_COLOR)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawCentredString(left_x, sig_y + 10, "Authorized Signatory")
    canvas.setFillColor(SUBTEXT_COLOR)
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(left_x, sig_y - 3, "Event Organizing Committee")
    canvas.restoreState()

    # Right Signature Line: Program Director / Issue Verification
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#94A3B8"))
    canvas.setLineWidth(1)
    right_x = PAGE_WIDTH - 180
    canvas.line(right_x - sig_line_len / 2, sig_y + 25, right_x + sig_line_len / 2, sig_y + 25)
    canvas.setFillColor(PRIMARY_COLOR)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawCentredString(right_x, sig_y + 10, "Program Director")
    canvas.setFillColor(SUBTEXT_COLOR)
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(right_x, sig_y - 3, f"Issued: {formatted_date}")
    canvas.restoreState()

    # 10. Footer / Verification Info
    canvas.saveState()
    canvas.setFillColor(SUBTEXT_COLOR)
    canvas.setFont("Helvetica", 8)
    footer_text = f"Certificate ID: CERT-{cert_id:06d} • Official Digital Credential"
    canvas.drawCentredString(center_x, 42, footer_text)
    canvas.restoreState()
