from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

res_dir = Path("resources")
res_dir.mkdir(parents=True, exist_ok=True)

# Generate high-res 256x256 gauge icon
size = (256, 256)
img = Image.new("RGBA", size, (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Outer circle gauge body
draw.ellipse([10, 10, 246, 246], fill="#1F4E79", outline="#002D54", width=6)
draw.ellipse([26, 26, 230, 230], fill="#FFFFFF", outline="#D9D9D9", width=4)

# Gauge tick marks
import math
center = (128, 128)
radius = 85
for angle_deg in range(135, 406, 30):
    rad = math.radians(angle_deg)
    x1 = center[0] + (radius - 12) * math.cos(rad)
    y1 = center[1] + (radius - 12) * math.sin(rad)
    x2 = center[0] + radius * math.cos(rad)
    y2 = center[1] + radius * math.sin(rad)
    draw.line([x1, y1, x2, y2], fill="#1F4E79", width=4)

# Pressure gauge needle pointing to ~75% (bar)
needle_angle = math.radians(310)
nx = center[0] + 70 * math.cos(needle_angle)
ny = center[1] + 70 * math.sin(needle_angle)
draw.line([center[0], center[1], nx, ny], fill="#D9534F", width=6)
draw.ellipse([116, 116, 140, 140], fill="#D9534F", outline="#900C3F", width=2)

# Blue accent band
draw.arc([36, 36, 220, 220], start=135, end=315, fill="#0055B8", width=8)

png_path = res_dir / "app_icon.png"
ico_path = res_dir / "app_icon.ico"

img.save(png_path, format="PNG")
img.save(ico_path, format="ICO", sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])

print("Icon created successfully at:", ico_path.resolve())
