#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

VERIFIED_SOURCE_SHA256 = "4817d3b0ea9d109fc124cf0e57053ad251b01c05ac27511d52f0c2d79d3f6983"


def q(value):
    return json.dumps(value, ensure_ascii=False)


def replace_scalar(html, key, value):
    pattern = rf'(^\s*{re.escape(key)}:\s*)"[^"]*"(,?)\s*$'
    out, count = re.subn(pattern, lambda m: m.group(1) + q(value) + m.group(2), html, count=1, flags=re.M)
    if count != 1:
        raise RuntimeError(f"config key not found exactly once: {key}")
    return out


def staff_grid(grid_id, items):
    cards = []
    for item in items:
        name = item.get("name", "").strip()
        if not name:
            continue
        position = item.get("position", "")
        role = item.get("role", "")
        photo = item.get("photo", "")
        cards.append(
            f'''    <article class="staff-card">\n'''
            f'''      <div class="staff-photo"><img src="assets/{photo}" alt="{name}"></div>\n'''
            f'''      <div class="staff-info"><div class="staff-role">{position}<br>{role}</div><div class="staff-name">{name}</div></div>\n'''
            f'''    </article>'''
        )
    return f'''  <div class="staff-grid staff-grid-mobile-safe" id="{grid_id}">\n''' + "\n".join(cards) + "\n  </div>"


def replace_grid(html, grid_id, new_grid):
    # The verified source has one static card inside each grid. Replace the whole grid only.
    pattern = rf'  <div class="staff-grid staff-grid-mobile-safe" id="{re.escape(grid_id)}">.*?</div>\s*</div>'
    out, count = re.subn(pattern, new_grid, html, count=1, flags=re.S)
    if count != 1:
        # MASTER itself has an empty grid; support that too.
        pattern2 = rf'  <div class="staff-grid staff-grid-mobile-safe" id="{re.escape(grid_id)}"></div>'
        out, count = re.subn(pattern2, new_grid, html, count=1)
    if count != 1:
        raise RuntimeError(f"staff grid not found exactly once: {grid_id}")
    return out


def replace_staff_array(html, key, items):
    blocks = []
    for item in items:
        if not item.get("name", "").strip():
            continue
        image_key = "directorImage" if key == "doctors" else "therapistImage"
        blocks.append(
            "      {\n"
            f"        position: {q(item.get('position',''))},\n"
            f"        role: {q(item.get('role',''))},\n"
            f"        name: {q(item.get('name',''))},\n"
            f"        imageKey: {q(image_key)}\n"
            "      }"
        )
    replacement = f"    {key}: [\n" + ",\n".join(blocks) + "\n    ],"
    next_key = "therapists" if key == "doctors" else "directorRole"
    if key == "doctors":
        pattern = r'    doctors: \[.*?\n    \],\n    therapists:'
        replacement += "\n    therapists:"
    else:
        pattern = r'    therapists: \[.*?\n    \],\n    directorRole:'
        replacement += "\n    directorRole:"
    out, count = re.subn(pattern, replacement, html, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"staff config array not found: {key}")
    return out


