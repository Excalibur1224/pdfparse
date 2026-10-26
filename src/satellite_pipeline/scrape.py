"""Download documents from FCC ICFS "Recent Filings" with Selenium.

Library use:   from satellite_pipeline import download_filings
CLI use:       python -m satellite_pipeline.scrape [root] [--no-headless] [--max-filings N]
"""
import argparse
import os
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

START_URL = "https://fccprod.servicenowservices.com/icfs"
WAIT_SECONDS = 60
DOWNLOAD_TIMEOUT = 120
RENDER_DELAY = 6

FILING_PATTERN = re.compile(r"\b[A-Za-z0-9]{2,10}-[A-Za-z0-9/]{1,10}-\d{8}-\d{5}\b")
_LOWER = "translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"


# ---------------------------------------------------------------- helpers
def _text(e):
    try:
        return re.sub(r"\s+", " ", e.text or "").strip()
    except Exception:
        return ""


def _visible(e):
    try:
        return e.is_displayed()
    except Exception:
        return False


def _safe(s):
    return re.sub(r"\s+", " ", re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s)).strip(" .")


def _unique(p):
    if not p.exists():
        return p
    n = 1
    while (q := p.with_name(f"{p.stem}_{n}{p.suffix}")).exists():
        n += 1
    return q


def _wait_page(d):
    WebDriverWait(d, WAIT_SECONDS).until(
        lambda x: x.execute_script("return document.readyState") == "complete")


def _wait_download(directory, before):
    end = time.time() + DOWNLOAD_TIMEOUT
    while time.time() < end:
        files = set(directory.iterdir())
        partial = [x for x in files if x.name.endswith(".crdownload")]
        done = [x for x in files - before if x.is_file() and not x.name.endswith(".crdownload")]
        if done and not partial:
            return max(done, key=lambda x: x.stat().st_mtime)
        time.sleep(.5)
    raise TimeoutException("Download timeout")


