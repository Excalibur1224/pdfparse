from docling.document_converter import DocumentConverter
import os
directory = "fcc_recent_filings"

for source in os.scandir(directory):  
    folder = source.path
    for entry in os.scandir(folder):
        file = entry.path
        converter = DocumentConverter()
        converted_document = converter.convert(file).document
        # print(converted_document.export_to_markdown())

        md_path = os.path.join(folder, entry.name+"convert.md")
        filename = entry.name + "convert.md"
        converted_document.save_as_markdown(md_path)

        json_path = os.path.join(folder, entry.name+"convert.json")
        filename = entry.name + "convert.json"
        converted_document.save_as_json(json_path)
