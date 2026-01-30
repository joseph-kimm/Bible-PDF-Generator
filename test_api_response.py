#!/usr/bin/env python3
"""
Test script to examine the NLT API response structure for section headers
"""

import requests
from bs4 import BeautifulSoup

API_BASE_URL = "https://api.nlt.to/api/passages"
API_KEY = "a28921c8-45d5-40e1-b11a-90723f427a72"

# Fetch Jonah chapter 1 to see section headers
url = f"{API_BASE_URL}?key={API_KEY}&version=NLT&ref=Jonah+1"

print("Fetching Jonah chapter 1...")
response = requests.get(url, timeout=30)
response.raise_for_status()

# Save raw HTML to file for inspection
with open('jonah_1_response.html', 'w', encoding='utf-8') as f:
    f.write(response.text)

print("Saved raw HTML to jonah_1_response.html")

# Parse and print structure
soup = BeautifulSoup(response.text, 'html.parser')

print("\n=== HTML Structure ===")
print("\nAll tags found:")
for tag in soup.find_all():
    if tag.name not in ['html', 'body', 'br']:
        print(f"  <{tag.name}> {dict(tag.attrs)} - Text: {tag.get_text(strip=True)[:80]}")

print("\n=== Verse Export Tags ===")
for verse_tag in soup.find_all('verse_export'):
    print(f"\nVerse {verse_tag.get('ch')}:{verse_tag.get('vn')}")
    print(f"  HTML: {str(verse_tag)[:200]}...")

    # Check for section headers
    for child in verse_tag.children:
        if hasattr(child, 'name'):
            print(f"  Child: <{child.name}> {dict(child.attrs) if hasattr(child, 'attrs') else ''}")
