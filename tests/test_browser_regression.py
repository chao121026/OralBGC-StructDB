import socket
import sqlite3
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest


PROTEIN_ID = "PHRC|CM_NA0009364731_S111_metawrap_50_10_bins_metawrap_50_10_bins_bin.14_CM_NA0009364731_S111_contig_247_region001_cds11"


def _representative_bgc_id() -> str:
    conn = sqlite3.connect("app/data/phrc_bgcstructdb.sqlite")
    row = conn.execute("select public_bgc_id from bgc_summary where public_bgc_id is not null order by public_bgc_id limit 1").fetchone()
    assert row
    return row[0]


def open_page(page, url: str) -> None:
    response = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    assert response is not None, f"Navigation returned no response for {url}"
    assert response.ok, (
        f"Navigation failed: {response.status} "
        f"{response.status_text} for {url}"
    )
    assert page.locator("main").count() == 1, f"Main content missing on {page.url}"
    page.locator("main").wait_for(state="visible", timeout=30_000)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
      for _ in range(60):
          try:
              with urlopen(base_url + "/api/health", timeout=0.5) as response:
                  if response.status == 200:
                      break
          except Exception:
              time.sleep(0.25)
      else:
          pytest.fail("uvicorn test server did not start")
      yield base_url
    finally:
      proc.terminate()
      try:
          proc.wait(timeout=5)
      except subprocess.TimeoutExpired:
          proc.kill()


@pytest.fixture(scope="module")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("Playwright is not installed")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Playwright Chromium cannot launch in this environment: {exc}")
        yield browser
        browser.close()


def _assert_no_horizontal_overflow(page):
    dimensions = page.evaluate(
        """
        () => ({
            viewportWidth: window.innerWidth,
            documentWidth: document.documentElement.scrollWidth,
            bodyWidth: document.body.scrollWidth
        })
        """
    )
    assert dimensions["documentWidth"] <= dimensions["viewportWidth"] + 1, dimensions
    assert dimensions["bodyWidth"] <= dimensions["viewportWidth"] + 1, dimensions


@pytest.mark.parametrize("path", ["/", "/proteins", "/downloads", f"/proteins/{PROTEIN_ID}"])
def test_key_pages_do_not_overflow_mobile(browser, live_server, path):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        open_page(page, live_server + path)
        if path == "/":
            page.locator(".site-header").wait_for(state="visible", timeout=30_000)
        elif path == "/proteins":
            page.locator(".mobile-cards").first.wait_for(state="visible", timeout=30_000)
        elif path.startswith("/proteins/"):
            page.locator(".structure-viewer").wait_for(state="visible", timeout=30_000)
        _assert_no_horizontal_overflow(page)
    finally:
        page.close()


def test_mobile_navigation_drawer_is_controlled_by_button_escape_and_overlay(browser, live_server):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        open_page(page, live_server + "/")
        page.locator(".site-header").wait_for(state="visible", timeout=30_000)
        assert page.locator("body.nav-open").count() == 0
        page.locator("#mobile-menu-toggle").click()
        assert page.locator("body.nav-open").count() == 1
        assert page.locator("#nav-overlay:not([hidden])").count() == 1
        page.keyboard.press("Escape")
        assert page.locator("body.nav-open").count() == 0
    finally:
        page.close()


def test_structure_viewer_canvas_stays_inside_viewer(browser, live_server):
    page = browser.new_page(viewport={"width": 768, "height": 1024})
    try:
        open_page(page, live_server + f"/proteins/{PROTEIN_ID}")
        page.locator(".structure-viewer").wait_for(state="visible", timeout=30_000)
        page.wait_for_selector(".structure-ready canvas, .structure-error", timeout=15000)
        _assert_no_horizontal_overflow(page)
        canvas_outside = page.locator("body > canvas").count()
        assert canvas_outside == 0
        viewer_box = page.locator("#viewer").bounding_box()
        assert viewer_box and viewer_box["width"] > 300 and viewer_box["height"] > 300
        assert page.locator(".viewer-controls button").count() >= 6
    finally:
        page.close()


def test_visual_polish_browser_contracts(browser, live_server):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        open_page(page, live_server + "/")
        page.locator(".site-header").wait_for(state="visible", timeout=30_000)
        header_box = page.locator(".site-header").bounding_box()
        assert header_box is not None
        assert header_box["height"] <= 76
    finally:
        page.close()

    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        open_page(page, live_server + "/proteins")
        page.locator(".mobile-cards").first.wait_for(state="visible", timeout=30_000)
        cards = page.locator(".data-table.mobile-cards tbody tr")
        assert cards.count() > 0, f"No mobile protein cards were rendered on {page.url}"
        first_card = cards.first
        first_card.wait_for(state="visible", timeout=30_000)
        card_box = first_card.bounding_box()
        assert card_box is not None
        assert card_box["height"] < 280, card_box
        assert first_card.locator(".protein-card-extra").count() == 1
    finally:
        page.close()

    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        open_page(page, live_server + f"/proteins/{PROTEIN_ID}")
        page.locator(".structure-viewer").wait_for(state="visible", timeout=30_000)
        assert page.locator(".identifier-row .copy-button").count() >= 2
    finally:
        page.close()

    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        open_page(page, live_server + f"/bgcs/{_representative_bgc_id()}")
        page.locator(".gene-track-wrap").wait_for(state="visible", timeout=30_000)
        scrollable = page.locator(".gene-track-wrap").evaluate("el => el.scrollWidth > el.clientWidth")
        assert scrollable
    finally:
        page.close()
