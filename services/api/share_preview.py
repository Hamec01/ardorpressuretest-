"""Link preview card for public share links (Open Graph image for WhatsApp, Telegram, ...).

A 1200x630 JPEG: log number, pressure, pipe count and date over the pressure graph and a
pipe (or gauge) photo of the shared log's current revision. Cached per share and
revision, so a new revision gets a new card. Only files that belong to the published
revision are read.
"""
import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import matplotlib
from PIL import Image, ImageDraw, ImageFont, ImageOps

from services.api.config import settings
from services.api.models import Artifact, PressureTest, TestRevision
from services.api.storage import storage

WIDTH, HEIGHT = 1200, 630
CARD_VERSION = "v2"
# Dates on the card follow the site, not UTC (a test at 00:34 belongs to that day).
SITE_TIMEZONE = ZoneInfo("Europe/Helsinki")
BACKGROUND = (11, 18, 36)
PANEL = (20, 32, 61)
CYAN = (56, 189, 248)
TEXT = (232, 238, 248)
MUTED = (154, 171, 198)

_FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_FONT_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)


def preview_cache_path(share_id: str, revision_id: str) -> Path:
    safe_revision = "".join(ch for ch in revision_id if ch.isalnum() or ch in "-_")[:64]
    return Path(settings.storage_dir) / "_share_previews" / f"{share_id}-{safe_revision}-{CARD_VERSION}.jpg"


def _open_artifact(artifact: Optional[Artifact]) -> Optional[Image.Image]:
    if artifact is None:
        return None
    path = storage.get_file_path(artifact.storage_key)
    if not path or not path.exists():
        return None
    try:
        image = Image.open(path)
        image = ImageOps.exif_transpose(image)
        return image.convert("RGB")
    except Exception:
        return None


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def _paste_contain(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int], background) -> None:
    x0, y0, x1, y1 = box
    panel = Image.new("RGB", (x1 - x0, y1 - y0), background)
    fitted = ImageOps.contain(image, (panel.width - 24, panel.height - 24), Image.LANCZOS)
    panel.paste(fitted, ((panel.width - fitted.width) // 2, (panel.height - fitted.height) // 2))
    canvas.paste(panel, (x0, y0), _rounded_mask(panel.size, 18))


def _paste_cover(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    fitted = ImageOps.fit(image, (x1 - x0, y1 - y0), Image.LANCZOS, centering=(0.5, 0.5))
    canvas.paste(fitted, (x0, y0), _rounded_mask(fitted.size, 18))


def _summary(test: PressureTest, rev: TestRevision) -> str:
    metadata = rev.metadata_json or {}
    parts = []
    if metadata.get("test_pressure"):
        parts.append(str(metadata["test_pressure"]))
    pipes = metadata.get("pipe_numbers") or []
    if pipes:
        parts.append(f"{len(pipes)} pipe{'s' if len(pipes) != 1 else ''}")
    if rev.created_at:
        created = rev.created_at if rev.created_at.tzinfo else rev.created_at.replace(tzinfo=timezone.utc)
        parts.append(created.astimezone(SITE_TIMEZONE).strftime("%d.%m.%Y"))
    return " · ".join(parts)


def description(test: PressureTest, rev: Optional[TestRevision]) -> str:
    summary = _summary(test, rev) if rev else ""
    return " · ".join(part for part in ("Pressure test", summary, "graph, photos and files") if part)


def render_preview(test: PressureTest, rev: TestRevision) -> bytes:
    canvas = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, WIDTH, 6), fill=CYAN)

    draw.text((56, 38), "ARDOR", font=_font(True, 26), fill=MUTED, spacing=4)
    draw.text((56 + 118, 42), "Pressure Test", font=_font(False, 22), fill=MUTED)
    draw.text((56, 76), f"Log {test.log_no}", font=_font(True, 62), fill=CYAN)
    summary = _summary(test, rev)
    if summary:
        draw.text((58, 160), summary, font=_font(False, 30), fill=TEXT)

    artifacts = list(rev.artifacts)
    graph = _open_artifact(next((a for a in artifacts if a.file_type == "graph_png"), None))
    photos = [a for a in artifacts if a.file_type == "photo"]
    photo_artifact = next((a for a in photos if a.category == "pipe"), None) or next((a for a in photos if a.category == "gauge"), None) or (photos[0] if photos else None)
    photo = _open_artifact(photo_artifact)

    top, bottom = 222, 590
    if graph and photo:
        _paste_contain(canvas, graph, (56, top, 772, bottom), (255, 255, 255))
        _paste_cover(canvas, photo, (796, top, 1144, bottom))
    elif graph:
        _paste_contain(canvas, graph, (56, top, 1144, bottom), (255, 255, 255))
    elif photo:
        _paste_cover(canvas, photo, (56, top, 1144, bottom))
    else:
        draw.rounded_rectangle((56, top, 1144, bottom), radius=18, fill=PANEL)
        draw.text((90, top + 150), "Pressure test log", font=_font(True, 40), fill=MUTED)

    host = settings.public_origin.split("://", 1)[-1].rstrip("/")
    draw.text((WIDTH - 56, HEIGHT - 14), host, font=_font(False, 18), fill=MUTED, anchor="rd")

    buffer = io.BytesIO()
    canvas.save(buffer, "JPEG", quality=82, optimize=True, progressive=True)
    return buffer.getvalue()


def cached_preview(share_id: str, test: PressureTest, rev: TestRevision) -> bytes:
    path = preview_cache_path(share_id, rev.revision_id)
    if path.exists():
        return path.read_bytes()
    data = render_preview(test, rev)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".tmp-{os.getpid()}")
        tmp.write_bytes(data)
        tmp.replace(path)
    except OSError:
        pass  # caching is best-effort; the card is still served
    return data
