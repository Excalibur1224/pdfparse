import argparse
from pathlib import Path

SUFFIX = ".convert.md"


def convert_folder(root="fcc_recent_filings", overwrite=False):
    """Convert every file in every subfolder of `root`. Returns the markdown files written."""
    from docling.document_converter import DocumentConverter   # heavy import, kept local
    converter = DocumentConverter()

    written = []
    for src in sorted(Path(root).glob("*/*")):
        out = src.with_name(src.name + SUFFIX)
        if not src.is_file() or src.name.endswith(SUFFIX) or (out.exists() and not overwrite):
            continue
        try:
            converter.convert(str(src)).document.save_as_markdown(out)
            written.append(out)
            print(f"[OK] {src}")
        except Exception as e:                 # one bad file shouldn't stop the batch
            print(f"[FAIL] {src}: {e}")
    return written


def main(argv=None):
    p = argparse.ArgumentParser(description="Convert filing documents to markdown with docling")
    p.add_argument("root", nargs="?", default="fcc_recent_filings")
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args(argv)
    convert_folder(a.root, overwrite=a.overwrite)


if __name__ == "__main__":
    main()