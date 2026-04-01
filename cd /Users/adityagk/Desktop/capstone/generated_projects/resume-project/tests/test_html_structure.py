import pytest
import os
from bs4 import BeautifulSoup

def get_html_content():
    # Expects test to be run from project root
    file_path = 'public/index.html'
    assert os.path.exists(file_path), f"File not found at {file_path}"
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def test_html_has_lang_attribute():
    soup = BeautifulSoup(get_html_content(), 'html.parser')
    assert soup.html.has_attr('lang'), "The <html> tag must have a 'lang' attribute for accessibility."

def test_html_has_main_sections():
    soup = BeautifulSoup(get_html_content(), 'html.parser')
    assert soup.find('header') is not None, "Document missing <header> section."
    assert soup.find('main') is not None, "Document missing <main> section."
    assert soup.find('footer') is not None, "Document missing <footer> section."

def test_has_h1_header():
    soup = BeautifulSoup(get_html_content(), 'html.parser')
    h1_tags = soup.find_all('h1')
    assert len(h1_tags) == 1, "Document should have exactly one <h1> for the main title."

def test_has_sections():
    soup = BeautifulSoup(get_html_content(), 'html.parser')
    sections = soup.find_all('section')
    assert len(sections) >= 2, "Document should contain at least two <section> elements for structured content."
