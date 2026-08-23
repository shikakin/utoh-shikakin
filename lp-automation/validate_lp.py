#!/usr/bin/env python3
import argparse
import hashlib
import html as html_module
import json
import re
import sys
from pathlib import Path

from PIL import Image


VERIFIED_MASTER_SHA256 = "0b09fafe346e7bee633615ca99afe7ef0eaf50c867b393b767a62004a9da5b6d"
PLACEHOLDERS = (
    "〇〇歯科医院",
    "〇〇 〇〇",
    "https://example.com/reserve",
    "https://lin.ee/xxxxxx",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    output_dir = Path(args.dir)
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    index_path = output_dir / "index.html"
    snapshot_path = output_dir / "_MASTER_snapshot.html"
    errors = []

    if not index_path.exists():
        errors.append(f"index.htmlなし: {index_path}")
        html = ""
    else:
        html = index_path.read_text(encoding="utf-8")

    if not snapshot_path.exists():
        errors.append("_MASTER_snapshot.htmlなし")
    elif hashlib.sha256(snapshot_path.read_bytes()).hexdigest() != VERIFIED_MASTER_SHA256:
        errors.append("MASTERスナップショットのハッシュ不一致")

    for placeholder in PLACEHOLDERS:
        if placeholder in html:
            errors.append(f"プレースホルダー残存: {placeholder}")

    required_values = {
        "医院名": cfg.get("clinic_name"),
        "医院HP": cfg.get("clinic_hp"),
        "予約URL": cfg.get("reservation_url"),
        "郵便番号": cfg.get("postal_code"),
        "住所": cfg.get("address"),
        "電話番号": cfg.get("phone"),
        "アクセス": cfg.get("access"),
        "Google Map": cfg.get("google_map_url"),
        "診療時間": cfg.get("hours_html"),
    }
    for label, value in required_values.items():
        if not isinstance(value, str) or not value.strip() or value == "未設定":
            errors.append(f"必須設定なし: {label}")
        elif value not in html_module.unescape(html):
            errors.append(f"未反映: {label}")

    if output_dir.name != cfg.get("slug"):
        errors.append(f"出力先slug不一致: {output_dir.name} != {cfg.get('slug')}")

    for item in cfg.get("doctors", []) + cfg.get("therapists", []):
        if not item.get("name", "").strip():
            continue
        for label, key in (("氏名", "name"), ("役職", "position"), ("職種・肩書", "role")):
            value = item.get(key, "")
            if not value or value not in html:
                errors.append(f"{label}未反映: {item.get('name', '人物名なし')}")
        photo = output_dir / "assets" / item.get("photo", "")
        if not photo.exists():
            errors.append(f"写真なし: {photo}")
            continue
        try:
            with Image.open(photo) as image:
                image.verify()
            with Image.open(photo) as image:
                if image.format != "JPEG":
                    errors.append(f"写真がJPEGではありません: {photo}")
                if image.width <= 0 or image.height <= 0:
                    errors.append(f"写真サイズ不正: {photo}")
        except Exception:
            errors.append(f"写真破損: {photo}")
        if f"assets/{item['photo']}" not in html:
            errors.append(f"写真リンク未反映: {item['name']}")

    if re.search(r'data:image/[^;]+;base64,', html):
        # Shared MASTER images remain embedded; only staff images must be external.
        for key in ("directorImage", "therapistImage"):
            if re.search(rf'{key}:\s*"data:image/', html):
                errors.append(f"人物写真がBase64のまま: {key}")

    if errors:
        print("FAIL")
        for error in errors:
            print("- " + error)
        sys.exit(1)

    print("PASS")
    print("clinic:", cfg["clinic_name"])
    print("master_sha256:", VERIFIED_MASTER_SHA256)
    print("placeholder_count: 0")
    print("images: OK")


if __name__ == "__main__":
    main()
