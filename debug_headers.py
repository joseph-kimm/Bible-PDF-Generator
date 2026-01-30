#!/usr/bin/env python3
"""Debug script to check section header extraction"""

import csv
import re

CSV_FILE = "biblia_ntv_.csv"

def extract_spanish_section_header(text):
    """Extract section header from Spanish text"""
    pattern = r'^(.*?[a-záéíóúñ])\s+(El|La|Los|Las|Un|Una|Cuando|Entonces|Y|Pero|Así|Después|Ahora|Al|Del|En|Por)\s+[A-ZÁÉÍÓÚÑ]'
    match = re.match(pattern, text)
    if match:
        header = match.group(1).strip()
        if len(header) < 80 and len(header) > 10:
            remaining = text[len(header):].strip()
            return header, remaining
    return None, text

# Read Jonah verses
with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['libro'] == 'Jonás':
            text = row['texto'].strip()
            verse_num = row['verso']

            # Remove verse number from start
            if text.startswith(verse_num + ' '):
                text = text[len(verse_num) + 1:].strip()

            header, remaining = extract_spanish_section_header(text)

            if header:
                print(f"\nChapter {row['capitulo']}, Verse {verse_num}:")
                print(f"  Header: {header}")
                print(f"  Remaining: {remaining[:100]}...")
            elif row['verso'] == '1':  # First verse of each chapter
                print(f"\nChapter {row['capitulo']}, Verse {verse_num}: NO HEADER DETECTED")
                print(f"  Text: {text[:150]}...")