def build(source_path, config_path, output_path):
    source_bytes = Path(source_path).read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if source_hash != VERIFIED_SOURCE_SHA256:
        raise RuntimeError(
            "Verified MASTER-derived source has changed. Build stopped to protect the approved LP design."
        )
    html = source_bytes.decode("utf-8")
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))

    clinic = cfg["clinic_name"]
    doctors = [x for x in cfg.get("doctors", []) if x.get("name", "").strip()]
    therapists = [x for x in cfg.get("therapists", []) if x.get("name", "").strip()]
    if not doctors:
        raise RuntimeError("At least one named doctor is required")

    # The verified source differs from the approved MASTER only in permitted clinic/staff fields.
    # Replace clinic identity throughout, including recommendation copy, without touching shared copy/design/assets.
    html = html.replace("宇藤歯科医院", clinic)

    # Remove the previous clinic's optional LINE-only display customization.
    html = html.replace(
        ' data-text="lineCtaLabel" href="#" style="display:none;"',
        ' data-text="lineCtaLabel" href="#"'
    )

    scalar_map = {
        "sourceWebsiteUrl": cfg.get("clinic_hp", ""),
        "clinicName": clinic,
        "directorName": doctors[0]["name"],
        "therapistName": therapists[0]["name"] if therapists else "",
        "directorRole": doctors[0].get("role", "歯科医師 / シカキンマネジメントドクター"),
        "therapistRole": therapists[0].get("role", "") if therapists else "",
        "postalCode": cfg.get("postal_code", "未設定"),
        "address": cfg.get("address", "未設定"),
        "tel": cfg.get("phone", "未設定"),
        "access": cfg.get("access", "未設定"),
        "reservationUrl": cfg.get("reservation_url", "未設定"),
        # No LINE was supplied; never publish a false example URL.
        "lineUrl": "",
    }
    for key, value in scalar_map.items():
        html = replace_scalar(html, key, value)

    html = replace_staff_array(html, "doctors", doctors)
    html = replace_staff_array(html, "therapists", therapists)

    # Staff photos are the only image references changed. All shared MASTER images stay byte-for-byte intact.
    html, c1 = re.subn(
        r'(\s*directorImage:\s*)"data:image/jpeg;base64,[^"]*"',
        r'\1"assets/doctor-01.jpg"', html, count=1
    )
    if c1 != 1:
        raise RuntimeError("directorImage not found")
    html, c2 = re.subn(
        r'(\s*therapistImage:\s*)"data:image/jpeg;base64,[^"]*"',
        r'\1"assets/therapist-01.jpg"', html, count=1
    )
    if c2 != 1:
        raise RuntimeError("therapistImage not found")

    html = replace_grid(html, "doctorStaffGrid", staff_grid("doctorStaffGrid", doctors))
    html = replace_grid(html, "therapistStaffGrid", staff_grid("therapistStaffGrid", therapists))

    # Fallback clinic identity in the existing MASTER script.
    html = html.replace(
        'const clinicName = config.clinicName || "宇藤歯科医院";',
        f'const clinicName = config.clinicName || {q(clinic)};'
    )

    # Clinic information is an explicitly permitted replacement area.
    hours = cfg.get("hours_html", "未設定")
    map_url = cfg.get("google_map_url", "未設定")
    map_html = ""
    if map_url and map_url != "未設定":
        map_html = f'<br><br><a href="{map_url}" target="_blank" rel="noopener">Googleマップを開く</a>'
    clinic_info = (
        '      clinicInfoHtml: `${clinicName}<br>${config.postalCode || ""}<br>${config.address || ""}'
        '<br>TEL：${config.tel || ""}<br>${config.access ? "アクセス：" + config.access + "<br>" : ""}'
        f'<br><strong>診療時間</strong><br>{hours}{map_html}`,'
    )
    html, info_count = re.subn(r'^\s*clinicInfoHtml:.*$', clinic_info, html, count=1, flags=re.M)
    if info_count != 1:
        raise RuntimeError("clinicInfoHtml not found")

    forbidden_old = [
        "宇藤歯科医院", "宇藤 博文", "A.Uto", "042-721-6474",
        "東京都町田市原町田6-3-3町映ビル4F", "utoh-dental.jp"
    ]
    remain = [x for x in forbidden_old if x in html]
    if remain:
        raise RuntimeError("Previous clinic data remains: " + ", ".join(remain))
    if "〇〇歯科医院" in html:
        raise RuntimeError("MASTER placeholder remains")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"BUILT {out} bytes={len(html.encode('utf-8'))}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="utoh_shikakin_lp_embedded.html")
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    try:
        build(a.source, a.config, a.output)
    except Exception as exc:
        print("BUILD FAIL:", exc, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
