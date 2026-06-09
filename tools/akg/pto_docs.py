# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""PTO documentation loader and instruction-card extractor.

The public PTO manual is built from `docs/mkdocs/mkdocs.yml`. The automatic kernel generator needs instruction cards for
exact retrieval and legality checks, so this module builds one JSON card for every documented ISA instruction in that nav.
The official instruction-card set has 283 unique instructions: it excludes documented helper/view pseudo-ops and system
scheduling helper pages, and it merges duplicated communication/tile spellings such as `tgather` and `tscatter` into one
card with multiple source pages.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

INSTRUCTION_RE = re.compile(r"\bpto\.([a-z][a-z0-9_]*)\b", re.IGNORECASE)
NAV_ENTRY_RE = re.compile(r"\s*-\s+pto\.([a-z][a-z0-9_]*):\s+(.+)")
NAV_SECTION_RE = re.compile(r"\s*-\s+([^:]+):\s*$")
TOKEN_RE = re.compile(r"[^a-z0-9_]+")
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

EXCLUDED_NAV_SECTIONS = {"View And Tile Buffer", "12. System Scheduling ISA Reference"}
REPO_ROOT = Path(__file__).resolve().parents[2]
MKDOCS_NAV = REPO_ROOT / "docs" / "mkdocs" / "mkdocs.yml"


@dataclass(frozen=True)
class NavEntry:
    name: str
    path: Path
    sections: tuple[str, ...]


class LinkAndTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href" and value:
                self.links.append(value)

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    @property
    def text(self) -> str:
        return "\n".join(self.parts)


def fetch_url(url: str, timeout: int = 15) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "pto-akg-doc-loader/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        final_url = response.geturl()
    return data.decode("utf-8", errors="ignore"), final_url


def crawl_docs(base_url: str, max_pages: int = 80) -> list[dict[str, str]]:
    base = base_url.rstrip("/") + "/"
    queue = [base]
    seen: set[str] = set()
    pages: list[dict[str, str]] = []
    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        html, final_url = fetch_url(url)
        parser = LinkAndTextParser()
        parser.feed(html)
        pages.append({"url": final_url, "text": parser.text})
        for href in parser.links:
            absolute = urllib.parse.urljoin(final_url, href).split("#", 1)[0]
            if not absolute.startswith(base) or absolute in seen or absolute in queue:
                continue
            if any(absolute.endswith(suffix) for suffix in [".png", ".jpg", ".jpeg", ".svg", ".pdf", ".zip"]):
                continue
            queue.append(absolute)
    return pages


def load_nav_entries(nav_path: Path = MKDOCS_NAV) -> list[NavEntry]:
    current: list[tuple[int, str]] = []
    entries: list[NavEntry] = []
    for line in nav_path.read_text(encoding="utf-8").splitlines():
        indent = len(line) - len(line.lstrip())
        section_match = NAV_SECTION_RE.match(line)
        if section_match and "pto." not in line:
            current = [item for item in current if item[0] < indent] + [(indent, section_match.group(1).strip())]
            continue
        entry_match = NAV_ENTRY_RE.match(line)
        if not entry_match:
            continue
        name = entry_match.group(1).lower()
        rel_path = entry_match.group(2).strip()
        sections = tuple(section for _indent, section in current)
        if any(section in EXCLUDED_NAV_SECTIONS for section in sections):
            continue
        entries.append(NavEntry(name=name, path=REPO_ROOT / rel_path, sections=sections))
    return entries


def extract_section(text: str, section_name: str, max_chars: int = 2400) -> str:
    matches = list(SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1).strip().lower() != section_name.lower():
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[start:end].strip()[:max_chars]
    return ""


