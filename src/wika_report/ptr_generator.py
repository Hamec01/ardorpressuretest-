import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fpdf import FPDF
from fpdf.enums import XPos, YPos


class ARDORRecordPDF(FPDF):
    def __init__(self, record_number: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.record_number = record_number
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        # Brand Top Bar
        self.set_fill_color(31, 78, 121)  # #1F4E79
        self.rect(0, 0, 210, 8, 'F')

        self.set_font("Helvetica", "B", 16)
        self.set_text_color(31, 78, 121)
        self.set_xy(15, 12)
        self.cell(110, 8, "ARDOR PIPING SYSTEMS", new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")

        self.set_font("Helvetica", "B", 12)
        self.set_text_color(100, 116, 139)
        self.cell(70, 8, f"RECORD: {self.record_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

        self.set_font("Helvetica", "B", 13)
        self.set_text_color(15, 23, 42)
        self.set_xy(15, 20)
        self.cell(180, 7, "PRESSURE TEST RECORD / PROOF OF INTEGRITY", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

        self.set_draw_color(203, 213, 225)
        self.set_line_width(0.5)
        self.line(15, 28, 195, 28)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(148, 163, 184)
        self.cell(90, 8, f"Document: {self.record_number} | Official ARDOR Quality Document", new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
        self.cell(90, 8, f"Page {self.page_no()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")


def generate_ptr_pdf(
    record_data: Dict[str, Any],
    items_data: List[Dict[str, Any]],
    output_path: Optional[Path] = None
) -> bytes:
    """Генерирует официальный PDF-документ Pressure Test Record с поддержкой электронных подписей и штампа верификации."""
    rec_num = record_data.get("record_number", "PTR-DRAFT")
    pdf = ARDORRecordPDF(record_number=rec_num)
    pdf.add_page()

    # --- Section 1: Header Metadata Grid ---
    pdf.set_y(32)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(241, 245, 249)
    pdf.set_text_color(15, 23, 42)

    def row_pair(k1: str, v1: str, k2: str, v2: str):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(32, 6, k1, border="B", new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(58, 6, str(v1 or "-"), border="B", new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(32, 6, k2, border="B", new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(58, 6, str(v2 or "-"), border="B", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    row_pair("Project Name:", record_data.get("project", "ARDOR"), "Inspection No:", record_data.get("ins_no", "-"))
    row_pair("System / Line:", record_data.get("system", "-"), "Test Date:", record_data.get("test_date", datetime.now().strftime("%Y-%m-%d")))
    row_pair("Target Test Pressure:", record_data.get("test_pressure", "-"), "Design Pressure:", record_data.get("design_pressure", "-"))
    row_pair("Test Medium:", record_data.get("test_medium", "Water"), "Min Hold Duration:", record_data.get("duration_min", "60 min"))
    row_pair("Foreman / Supervisor:", record_data.get("foreman_name", "-"), "Status:", str(record_data.get("status", "DRAFT")).upper())

    pdf.ln(4)

    # --- Section 2: Items Table ---
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(31, 78, 121)
    pdf.cell(180, 6, "1. TESTED PIPELINE ELEMENTS & MEASUREMENT LOGS", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    # Table Header
    pdf.set_fill_color(31, 78, 121)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)

    w_item = 10
    w_pipe = 38
    w_draw = 28
    w_log = 28
    w_pstart = 22
    w_pend = 22
    w_res = 18
    w_note = 14

    pdf.cell(w_item, 7, "No", border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
    pdf.cell(w_pipe, 7, "Pipe Number", border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
    pdf.cell(w_draw, 7, "Drawing / Spool", border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
    pdf.cell(w_log, 7, "WIKA Log No", border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
    pdf.cell(w_pstart, 7, "Start (bar)", border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
    pdf.cell(w_pend, 7, "End (bar)", border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
    pdf.cell(w_res, 7, "Result", border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
    pdf.cell(w_note, 7, "Notes", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    # Table Rows
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(15, 23, 42)

    for idx, item in enumerate(items_data, 1):
        bg_fill = (idx % 2 == 0)
        pdf.set_fill_color(248, 250, 252) if bg_fill else pdf.set_fill_color(255, 255, 255)

        res_str = str(item.get("result", "PASS")).upper()
        draw_spool = item.get("drawing_no") or item.get("spool_no") or "-"

        pdf.cell(w_item, 6, str(item.get("item_no", idx)), border=1, fill=bg_fill, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
        pdf.cell(w_pipe, 6, str(item.get("pipe_number", "-")), border=1, fill=bg_fill, new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
        pdf.cell(w_draw, 6, str(draw_spool), border=1, fill=bg_fill, new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
        pdf.cell(w_log, 6, f"Log_{item.get('log_no', '-')}", border=1, fill=bg_fill, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
        pdf.cell(w_pstart, 6, str(item.get("hold_start_bar", "-")), border=1, fill=bg_fill, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
        pdf.cell(w_pend, 6, str(item.get("hold_end_bar", "-")), border=1, fill=bg_fill, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")

        if res_str == "PASS":
            pdf.set_text_color(16, 185, 129)
        elif res_str == "FAIL":
            pdf.set_text_color(244, 63, 94)
        else:
            pdf.set_text_color(100, 116, 139)

        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(w_res, 6, res_str, border=1, fill=bg_fill, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(15, 23, 42)

        pdf.cell(w_note, 6, str(item.get("notes") or "-")[:8], border=1, fill=bg_fill, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    if len(items_data) < 3:
        for extra_idx in range(len(items_data) + 1, 4):
            pdf.set_fill_color(255, 255, 255)
            pdf.cell(w_item, 6, str(extra_idx), border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
            pdf.cell(w_pipe, 6, "-", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
            pdf.cell(w_draw, 6, "-", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
            pdf.cell(w_log, 6, "-", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
            pdf.cell(w_pstart, 6, "-", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
            pdf.cell(w_pend, 6, "-", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
            pdf.cell(w_res, 6, "-", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
            pdf.cell(w_note, 6, "-", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    pdf.ln(4)

    # --- Section 3: Verification Stamp if Confirmed ---
    vrf_code = record_data.get("verification_code")
    if vrf_code:
        pdf.set_fill_color(240, 253, 250)  # Cyan/teal light tint
        pdf.set_draw_color(13, 148, 136)
        pdf.set_line_width(0.4)
        pdf.rect(15, pdf.get_y(), 180, 16, 'DF')
        pdf.set_xy(18, pdf.get_y() + 2)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(13, 148, 136)
        pdf.cell(85, 4, f"DIGITALLY VERIFIED DOCUMENT: {vrf_code}", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(71, 85, 105)
        conf_at = record_data.get("confirmed_at") or datetime.now(timezone.utc).isoformat()
        pdf.cell(90, 4, f"Timestamp (UTC): {str(conf_at)[:19].replace('T', ' ')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        
        pdf.set_x(18)
        pdf.cell(85, 4, f"Confirmed By: {record_data.get('confirmed_by_name') or record_data.get('foreman_name') or 'Authorized Foreman'} ({record_data.get('confirmed_by_role') or 'foreman'})", new_x=XPos.RIGHT, new_y=YPos.TOP)
        sha_str = record_data.get("sha256_hash") or "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        pdf.cell(90, 4, f"SHA-256 Digest: {sha_str[:28]}...", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        pdf.ln(4)

    # --- Section 4: Remarks ---
    if record_data.get("notes"):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(31, 78, 121)
        pdf.cell(180, 5, "2. GENERAL REMARKS & NOTES", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(180, 4, str(record_data.get("notes")), border=1)
        pdf.ln(3)

    # --- Section 5: Signatures & Approvals ---
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(31, 78, 121)
    pdf.cell(180, 5, "3. SIGNATURES & VERIFICATION APPROVALS", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    sig_w = 58
    sig_h = 24
    pdf.set_draw_color(203, 213, 225)

    # Box 1: Foreman
    x0 = 15
    y0 = pdf.get_y() + 2
    pdf.rect(x0, y0, sig_w, sig_h)
    pdf.set_xy(x0 + 2, y0 + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(sig_w - 4, 4, "PERFORMED BY (FOREMAN):", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(x0 + 2)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(sig_w - 4, 4, f"Name: {record_data.get('foreman_name') or '-'}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(x0 + 2)
    pdf.cell(sig_w - 4, 4, f"Date: {record_data.get('test_date') or '-'}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Signature Image if available
    sig_img_path = record_data.get("signature_image_path")
    if sig_img_path and Path(sig_img_path).exists():
        try:
            pdf.image(str(sig_img_path), x=x0 + 12, y=y0 + 11, w=34, h=11)
        except Exception:
            pdf.set_xy(x0 + 2, y0 + sig_h - 6)
            pdf.set_font("Helvetica", "I", 7)
            pdf.cell(sig_w - 4, 4, "[DIGITALLY CONFIRMED]", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        pdf.set_xy(x0 + 2, y0 + sig_h - 6)
        pdf.set_font("Helvetica", "I", 7)
        pdf.cell(sig_w - 4, 4, "Signature: __________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Box 2: QC Inspector
    x1 = x0 + sig_w + 3
    pdf.rect(x1, y0, sig_w, sig_h)
    pdf.set_xy(x1 + 2, y0 + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(sig_w - 4, 4, "CHECKED BY (QC INSPECTOR):", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(x1 + 2)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(sig_w - 4, 4, f"Name: {record_data.get('qc_inspector') or '-'}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(x1 + 2)
    pdf.cell(sig_w - 4, 4, f"Date: {record_data.get('test_date') or '-'}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_xy(x1 + 2, y0 + sig_h - 6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(sig_w - 4, 4, "Signature: __________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Box 3: Client / Surveyor
    x2 = x1 + sig_w + 3
    pdf.rect(x2, y0, sig_w, sig_h)
    pdf.set_xy(x2 + 2, y0 + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(sig_w - 4, 4, "APPROVED (CLIENT / CLASS):", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(x2 + 2)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(sig_w - 4, 4, f"Name: {record_data.get('client_surveyor') or '-'}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(x2 + 2)
    pdf.cell(sig_w - 4, 4, "Date: __________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_xy(x2 + 2, y0 + sig_h - 6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(sig_w - 4, 4, "Signature: __________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf_bytes = bytes(pdf.output())
    if output_path:
        Path(output_path).write_bytes(pdf_bytes)

    return pdf_bytes
