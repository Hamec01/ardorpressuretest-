import logging
from pathlib import Path
from typing import List
from fpdf import FPDF
from PIL import Image

logger = logging.getLogger("wika_report")

def build_pdf_report(
    graph_png_path: Path,
    photo_paths: List[Path],
    output_pdf_path: Path
) -> Path:
    """
    Generates a PDF containing the main pressure graph on the first page,
    followed by any attached photos resized to fit standard A4 pages.
    """
    logger.info(f"Generating PDF report: {output_pdf_path.name}")
    
    # A4 dimensions: 210 x 297 mm
    pdf = FPDF(orientation="portrait", unit="mm", format="A4")
    
    # Page 1: Main Graph (usually landscape aspect ratio)
    pdf.add_page()
    
    # Width of A4 printable area is ~190mm (with 10mm margins)
    # Graph is 14x7 inches (2:1 ratio). So width 190mm, height 95mm.
    # Center it vertically a bit
    pdf.image(str(graph_png_path), x=10, y=20, w=190, h=95)
    
    # Page 2+: Photo attachments
    for photo_path in photo_paths:
        if not photo_path.exists():
            logger.warning(f"Attached photo not found: {photo_path}")
            continue
            
        pdf.add_page()
        try:
            # Downscale image if it is too large to prevent PDF memory bloat
            # We resize it so the maximum dimension is 1920px
            temp_photo_path = photo_path
            with Image.open(photo_path) as img:
                # Rotate image based on EXIF tag if present to preserve orientation
                try:
                    from PIL import ImageOps
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass
                
                img_w, img_h = img.size
                max_dim = max(img_w, img_h)
                if max_dim > 1920:
                    scale = 1920.0 / max_dim
                    new_size = (int(img_w * scale), int(img_h * scale))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    img_w, img_h = img.size
                    # Save a temporary downscaled image
                    temp_dir = photo_path.parent / "temp"
                    temp_dir.mkdir(exist_ok=True)
                    temp_photo_path = temp_dir / photo_path.name
                    img.save(temp_photo_path, quality=85)
                
            # Scale to fit A4 (max width 190, max height 260 to fit page)
            ratio = min(190.0 / img_w, 260.0 / img_h)
            new_w = img_w * ratio
            new_h = img_h * ratio
            
            # Center on A4 page
            x_pos = 10 + (190 - new_w) / 2
            y_pos = 15 + (260 - new_h) / 2
            
            pdf.image(str(temp_photo_path), x=x_pos, y=y_pos, w=new_w, h=new_h)
            
            # Remove temp resized photo if created
            if temp_photo_path != photo_path and temp_photo_path.exists():
                try:
                    temp_photo_path.unlink()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to insert image {photo_path} in PDF: {e}")
            
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_pdf_path))
    return output_pdf_path