def first_code_block(text: str) -> str:
    match = re.search(r"```[A-Za-z0-9_+-]*\n(.*?)\n```", text, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_operands(section: str) -> list[str]:
    operands: list[str] = []
    for line in section.splitlines():
        match = re.match(r"\|\s*`?%?([A-Za-z_][A-Za-z0-9_]*)`?\s*\|", line)
        if match and match.group(1).lower() not in {"operand", "result"}:
            operands.append(match.group(1))
    return operands


def category_for(entry: NavEntry) -> str:
    if len(entry.sections) >= 2:
        return entry.sections[-1]
    return entry.sections[0] if entry.sections else "unknown"


def build_card_from_nav(entry: NavEntry) -> dict[str, Any]:
    text = entry.path.read_text(encoding="utf-8", errors="ignore") if entry.path.exists() else ""
    summary = extract_section(text, "Summary", max_chars=1000) or f"Documented PTO instruction `pto.{entry.name}`."
    syntax = extract_section(text, "Syntax")
    cpp_intrinsic = extract_section(text, "C++ Intrinsic")
    inputs = extract_section(text, "Inputs")
    outputs = extract_section(text, "Expected Outputs")
    constraints = extract_section(text, "Constraints")
    exceptions = extract_section(text, "Exceptions")
    target_restrictions = extract_section(text, "Target-Profile Restrictions")
    examples = extract_section(text, "Examples")
    operands = extract_operands(inputs)
    return {
        "name": f"pto.{entry.name}",
        "mnemonic": entry.name.upper(),
        "category": category_for(entry),
        "instruction_set_path": list(entry.sections),
        "summary": summary,
        "syntax": first_code_block(syntax),
        "cpp_intrinsic": first_code_block(cpp_intrinsic),
        "operands": operands,
        "outputs": extract_operands(outputs),
        "constraints": constraints,
        "illegal_cases": exceptions,
        "target_profile_restrictions": target_restrictions,
        "examples": [first_code_block(examples)] if first_code_block(examples) else [],
        "sources": [str(entry.path.relative_to(REPO_ROOT)) if entry.path.exists() else str(entry.path)],
    }


def build_cards_from_nav() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cards_by_name: dict[str, dict[str, Any]] = {}
    duplicate_sources: dict[str, list[str]] = {}
    entries = load_nav_entries()
    for entry in entries:
        card = build_card_from_nav(entry)
        if entry.name in cards_by_name:
            cards_by_name[entry.name]["sources"].extend(card["sources"])
            duplicate_sources.setdefault(entry.name, cards_by_name[entry.name]["sources"])
            continue
        cards_by_name[entry.name] = card
    cards = sorted(cards_by_name.values(), key=lambda card: card["name"])
    manifest = {
        "schema_version": 1,
        "source": "docs/mkdocs/mkdocs.yml",
        "card_count": len(cards),
        "nav_entry_count_after_filter": len(entries),
        "excluded_nav_sections": sorted(EXCLUDED_NAV_SECTIONS),
        "duplicate_instruction_sources": duplicate_sources,
        "cards": [card["name"] for card in cards],
    }
    return cards, manifest


def build_cards_from_remote_index(base_url: str, max_pages: int = 80) -> dict[str, Any]:
    pages = crawl_docs(base_url, max_pages=max_pages)
    names = sorted({match.group(1).lower() for page in pages for match in INSTRUCTION_RE.finditer(page["text"])})
    return {
        "page_count": len(pages),
        "instruction_mentions": len(names),
        "instructions": [f"pto.{name}" for name in names],
    }


def card_filename(card_name: str) -> str:
    return TOKEN_RE.sub("_", card_name.removeprefix("pto.").lower()).strip("_") + ".json"


def write_cards(cards: list[dict[str, Any]], output_dir: Path, manifest: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in output_dir.glob("*.json"):
        old_file.unlink()
    for card in cards:
        (output_dir / card_filename(card["name"])).write_text(
            json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_from_site(base_url: str, output_dir: Path, max_pages: int = 80) -> dict[str, Any]:
    cards, manifest = build_cards_from_nav()
    remote_result: dict[str, Any] | None = None
    fetch_error = None
    try:
        remote_result = build_cards_from_remote_index(base_url, max_pages=max_pages)
    except Exception as exc:
        fetch_error = str(exc)
    manifest["docs_url"] = base_url
    manifest["remote_index"] = remote_result
    manifest["remote_fetch_error"] = fetch_error
    write_cards(cards, output_dir, manifest)
    return {
        "base_url": base_url,
        "source": "mkdocs_nav_with_remote_index_probe",
        "fetch_error": fetch_error,
        "remote_index": remote_result,
        "card_count": len(cards),
        "output_dir": str(output_dir),
    }
