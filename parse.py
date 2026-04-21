from docling.document_converter import DocumentConverter
import os
directory = "pdfs"

for entry in os.scandir(directory):  
    source = entry.path
    converter = DocumentConverter()
    converted_document = converter.convert(source).document

    print(converted_document.export_to_markdown())
    filename = entry.name + "convert.json"
    converted_document.save_as_json("parsed_pdfs/"+filename)

# source = "https://docs.fcc.gov/public/attachments/DOC-418875A2.pdf"
# converter = DocumentConverter()
# converted_document = converter.convert(source).document
# print(converted_document.export_to_markdown())
# filename = "convert.json"
# converted_document.save_as_json(filename)