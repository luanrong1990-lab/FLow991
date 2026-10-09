"""Fixed layouts: typography and mascot are composed locally, never generated in backgrounds."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from channel.rules import thumb_issues


def font_at(path, size):
    if not path or not Path(path).is_file():
        raise ValueError("Chọn file font Noto Sans JP Bold/Heavy (.ttf hoặc .otf) trong Tài sản kênh.")
    font = ImageFont.truetype(str(path), size)
    if "Noto Sans JP" not in font.getname()[0]:
        raise ValueError("Font phải là Noto Sans JP để giữ nhận diện kênh.")
    try:
        font.set_variation_by_axes([800])
    except (OSError, AttributeError):
        pass  # Static Bold/Heavy font.
    return font


def fit_font(path, text, max_size, width):
    for size in range(max_size, 19, -2):
        font = font_at(path, size)
        if font.getlength(text) <= width:
            return font
    raise ValueError("Chữ quá dài cho bố cục.")


def mascot_asset(folder, pose):
    path = Path(folder) / f"mascot_{pose}.png"
    if not path.is_file():
        raise ValueError(f"Thiếu mascot cố định: {path.name}")
    with Image.open(path) as source:
        image = source.convert("RGBA")
    if image.getextrema()[3][0] == 255:
        raise ValueError(f"{path.name} cần có nền trong suốt.")
    return image


def paste_mascot(canvas, image, box):
    fitted = ImageOps.contain(image, (box[2], box[3]), Image.Resampling.LANCZOS)
    canvas.paste(fitted, (box[0] + (box[2]-fitted.width)//2, box[1] + box[3]-fitted.height), fitted)


def thumbnails(folder, lines, count, profile, assets):
    issues = thumb_issues(lines, profile)
    if issues:
        raise ValueError("\n".join(issues))
    mascot = mascot_asset(assets.get("mascot_dir", ""), "surprised")
    output = Path(folder); output.mkdir(parents=True, exist_ok=True)
    palette, paths = profile["palette"], []
    for index, (background, foreground) in enumerate([(palette["navy"], palette["yellow"]), (palette["cream"], "#111111")], 1):
        canvas = Image.new("RGB", (1280, 720), background)
        draw = ImageDraw.Draw(canvas)
        draw.polygon([(1040, 0), (1280, 0), (1280, 720), (790, 720)], fill=palette["red"])
        paste_mascot(canvas, mascot, (0, 30, 512, 690))
        for row, text in enumerate(lines):
            font = fit_font(assets.get("font"), text, 86, 716)
            draw.text((530, 160 + row*145), text, font=font, fill=foreground, stroke_width=2,
                      stroke_fill=background)
        draw.ellipse((1030, 475, 1240, 685), fill="white")
        label = f"{count}選"
        draw.text((1135, 580), label, font=fit_font(assets.get("font"), label, 66, 180), fill=palette["red"], anchor="mm")
        path = output / f"thumb_v{index}.png"
        canvas.save(path); paths.append(str(path))
    return paths


def scene_frame(scene, output, profile, assets, bumper=False):
    palette = profile["palette"]
    if bumper:
        canvas = Image.new("RGB", (1920, 1080), palette["red"])
        draw = ImageDraw.Draw(canvas)
        draw.ellipse((780, 150, 1140, 510), fill="white")
        draw.text((960, 330), str(scene["number"]), fill=palette["red"], font=font_at(assets.get("font"), 180), anchor="mm")
        draw.text((960, 690), scene["telop"], fill="white", font=fit_font(assets.get("font"), scene["telop"], 100, 1640), anchor="mm")
    else:
        with Image.open(scene["image_path"]) as background:
            canvas = ImageOps.fit(background.convert("RGB"), (1920, 1080), method=Image.Resampling.LANCZOS)
        paste_mascot(canvas, mascot_asset(assets.get("mascot_dir", ""), scene["emotion"]), (0, 540, 480, 540))
        draw = ImageDraw.Draw(canvas)
        draw.text((960, round(1080*0.78)), scene["telop"], fill=palette["yellow"],
                  font=fit_font(assets.get("font"), scene["telop"], 86, 1400), anchor="mm", stroke_width=8, stroke_fill="black")
        if scene["type"] == "item":
            draw.ellipse((1660, 45, 1870, 255), fill=palette["red"])
            draw.text((1765, 150), str(scene["number"]), fill="white", font=font_at(assets.get("font"), 100), anchor="mm")
    canvas.save(output)
    return str(output)
