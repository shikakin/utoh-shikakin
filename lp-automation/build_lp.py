#!/usr/bin/env python3
import argparse
import hashlib
import html as html_module
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps


VERIFIED_MASTER_SHA256 = "0b09fafe346e7bee633615ca99afe7ef0eaf50c867b393b767a62004a9da5b6d"
REQUIRED_CONFIG_KEYS = (
    "slug",
    "clinic_name",
    "clinic_hp",
    "reservation_url",
    "postal_code",
    "address",
    "phone",
    "access",
    "google_map_url",
    "hours_html",
)


def q(value):
    return json.dumps(value, ensure_ascii=False)


def require_text(cfg, key):
    value = cfg.get(key)
    if not isinstance(value, str) or not value.strip() or value == "未設定":
        raise RuntimeError(f"Required config value is missing: {key}")
    return value


def validate_config(cfg):
    for key in REQUIRED_CONFIG_KEYS:
        require_text(cfg, key)
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", cfg["slug"]):
        raise RuntimeError("slug must contain only lowercase letters, numbers, and hyphens")

    doctors = [x for x in cfg.get("doctors", []) if x.get("name", "").strip()]
    therapists = [x for x in cfg.get("therapists", []) if x.get("name", "").strip()]
    if not doctors:
        raise RuntimeError("At least one named doctor is required")

    for group_name, items in (("doctors", doctors), ("therapists", therapists)):
        for index, item in enumerate(items, start=1):
            for key in ("name", "position", "role", "photo"):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    raise RuntimeError(f"{group_name}[{index}] is missing {key}")
            if Path(item["photo"]).name != item["photo"] or not item["photo"].lower().endswith(".jpg"):
                raise RuntimeError(f"{group_name}[{index}].photo must be a plain .jpg filename")
    return doctors, therapists


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
        raise RuntimeError(f"config key not found exactly once: {key}")
    return out


def staff_grid(grid_id, items):
    cards = []
    for item in items:
        name = html_module.escape(item["name"], quote=True)
        position = html_module.escape(item["position"], quote=True)
        role = html_module.escape(item["role"], quote=True)
        photo = html_module.escape(item["photo"], quote=True)
        cards.append(
            '    <article class="staff-card">\n'
            f'      <div class="staff-photo"><img src="assets/{photo}" alt="{name}"></div>\n'
            '      <div class="staff-meta">\n'
            f'        <div class="staff-position">{position}<br>{role}</div>\n'
            f'        <div class="staff-name">{name}</div>\n'
            '      </div>\n'
            '    </article>'
        )
    return (
        f'  <div class="staff-grid staff-grid-mobile-safe" id="{grid_id}">\n'
        + "\n".join(cards)
        + "\n  </div>"
    )


def replace_grid(html, grid_id, new_grid):
    pattern = rf'  <div class="staff-grid staff-grid-mobile-safe" id="{re.escape(grid_id)}"></div>'
    out, count = re.subn(pattern, new_grid, html, count=1)
    if count != 1:
        raise RuntimeError(f"empty MASTER staff grid not found exactly once: {grid_id}")
    return out


