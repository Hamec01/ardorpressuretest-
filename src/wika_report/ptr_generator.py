import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fpdf import FPDF


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
        self.cell(110, 8, "ARDOR PIPING SYSTEMS", ln=0, align="L")

        self.set_font("Helvetica", "B", 12)
        self.set_text_color(100, 116, 139)
        self.cell(70, 8, f"RECORD: {self.record_number}", ln=1, align="R")

        self.set_font("Helvetica", "B", 13)
        self.set_text_color(15, 23, 42)
        self.set_xy(15, 20)
        self.cell(180, 7, "PRESSURE TEST RECORD / PROOF OF INTEGRITY", ln=1, align="L")

        self.set_draw_color(203, 213, 225)
        self.set_line_width(0.5)
        self.line(15, 28, 195, 28)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(148, 163, 184)
        self.cell(90, 8, f"Document: {self.record_number} | Official ARDOR Quality Document", ln=0, align="L")
        self.cell(90, 8, f"Page {self.page_no()}", ln=0, align="R")


def generate_ptr_pdf(
    record_data: Dict[str, Any],
    items_data: List[Dict[str, Any]],
    output_path: Optional[Path] = None
) -> bytes:
    """Генерирует официальный PDF-документ Pressure Test Record."""
    rec_num = record_data.get("record_number", "PTR-DRAFT")
    pdf = ARDORRecordPDF(record_number=rec_num)
    pdf.add_page()

    # --- Section 1: Header Metadata Grid ---
    pdf.set_y(32)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(241, 245, 249)
    pdf.set_text_color(15, 23, 42)

    # Info Grid (2 columns)
    col1_w, col2_w = 90, 90
    
    def row_pair(k1: str, v1: str, k2: str, v2: str):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(32, 6, k1, border="B", align="L")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(58, 6, str(v1 or "-"), border="B", align="L")

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(32, 6, k2, border="B", align="L")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(58, 6, str(v2 or "-"), border="B", align="L")
        pdf.ln(6)

    row_pair("Project Name:", record_data.get("project", "ARDOR"), "Inspection No:", record_data.get("ins_no", "-"))
    row_pair("System / Line:", record_data.get("system", "-"), "Test Date:", record_data.get("test_date", datetime.now().strftime("%Y-%m-%d")))
    row_pair("Target Test Pressure:", record_data.get("test_pressure", "-"), "Design Pressure:", record_data.get("design_pressure", "-"))
    row_pair("Test Medium:", record_data.get("test_medium", "Water"), "Min Hold Duration:", record_data.get("duration_min", "60 min"))
    row_pair("Foreman / Supervisor:", record_data.get("foreman_name", "-"), "Status:", str(record_data.get("status", "DRAFT")).upper())

    pdf.ln(5)

    # --- Section 2: Items Table ---
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(31, 78, 121)
    pdf.cell(180, 6, "1. TESTED PIPELINE ELEMENTS & MEASUREMENT LOGS", ln=1, align="L")

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

    pdf.cell(w_item, 7, "No", border=1, fill=True, align="C")
    pdf.cell(w_pipe, 7, "Pipe Number", border=1, fill=True, align="L")
    pdf.cell(w_draw, 7, "Drawing / Spool", border=1, fill=True, align="L")
    pdf.cell(w_log, 7, "WIKA Log No", border=1, fill=True, align="C")
    pdf.cell(w_pstart, 7, "Start (bar)", border=1, fill=True, align="C")
    pdf.cell(w_pend, 7, "End (bar)", border=1, fill=True, align="C")
    pdf.cell(w_res, 7, "Result", border=1, fill=True, align="C")
    pdf.cell(w_note, 7, "Notes", border=1, fill=True, align="C")
    pdf.ln(7)

    # Table Rows
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(15, 23, 42)

    for idx, item in enumerate(items_data, 1):
        bg_fill = (idx % 2 == 0)
        pdf.set_fill_color(248, 250, 252) if bg_fill else pdf.set_fill_color(255, 255, 255)

        res_str = str(item.get("result", "PASS")).upper()
        draw_spool = item.get("drawing_no") or item.get("spool_no") or "-"

        pdf.cell(w_item, 6, str(item.get("item_no", idx)), border=1, fill=bg_fill, align="C")
        pdf.cell(w_pipe, 6, str(item.get("pipe_number", "-")), border=1, fill=bg_fill, align="L")
        pdf.cell(w_draw, 6, str(draw_spool), border=1, fill=bg_fill, align="L")
        pdf.cell(w_log, 6, f"Log_{item.get('log_no', '-')}", border=1, fill=bg_fill, align="C")
        pdf.cell(w_pstart, 6, str(item.get("hold_start_bar", "-")), border=1, fill=bg_fill, align="C")
        pdf.cell(w_pend, 6, str(item.get("hold_end_bar", "-")), border=1, fill=bg_fill, align="C")

        # Color for Result
        if res_str == "PASS":
            pdf.set_text_color(16, 185, 129)
        elif res_str == "FAIL":
            pdf.set_text_color(244, 63, 94)
        else:
            pdf.set_text_color(100, 116, 139)

        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(w_res, 6, res_str, border=1, fill=bg_fill, align="C")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(15, 23, 42)

        pdf.cell(w_note, 6, str(item.get("notes") or "-")[:8], border=1, fill=bg_fill, align="C")
        pdf.ln(6)

    # Empty rows if few items
    if len(items_data) < 4:
        for extra_idx in range(len(items_data) + 1, 5):
            pdf.set_fill_color(255, 255, 255)
            pdf.cell(w_item, 6, str(extra_idx), border=1, align="C")
            pdf.cell(w_pipe, 6, "-", border=1, align="L")
            pdf.cell(w_draw, 6, "-", border=1, align="L")
            pdf.cell(w_log, 6, "-", border=1, align="C")
            pdf.cell(w_pstart, 6, "-", border=1, align="C")
            pdf.cell(w_pend, 6, "-", border=1, align="C")
            pdf.cell(w_res, 6, "-", border=1, align="C")
            pdf.cell(w_note, 6, "-", border=1, align="C")
            pdf.ln(6)

    pdf.ln(6)

    # --- Section 3: Notes & Comments ---
    if record_data.get("notes"):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(31, 78, 121)
        pdf.cell(180, 5, "2. GENERAL REMARKS & NOTES", ln=1, align="L")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(180, 4, str(record_data.get("notes")), border=1)
        pdf.ln(4)

    # --- Section 4: Signatures & Approvals ---
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(31, 78, 121)
    pdf.cell(180, 5, "3. SIGNATURES & VERIFICATION APPROVALS", ln=1, align="L")

    sig_w = 58
    sig_h = 24

    # Box 1: Foreman
    x0 = 15
    y0 = pdf.get_y() + 2
    pdf.rect(x0, y0, sig_w, sig_h)
    pdf.set_xy(x0 + 2, y0 + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(sig_w - 4, 4, "PERFORMED BY (FOREMAN):", ln=1)
    pdf.set_x(x0 + 2)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(sig_w - 4, 4, f"Name: {record_data.get('foreman_name') or '-'}", ln=1)
    pdf.set_x(x0 + 2)
    pdf.cell(sig_w - 4, 4, f"Date: {record_data.get('test_date') or '-'}", ln=1)
    pdf.set_xy(x0 + 2, y0 + sig_h - 6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(sig_w - 4, 4, "Signature: __________________", ln=1)

    # Box 2: QC Inspector
    x1 = x0 + sig_w + 3
    pdf.rect(x1, y0, sig_w, sig_h)
    pdf.set_xy(x1 + 2, y0 + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(sig_w - 4, 4, "CHECKED BY (QC INSPECTOR):", ln=1)
    pdf.set_x(x1 + 2)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(sig_w - 4, 4, f"Name: {record_data.get('qc_inspector') or '-'}", ln=1)
    pdf.set_x(x1 + 2)
    pdf.cell(sig_w - 4, 4, f"Date: {record_data.get('test_date') or '-'}", ln=1)
    pdf.set_xy(x1 + 2, y0 + sig_h - 6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(sig_w - 4, 4, "Signature: __________________", ln=1)

    # Box 3: Client / Surveyor
    x2 = x1 + sig_w + 3
    pdf.rect(x2, y0, sig_w, sig_h)
    pdf.set_xy(x2 + 2, y0 + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(sig_w - 4, 4, "APPROVED (CLIENT / CLASS):", ln=1)
    pdf.set_x(x2 + 2)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(sig_w - 4, 4, f"Name: {record_data.get('client_surveyor') or '-'}", ln=1)
    pdf.set_x(x2 + 2)
    pdf.cell(sig_w - 4, 4, "Date: __________________", ln=1)
    pdf.set_xy(x2 + 2, y0 + sig_h - 6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(sig_w - 4, 4, "Signature: __________________", ln=1)

    pdf_bytes = bytes(pdf.output())
    if output_path:
        Path(output_path).write_bytes(pdf_bytes)

    return pdf_bytes
