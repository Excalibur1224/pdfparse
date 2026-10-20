"""satellite_pipeline: scrape FCC filings -> convert -> extract with an LLM -> merge into CSV."""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

__version__ = "0.2.0"
__all__ = ["scrape", "parse", "gemma_workflow", "insert", "run_all"]

DEFAULT_ROOT = "fcc_recent_filings"
DEFAULT_RAG_OUT = "rag_output"
DEFAULT_CSV = "satellites.csv"


def _ollama_url(base_url=None):
    """Resolve and validate the Ollama URL (argument first, then OLLAMA_BASE_URL)."""
    try:
        url = (base_url or os.environ["OLLAMA_BASE_URL"]).strip()
    except KeyError:
        raise RuntimeError("OLLAMA_BASE_URL is not set. "
                           "Example: export OLLAMA_BASE_URL=http://127.0.0.1:11434") from None
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError(f"Invalid Ollama URL: {url!r}")
    return url.rstrip("/")


def scrape(download_root=DEFAULT_ROOT, headless=True, max_filings=None):
    """Download recent FCC ICFS filings. Returns the list of saved files."""
    from .scrape import fetch_recent_filings          # selenium loads only here
    return fetch_recent_filings(Path(download_root), headless=headless,
                                max_filings=max_filings)


def convert(root=DEFAULT_ROOT, overwrite=False):
    """Convert downloaded files to markdown with docling."""
    from .parse import convert_folder               # docling/torch load only here
    return convert_folder(Path(root), overwrite=overwrite)


def rag(parent=DEFAULT_ROOT, output=DEFAULT_RAG_OUT, model="llama3.1:8b",
        embed="mock", base_url=None, timeout=1200.0, context_window=16384):
    """Run the Ollama extraction on every subfolder. Returns the output files."""
    from .gemma_workflow import extract_satellites               # llama-index loads only here
    return extract_satellites(Path(parent), Path(output), model=model, embed=embed,
                              base_url=_ollama_url(base_url), timeout=timeout,
                              context_window=context_window)


def merge(csv_file=DEFAULT_CSV, inputs=(DEFAULT_RAG_OUT,), company=None,
          plain_bw=False, create=True, backup=True):
    """Merge LLM output (JSON after the first ```) into the CSV, one row per band."""
    from .insert import merge_into_csv                 # standard library only
    return merge_into_csv(Path(csv_file), [Path(i) for i in inputs], company=company,
                          plain_bw=plain_bw, create=create, backup=backup)


def run_all(root=DEFAULT_ROOT, output=DEFAULT_RAG_OUT, csv_file=DEFAULT_CSV,
            headless=True, max_filings=None, formats=("md", "json"),
            model="llama3.1:8b", embed="mock", company=None, **rag_options):
    """Run every step in order."""
    scrape(root, headless=headless, max_filings=max_filings)
    convert(root, formats=formats)
    rag(root, output, model=model, embed=embed, **rag_options)
    return merge(csv_file, [output], company=company)