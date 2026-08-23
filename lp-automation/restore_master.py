#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path


VERIFIED_SOURCE_SHA256 = "4817d3b0ea9d109fc124cf0e57053ad251b01c05ac27511d52f0c2d79d3f6983"
VERIFIED_MASTER_SHA256 = "0b09fafe346e7bee633615ca99afe7ef0eaf50c867b393b767a62004a9da5b6d"


def q(value):
    return json.dumps(value, ensure_ascii=False)


def replace_scalar(html, key, value):
    pattern = rf'(^\s*{re.escape(key)}:\s*)"[^"]*"(,?)\s*$'
    out, count = re.subn(
        pattern,
        lambda match: match.group(1) + q(value) + match.group(2),
        html,
        count=1,
        flags=re.M,
    )
    if count != 1:
        raise RuntimeError(f"source config key not found exactly once: {key}")
    return out


def replace_staff_array(html, key, items):
    blocks = []
    for item in items:
        blocks.append(
            "      {\n"
            f"        position: {q(item['position'])},\n"
            f"        role: {q(item['role'])},\n"
            f"        name: {q(item['name'])},\n"
            f"        imageKey: {q(item['imageKey'])}\n"
            "      }"
        )
    replacement = f"    {key}: [\n" + ",\n".join(blocks) + "\n    ],"
    next_key = "therapists" if key == "doctors" else "directorRole"
    pattern = rf'    {key}: \[.*?\n    \],\n    {next_key}:'
    out, count = re.subn(
        pattern,
        replacement + f"\n    {next_key}:",
        html,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(f"source staff array not found exactly once: {key}")
    return out


def empty_staff_grid(html, grid_id):
    pattern = (
        rf'  <div class="staff-grid staff-grid-mobile-safe" id="{re.escape(grid_id)}">'
        r'.*?\n  </div>\n</section>'
    )
    replacement = (
        f'  <div class="staff-grid staff-grid-mobile-safe" id="{grid_id}"></div>\n'
        "</section>"
    )
    out, count = re.subn(pattern, replacement, html, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"source staff grid not found exactly once: {grid_id}")
    return out


def replace_staff_image(html, key, image_path):
    encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    pattern = rf'(\s*{re.escape(key)}:\s*)"data:image/jpeg;base64,[^"]*"'
    out, count = re.subn(
        pattern,
        lambda match: match.group(1) + q("data:image/jpeg;base64," + encoded),
        html,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"source staff image not found exactly once: {key}")
    return out


def restore(source_path, output_path, asset_dir):
    source_bytes = Path(source_path).read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if source_hash != VERIFIED_SOURCE_SHA256:
        raise RuntimeError("Verified MASTER-derived source hash mismatch")

    html = source_bytes.decode("utf-8")
    html = html.replace("宇藤歯科医院", "〇〇歯科医院")
    html = html.replace(
        ' data-text="lineCtaLabel" href="#" style="display:none;"',
        ' data-text="lineCtaLabel" href="#"',
    )

    scalar_map = {
        "sourceWebsiteUrl": "",
        "clinicName": "〇〇歯科医院",
        "directorName": "〇〇 〇〇",
        "therapistName": "〇〇 〇〇",
        "directorRole": "歯科医師 / シカキンマネジメントドクター",
        "therapistRole": "シカキンセラピー認定セラピスト",
        "postalCode": "〒000-0000",
        "address": "〇〇県〇〇市〇〇町0-0-0",
        "tel": "000-0000-0000",
        "access": "〇〇駅から徒歩〇分",
        "reservationUrl": "https://example.com/reserve",
        "lineUrl": "https://lin.ee/xxxxxx",
    }
    for key, value in scalar_map.items():
        html = replace_scalar(html, key, value)

    html = replace_staff_array(
        html,
        "doctors",
        [{
            "position": "院長",
            "role": "歯科医師 / シカキンマネジメントドクター",
            "name": "〇〇 〇〇",
            "imageKey": "directorImage",
        }],
    )
    html = replace_staff_array(
        html,
        "therapists",
        [{
            "position": "シカキンセラピスト",
            "role": "シカキンセラピー認定セラピスト",
            "name": "〇〇 〇〇",
            "imageKey": "therapistImage",
        }],
    )
    html = empty_staff_grid(html, "doctorStaffGrid")
    html = empty_staff_grid(html, "therapistStaffGrid")
    asset_dir = Path(asset_dir)
    html = replace_staff_image(
        html,
        "directorImage",
        asset_dir / "director-placeholder.jpg",
    )
    html = replace_staff_image(
        html,
        "therapistImage",
        asset_dir / "therapist-placeholder.jpg",
    )

    output_bytes = html.encode("utf-8")
    output_hash = hashlib.sha256(output_bytes).hexdigest()
    if output_hash != VERIFIED_MASTER_SHA256:
        raise RuntimeError(f"Restored MASTER hash mismatch: {output_hash}")
    Path(output_path).write_bytes(output_bytes)
    print(f"RESTORED {output_path}")
    print(f"MASTER sha256={output_hash}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--asset-dir",
        default="lp-automation/master-assets",
    )
    args = parser.parse_args()
    try:
        restore(args.source, args.output, args.asset_dir)
    except Exception as exc:
        print("RESTORE FAIL:", exc, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
