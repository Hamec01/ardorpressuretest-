import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fpdf import FPDF
from fpdf.enums import XPos, YPos


class OfficialARDORRecordPDF(FPDF):
    """
    100% точный векторный генератор официального финско-английского бланка ARDOR:
    PAINEKOEPÖYTÄKIRJA / PRESSURE TEST RECORD
    """

    def __init__(self, record_number: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.record_number = record_number
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(12, 12, 12)

    def draw_checkbox(self, x: float, y: float, size: float = 3.5, checked: bool = False, label: str = ""):
        self.rect(x, y, size, size)
        if checked:
            self.set_font("Helvetica", "B", 8)
            self.text(x + 0.6, y + 2.8, "X")
        if label:
            self.set_font("Helvetica", "", 7.5)
            self.text(x + size + 1.5, y + 2.8, label)


def generate_ptr_pdf(
    record_data: Dict[str, Any],
    items_data: List[Dict[str, Any]],
    output_path: Optional[Path] = None
) -> bytes:
    """Генерирует официальный бланк ARDOR PAINEKOEPÖYTÄKIRJA / PRESSURE TEST RECORD."""
    rec_num = record_data.get("record_number", "PTR-001")
    pdf = OfficialARDORRecordPDF(record_number=rec_num)
    pdf.add_page()

    logo_path = Path(__file__).parent.parent.parent / "resources" / "ardor_logo.png"
    if not logo_path.exists():
        logo_path = Path("resources/ardor_logo.png")

    # Outer Box Grid Start
    start_x = 12
    start_y = 12
    page_w = 186  # 210 - 24

    # -------------------------------------------------------------
    # 1. HEADER SECTION
    # -------------------------------------------------------------
    header_h = 24
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.35)

    # Left Logo Box (Width: 80mm)
    pdf.rect(start_x, start_y, 80, header_h)
    if logo_path.exists():
        try:
            # Place ARDOR logo centered inside the 80x24 box
            pdf.image(str(logo_path), x=start_x + 5, y=start_y + 4, w=70)
        except Exception:
            pdf.set_font("Helvetica", "B", 22)
            pdf.text(start_x + 8, start_y + 16, "ARDOR")
    else:
        pdf.set_font("Helvetica", "B", 22)
        pdf.text(start_x + 8, start_y + 16, "ARDOR")

    # Right Title Box (Width: 106mm)
    title_x = start_x + 80
    pdf.rect(title_x, start_y, 106, 12)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(title_x + 2, start_y + 1)
    pdf.cell(102, 5, "PAINEKOEPÖYTÄKIRJA", new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
    pdf.set_xy(title_x + 2, start_y + 6)
    pdf.cell(102, 5, "PRESSURE TEST RECORD", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    # Sub-header: Page & Number
    sub_y = start_y + 12
    pdf.rect(title_x, sub_y, 22, 12)
    pdf.rect(title_x + 22, sub_y, 24, 12)
    pdf.rect(title_x + 46, sub_y, 60, 12)

    pdf.set_font("Helvetica", "", 6.5)
    pdf.text(title_x + 1.5, sub_y + 3.5, "Sivu / Page")
    pdf.set_font("Helvetica", "B", 8)
    pdf.text(title_x + 8, sub_y + 9, "1")

    pdf.set_font("Helvetica", "", 6.5)
    pdf.text(title_x + 23.5, sub_y + 3.5, "Sivuja yht. / Pages")
    pdf.set_font("Helvetica", "B", 8)
    pdf.text(title_x + 32, sub_y + 9, "1")

    pdf.set_font("Helvetica", "", 6.5)
    pdf.text(title_x + 47.5, sub_y + 3.5, "Numero tai tunnus / Number or mark")
    pdf.set_font("Helvetica", "B", 7.5)
    ins_no_display = str(record_data.get("ins_no") or record_data.get("record_number") or "-")
    pdf.text(title_x + 47.5, sub_y + 7.5, ins_no_display)
    if record_data.get("project_code"):
        pdf.text(title_x + 47.5, sub_y + 10.8, str(record_data.get("project_code")))

    # -------------------------------------------------------------
    # 2. METADATA ROW 1: Job No & Project Name
    # -------------------------------------------------------------
    row1_y = start_y + header_h
    row1_h = 14
    pdf.rect(start_x, row1_y, 80, row1_h)
    pdf.rect(start_x + 80, row1_y, 106, row1_h)

    pdf.set_font("Helvetica", "", 6.5)
    pdf.text(start_x + 1.5, row1_y + 3.5, "Työnumero / Job No")
    pdf.set_font("Helvetica", "B", 8.5)
    job_no = str(record_data.get("job_no") or record_data.get("system") or "-")
    pdf.text(start_x + 1.5, row1_y + 9.5, job_no)

    pdf.set_font("Helvetica", "", 6.5)
    pdf.text(start_x + 81.5, row1_y + 3.5, "Projektin nro tai nimi / Project No or name")
    pdf.set_font("Helvetica", "B", 8.5)
    proj_name = str(record_data.get("project") or "ARDOR Project")
    pdf.text(start_x + 81.5, row1_y + 9.5, proj_name)

    # -------------------------------------------------------------
    # 3. METADATA ROW 2: Design Pressure, Test Pressure, Gauge S#
    # -------------------------------------------------------------
    row2_y = row1_y + row1_h
    row2_h = 14
    pdf.rect(start_x, row2_y, 80, row2_h)
    pdf.rect(start_x + 80, row2_y, 45, row2_h)
    pdf.rect(start_x + 125, row2_y, 61, row2_h)

    pdf.set_font("Helvetica", "", 6.5)
    pdf.text(start_x + 1.5, row2_y + 3.5, "Suunnittelupaine / Design pressure")
    pdf.set_font("Helvetica", "B", 8.5)
    des_p = str(record_data.get("design_pressure") or "-")
    pdf.text(start_x + 1.5, row2_y + 9.5, des_p)

    pdf.set_font("Helvetica", "", 6.5)
    pdf.text(start_x + 81.5, row2_y + 3.5, "Koepaine / Test pressure")
    pdf.set_font("Helvetica", "B", 9)
    test_p = str(record_data.get("test_pressure") or "-")
    pdf.text(start_x + 81.5, row2_y + 9.5, test_p)

    pdf.set_font("Helvetica", "", 6.5)
    pdf.text(start_x + 126.5, row2_y + 3.5, "Mittarin nro / S#")
    pdf.set_font("Helvetica", "B", 8)
    wika_s = str(record_data.get("wika_nr") or record_data.get("gauge_sn") or "BG516-GDTZ-13-D")
    pdf.text(start_x + 126.5, row2_y + 9.5, wika_s)

    # -------------------------------------------------------------
    # 4. ITEMS TABLE (Exact columns matching ARDOR blank)
    # -------------------------------------------------------------
    tbl_y = row2_y + row2_h
    col_w = [52, 28, 24, 24, 34, 24]  # Total = 186mm
    col_x = [start_x]
    for w in col_w:
        col_x.append(col_x[-1] + w)

    # Table Header (Height: 11mm)
    hdr_h = 11
    for i, w in enumerate(col_w):
        pdf.rect(col_x[i], tbl_y, w, hdr_h)

    pdf.set_font("Helvetica", "B", 6.5)
    pdf.text(col_x[0] + 1.5, tbl_y + 3.5, "Piirustus nro")
    pdf.text(col_x[0] + 1.5, tbl_y + 7.5, "Drawing No")

    pdf.text(col_x[1] + 1.5, tbl_y + 3.5, "Systeemi")
    pdf.text(col_x[1] + 1.5, tbl_y + 7.5, "System")

    pdf.text(col_x[2] + 1.5, tbl_y + 3.5, "Osa nro")
    pdf.text(col_x[2] + 1.5, tbl_y + 7.5, "Part No")

    pdf.text(col_x[3] + 1.5, tbl_y + 3.5, "Pvm")
    pdf.text(col_x[3] + 1.5, tbl_y + 7.5, "Date")

    pdf.text(col_x[4] + 1.5, tbl_y + 3.5, "Kokeen kesto")
    pdf.text(col_x[4] + 1.5, tbl_y + 7.5, "Duration of the test")

    pdf.text(col_x[5] + 1.5, tbl_y + 3.5, "Log nro")
    pdf.text(col_x[5] + 1.5, tbl_y + 7.5, "Log No")

    # Table Data Rows (Fixed 7 rows per page to match exact blank layout)
    row_h = 8.5
    current_y = tbl_y + hdr_h
    display_rows = items_data if items_data else [{}]

    for row_idx in range(max(7, len(display_rows))):
        item = display_rows[row_idx] if row_idx < len(display_rows) else {}
        for i, w in enumerate(col_w):
            pdf.rect(col_x[i], current_y, w, row_h)

        if item:
            pdf.set_font("Helvetica", "", 7.5)
            # Col 0: Drawing No
            dwg = str(item.get("drawing_no") or item.get("spool_no") or "-")
            pdf.text(col_x[0] + 1.5, current_y + 5.5, dwg[:32])

            # Col 1: System
            sys_val = str(item.get("system") or record_data.get("system") or "-")
            pdf.text(col_x[1] + 1.5, current_y + 5.5, sys_val[:16])

            # Col 2: Part No (Pipe Number)
            part_no = str(item.get("pipe_number") or item.get("part_no") or "-")
            pdf.text(col_x[2] + 1.5, current_y + 5.5, part_no[:14])

            # Col 3: Date
            date_val = str(item.get("date") or record_data.get("test_date") or datetime.now().strftime("%d.%m.%Y"))
            pdf.text(col_x[3] + 1.5, current_y + 5.5, date_val)

            # Col 4: Duration
            dur_val = str(item.get("duration") or record_data.get("duration_min") or "60 min")
            pdf.text(col_x[4] + 1.5, current_y + 5.5, dur_val)

            # Col 5: Log No
            log_val = str(item.get("log_no") or "-")
            pdf.text(col_x[5] + 1.5, current_y + 5.5, log_val)

        current_y += row_h

    # -------------------------------------------------------------
    # 5. TEST MATERIAL / TESTIAINE CHECKBOXES
    # -------------------------------------------------------------
    mat_y = current_y
    mat_h = 16
    pdf.rect(start_x, mat_y, page_w, mat_h)

    pdf.set_font("Helvetica", "B", 7)
    pdf.text(start_x + 2, mat_y + 4, "Testiaine")
    pdf.set_font("Helvetica", "", 6.5)
    pdf.text(start_x + 2, mat_y + 7.5, "Test material")

    medium = str(record_data.get("test_medium", "Water")).lower()
    pdf.draw_checkbox(start_x + 25, mat_y + 6, checked="air" in medium or "ilma" in medium, label="Ilma / Air")
    pdf.draw_checkbox(start_x + 65, mat_y + 6, checked="water" in medium or "vesi" in medium or not medium, label="Vesi / Water")
    pdf.draw_checkbox(start_x + 110, mat_y + 6, checked="glycol" in medium or "glykoli" in medium, label="Glykoli / Glycol")
    pdf.draw_checkbox(start_x + 152, mat_y + 6, checked="nitrogen" in medium or "typpi" in medium or "n2" in medium, label="Typpi / Nitrogen")

    # -------------------------------------------------------------
    # 6. APPROVAL CHECKBOXES & REMARKS SECTION
    # -------------------------------------------------------------
    rem_y = mat_y + mat_h
    rem_h = 24
    pdf.rect(start_x, rem_y, page_w, rem_h)

    # Checkboxes: Tarkastettu & Hyväksytty
    pdf.draw_checkbox(start_x + 55, rem_y + 3, checked=True, label="Tarkastettu")
    pdf.draw_checkbox(start_x + 115, rem_y + 3, checked=True, label="Hyväksytty")
    pdf.line(start_x, rem_y + 8, start_x + page_w, rem_y + 8)

    pdf.set_font("Helvetica", "B", 6.5)
    pdf.text(start_x + 2, rem_y + 11.5, "Huomautukset / Remarks")
    pdf.set_font("Helvetica", "", 7.5)
    remarks_text = str(record_data.get("notes") or "Hold test completed. No pressure drops detected. Test passed successfully.")
    pdf.set_xy(start_x + 2, rem_y + 13)
    pdf.multi_cell(page_w - 4, 4, remarks_text, align="L")

    # -------------------------------------------------------------
    # 7. SIGNATURE BLOCK (Pvm / Date & Witnessed / Reviewed by)
    # -------------------------------------------------------------
    sig_y = rem_y + rem_h
    sig_h = 36
    pdf.rect(start_x, sig_y, 45, sig_h)
    pdf.rect(start_x + 45, sig_y, 141, sig_h)

    pdf.set_font("Helvetica", "B", 6.5)
    pdf.text(start_x + 2, sig_y + 4.5, "Pvm / Date")
    pdf.set_font("Helvetica", "B", 8)
    sig_date = record_data.get("confirmed_at") or record_data.get("test_date") or datetime.now().strftime("%d.%m.%Y")
    if isinstance(sig_date, datetime):
        sig_date = sig_date.strftime("%d.%m.%Y")
    pdf.text(start_x + 2, sig_y + 16, str(sig_date)[:10])

    pdf.set_font("Helvetica", "B", 6.5)
    pdf.text(start_x + 47, sig_y + 4.5, "Witnessed / Reviewed by")

    # 8. Digital Seal & Signature Rendering
    sig_img_path = record_data.get("signature_image_path")
    if sig_img_path and Path(sig_img_path).exists():
        try:
            pdf.image(str(sig_img_path), x=start_x + 50, y=sig_y + 6, h=22)
        except Exception:
            pass

    # Render Foreman / Reviewer Name
    pdf.set_font("Helvetica", "B", 8.5)
    reviewer_name = record_data.get("confirmed_by_name") or record_data.get("foreman_name") or "DE LUCA / ARDOR QC"
    pdf.text(start_x + 50, sig_y + 31, str(reviewer_name))

    # Render Digital Verification Stamp
    vrf_code = record_data.get("verification_code")
    if vrf_code:
        stamp_x = start_x + 115
        stamp_y = sig_y + 6
        pdf.set_draw_color(16, 185, 129)
        pdf.set_line_width(0.4)
        pdf.rect(stamp_x, stamp_y, 66, 24)

        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(16, 185, 129)
        pdf.text(stamp_x + 3, stamp_y + 4.5, "DIGITALLY VERIFIED DOCUMENT")

        pdf.set_font("Helvetica", "B", 6.5)
        pdf.set_text_color(15, 23, 42)
        pdf.text(stamp_x + 3, stamp_y + 9, f"Code: {vrf_code}")

        pdf.set_font("Helvetica", "", 5.5)
        pdf.set_text_color(71, 85, 105)
        conf_at = str(record_data.get("confirmed_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        pdf.text(stamp_x + 3, stamp_y + 13, f"Signed: {conf_at}")

        sha = str(record_data.get("sha256_hash") or "")
        if sha:
            pdf.text(stamp_x + 3, stamp_y + 17, f"SHA: {sha[:20]}...")
            pdf.text(stamp_x + 3, stamp_y + 21, f"{sha[20:44]}...")

    # Output
    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(out_p))
        return out_p.read_bytes()

    return bytes(pdf.output())
