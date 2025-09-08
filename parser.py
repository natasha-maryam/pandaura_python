import pypdf
import google.generativeai as genai
from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI


load_dotenv()
google_api_key = os.getenv("GEMINI_API_KEY")

def parse_pdf(file_path):
    pdf_file = open(file_path, 'rb')
    pdf_reader = pypdf.PdfReader(pdf_file)
    text = ""
    for page_num in range(pdf_reader.get_num_pages()):
        page = pdf_reader.get_page(page_num)
        text += page.extract_text()
    pdf_file.close()
    return text

def write_to_file(text, file_name):
    with open(file_name, 'w') as file:
        file.write(text)

file_path = '/home/ambreen/Downloads/pandura-chat/PLC Functional Design Specification .pdf'
parsed_text = parse_pdf(file_path)
write_to_file(parsed_text, 'parsed_text.txt')