def _switch_new_window(d, old, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        new = [h for h in d.window_handles if h not in old]
        if new:
            d.switch_to.window(new[0])
            return True
        time.sleep(.5)
    return False


def _click(d, element):
    d.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    time.sleep(1)
    try:
        d.execute_script("arguments[0].click();", element)
    except Exception:
        element.click()


# ---------------------------------------------------------------- page logic
def _find_recent(d):
    xpaths = [
        f"//*[self::a or self::button][contains({_LOWER},'recent filings')]",
        f"//*[@role='tab'][contains({_LOWER},'recent filings')]",
        "//*[contains(@aria-label,'Recent Filings')]",
        "//*[contains(@title,'Recent Filings')]",
    ]
    for x in xpaths:
        try:
            for e in d.find_elements(By.XPATH, x):
                if _visible(e):
                    return e
        except Exception:
            pass
    return None


def _go_recent(d):
    print("Navigating to Recent Filings...")
    e = _find_recent(d)
    if not e:
        time.sleep(3)
        e = _find_recent(d)
    if not e:
        print("Recent Filings link not found.")
        return False
    old = set(d.window_handles)
    try:
        _click(d, e)
    except Exception:
        return False
    _switch_new_window(d, old, 10)
    _wait_page(d)
    time.sleep(RENDER_DELAY)
    print("Recent Filings loaded:", d.current_url)
    return True


def _find_table(d):
    for _ in range(15):
        for e in d.find_elements(By.XPATH, "//table|//*[@role='grid']"):
            try:
                if _visible(e):
                    s = _text(e).lower()
                    if "file number" in s and "applicant name" in s:
                        return e
            except Exception:
                pass
        time.sleep(2)
    return None


def _get_rows(table):
    result, seen = [], set()
    for selector in (".//tr", ".//*[@role='row']"):
        try:
            for r in table.find_elements(By.XPATH, selector):
                s = _text(r)
                if s and s not in seen:
                    seen.add(s)
                    result.append(r)
        except Exception:
            pass
    return result


def _find_filing_element(row, number):
    try:
        elements = row.find_elements(By.XPATH, ".//*[contains(.,%s)]" % repr(number))
    except Exception:
        elements = []
    candidates = [e for e in elements if _visible(e) and number in _text(e)]
    for e in candidates:
        try:
            role = (e.get_attribute("role") or "").lower()
            cls = (e.get_attribute("class") or "").lower()
            if (e.tag_name.lower() in ("a", "button") or role in ("link", "button")
                    or e.get_attribute("href") or e.get_attribute("onclick")
                    or "link" in cls or "click" in cls):
                return e
        except Exception:
            pass
    return candidates[-1] if candidates else None


def _get_filings(d):
    table = _find_table(d)
    if not table:
        raise RuntimeError("Recent Filings table not found.")
    filings, seen = [], set()
    for i, row in enumerate(_get_rows(table), 1):
        s = _text(row)
        m = FILING_PATTERN.search(s)
        if m and m.group(0) not in seen:
            seen.add(m.group(0))
            filings.append({"number": m.group(0), "text": s})
            print(f"ROW {i}: {m.group(0)} MATCH")
    return filings


def _find_filing(d, number):
    table = _find_table(d)
    if not table:
        return None
    for row in _get_rows(table):
        if number in _text(row):
            return _find_filing_element(row, number)
    return None


def _get_documents(d):
    result, seen = [], set()
    for selector in ("//a[contains(@href,'sys_attachment')]", "//a[contains(@href,'attachment')]",
                     "//a[contains(@href,'download')]", "//a[@download]"):
        try:
            for a in d.find_elements(By.XPATH, selector):
                href = a.get_attribute("href")
                if _visible(a) and href and href not in seen:
                    seen.add(href)
                    result.append({"text": _text(a) or "document", "href": href})
        except Exception:
            pass
    return result


def _return_home(d):
    print("Returning to ICFS home...")
    d.get(START_URL)
    _wait_page(d)
    time.sleep(RENDER_DELAY)
    print("Home loaded:", d.current_url)


def _make_driver(download_root, headless):
    o = Options()
    binary = os.environ.get("CHROME_BINARY")      # optional, e.g. /opt/google/chrome/chrome
    if binary:
        o.binary_location = binary
    o.add_experimental_option("prefs", {
        "download.default_directory": str(download_root.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
    })
    if headless:
        o.add_argument("--headless=new")
        o.add_argument("--window-size=1920,1080")  # --start-maximized does nothing headless
    else:
        o.add_argument("--start-maximized")
    o.add_argument("--disable-notifications")
    o.add_argument("--disable-gpu")
    o.add_argument("--no-sandbox")                 # needed in containers or when running as root
    o.add_argument("--disable-dev-shm-usage")      # avoids crashes when /dev/shm is small
    return webdriver.Chrome(service=Service(), options=o)


# ---------------------------------------------------------------- public API
def fetch_recent_filings(download_root="fcc_recent_filings", headless=True, max_filings=None):
    """Download every document of the recent filings into one subfolder per filing.

    Returns the list of saved file paths.
    """
    root = Path(download_root)
    root.mkdir(parents=True, exist_ok=True)
    saved = []
    d = _make_driver(root, headless)
    try:
        d.get(START_URL)
        _wait_page(d)
        time.sleep(RENDER_DELAY)
        if not _go_recent(d):
            raise RuntimeError("Could not navigate to Recent Filings.")

        filings = _get_filings(d)
        if max_filings:
            filings = filings[:max_filings]
        print("\nFILINGS FOUND:", len(filings))
        for i, f in enumerate(filings, 1):
            print(f"{i}. {f['number']} | {f['text']}")

        for index, f in enumerate(filings, 1):
            print("\n" + "=" * 75)
            print(f"PROCESSING FILING {index}/{len(filings)}")
            print(f["text"])
            print("=" * 75)

            if index > 1:                           # back to the list for the next filing
                _return_home(d)
                if not _go_recent(d):
                    raise RuntimeError("Could not re-navigate to Recent Filings.")

            element = _find_filing(d, f["number"])
            if not element:
                print("Could not find filing:", f["number"])
                continue

            folder = root / _safe(f"{index:03d}_{f['text']}")
            folder.mkdir(parents=True, exist_ok=True)
            recent_window = d.current_window_handle
            old_handles = set(d.window_handles)

            try:
                _click(d, element)
            except Exception as e:
                print("CLICK ERROR:", e)
                continue

            _switch_new_window(d, old_handles, 10)
            try:
                WebDriverWait(d, 20).until(
                    lambda x: x.current_url != START_URL or len(x.window_handles) > 1)
            except Exception:
                pass
            _wait_page(d)
            time.sleep(RENDER_DELAY)
            filing_window = d.current_window_handle
            print("Filing page:", d.current_url)

            docs = _get_documents(d)
            print("Documents found:", len(docs))
            for n, doc in enumerate(docs, 1):
                print(f"Downloading {n}/{len(docs)}: {doc['text']}")
                before = set(root.iterdir())
                old = set(d.window_handles)
                try:
                    d.execute_script("window.open(arguments[0],'_blank');", doc["href"])
                    if not _switch_new_window(d, old, 15):
                        raise RuntimeError("Download tab did not open.")
                    time.sleep(2)
                    downloaded = _wait_download(root, before)
                    destination = _unique(folder / downloaded.name)
                    downloaded.rename(destination)
                    saved.append(destination)
                    print("SAVED:", destination)
                    d.close()
                    d.switch_to.window(filing_window)
                except Exception as e:
                    print("DOWNLOAD ERROR:", e)
                    try:
                        while len(d.window_handles) > 1:
                            d.switch_to.window(d.window_handles[-1])
                            d.close()
                        d.switch_to.window(filing_window)
                    except Exception:
                        pass

            print(f"Finished filing {f['number']}.")
            if filing_window != recent_window:
                try:
                    d.switch_to.window(filing_window)
                    d.close()
                except Exception:
                    pass
            if recent_window in d.window_handles:
                d.switch_to.window(recent_window)

        print("\n" + "=" * 75)
        print("DOWNLOAD COMPLETE")
        print("Filings processed:", len(filings))
        print("Output:", root.resolve())
        print("=" * 75)
    finally:
        print("Closing browser...")
        d.quit()
    return saved


def main(argv=None):
    p = argparse.ArgumentParser(description="Download recent FCC ICFS filings")
    p.add_argument("root", nargs="?", default="fcc_recent_filings")
    p.add_argument("--no-headless", action="store_true", help="show the browser window")
    p.add_argument("--max-filings", type=int, default=None)
    a = p.parse_args(argv)
    headless = not a.no_headless and os.environ.get("HEADLESS", "1") == "1"
    fetch_recent_filings(a.root, headless=headless, max_filings=a.max_filings)


if __name__ == "__main__":
    main()