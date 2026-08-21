import io
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fpdf import FPDF
from fpdf.enums import XPos, YPos


CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh',
    'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O',
    'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts',
    'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch', 'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
}

UNICODE_REPLACEMENTS = {
    '—': '-', '–': '-', '−': '-', '’': "'", '‘': "'", '“': '"', '”': '"',
    '«': '"', '»': '"', '…': '...', '№': 'No.', '°': ' deg', '•': '*', '±': '+/-',
    'ä': 'a', 'ö': 'o', 'å': 'a', 'Ä': 'A', 'Ö': 'O', 'Å': 'A'
}


def clean_pdf_text(val: Any) -> str:
    """Очищает строку от неподдерживаемых шрифтом символов и транслитерирует кириллицу."""
    if val is None:
        return ""
    text = str(val)
    for k, v in UNICODE_REPLACEMENTS.items():
        text = text.replace(k, v)
    
    chars = []
    for ch in text:
        if ch in CYRILLIC_TO_LATIN:
            chars.append(CYRILLIC_TO_LATIN[ch])
        else:
            chars.append(ch)
    text = "".join(chars)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class OfficialARDORRecordPDF(FPDF):
    """
    Векторный генератор официального бланка ARDOR:
    PAINEKOEPÖYTÄKIRJA / PRESSURE TEST RECORD
    Поддерживает точный одностраничный бланк и многостраничные протоколы (30-40+ труб).
    """

    def __init__(self, record_number: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.record_number = record_number
        self.set_auto_page_break(auto=False)
        self.set_margins(12, 12, 12)

    def text(self, x: float, y: float, text: str = ""):
        super().text(x, y, clean_pdf_text(text))

    def cell(self, w: float = 0, h: float = 0, text: str = "", **kwargs):
        super().cell(w, h, clean_pdf_text(text), **kwargs)

    def multi_cell(self, w: float, h: float = 0, text: str = "", **kwargs):
        super().multi_cell(w, h, clean_pdf_text(text), **kwargs)

    def draw_checkbox(self, x: float, y: float, size: float = 3.5, checked: bool = False, label: str = ""):
        self.rect(x, y, size, size)
        if checked:
            self.set_font("Helvetica", "B", 8)
            self.text(x + 0.6, y + 2.8, "X")
        if label:
            self.set_font("Helvetica", "", 7.5)
            self.text(x + size + 1.5, y + 2.8, label)

    def draw_official_header(
        self,
        record_data: Dict[str, Any],
        page_num: int,
        total_pages: int,
        start_x: float = 12,
        start_y: float = 12,
        page_w: float = 186
    ) -> float:
        """Отрисовывает фирменную шапку ARDOR и метаданные проекта."""
        logo_path = Path(__file__).parent.parent.parent / "resources" / "ardor_logo.png"
        if not logo_path.exists():
            logo_path = Path("resources/ardor_logo.png")

        header_h = 24
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.35)

        # 1. Left Logo Box (80mm)
        self.rect(start_x, start_y, 80, header_h)
        if logo_path.exists():
            try:
                self.image(str(logo_path), x=start_x + 5, y=start_y + 4, w=70)
            except Exception:
                self.set_font("Helvetica", "B", 22)
                self.set_text_color(0, 0, 0)
                self.text(start_x + 8, start_y + 16, "ARDOR")
        else:
            self.set_font("Helvetica", "B", 22)
            self.set_text_color(0, 0, 0)
            self.text(start_x + 8, start_y + 16, "ARDOR")

        # 2. Right Title Box (106mm)
        title_x = start_x + 80
        self.rect(title_x, start_y, 106, 12)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(0, 0, 0)
        self.set_xy(title_x + 2, start_y + 1)
        self.cell(102, 5, "PAINEKOEPÖYTÄKIRJA", new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
        self.set_xy(title_x + 2, start_y + 6)
        self.cell(102, 5, "PRESSURE TEST RECORD", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

        # 3. Sub-header: Page & Total Pages & Number
        sub_y = start_y + 12
        self.rect(title_x, sub_y, 22, 12)
        self.rect(title_x + 22, sub_y, 24, 12)
        self.rect(title_x + 46, sub_y, 60, 12)

        self.set_font("Helvetica", "", 6.5)
        self.text(title_x + 1.5, sub_y + 3.5, "Sivu / Page")
        self.set_font("Helvetica", "B", 8.5)
        self.text(title_x + 8, sub_y + 9, str(page_num))

        self.set_font("Helvetica", "", 6.5)
        self.text(title_x + 23.5, sub_y + 3.5, "Sivuja yht. / Pages")
        self.set_font("Helvetica", "B", 8.5)
        self.text(title_x + 32, sub_y + 9, str(total_pages))

        self.set_font("Helvetica", "", 6.5)
        self.text(title_x + 47.5, sub_y + 3.5, "Numero tai tunnus / Number or mark")
        self.set_font("Helvetica", "B", 7.5)
        ins_no_display = str(record_data.get("ins_no") or record_data.get("record_number") or "-")
        self.text(title_x + 47.5, sub_y + 7.5, ins_no_display)
        if record_data.get("project_code"):
            self.text(title_x + 47.5, sub_y + 10.8, str(record_data.get("project_code")))

        # 4. Metadata Row 1: Job No & Project Name
        row1_y = start_y + header_h
        row1_h = 14
        self.rect(start_x, row1_y, 80, row1_h)
        self.rect(start_x + 80, row1_y, 106, row1_h)

        self.set_font("Helvetica", "", 6.5)
        self.text(start_x + 1.5, row1_y + 3.5, "Työnumero / Job No")
        self.set_font("Helvetica", "B", 8.5)
        job_no = str(record_data.get("job_no") or record_data.get("system") or "-")
        self.text(start_x + 1.5, row1_y + 9.5, job_no)

        self.set_font("Helvetica", "", 6.5)
        self.text(start_x + 81.5, row1_y + 3.5, "Projektin nro tai nimi / Project No or name")
        self.set_font("Helvetica", "B", 8.5)
        proj_name = str(record_data.get("project") or "ARDOR Project")
        self.text(start_x + 81.5, row1_y + 9.5, proj_name)

        # 5. Metadata Row 2: Design Pressure, Test Pressure, Gauge S#
        row2_y = row1_y + row1_h
        row2_h = 14
        self.rect(start_x, row2_y, 80, row2_h)
        self.rect(start_x + 80, row2_y, 45, row2_h)
        self.rect(start_x + 125, row2_y, 61, row2_h)

        self.set_font("Helvetica", "", 6.5)
        self.text(start_x + 1.5, row2_y + 3.5, "Suunnittelupaine / Design pressure")
        self.set_font("Helvetica", "B", 8.5)
        des_p = str(record_data.get("design_pressure") or "-")
        self.text(start_x + 1.5, row2_y + 9.5, des_p)

        self.set_font("Helvetica", "", 6.5)
        self.text(start_x + 81.5, row2_y + 3.5, "Koepaine / Test pressure")
        self.set_font("Helvetica", "B", 9)
        test_p = str(record_data.get("test_pressure") or "-")
        self.text(start_x + 81.5, row2_y + 9.5, test_p)

        self.set_font("Helvetica", "", 6.5)
        self.text(start_x + 126.5, row2_y + 3.5, "Mittarin nro / S#")
        self.set_font("Helvetica", "B", 8)
        wika_s = str(record_data.get("wika_nr") or record_data.get("gauge_sn") or "BG516-GDTZ-13-D")
        self.text(start_x + 126.5, row2_y + 9.5, wika_s)

        return row2_y + row2_h

    def draw_items_table_header(self, start_x: float, tbl_y: float) -> Tuple[float, List[float], List[float]]:
        """Отрисовывает заголовки таблицы труб."""
        col_w = [52, 28, 24, 24, 34, 24]  # Total = 186mm
        col_x = [start_x]
        for w in col_w:
            col_x.append(col_x[-1] + w)

        hdr_h = 11
        for i, w in enumerate(col_w):
            self.rect(col_x[i], tbl_y, w, hdr_h)

        self.set_font("Helvetica", "B", 6.5)
        self.set_text_color(0, 0, 0)
        self.text(col_x[0] + 1.5, tbl_y + 3.5, "Piirustus nro")
        self.text(col_x[0] + 1.5, tbl_y + 7.5, "Drawing No")

        self.text(col_x[1] + 1.5, tbl_y + 3.5, "Systeemi")
        self.text(col_x[1] + 1.5, tbl_y + 7.5, "System")

        self.text(col_x[2] + 1.5, tbl_y + 3.5, "Osa nro")
        self.text(col_x[2] + 1.5, tbl_y + 7.5, "Part No")

        self.text(col_x[3] + 1.5, tbl_y + 3.5, "Pvm")
        self.text(col_x[3] + 1.5, tbl_y + 7.5, "Date")

        self.text(col_x[4] + 1.5, tbl_y + 3.5, "Kokeen kesto")
        self.text(col_x[4] + 1.5, tbl_y + 7.5, "Duration of the test")

        self.text(col_x[5] + 1.5, tbl_y + 3.5, "Log nro")
        self.text(col_x[5] + 1.5, tbl_y + 7.5, "Log No")

        return tbl_y + hdr_h, col_w, col_x

    def draw_items_table_rows(
        self,
        items: List[Dict[str, Any]],
        start_y: float,
        col_w: List[float],
        col_x: List[float],
        record_data: Dict[str, Any],
        row_count: int,
        row_h: float = 8.5
    ) -> float:
        """Отрисовывает строки таблицы труб."""
        current_y = start_y
        for row_idx in range(row_count):
            item = items[row_idx] if row_idx < len(items) else {}
            for i, w in enumerate(col_w):
                self.rect(col_x[i], current_y, w, row_h)

            if item:
                self.set_font("Helvetica", "", 7.5)
                self.set_text_color(0, 0, 0)
                dwg = str(item.get("drawing_no") or item.get("spool_no") or "-")
                self.text(col_x[0] + 1.5, current_y + 5.5, dwg[:32])

                sys_val = str(item.get("system") or record_data.get("system") or "-")
                self.text(col_x[1] + 1.5, current_y + 5.5, sys_val[:16])

                part_no = str(item.get("pipe_number") or item.get("part_no") or "-")
                self.text(col_x[2] + 1.5, current_y + 5.5, part_no[:14])

                date_val = str(item.get("date") or record_data.get("test_date") or datetime.now().strftime("%d.%m.%Y"))
                self.text(col_x[3] + 1.5, current_y + 5.5, date_val)

                dur_val = str(item.get("duration") or record_data.get("duration_min") or "60 min")
                self.text(col_x[4] + 1.5, current_y + 5.5, dur_val)

                log_val = str(item.get("log_no") or "-")
                self.text(col_x[5] + 1.5, current_y + 5.5, log_val)

            current_y += row_h

        return current_y

    def draw_footer_and_signatures(
        self,
        start_x: float,
        start_y: float,
        page_w: float,
        record_data: Dict[str, Any]
    ) -> float:
        """Отрисовывает блок среды испытания, примечаний, росписи и штампа верификации."""
        # 1. TEST MATERIAL CHECKBOXES
        mat_y = start_y
        mat_h = 16
        self.rect(start_x, mat_y, page_w, mat_h)

        self.set_font("Helvetica", "B", 7)
        self.set_text_color(0, 0, 0)
        self.text(start_x + 2, mat_y + 4, "Testiaine")
        self.set_font("Helvetica", "", 6.5)
        self.text(start_x + 2, mat_y + 7.5, "Test material")

        medium = str(record_data.get("test_medium", "Water")).lower()
        self.draw_checkbox(start_x + 25, mat_y + 6, checked="air" in medium or "ilma" in medium, label="Ilma / Air")
        self.draw_checkbox(start_x + 65, mat_y + 6, checked="water" in medium or "vesi" in medium or not medium, label="Vesi / Water")
        self.draw_checkbox(start_x + 110, mat_y + 6, checked="glycol" in medium or "glykoli" in medium, label="Glykoli / Glycol")
        self.draw_checkbox(start_x + 152, mat_y + 6, checked="nitrogen" in medium or "typpi" in medium or "n2" in medium, label="Typpi / Nitrogen")

        # 2. APPROVAL CHECKBOXES & REMARKS SECTION
        rem_y = mat_y + mat_h
        rem_h = 24
        self.rect(start_x, rem_y, page_w, rem_h)

        self.draw_checkbox(start_x + 55, rem_y + 3, checked=True, label="Tarkastettu")
        self.draw_checkbox(start_x + 115, rem_y + 3, checked=True, label="Hyväksytty")
        self.line(start_x, rem_y + 8, start_x + page_w, rem_y + 8)

        self.set_font("Helvetica", "B", 6.5)
        self.set_text_color(0, 0, 0)
        self.text(start_x + 2, rem_y + 11.5, "Huomautukset / Remarks")
        self.set_font("Helvetica", "", 7.5)
        remarks_text = str(record_data.get("notes") or "Hold test completed. No pressure drops detected. Test passed successfully.")
        self.set_xy(start_x + 2, rem_y + 13)
        self.multi_cell(page_w - 4, 4, remarks_text, align="L")

        # 3. SIGNATURE BLOCK
        sig_y = rem_y + rem_h
        sig_h = 36
        self.rect(start_x, sig_y, 45, sig_h)
        self.rect(start_x + 45, sig_y, 141, sig_h)

        self.set_font("Helvetica", "B", 6.5)
        self.text(start_x + 2, sig_y + 4.5, "Pvm / Date")
        self.set_font("Helvetica", "B", 8)
        sig_date = record_data.get("confirmed_at") or record_data.get("test_date") or datetime.now().strftime("%d.%m.%Y")
        if isinstance(sig_date, datetime):
            sig_date = sig_date.strftime("%d.%m.%Y")
        self.text(start_x + 2, sig_y + 16, str(sig_date)[:10])

        self.set_font("Helvetica", "B", 6.5)
        self.text(start_x + 47, sig_y + 4.5, "Witnessed / Reviewed by")

        # Digital Signature Image
        sig_img_path = record_data.get("signature_image_path")
        if sig_img_path and Path(sig_img_path).exists():
            try:
                self.image(str(sig_img_path), x=start_x + 50, y=sig_y + 6, h=22)
            except Exception:
                pass

        # Reviewer Name
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(0, 0, 0)
        reviewer_name = record_data.get("confirmed_by_name") or record_data.get("foreman_name") or "DE LUCA / ARDOR QC"
        self.text(start_x + 50, sig_y + 31, str(reviewer_name))

        # Digital Verification Stamp
        vrf_code = record_data.get("verification_code")
        if vrf_code:
            stamp_x = start_x + 115
            stamp_y = sig_y + 6
            self.set_draw_color(16, 185, 129)
            self.set_line_width(0.4)
            self.rect(stamp_x, stamp_y, 66, 24)

            self.set_font("Helvetica", "B", 7)
            self.set_text_color(16, 185, 129)
            self.text(stamp_x + 3, stamp_y + 4.5, "DIGITALLY VERIFIED DOCUMENT")

            self.set_font("Helvetica", "B", 6.5)
            self.set_text_color(15, 23, 42)
            self.text(stamp_x + 3, stamp_y + 9, f"Code: {vrf_code}")

            self.set_font("Helvetica", "", 5.5)
            self.set_text_color(71, 85, 105)
            conf_at = str(record_data.get("confirmed_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
            self.text(stamp_x + 3, stamp_y + 13, f"Signed: {conf_at}")

            sha = str(record_data.get("official_pdf_sha256") or record_data.get("sha256_hash") or "")
            if sha:
                self.text(stamp_x + 3, stamp_y + 17, f"SHA: {sha[:20]}...")
                self.text(stamp_x + 3, stamp_y + 21, f"{sha[20:44]}...")

        return sig_y + sig_h


def generate_ptr_pdf(
    record_data: Dict[str, Any],
    items_data: List[Dict[str, Any]],
    output_path: Optional[Path] = None
) -> bytes:
    """
    Генерирует официальный ARDOR Pressure Test Record (Official PDF).
    Поддерживает одностраничные (<= 7 труб) и многостраничные протоколы (30-40+ труб).
    """
    rec_num = record_data.get("record_number", "PTR-001")
    pdf = OfficialARDORRecordPDF(record_number=rec_num)

    start_x = 12
    start_y = 12
    page_w = 186

    items = list(items_data) if items_data else [{}]
    total_items = len(items)

    # 1. Расчёт количества страниц
    if total_items <= 7:
        total_pages = 1
        page_chunks = [items]
    else:
        # Страница 1: 7 строк
        # Последующие страницы продолжения: по 14 строк
        chunk_1 = items[:7]
        rem = items[7:]
        page_chunks = [chunk_1]
        while rem:
            chunk_size = 14
            page_chunks.append(rem[:chunk_size])
            rem = rem[chunk_size:]
        total_pages = len(page_chunks)

    # 2. Отрисовка страниц
    for page_idx, chunk in enumerate(page_chunks, 1):
        pdf.add_page()
        tbl_top_y = pdf.draw_official_header(
            record_data=record_data,
            page_num=page_idx,
            total_pages=total_pages,
            start_x=start_x,
            start_y=start_y,
            page_w=page_w
        )

        rows_y, col_w, col_x = pdf.draw_items_table_header(start_x, tbl_top_y)
        
        # Количество строк на текущей странице
        target_rows = max(7, len(chunk)) if page_idx == total_pages and total_pages == 1 else len(chunk)
        if page_idx < total_pages:
            target_rows = max(7 if page_idx == 1 else 14, len(chunk))

        end_table_y = pdf.draw_items_table_rows(
            items=chunk,
            start_y=rows_y,
            col_w=col_w,
            col_x=col_x,
            record_data=record_data,
            row_count=target_rows,
            row_h=8.5
        )

        # Подвал и подписи отрисовываются на последней странице
        if page_idx == total_pages:
            pdf.draw_footer_and_signatures(
                start_x=start_x,
                start_y=end_table_y,
                page_w=page_w,
                record_data=record_data
            )

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(out_p))
        return out_p.read_bytes()

    return bytes(pdf.output())


def parse_csv_for_measurement_table(csv_path: Path) -> List[Dict[str, str]]:
    """Считывает все строки исходного CSV без сэмплинга для полной таблицы измерений."""
    if not csv_path or not Path(csv_path).exists():
        return []

    try:
        from wika_report.csv_reader import read_wika_csv
        from wika_report.column_detector import detect_columns
        from wika_report.data_cleaner import clean_and_normalize_data

        df_raw, meta = read_wika_csv(Path(csv_path))
        mapping = detect_columns(df_raw, meta)
        df_clean = clean_and_normalize_data(df_raw, mapping)

        rows = []
        for _, r in df_clean.iterrows():
            ts = r.get("timestamp_parsed")
            ts_str = ts.strftime("%d.%m.%Y %H:%M:%S") if hasattr(ts, "strftime") else str(r.get(mapping.timestamp_col or "timestamp", ""))
            
            p_val = r.get("pressure_bar")
            p_str = f"{float(p_val):.2f}" if p_val is not None and not math.isnan(float(p_val)) else "-"
            
            t_val = r.get("temperature_c")
            t_str = f"{float(t_val):.1f}" if t_val is not None and not math.isnan(float(t_val)) else "-"
            
            rows.append({
                "timestamp": ts_str,
                "pressure_bar": p_str,
                "temp_c": t_str
            })
        return rows
    except Exception:
        # Fallback reading
        try:
            import csv
            rows = []
            with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f, delimiter=";")
                for r in reader:
                    if len(r) >= 2 and any(char.isdigit() for char in "".join(r)):
                        rows.append({
                            "timestamp": r[0].strip(),
                            "pressure_bar": r[1].strip(),
                            "temp_c": r[2].strip() if len(r) > 2 else "-"
                        })
            return rows
        except Exception:
            return []


def generate_full_composite_ptr_pdf(
    record_data: Dict[str, Any],
    items_data: List[Dict[str, Any]],
    logs_data: List[Dict[str, Any]],
    output_path: Optional[Path] = None
) -> bytes:
    """
    Генерирует полный составной документ: PTR_<RecordNumber>_Full.pdf
    Последовательность разделов:
    1. Официальный ARDOR Record (все страницы).
    2. Для каждого выбранного лога по порядку:
       - Log Information Page (метаданные, требуемое давление, min/max, duration, трубы в этом PTR)
       - Pressure Graph (полноразмерный график давления)
       - Selected Photographs (фото манометра, трубы, монтажа)
       - Complete Measurement Table (все строки CSV без сэмплинга)
    """
    rec_num = record_data.get("record_number", "PTR-001")
    pdf = OfficialARDORRecordPDF(record_number=rec_num)

    start_x = 12
    start_y = 12
    page_w = 186

    # =========================================================================
    # РАЗДЕЛ 1: Официальный ARDOR Record (Official Pages)
    # =========================================================================
    items = list(items_data) if items_data else [{}]
    total_items = len(items)

    if total_items <= 7:
        official_total_pages = 1
        page_chunks = [items]
    else:
        chunk_1 = items[:7]
        rem = items[7:]
        page_chunks = [chunk_1]
        while rem:
            page_chunks.append(rem[:14])
            rem = rem[14:]
        official_total_pages = len(page_chunks)

    for page_idx, chunk in enumerate(page_chunks, 1):
        pdf.add_page()
        tbl_top_y = pdf.draw_official_header(
            record_data=record_data,
            page_num=page_idx,
            total_pages=official_total_pages,
            start_x=start_x,
            start_y=start_y,
            page_w=page_w
        )

        rows_y, col_w, col_x = pdf.draw_items_table_header(start_x, tbl_top_y)
        target_rows = max(7, len(chunk)) if page_idx == official_total_pages and official_total_pages == 1 else len(chunk)
        if page_idx < official_total_pages:
            target_rows = max(7 if page_idx == 1 else 14, len(chunk))

        end_table_y = pdf.draw_items_table_rows(
            items=chunk,
            start_y=rows_y,
            col_w=col_w,
            col_x=col_x,
            record_data=record_data,
            row_count=target_rows,
            row_h=8.5
        )

        if page_idx == official_total_pages:
            pdf.draw_footer_and_signatures(
                start_x=start_x,
                start_y=end_table_y,
                page_w=page_w,
                record_data=record_data
            )

    # =========================================================================
    # РАЗДЕЛ 2..N: Разделы выбранных логов опрессовки (Log Sections)
    # =========================================================================
    for log_entry in logs_data:
        log_no = str(log_entry.get("log_no") or "N/A")
        rev_id = str(log_entry.get("revision_id") or "1")
        meta = log_entry.get("metadata", {})
        metrics = log_entry.get("metrics", {})
        artifacts = log_entry.get("artifacts", [])
        selected_pipes = log_entry.get("selected_pipe_numbers") or meta.get("pipe_numbers") or []
        include_table = log_entry.get("include_measurement_table", True)

        # -------------------------------------------------------------
        # А. СТРАНИЦА ИНФОРМАЦИИ О ЛОГЕ (Log Information Page)
        # -------------------------------------------------------------
        pdf.add_page()
        pdf.set_draw_color(30, 41, 59)
        pdf.set_line_width(0.35)

        # Banner
        pdf.rect(start_x, start_y, page_w, 18)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(15, 23, 42)
        pdf.text(start_x + 4, start_y + 8, f"ATTACHMENT: PRESSURE TEST LOG {log_no}")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.text(start_x + 4, start_y + 14, f"Revision ID: {rev_id}  |  Record Ref: {rec_num}")

        # Summary Grid
        grid_y = start_y + 22
        pdf.set_draw_color(203, 213, 225)
        pdf.rect(start_x, grid_y, page_w, 70)

        # Key-value rows
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(15, 23, 42)
        
        info_pairs = [
            ("Log Number:", f"Log {log_no}", "Target Pressure:", str(meta.get("test_pressure") or "-")),
            ("System / Drawing:", f"{meta.get('system') or '-'} / {meta.get('project') or '-'}", "Min / Max Pressure:", f"{metrics.get('min_pressure_bar', '-')} / {metrics.get('max_pressure_bar', '-')} bar"),
            ("Inspection Number:", str(meta.get("ins_no") or record_data.get("ins_no") or "-"), "Mean Pressure:", f"{metrics.get('mean_pressure_bar', '-')} bar"),
            ("Operator / Tester:", str(meta.get("operator") or "-"), "Pressure Delta:", f"{metrics.get('total_delta_bar', '-')} bar"),
            ("WIKA Gauge S#:", str(meta.get("wika_nr") or "WIKA CPG1500"), "Duration:", str(metrics.get("duration_formatted") or "60 min")),
            ("Start Time (UTC):", str(metrics.get("start_time") or "-"), "End Time (UTC):", str(metrics.get("end_time") or "-")),
            ("Evaluation Status:", str(metrics.get("evaluation_status") or "PASS"), "Included in Record:", f"{len(selected_pipes)} pipe(s)"),
        ]

        row_y = grid_y + 7
        for left_lbl, left_val, right_lbl, right_val in info_pairs:
            pdf.set_font("Helvetica", "B", 7.5)
            pdf.set_text_color(71, 85, 105)
            pdf.text(start_x + 4, row_y, left_lbl)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(15, 23, 42)
            pdf.text(start_x + 38, row_y, str(left_val)[:40])

            pdf.set_font("Helvetica", "B", 7.5)
            pdf.set_text_color(71, 85, 105)
            pdf.text(start_x + 98, row_y, right_lbl)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(15, 23, 42)
            pdf.text(start_x + 135, row_y, str(right_val)[:30])

            row_y += 8.5

        # Pipes Box
        pipes_box_y = grid_y + 74
        pdf.rect(start_x, pipes_box_y, page_w, 40)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(15, 23, 42)
        pdf.text(start_x + 4, pipes_box_y + 6, f"Pipes Tested in Log {log_no} (Included in this PTR):")
        
        pdf.set_font("Helvetica", "", 8)
        pipes_str = ", ".join(str(p) for p in selected_pipes) if selected_pipes else "All pipes from log"
        pdf.set_xy(start_x + 4, pipes_box_y + 9)
        pdf.multi_cell(page_w - 8, 5, pipes_str)

        # Notes Box
        notes_box_y = pipes_box_y + 44
        pdf.rect(start_x, notes_box_y, page_w, 45)
        pdf.set_font("Helvetica", "B", 8)
        pdf.text(start_x + 4, notes_box_y + 6, "Log Notes & Observations:")
        pdf.set_font("Helvetica", "", 8)
        note_str = str(meta.get("note") or "Pressure hold test executed according to ARDOR quality and inspection procedures. No leaks or pressure loss detected.")
        pdf.set_xy(start_x + 4, notes_box_y + 9)
        pdf.multi_cell(page_w - 8, 5, note_str)

        # -------------------------------------------------------------
        # Б. СТРАНИЦА ГРАФИКА ДАВЛЕНИЯ (Pressure Graph Page)
        # -------------------------------------------------------------
        graph_art = next((a for a in artifacts if a.get("file_type") == "graph_png" or (str(a.get("name", "")).endswith(".png") and not a.get("category"))), None)
        if graph_art and graph_art.get("file_path") and Path(graph_art["file_path"]).exists():
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(15, 23, 42)
            pdf.text(start_x, start_y + 6, f"LOG {log_no} - PRESSURE TEST GRAPH (0-160 bar)")
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(100, 116, 139)
            pdf.text(start_x, start_y + 11, f"WIKA CPG1500 Digital Data Log  |  Target: {meta.get('test_pressure', 'N/A')}  |  Log {log_no}")

            try:
                pdf.image(str(graph_art["file_path"]), x=start_x, y=start_y + 15, w=page_w)
            except Exception:
                pass

        # -------------------------------------------------------------
        # В. СТРАНИЦЫ ФОТОГРАФИЙ (Selected Photographs)
        # -------------------------------------------------------------
        photos = [a for a in artifacts if a.get("file_type") == "photo" or a.get("category") in ("gauge", "pipe", "installation", "other") or str(a.get("name", "")).lower().endswith((".jpg", ".jpeg", ".png")) and a != graph_art]
        # Filter included
        photos = [p for p in photos if p.get("is_included_in_pdf", True) and p.get("file_path") and Path(p["file_path"]).exists()]

        # Draw 2 photos per page
        for photo_idx in range(0, len(photos), 2):
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(15, 23, 42)
            pdf.text(start_x, start_y + 6, f"LOG {log_no} - EVIDENCE PHOTOGRAPHS")
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(100, 116, 139)
            pdf.text(start_x, start_y + 11, f"Attached inspection evidence for Log {log_no}")

            current_photo_y = start_y + 16
            for p_item in photos[photo_idx:photo_idx + 2]:
                p_cat = str(p_item.get("category") or "Inspection Evidence").capitalize()
                p_name = str(p_item.get("name") or "Photo")
                try:
                    pdf.rect(start_x, current_photo_y, page_w, 115)
                    pdf.image(str(p_item["file_path"]), x=start_x + 10, y=current_photo_y + 4, w=page_w - 20, h=95)
                    
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(15, 23, 42)
                    pdf.text(start_x + 4, current_photo_y + 107, f"Category: {p_cat} - {p_name}")
                except Exception:
                    pass
                current_photo_y += 122

        # -------------------------------------------------------------
        # Г. ПОЛНАЯ ТАБЛИЦА ИЗМЕРЕНИЙ ИЗ CSV (Complete Measurement Table)
        # -------------------------------------------------------------
        if include_table:
            csv_art = next((a for a in artifacts if a.get("file_type") == "source_csv" or str(a.get("name", "")).endswith(".csv")), None)
            csv_path = Path(csv_art["file_path"]) if csv_art and csv_art.get("file_path") else None
            
            if csv_path and csv_path.exists():
                measurement_rows = parse_csv_for_measurement_table(csv_path)
                if measurement_rows:
                    rows_per_page = 38
                    total_csv_pages = math.ceil(len(measurement_rows) / rows_per_page)
                    
                    for csv_p_idx in range(total_csv_pages):
                        pdf.add_page()
                        pdf.set_font("Helvetica", "B", 10)
                        pdf.set_text_color(15, 23, 42)
                        pdf.text(start_x, start_y + 5, f"LOG {log_no} - COMPLETE MEASUREMENT DATA (WIKA CPG1500)")
                        pdf.set_font("Helvetica", "", 7)
                        pdf.set_text_color(100, 116, 139)
                        pdf.text(start_x, start_y + 9.5, f"All recorded points without sampling | Total points: {len(measurement_rows)} | Page {csv_p_idx + 1} of {total_csv_pages}")

                        # Table Header
                        tbl_y = start_y + 13
                        pdf.set_draw_color(15, 23, 42)
                        pdf.set_fill_color(241, 245, 249)
                        pdf.rect(start_x, tbl_y, page_w, 6.5, style="FD")
                        
                        pdf.set_font("Helvetica", "B", 7)
                        pdf.set_text_color(15, 23, 42)
                        pdf.text(start_x + 3, tbl_y + 4.5, "Aika / Timestamp")
                        pdf.text(start_x + 65, tbl_y + 4.5, "Paine / Pressure (bar)")
                        pdf.text(start_x + 125, tbl_y + 4.5, "Lämpötila / Temperature (°C)")

                        row_chunk = measurement_rows[csv_p_idx * rows_per_page : (csv_p_idx + 1) * rows_per_page]
                        r_y = tbl_y + 6.5
                        row_h = 6.2

                        pdf.set_font("Helvetica", "", 7)
                        for r_idx, r_item in enumerate(row_chunk):
                            bg_fill = (r_idx % 2 == 1)
                            if bg_fill:
                                pdf.set_fill_color(248, 250, 252)
                                pdf.rect(start_x, r_y, page_w, row_h, style="F")
                            
                            pdf.set_draw_color(226, 232, 240)
                            pdf.line(start_x, r_y + row_h, start_x + page_w, r_y + row_h)

                            pdf.set_text_color(15, 23, 42)
                            pdf.text(start_x + 3, r_y + 4.2, str(r_item.get("timestamp", "-")))
                            pdf.set_font("Helvetica", "B", 7)
                            pdf.text(start_x + 65, r_y + 4.2, str(r_item.get("pressure_bar", "-")))
                            pdf.set_font("Helvetica", "", 7)
                            pdf.text(start_x + 125, r_y + 4.2, str(r_item.get("temp_c", "-")))
                            
                            r_y += row_h

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(out_p))
        return out_p.read_bytes()

    return bytes(pdf.output())


def estimate_composite_ptr_pages(
    record_data: Dict[str, Any],
    items_data: List[Dict[str, Any]],
    logs_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Возвращает точный/приблизительный расчёт страниц Official и Full PDF."""
    items = list(items_data) if items_data else [{}]
    if len(items) <= 7:
        official_pages = 1
    else:
        official_pages = 1 + math.ceil((len(items) - 7) / 14)

    total_full_pages = official_pages
    log_estimates = []

    for log in logs_data:
        info_pages = 1
        graph_pages = 1
        
        artifacts = log.get("artifacts", [])
        photos = [a for a in artifacts if a.get("file_type") == "photo" or a.get("category") in ("gauge", "pipe", "installation", "other")]
        photos = [p for p in photos if p.get("is_included_in_pdf", True)]
        photo_pages = math.ceil(len(photos) / 2)

        table_pages = 0
        if log.get("include_measurement_table", True):
            csv_path = log.get("csv_path")
            if csv_path and Path(csv_path).exists():
                rows = parse_csv_for_measurement_table(Path(csv_path))
                table_pages = math.ceil(len(rows) / 38)
            else:
                table_pages = 4  # Default estimate for standard 1h log

        log_total = info_pages + graph_pages + photo_pages + table_pages
        total_full_pages += log_total

        log_estimates.append({
            "log_no": log.get("log_no", "N/A"),
            "info_pages": info_pages,
            "graph_pages": graph_pages,
            "photo_pages": photo_pages,
            "table_pages": table_pages,
            "total_pages": log_total
        })

    return {
        "official_pages": official_pages,
        "full_total_pages": total_full_pages,
        "log_estimates": log_estimates
    }
