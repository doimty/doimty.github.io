#!/usr/bin/env python3
"""Validate the generated Cydia/APT index files in the repository."""
from __future__ import annotations

import gzip
import hashlib
import lzma
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_NAMES = ("Packages", "Packages.gz", "Packages.xz", "Packages.lzma")
REQUIRED_FIELDS = ("Package", "Version", "Architecture", "Filename", "Size", "MD5sum", "SHA1", "SHA256")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(packages: str) -> list[dict[str, str]]:
    result = []
    for block in re.split(r"\n\s*\n", packages.strip()):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if not line or line[0].isspace():
                continue
            key, separator, value = line.partition(": ")
            if separator:
                fields[key] = value
        result.append(fields)
    return result


def fail(message: str) -> None:
    print(f"FATAL: {message}", file=sys.stderr)
    raise SystemExit(1)


packages_path = ROOT / "Packages"
release_path = ROOT / "Release"
if not packages_path.is_file() or not release_path.is_file():
    fail("Packages and Release must exist")

packages = packages_path.read_text(encoding="utf-8")
entries = records(packages)
if not entries:
    fail("Packages is empty")

keys: set[tuple[str, str, str, str]] = set()
for index, entry in enumerate(entries, start=1):
    missing = [field for field in REQUIRED_FIELDS if not entry.get(field)]
    if missing:
        fail(f"Packages stanza {index} missing: {', '.join(missing)}")
    filename = ROOT / entry["Filename"]
    if not filename.is_file():
        fail(f"Packages stanza {index} points to missing file: {entry['Filename']}")
    key = (entry["Package"], entry["Version"], entry["Architecture"], entry["Filename"])
    if key in keys:
        fail(f"duplicate Packages stanza: {key}")
    keys.add(key)

release = release_path.read_text(encoding="utf-8")
if len(release.encode("utf-8")) < 100:
    fail("Release is too small")

for name in INDEX_NAMES:
    path = ROOT / name
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"missing or empty index: {name}")
    if name == "Packages.gz":
        if gzip.decompress(path.read_bytes()) != packages_path.read_bytes():
            fail("Packages.gz does not match Packages")
    elif name == "Packages.xz":
        if lzma.decompress(path.read_bytes(), format=lzma.FORMAT_XZ) != packages_path.read_bytes():
            fail("Packages.xz does not match Packages")
    elif name == "Packages.lzma":
        if lzma.decompress(path.read_bytes(), format=lzma.FORMAT_ALONE) != packages_path.read_bytes():
            fail("Packages.lzma does not match Packages")

sha_section = release.split("SHA256:\n", 1)[-1]
for name in INDEX_NAMES:
    matches = re.findall(rf"^ ([0-9a-f]{{64}}) (\d+) {re.escape(name)}$", sha_section, re.MULTILINE)
    if len(matches) != 1:
        fail(f"Release has no unique SHA256 entry for {name}")
    expected_hash, expected_size = matches[0]
    path = ROOT / name
    if expected_hash != sha256(path) or int(expected_size) != path.stat().st_size:
        fail(f"Release checksum mismatch for {name}")

print(f"APT index validation: PASS ({len(entries)} package stanzas)")
