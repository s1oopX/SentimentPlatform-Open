from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SVG = ROOT / "public/brand/yx-logo.svg"
OUTPUT_ICO = ROOT / "public/favicon.ico"


def parse_color(value: str, *, opacity: float = 1.0) -> tuple[int, int, int, int]:
    value = (value or "").strip()
    if not value.startswith("#"):
        raise ValueError(f"unsupported color value: {value}")
    if len(value) == 7:
        red = int(value[1:3], 16)
        green = int(value[3:5], 16)
        blue = int(value[5:7], 16)
        alpha = round(255 * opacity)
        return red, green, blue, alpha
    raise ValueError(f"unsupported color length: {value}")


def scale_point(point: tuple[float, float], factor: float) -> tuple[float, float]:
    return point[0] * factor, point[1] * factor


def rounded_rect_box(element: ET.Element, factor: float) -> tuple[float, float, float, float]:
    x = float(element.attrib.get("x", "0"))
    y = float(element.attrib.get("y", "0"))
    width = float(element.attrib["width"])
    height = float(element.attrib["height"])
    return (x * factor, y * factor, (x + width) * factor, (y + height) * factor)


def translate_from_group(group: ET.Element) -> tuple[float, float]:
    transform = group.attrib.get("transform", "")
    match = re.search(r"translate\(([-\d.]+)\s+([-\d.]+)\)", transform)
    if match:
        return float(match.group(1)), float(match.group(2))
    match = re.search(r"translate\(([-\d.]+),([-\d.]+)\)", transform)
    if match:
        return float(match.group(1)), float(match.group(2))
    return 0.0, 0.0


def tokenize_path(path_data: str) -> list[str]:
    return re.findall(r"[MLHVZ]|-?\d+(?:\.\d+)?", path_data)


def path_to_points(path_data: str, translate: tuple[float, float], factor: float) -> list[tuple[float, float]]:
    tokens = tokenize_path(path_data)
    points: list[tuple[float, float]] = []
    cursor_x = 0.0
    cursor_y = 0.0
    index = 0
    command = ""
    offset_x, offset_y = translate

    while index < len(tokens):
        token = tokens[index]
        if token in {"M", "L", "H", "V", "Z"}:
            command = token
            index += 1
            if command == "Z":
                continue
        if command == "M" or command == "L":
            cursor_x = float(tokens[index])
            cursor_y = float(tokens[index + 1])
            index += 2
            points.append(scale_point((cursor_x + offset_x, cursor_y + offset_y), factor))
            continue
        if command == "H":
            cursor_x = float(tokens[index])
            index += 1
            points.append(scale_point((cursor_x + offset_x, cursor_y + offset_y), factor))
            continue
        if command == "V":
            cursor_y = float(tokens[index])
            index += 1
            points.append(scale_point((cursor_x + offset_x, cursor_y + offset_y), factor))
            continue
        raise ValueError(f"unsupported path command in {path_data!r}")

    return points


def render_favicon(source_svg: Path, output_ico: Path, canvas_size: int = 256) -> None:
    tree = ET.parse(source_svg)
    root = tree.getroot()
    view_box = [float(part) for part in root.attrib["viewBox"].split()]
    width = view_box[2]
    factor = canvas_size / width

    namespace = {"svg": "http://www.w3.org/2000/svg"}
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    background_rect, stroke_rect = root.findall("svg:rect", namespace)

    background_fill = parse_color(background_rect.attrib["fill"])
    background_radius = float(background_rect.attrib["rx"]) * factor
    draw.rounded_rectangle(
        rounded_rect_box(background_rect, factor),
        radius=background_radius,
        fill=background_fill,
    )

    stroke_opacity = float(stroke_rect.attrib.get("stroke-opacity", "1"))
    stroke_fill = parse_color(stroke_rect.attrib["stroke"], opacity=stroke_opacity)
    stroke_radius = float(stroke_rect.attrib["rx"]) * factor
    draw.rounded_rectangle(
        rounded_rect_box(stroke_rect, factor),
        radius=stroke_radius,
        outline=stroke_fill,
        width=max(1, round(factor)),
    )

    group = root.find("svg:g", namespace)
    translate = translate_from_group(group)
    path_fill = parse_color(group.attrib["fill"])

    for path in group.findall("svg:path", namespace):
        draw.polygon(path_to_points(path.attrib["d"], translate, factor), fill=path_fill)

    output_ico.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_ico, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64)])


if __name__ == "__main__":
    render_favicon(SOURCE_SVG, OUTPUT_ICO)
