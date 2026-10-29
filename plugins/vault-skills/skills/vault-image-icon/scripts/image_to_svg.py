"""Embed an original local PNG/JPEG/GIF in an Iconize-compatible SVG."""

import argparse
import base64
import io
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET


def image_info(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 33 or data[12:16] != b"IHDR":
            raise ValueError("Invalid PNG header")
        return "image/png", *struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        if len(data) < 13:
            raise ValueError("Invalid GIF header")
        return "image/gif", *struct.unpack("<HH", data[6:10])
    if data.startswith(b"\xff\xd8"):
        stream = io.BytesIO(data)
        stream.seek(2)
        frames = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                  0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while stream.tell() < len(data):
            if stream.read(1) != b"\xff":
                raise ValueError("Invalid JPEG marker")
            marker = stream.read(1)
            while marker == b"\xff":
                marker = stream.read(1)
            if not marker or marker[0] in (0xD9, 0xDA):
                break
            if marker[0] == 0x01 or 0xD0 <= marker[0] <= 0xD8:
                continue
            length_bytes = stream.read(2)
            if len(length_bytes) != 2:
                break
            length = struct.unpack(">H", length_bytes)[0]
            if length < 2 or stream.tell() + length - 2 > len(data):
                raise ValueError("Invalid JPEG segment length")
            if marker[0] in frames:
                frame = stream.read(length - 2)
                if len(frame) < 6:
                    raise ValueError("Invalid JPEG frame")
                height, width = struct.unpack(">HH", frame[1:5])
                return "image/jpeg", width, height
            stream.seek(length - 2, 1)
        raise ValueError("JPEG dimensions not found")
    raise ValueError("Supported source formats: PNG, JPEG, GIF")


def create_svg(data):
    mime, width, height = image_info(data)
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive")
    uri = "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {width} {height}" width="16" height="16">'
        f'<image width="{width}" height="{height}" '
        f'preserveAspectRatio="xMidYMid meet" href="{uri}" xlink:href="{uri}"/>'
        '</svg>\n'
    )
    parsed = ET.fromstring(svg)
    assert base64.b64decode(parsed[0].attrib["href"].split(",", 1)[1]) == data
    return svg.encode("utf-8"), width, height


def pack_prefix(pack):
    parts = pack.split("-")
    if len(parts) > 1:
        return parts[0][0].upper() + "".join(p[0].lower() for p in parts[1:])
    return pack[0].upper() + pack[1:2].lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--pack", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--write", action="store_true", help="Write; otherwise dry-run")
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", args.pack):
            raise ValueError("Pack name must be lowercase words separated by hyphens")
        if args.output.suffix != ".svg" or not re.fullmatch(
                r"[A-Z][A-Za-z0-9]*", args.output.stem):
            raise ValueError("Use an uppercase-leading, letters/digits SVG filename")
        if args.output.parent.name != args.pack:
            raise ValueError("Output must be inside a folder named after the pack")
        svg, width, height = create_svg(args.image.read_bytes())
        same = args.output.exists() and args.output.read_bytes() == svg
        if args.output.exists() and not same:
            raise ValueError("Output already contains different content; not overwritten")
        if args.write and not same:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as target:
                target.write(svg)
        print(json.dumps({"mode": "write" if args.write else "dry-run",
                          "icon_id": pack_prefix(args.pack) + args.output.stem,
                          "output": str(args.output), "width": width, "height": height,
                          "svg_bytes": len(svg), "already_identical": same}))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
