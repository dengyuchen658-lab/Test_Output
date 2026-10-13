#!/usr/bin/env python3
"""Compose a cultural-event PNG with exact, editable-in-JSON copy.

Requires Pillow. This is a dependable starting layout, not a substitute for
project-specific art direction and visual review.
"""

import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageColor, ImageDraw, ImageFont


FIELDS = ("organizer", "title", "tagline", "dates", "hours", "venue", "cta")


def copy_digest(copy: dict) -> str:
    canonical = json.dumps(copy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def choose_font(language: str, explicit: str | None) -> str:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ValueError(f"Font not found: {path}")
        return str(path)
    if language.startswith("zh"):
        candidates = (
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        )
    else:
        candidates = (
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        )
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    raise ValueError("No suitable font found. Pass --font /path/to/a/font.ttf")


def font_at(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, max(8, int(size)))


def width(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(value, font=font)


def wrap(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.FreeTypeFont,
         max_width: int, language: str) -> list[str]:
    lines: list[str] = []
    for paragraph in value.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        tokens = list(paragraph) if language.startswith("zh") else paragraph.split(" ")
        separator = "" if language.startswith("zh") else " "
        current = ""
        for token in tokens:
            candidate = token if not current else current + separator + token
            if width(draw, candidate, font) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            if width(draw, token, font) <= max_width:
                current = token
                continue
            # Split a single overlong token without dropping any characters.
            for char in token:
                if current and width(draw, current + char, font) > max_width:
                    lines.append(current)
                    current = ""
                current += char
        lines.append(current)
    return lines


def fit(draw: ImageDraw.ImageDraw, value: str, path: str, max_width: int,
        max_height: int, preferred: int, minimum: int, language: str,
        spacing_ratio: float = 1.2):
    for size in range(preferred, minimum - 1, -1):
        font = font_at(path, size)
        lines = wrap(draw, value, font, max_width, language)
        line_height = round(size * spacing_ratio)
        if len(lines) * line_height <= max_height:
            return font, lines, line_height
    raise ValueError(f"Text does not fit in its layout region: {value[:70]!r}")


def gradient_overlay(image: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    w, h = image.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(h):
        t = y / h
        top = max(0.0, 1 - t / 0.48) * 0.77
        bottom = max(0.0, (t - 0.57) / 0.43) * 0.87
        alpha = round(255 * max(top, bottom))
        draw.line((0, y, w, y), fill=(*color, alpha))
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def draw_lines(draw: ImageDraw.ImageDraw, lines: list[str], xy: tuple[int, int],
               font: ImageFont.FreeTypeFont, line_height: int, fill: str,
               stroke: int = 0, stroke_fill: str | None = None):
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill, anchor="lt",
                  stroke_width=stroke, stroke_fill=stroke_fill)
        y += line_height
    return y


def render(data: dict, language: str, background: Path, output: Path,
           explicit_font: str | None, draft: bool = False):
    project = data.get("project", {})
    canvas = project.get("canvas", {})
    w, h = int(canvas.get("width", 1200)), int(canvas.get("height", 1500))
    if w < 400 or h < 500 or w > 10000 or h > 10000:
        raise ValueError("Canvas dimensions must each be 400-10000 px (height at least 500 px)")
    if str(project.get("format", "PNG")).upper() != "PNG":
        raise ValueError("This composer outputs PNG only; use another tool for other formats")
    versions = data.get("languages", {})
    if language not in versions:
        raise ValueError(f"No copy for language {language!r}; available: {list(versions)}")
    copy = versions[language]
    required = data.get("required_fields", list(FIELDS))
    unknown = set(required) - set(FIELDS)
    if unknown:
        raise ValueError(f"Unsupported required fields: {sorted(unknown)}")
    missing = [field for field in required if not str(copy.get(field, "")).strip()]
    if missing:
        raise ValueError(f"Missing required {language} copy: {', '.join(missing)}")
    if not draft:
        approval = data.get("copy_approval", {}).get(language, {})
        if (approval.get("status") != "approved"
                or not str(approval.get("confirmed_by", "")).strip()):
            raise ValueError(f"Final output blocked: {language} copy lacks explicit human approval; use --draft for a watermarked preview")
        if approval.get("copy_sha256") != copy_digest(copy):
            raise ValueError(f"Final output blocked: {language} copy changed after approval; request renewed confirmation")
    if not background.is_file():
        raise ValueError(f"Background not found: {background}")

    style = data.get("style", {})
    text_color = style.get("text_color", "#FFF8EA")
    accent_color = style.get("accent_color", "#E7BC76")
    overlay_color = ImageColor.getrgb(style.get("overlay_color", "#10151B"))
    for color in (text_color, accent_color):
        ImageColor.getrgb(color)
    font_path = choose_font(language, explicit_font)

    with Image.open(background) as source:
        source = source.convert("RGB")
        scale = max(w / source.width, h / source.height)
        sw, sh = round(source.width * scale), round(source.height * scale)
        source = source.resize((sw, sh), Image.Resampling.LANCZOS)
        left, top = (sw - w) // 2, (sh - h) // 2
        image = source.crop((left, top, left + w, top + h))

    image = gradient_overlay(image, overlay_color)
    draw = ImageDraw.Draw(image)
    x = round(w * 0.075)
    usable = w - 2 * x

    # Top identification and title. The typography adapts to both short CJK
    # titles and substantially longer English titles.
    organizer = str(copy.get("organizer", "")).strip()
    if organizer:
        org_font, org_lines, org_lh = fit(draw, organizer, font_path, usable,
                                           round(h * 0.08), round(w * 0.026),
                                           round(w * 0.018), language)
        draw_lines(draw, org_lines, (x, round(h * 0.066)), org_font, org_lh,
                   accent_color)
    draw.line((x, round(h * 0.137), x + round(w * 0.15), round(h * 0.137)),
              fill=accent_color, width=max(2, round(w * 0.003)))

    title = str(copy.get("title", "")).strip()
    title_font, title_lines, title_lh = fit(
        draw, title, font_path, usable, round(h * 0.28),
        round(w * (0.080 if language.startswith("zh") else 0.066)),
        round(w * 0.037), language, 1.17)
    title_end = draw_lines(draw, title_lines, (x, round(h * 0.18)), title_font,
                           title_lh, text_color, max(1, round(w * 0.001)),
                           "#15202A")
    tagline = str(copy.get("tagline", "")).strip()
    if tagline:
        tagline_y = title_end + round(h * 0.03)
        tag_font, tag_lines, tag_lh = fit(
            draw, tagline, font_path, usable, round(h * 0.12),
            round(w * 0.033), round(w * 0.022), language)
        if tagline_y + len(tag_lines) * tag_lh > round(h * 0.61):
            raise ValueError("Title and tagline exceed available title region")
        draw_lines(draw, tag_lines, (x, tagline_y), tag_font, tag_lh,
                   text_color, max(1, round(w * 0.001)), "#15202A")

    # Bottom information region. Copy is fitted independently to avoid
    # compressing all text because one translated field is longer.
    panel_top = round(h * 0.705)
    draw.line((x, panel_top, w - x, panel_top), fill=accent_color,
              width=max(2, round(w * 0.002)))
    rows = (("dates", 0.728, 0.057, 0.032),
            ("hours", 0.790, 0.045, 0.026),
            ("venue", 0.838, 0.065, 0.027))
    for key, y_frac, height_frac, size_frac in rows:
        value = str(copy.get(key, "")).strip()
        if not value:
            continue
        row_font, row_lines, row_lh = fit(
            draw, value, font_path, usable, round(h * height_frac),
            round(w * size_frac), round(w * 0.018), language)
        draw_lines(draw, row_lines, (x, round(h * y_frac)), row_font, row_lh,
                   text_color)

    cta = str(copy.get("cta", "")).strip()
    if cta:
        cta_y = round(h * 0.923)
        cta_font, cta_lines, cta_lh = fit(
            draw, cta, font_path, usable, round(h * 0.052),
            round(w * 0.034), round(w * 0.022), language)
        draw_lines(draw, cta_lines, (x, cta_y), cta_font, cta_lh,
                   accent_color)
        cta_width = max(width(draw, line, cta_font) for line in cta_lines)
        arrow_x = min(round(x + cta_width + w * 0.04), w - x - round(w * 0.05))
        arrow_y = cta_y + round(cta_lh * 0.42)
        if arrow_x > x + cta_width:
            draw.line((arrow_x - round(w * 0.025), arrow_y, arrow_x, arrow_y),
                      fill=accent_color, width=max(2, round(w * 0.002)))
            draw.line((arrow_x - round(w * 0.009), arrow_y - round(w * 0.009),
                       arrow_x, arrow_y, arrow_x - round(w * 0.009),
                       arrow_y + round(w * 0.009)), fill=accent_color,
                      width=max(2, round(w * 0.002)))

    if draft:
        label = "待核对 / DRAFT" if language.startswith("zh") else "DRAFT / UNCONFIRMED"
        mark = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        mark_draw = ImageDraw.Draw(mark)
        band_y = round(h * 0.51)
        mark_draw.rectangle((0, band_y, w, band_y + round(h * 0.085)),
                            fill=(13, 20, 28, 205))
        mark_font = font_at(font_path, round(w * 0.044))
        mark_draw.text((w // 2, band_y + round(h * 0.042)), label,
                       font=mark_font, fill=(255, 242, 220, 255), anchor="mm")
        image = Image.alpha_composite(image, mark)

    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output, format="PNG", optimize=True)
    print(f"Created {'DRAFT ' if draft else ''}{output} ({w}x{h}, {language})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, type=Path,
                        help="JSON master copy using references/brief-template.json")
    parser.add_argument("--background", type=Path,
                        help="Approved visual background image")
    parser.add_argument("--language", required=True,
                        help="Language key in the brief, e.g. zh or en")
    parser.add_argument("--output", type=Path,
                        help="Output PNG path")
    parser.add_argument("--font", help="Optional font path, required if no suitable font is found")
    parser.add_argument("--draft", action="store_true",
                        help="Create a watermarked preview before human copy approval")
    parser.add_argument("--print-copy-digest", action="store_true",
                        help="Print the language copy digest to record after explicit user confirmation")
    args = parser.parse_args()
    with args.brief.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if args.print_copy_digest:
        copy = data.get("languages", {}).get(args.language)
        if not isinstance(copy, dict):
            parser.error(f"No copy for language {args.language!r}")
        print(copy_digest(copy))
        return
    if args.background is None or args.output is None:
        parser.error("--background and --output are required unless --print-copy-digest is used")
    render(data, args.language, args.background, args.output, args.font, args.draft)


if __name__ == "__main__":
    main()
