"""Extract satellite info from converted FCC filings with an Ollama model.

Library use:   from satellite_pipeline import rag
CLI use:       python -m satellite_pipeline.gemma_workflow [model] [embed] [parent] [output]
"""
import argparse
import os
import sys
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

DEFAULT_NUM_CTX = 16384
PROMPT_RESERVE = 2500                            # tokens kept free for the prompt and the answer


class Satellite(BaseModel):
    satellite_name: str
    frequency_ranges: list[str] = Field(default_factory=list,
                                        description="'low-high UNIT', e.g. '1525-1559 MHz'")
    active_or_inactive: Literal["Active", "Inactive", "Not specified"]
    source_or_company_origin: Optional[str] = Field(None, description="Owning company, not a country")
    orbit_type: Optional[str] = None


INTRO = ("Below are documents from one FCC satellite filing, converted from PDF to markdown. "
         "Layouts differ between filings. Each document starts with '### FILE: <name>'.\n\n")
TASK = ("\n\n---\nUsing only the text above, give the satellite name, every frequency range "
        "('low-high UNIT'; forms often list a band as two numbers 'low high' under an MHz heading), "
        "Active/Inactive/Not specified, the owning company (not a country) and the orbit type. "
        "Use null or [] when not stated. Do not guess.")
NOTES = ("\n\n---\nWrite short notes: name, every frequency range copied exactly, status, "
         "owning company, orbit type. Write 'not stated' if absent.")


def _ask(client, model, num_ctx, prompt, schema=None):
    kw = dict(model=model, messages=[{"role": "user", "content": prompt}], format=schema,
              options={"temperature": 0, "num_ctx": num_ctx})
    try:
        r = client.chat(think=False, **kw)
    except TypeError:                            # older client without `think`
        r = client.chat(**kw)
    if (r.prompt_eval_count or 0) >= num_ctx - 8:
        print("  [WARN] context full, input likely truncated", file=sys.stderr)
    return (r.message.content or "").strip()


def _chunks(text, limit):                        # split on blank lines so tables stay whole
    out, cur = [], ""
    for block in text.split("\n\n"):
        if cur and len(cur) + len(block) > limit:
            out.append(cur)
            cur = ""
        cur += block + "\n\n"
    return out + [cur]


def _extract(client, model, num_ctx, folder, retries=3):
    limit = (num_ctx - PROMPT_RESERVE) * 3       # max input characters per call
    files = [f for f in sorted(folder.rglob("*"))
             if f.is_file() and f.suffix.lower() == ".md"]
    text = f"Filing folder: {folder.name}\n\n" + "\n\n".join(
        f"### FILE: {f.name}\n{f.read_text(errors='replace')}" for f in files)
    if len(text) > limit:                        # too long: take notes per part, then merge
        text = "\n\n".join(_ask(client, model, num_ctx, INTRO + c + NOTES)
                           for c in _chunks(text, limit))
    last_error = None
    for _ in range(retries):
        try:
            raw = _ask(client, model, num_ctx, INTRO + text + TASK, Satellite.model_json_schema())
            return Satellite.model_validate_json(raw)
        except Exception as e:                   # bad JSON or a transient Ollama error: retry
            last_error = e
    print(f"  [{folder.name}] last error: {last_error}", file=sys.stderr)
    return None


def extract_satellites(parent, output, model="gemma4:26b", embed="gemma",
                       base_url=None, timeout=1200.0, context_window=DEFAULT_NUM_CTX):
    """Run the extraction on every subfolder of `parent`; write one result file per
    subfolder into `output` and return the list of files written.

    `embed` is only used in the output file name (kept for compatibility).
    """
    from ollama import Client                    # imported here so the package imports fast

    base_url = base_url or os.environ.get("OLLAMA_BASE_URL")
    if not base_url:
        raise RuntimeError("Pass base_url or set OLLAMA_BASE_URL.")
    client = Client(host=base_url, timeout=timeout)

    parent, out_dir = Path(parent), Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for sub in sorted(p for p in parent.iterdir()
                      if p.is_dir() and p.resolve() != out_dir.resolve()):
        sat = _extract(client, model, context_window, sub)
        if sat is None:
            print(f"[FAIL] {sub.name}", file=sys.stderr)
            continue
        path = out_dir / f"{sub.name}.{embed}_{model.replace(':', '_')}.txt"
        path.write_text(sat.model_dump_json(indent=2))
        written.append(path)
        print(f"[OK] {sub.name}")
    return written


def main(argv=None):
    p = argparse.ArgumentParser(description="Extract satellite info from documents with an Ollama model")
    # Same positional order as before: model embed parent output
    p.add_argument("model", nargs="?", default="gemma4:26b",
                   help="LLM name in Ollama (default: %(default)s)")
    p.add_argument("embed", nargs="?", default="gemma",
                   help="label used in output file names (default: %(default)s)")
    p.add_argument("parent", nargs="?", default=".",
                   help="parent folder containing the input subfolders (default: %(default)s)")
    p.add_argument("output", nargs="?", default="output",
                   help="folder for the JSON results (default: %(default)s)")
    p.add_argument("--num-ctx", type=int, default=int(os.environ.get("NUM_CTX", DEFAULT_NUM_CTX)),
                   help="context window (default: NUM_CTX env var or %(default)s)")
    a = p.parse_args(argv)
    extract_satellites(a.parent, a.output, model=a.model, embed=a.embed, context_window=a.num_ctx)


if __name__ == "__main__":
    main()