#!/usr/bin/env python3
"""Capture four-page checkpoint screenshots with optional Playwright.

Install only in development:
    pip install playwright
    playwright install chromium
"""
import argparse
import asyncio
import os
import sqlite3
from pathlib import Path

VIEWPORTS = [(1440, 1000), (768, 1024), (390, 844)]
STATIC_PAGES = [
    ("home", "/"),
    ("mags", "/mags"),
    ("bgcs", "/bgcs"),
    ("gcfs", "/gcfs"),
    ("proteins", "/proteins"),
    ("structures", "/structures"),
    ("search", "/search?q=terpene"),
    ("networks", "/networks"),
    ("downloads", "/downloads"),
    ("help", "/help"),
    ("about", "/about"),
    ("contact", "/contact"),
]


def representative_protein(db_path: Path) -> str:
    conn = sqlite3.connect(db_path)
    row = conn.execute("""
        select public_protein_id from bgc_protein_summary
        where structure_available='1' and af3_qc_available='1' and foldseek_annotation_available='1'
        order by public_protein_id limit 1
    """).fetchone()
    if not row:
        raise SystemExit("No representative protein with structure, AF3 QC, and Foldseek annotation found.")
    return row[0]


def representative_records(db_path: Path) -> dict[str, str]:
    conn = sqlite3.connect(db_path)
    records = {
        "protein-detail": "/proteins/" + representative_protein(db_path),
    }
    for name, table, col, route in [
        ("mag-detail", "mag_summary", "public_mag_id", "/mags/"),
        ("bgc-detail", "bgc_summary", "public_bgc_id", "/bgcs/"),
        ("gcf-detail", "bigscape_gcf_summary", "public_gcf_id", "/gcfs/"),
    ]:
        row = conn.execute(f"select {col} from {table} where coalesce({col}, '') != '' order by {col} limit 1").fetchone()
        if row:
            records[name] = route + row[0]
    return records


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--db", default=os.getenv("DATABASE_PATH", "app/data/phrc_bgcstructdb.sqlite"))
    parser.add_argument("--out", default="artifacts/screenshots")
    args = parser.parse_args()

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise SystemExit("Playwright is not installed. Run: pip install playwright && playwright install chromium") from exc

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pages = STATIC_PAGES + list(representative_records(Path(args.db)).items())

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for width, height in VIEWPORTS:
            page = await browser.new_page(viewport={"width": width, "height": height})
            for name, path in pages:
                await page.goto(args.base_url.rstrip("/") + path, wait_until="networkidle")
                await page.screenshot(path=out / f"{name}-{width}x{height}.png", full_page=True)
            await page.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
