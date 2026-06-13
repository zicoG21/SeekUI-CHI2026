#!/usr/bin/env python
import argparse
import json
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path


OSF_NODE_API = "https://api.osf.io/v2/nodes/hmg9b/files/osfstorage/"
DEFAULT_FILE_NAME = "VSGUI10K.zip"


def load_json_url(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def find_download_url(file_name):
    url = OSF_NODE_API
    while url:
        data = load_json_url(url)
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            if attrs.get("name") == file_name:
                return {
                    "name": attrs.get("name"),
                    "size": attrs.get("size"),
                    "download": item.get("links", {}).get("download"),
                    "guid": attrs.get("guid"),
                    "id": item.get("id"),
                }
        url = data.get("links", {}).get("next")
    raise FileNotFoundError(f"Could not find {file_name} in OSF node hmg9b")


def download(url, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with urllib.request.urlopen(url, timeout=120) as response, open(tmp_path, "wb") as out:
        shutil.copyfileobj(response, out)
    os.replace(tmp_path, output_path)


def extract(zip_path, out_dir, extract_images):
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted_suffixes = (".csv", ".txt")
    extracted = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            name = member.filename
            if name.startswith("__MACOSX/") or member.is_dir():
                continue
            if name.startswith("data/vsgui10k-images/") and not extract_images:
                continue
            if (not name.startswith("data/vsgui10k-images/")) and (not name.endswith(wanted_suffixes)):
                continue
            zf.extract(member, out_dir)
            extracted.append(name)
    return extracted


def main():
    parser = argparse.ArgumentParser(description="Download and extract the OSF VSGUI10K dataset metadata/images.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--file-name", default=DEFAULT_FILE_NAME)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--extract-images", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    zip_path = out_dir / args.file_name
    metadata = find_download_url(args.file_name)
    if not args.skip_download and (args.force or not zip_path.exists()):
        download(metadata["download"], zip_path)
    extracted = extract(zip_path, out_dir / "extracted", args.extract_images)
    summary = {
        "osf_node": "https://osf.io/hmg9b/",
        "osf_api": OSF_NODE_API,
        "file": metadata,
        "zip_path": str(zip_path),
        "extract_dir": str(out_dir / "extracted"),
        "extract_images": args.extract_images,
        "extracted_files": len(extracted),
    }
    with open(out_dir / "download_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
