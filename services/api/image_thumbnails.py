import io
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


THUMBNAIL_MAX_EDGE = 300


class ThumbnailProcessingError(Exception):
    pass


def create_webp_thumbnail(file_path: Path) -> bytes:
    try:
        with Image.open(file_path) as source:
            image = ImageOps.exif_transpose(source)
            resampling = getattr(Image, "Resampling", Image)
            image.thumbnail(
                (THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE),
                resampling.LANCZOS,
            )
            if image.mode not in ("RGB", "RGBA"):
                has_alpha = "A" in image.getbands() or "transparency" in image.info
                image = image.convert("RGBA" if has_alpha else "RGB")

            output = io.BytesIO()
            image.save(output, format="WEBP", quality=78, method=4)
            return output.getvalue()
    except (Image.DecompressionBombError, OSError, UnidentifiedImageError) as exc:
        raise ThumbnailProcessingError("Unable to create a thumbnail from this photo.") from exc