def replace_staff_array(html, key, items):
    blocks = []
    for item in items:
        image_key = "directorImage" if key == "doctors" else "therapistImage"
        blocks.append(
            "      {\n"
            f"        position: {q(item['position'])},\n"
            f"        role: {q(item['role'])},\n"
            f"        name: {q(item['name'])},\n"
            f"        imageKey: {q(image_key)}\n"
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
        raise RuntimeError(f"staff config array not found exactly once: {key}")
    return out


def replace_embedded_staff_image(html, key, output_name):
    value = f"assets/{output_name}" if output_name else ""
    pattern = rf'(\s*{re.escape(key)}:\s*)"data:image/jpeg;base64,[^"]*"'
    out, count = re.subn(
        pattern,
        lambda match: match.group(1) + q(value),
        html,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"embedded MASTER image not found exactly once: {key}")
    return out


def replace_data_href(html, key, url, hide=False):
    pattern = rf'(<a\b[^>]*\bdata-href="{re.escape(key)}"[^>]*\bhref=")[^"]*(")'
    escaped_url = html_module.escape(url, quote=True)
    html, count = re.subn(
        pattern,
        lambda match: match.group(1) + escaped_url + match.group(2),
        html,
    )
    if count < 1:
        raise RuntimeError(f"link target not found: {key}")
    if hide:
        hide_pattern = rf'(<a\b[^>]*\bdata-href="{re.escape(key)}"[^>]*)(>)'
        html, hide_count = re.subn(
            hide_pattern,
            lambda match: match.group(1) + ' style="display:none;"' + match.group(2),
            html,
            count=1,
        )
        if hide_count != 1:
            raise RuntimeError(f"link could not be hidden: {key}")
    return html


def resolve_source_photo(config_dir, item, output_dir):
    source_name = item.get("source_photo", item["photo"])
    if Path(source_name).name != source_name:
        raise RuntimeError(f"source_photo must be a plain filename: {source_name}")
    source = config_dir / source_name
    if source.exists():
        return source
    existing = output_dir / "assets" / item["photo"]
    if existing.exists():
        return existing
    raise RuntimeError(f"Source photo not found: {source}")


def encode_photo(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.save(target, format="JPEG", quality=92, optimize=True)


def build(master_path, config_path, output_dir):
    master_path = Path(master_path)
    config_path = Path(config_path)
    output_dir = Path(output_dir)
    master_bytes = master_path.read_bytes()
    master_hash = hashlib.sha256(master_bytes).hexdigest()
    if master_hash != VERIFIED_MASTER_SHA256:
        raise RuntimeError(
            "Approved MASTER hash mismatch. Build stopped to protect the approved LP design."
        )

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    doctors, therapists = validate_config(cfg)
    html = master_bytes.decode("utf-8")
    clinic = cfg["clinic_name"]

    # Clinic identity is the only change made to recommendation copy.
    html = html.replace("〇〇歯科医院", clinic)

    scalar_map = {
        "sourceWebsiteUrl": cfg["clinic_hp"],
        "clinicName": clinic,
        "directorName": doctors[0]["name"],
        "therapistName": therapists[0]["name"] if therapists else "",
        "directorRole": doctors[0]["role"],
        "therapistRole": therapists[0]["role"] if therapists else "",
        "postalCode": cfg["postal_code"],
        "address": cfg["address"],
        "tel": cfg["phone"],
        "access": cfg["access"],
        "reservationUrl": cfg["reservation_url"],
        "lineUrl": cfg.get("line_url", ""),
    }
    for key, value in scalar_map.items():
        html = replace_scalar(html, key, value)

    primary_url = cfg.get("line_url") or cfg["reservation_url"]
    html = replace_data_href(html, "ctaMainUrl", primary_url)
    html = replace_data_href(html, "reservationUrl", cfg["reservation_url"])
    html = replace_data_href(
        html,
        "lineUrl",
        cfg.get("line_url") or "#",
        hide=not cfg.get("line_url"),
    )

    html = replace_staff_array(html, "doctors", doctors)
    html = replace_staff_array(html, "therapists", therapists)
    html = replace_embedded_staff_image(html, "directorImage", doctors[0]["photo"])
    html = replace_embedded_staff_image(
        html,
        "therapistImage",
        therapists[0]["photo"] if therapists else "",
    )
    html = replace_grid(html, "doctorStaffGrid", staff_grid("doctorStaffGrid", doctors))
    html = replace_grid(
        html,
        "therapistStaffGrid",
        staff_grid("therapistStaffGrid", therapists),
    )

    # Replace non-visible fallback placeholders so generated files contain no person placeholders.
    html = html.replace('data.directorName || "〇〇 〇〇"', f"data.directorName || {q(doctors[0]['name'])}")
    therapist_fallback = therapists[0]["name"] if therapists else "スタッフ"
    html = html.replace(
        'data.therapistName || "〇〇 〇〇"',
        f"data.therapistName || {q(therapist_fallback)}",
    )
    html = html.replace('item.name || "〇〇 〇〇"', 'item.name || "スタッフ"')

    # Clinic information is an approved clinic-specific replacement area.
    map_html = (
        f'<br><br><a href="{html_module.escape(cfg["google_map_url"], quote=True)}" '
        'target="_blank" rel="noopener">Googleマップを開く</a>'
    )
    clinic_info = (
        '      clinicInfoHtml: `${clinicName}<br>${config.postalCode || ""}<br>'
        '${config.address || ""}<br>TEL：${config.tel || ""}<br>'
        '${config.access ? "アクセス：" + config.access + "<br>" : ""}'
        f'<br><strong>診療時間</strong><br>{cfg["hours_html"]}{map_html}`,'
    )
    html, info_count = re.subn(
        r"^\s*clinicInfoHtml:.*$",
        clinic_info,
        html,
        count=1,
        flags=re.M,
    )
    if info_count != 1:
        raise RuntimeError("clinicInfoHtml not found exactly once")

    placeholder_values = (
        "〇〇歯科医院",
        "〇〇 〇〇",
        "https://example.com/reserve",
        "https://lin.ee/xxxxxx",
    )
    remaining = [value for value in placeholder_values if value in html]
    if remaining:
        raise RuntimeError("MASTER placeholders remain: " + ", ".join(remaining))

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    shutil.copyfile(master_path, output_dir / "_MASTER_snapshot.html")

    config_dir = config_path.parent
    for item in doctors + therapists:
        source = resolve_source_photo(config_dir, item, output_dir)
        encode_photo(source, output_dir / "assets" / item["photo"])

    print(f"BUILT {output_dir / 'index.html'} bytes={len(html.encode('utf-8'))}")
    print(f"MASTER sha256={master_hash}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        build(args.master, args.config, args.out)
    except Exception as exc:
        print("BUILD FAIL:", exc, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
