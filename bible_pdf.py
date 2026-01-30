#!/usr/bin/env python3
"""
Bilingual Bible PDF Generator
Creates side-by-side English (NLT) and Spanish (NTV) Bible PDFs with traditional formatting.

Usage:
    python bible_pdf.py Genesis
    python bible_pdf.py John
    python bible_pdf.py "1 John"
"""

import sys
import time
import csv
import os
import requests
from bs4 import BeautifulSoup
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.colors import HexColor

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# API Configuration
API_BASE_URL = "https://api.nlt.to/api/passages"
API_KEY = "a28921c8-45d5-40e1-b11a-90723f427a72"  # NLT API key
REQUEST_DELAY = 1.0  # Seconds between API requests
MAX_RETRIES = 3

# CSV File Configuration
CSV_FILE = "biblia_ntv_.csv"  # Spanish NTV Bible CSV file

# PDF Layout Configuration (all measurements in points; 1 inch = 72 points)
# A4 landscape for 2-up printing: 841.89 x 595.27 points
FULL_PAGE_WIDTH, FULL_PAGE_HEIGHT = landscape(A4)
PAGE_WIDTH = FULL_PAGE_WIDTH / 2  # Each "page" is half the width
PAGE_HEIGHT = FULL_PAGE_HEIGHT
MARGIN = 0.4 * inch  # 0.4" margins
COLUMN_GAP = 0.25 * inch  # Gap between English and Spanish columns
HEADER_HEIGHT = 0.3 * inch  # Space for header
HEADER_MARGIN = 0.15 * inch  # Space below header

# Typography Configuration
BOOK_TITLE_FONT = "Times-Bold"
BOOK_TITLE_SIZE = 20
CHAPTER_NUM_FONT = "Times-Bold"
CHAPTER_NUM_SIZE = 28
VERSE_NUM_FONT = "Times-Bold"
VERSE_NUM_SIZE = 10
BODY_FONT = "Times-Roman"
BODY_SIZE = 11
HEADER_FONT = "Times-Roman"
HEADER_SIZE = 9
LINE_SPACING = 1.3  # Multiplier for line height

# Color Configuration
CRIMSON = HexColor('#781c2e')  # Crimson color for titles

# Spacing Configuration
BOOK_TITLE_SPACING = 25  # Space below book title
CHAPTER_NUM_TOP_SPACING = 30  # Space above chapter number
CHAPTER_NUM_BOTTOM_SPACING = 5  # Space below chapter number
VERSE_SPACING = 4  # Space between verses

# ============================================================================
# BIBLE BOOK METADATA
# ============================================================================

# All 66 books of the Bible with chapter counts and API references
BIBLE_BOOKS = {
    'Genesis': {'chapters': 50, 'api_ref': 'Genesis'},
    'Exodus': {'chapters': 40, 'api_ref': 'Exodus'},
    'Leviticus': {'chapters': 27, 'api_ref': 'Leviticus'},
    'Numbers': {'chapters': 36, 'api_ref': 'Numbers'},
    'Deuteronomy': {'chapters': 34, 'api_ref': 'Deuteronomy'},
    'Joshua': {'chapters': 24, 'api_ref': 'Joshua'},
    'Judges': {'chapters': 21, 'api_ref': 'Judges'},
    'Ruth': {'chapters': 4, 'api_ref': 'Ruth'},
    '1 Samuel': {'chapters': 31, 'api_ref': '1+Samuel'},
    '2 Samuel': {'chapters': 24, 'api_ref': '2+Samuel'},
    '1 Kings': {'chapters': 22, 'api_ref': '1+Kings'},
    '2 Kings': {'chapters': 25, 'api_ref': '2+Kings'},
    '1 Chronicles': {'chapters': 29, 'api_ref': '1+Chronicles'},
    '2 Chronicles': {'chapters': 36, 'api_ref': '2+Chronicles'},
    'Ezra': {'chapters': 10, 'api_ref': 'Ezra'},
    'Nehemiah': {'chapters': 13, 'api_ref': 'Nehemiah'},
    'Esther': {'chapters': 10, 'api_ref': 'Esther'},
    'Job': {'chapters': 42, 'api_ref': 'Job'},
    'Psalms': {'chapters': 150, 'api_ref': 'Psalms'},
    'Proverbs': {'chapters': 31, 'api_ref': 'Proverbs'},
    'Ecclesiastes': {'chapters': 12, 'api_ref': 'Ecclesiastes'},
    'Song of Solomon': {'chapters': 8, 'api_ref': 'Song+of+Solomon'},
    'Isaiah': {'chapters': 66, 'api_ref': 'Isaiah'},
    'Jeremiah': {'chapters': 52, 'api_ref': 'Jeremiah'},
    'Lamentations': {'chapters': 5, 'api_ref': 'Lamentations'},
    'Ezekiel': {'chapters': 48, 'api_ref': 'Ezekiel'},
    'Daniel': {'chapters': 12, 'api_ref': 'Daniel'},
    'Hosea': {'chapters': 14, 'api_ref': 'Hosea'},
    'Joel': {'chapters': 3, 'api_ref': 'Joel'},
    'Amos': {'chapters': 9, 'api_ref': 'Amos'},
    'Obadiah': {'chapters': 1, 'api_ref': 'Obadiah'},
    'Jonah': {'chapters': 4, 'api_ref': 'Jonah'},
    'Micah': {'chapters': 7, 'api_ref': 'Micah'},
    'Nahum': {'chapters': 3, 'api_ref': 'Nahum'},
    'Habakkuk': {'chapters': 3, 'api_ref': 'Habakkuk'},
    'Zephaniah': {'chapters': 3, 'api_ref': 'Zephaniah'},
    'Haggai': {'chapters': 2, 'api_ref': 'Haggai'},
    'Zechariah': {'chapters': 14, 'api_ref': 'Zechariah'},
    'Malachi': {'chapters': 4, 'api_ref': 'Malachi'},
    'Matthew': {'chapters': 28, 'api_ref': 'Matthew'},
    'Mark': {'chapters': 16, 'api_ref': 'Mark'},
    'Luke': {'chapters': 24, 'api_ref': 'Luke'},
    'John': {'chapters': 21, 'api_ref': 'John'},
    'Acts': {'chapters': 28, 'api_ref': 'Acts'},
    'Romans': {'chapters': 16, 'api_ref': 'Romans'},
    '1 Corinthians': {'chapters': 16, 'api_ref': '1+Corinthians'},
    '2 Corinthians': {'chapters': 13, 'api_ref': '2+Corinthians'},
    'Galatians': {'chapters': 6, 'api_ref': 'Galatians'},
    'Ephesians': {'chapters': 6, 'api_ref': 'Ephesians'},
    'Philippians': {'chapters': 4, 'api_ref': 'Philippians'},
    'Colossians': {'chapters': 4, 'api_ref': 'Colossians'},
    '1 Thessalonians': {'chapters': 5, 'api_ref': '1+Thessalonians'},
    '2 Thessalonians': {'chapters': 3, 'api_ref': '2+Thessalonians'},
    '1 Timothy': {'chapters': 6, 'api_ref': '1+Timothy'},
    '2 Timothy': {'chapters': 4, 'api_ref': '2+Timothy'},
    'Titus': {'chapters': 3, 'api_ref': 'Titus'},
    'Philemon': {'chapters': 1, 'api_ref': 'Philemon'},
    'Hebrews': {'chapters': 13, 'api_ref': 'Hebrews'},
    'James': {'chapters': 5, 'api_ref': 'James'},
    '1 Peter': {'chapters': 5, 'api_ref': '1+Peter'},
    '2 Peter': {'chapters': 3, 'api_ref': '2+Peter'},
    '1 John': {'chapters': 5, 'api_ref': '1+John'},
    '2 John': {'chapters': 1, 'api_ref': '2+John'},
    '3 John': {'chapters': 1, 'api_ref': '3+John'},
    'Jude': {'chapters': 1, 'api_ref': 'Jude'},
    'Revelation': {'chapters': 22, 'api_ref': 'Revelation'},
}

# Spanish translations for book names
BOOK_NAMES_SPANISH = {
    'Genesis': 'Génesis', 'Exodus': 'Éxodo', 'Leviticus': 'Levítico',
    'Numbers': 'Números', 'Deuteronomy': 'Deuteronomio', 'Joshua': 'Josué',
    'Judges': 'Jueces', 'Ruth': 'Rut', '1 Samuel': '1 Samuel',
    '2 Samuel': '2 Samuel', '1 Kings': '1 Reyes', '2 Kings': '2 Reyes',
    '1 Chronicles': '1 Crónicas', '2 Chronicles': '2 Crónicas',
    'Ezra': 'Esdras', 'Nehemiah': 'Nehemías', 'Esther': 'Ester',
    'Job': 'Job', 'Psalms': 'Salmos', 'Proverbs': 'Proverbios',
    'Ecclesiastes': 'Eclesiastés', 'Song of Solomon': 'Cantares',
    'Isaiah': 'Isaías', 'Jeremiah': 'Jeremías', 'Lamentations': 'Lamentaciones',
    'Ezekiel': 'Ezequiel', 'Daniel': 'Daniel', 'Hosea': 'Oseas',
    'Joel': 'Joel', 'Amos': 'Amós', 'Obadiah': 'Abdías',
    'Jonah': 'Jonás', 'Micah': 'Miqueas', 'Nahum': 'Nahúm',
    'Habakkuk': 'Habacuc', 'Zephaniah': 'Sofonías', 'Haggai': 'Hageo',
    'Zechariah': 'Zacarías', 'Malachi': 'Malaquías', 'Matthew': 'Mateo',
    'Mark': 'Marcos', 'Luke': 'Lucas', 'John': 'Juan',
    'Acts': 'Hechos', 'Romans': 'Romanos', '1 Corinthians': '1 Corintios',
    '2 Corinthians': '2 Corintios', 'Galatians': 'Gálatas',
    'Ephesians': 'Efesios', 'Philippians': 'Filipenses',
    'Colossians': 'Colosenses', '1 Thessalonians': '1 Tesalonicenses',
    '2 Thessalonians': '2 Tesalonicenses', '1 Timothy': '1 Timoteo',
    '2 Timothy': '2 Timoteo', 'Titus': 'Tito', 'Philemon': 'Filemón',
    'Hebrews': 'Hebreos', 'James': 'Santiago', '1 Peter': '1 Pedro',
    '2 Peter': '2 Pedro', '1 John': '1 Juan', '2 John': '2 Juan',
    '3 John': '3 Juan', 'Jude': 'Judas', 'Revelation': 'Apocalipsis',
}

# ============================================================================
# API INTERACTION LAYER
# ============================================================================

def fetch_book_text(book_name, version="NLT"):
    """
    Fetch all verses for a Bible book from the NLT API, chapter by chapter.

    Fetches each chapter individually to avoid API truncation issues with large books.

    Args:
        book_name: Name of the book (e.g., "Genesis", "John")
        version: Bible version - "NLT" for English or "NTV" for Spanish

    Returns:
        List of verse dictionaries with structure:
        {'book': 'genesis', 'chapter': '1', 'verse_num': '1', 'text': '...'}

    Raises:
        ValueError: If book name is invalid
        requests.RequestException: If API request fails
    """
    # Validate book name
    if book_name not in BIBLE_BOOKS:
        raise ValueError(f"Invalid book name: {book_name}")

    # Get API reference and chapter count
    api_ref = BIBLE_BOOKS[book_name]['api_ref']
    num_chapters = BIBLE_BOOKS[book_name]['chapters']

    print(f"Fetching {version} text for {book_name} ({num_chapters} chapters)...")

    all_verses = []

    # Fetch each chapter individually
    for chapter in range(1, num_chapters + 1):
        # Construct API URL for this chapter
        url = f"{API_BASE_URL}?key={API_KEY}&version={version}&ref={api_ref}+{chapter}"

        # Make API request with retry logic
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                # Parse the HTML response
                verses = parse_html_response(response.text)

                if verses:
                    all_verses.extend(verses)
                    print(f"  Chapter {chapter}: {len(verses)} verses")
                else:
                    print(f"  Warning: No verses returned for chapter {chapter}")

                break  # Success, exit retry loop

            except requests.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"  Chapter {chapter} attempt {attempt + 1} failed, retrying...")
                    time.sleep(REQUEST_DELAY * (attempt + 1))  # Exponential backoff
                else:
                    raise Exception(f"Failed to fetch {book_name} chapter {chapter} after {MAX_RETRIES} attempts: {e}")

        # Add delay between chapter requests to respect rate limits
        time.sleep(REQUEST_DELAY)

    if not all_verses:
        raise ValueError(f"No verses returned for {book_name}")

    print(f"  Total: {len(all_verses)} verses retrieved")
    return all_verses


def parse_html_response(html_content):
    """
    Parse HTML response from NLT API and extract verses and section headers.

    The API returns HTML with <verse_export> tags containing attributes:
    - bk: book name
    - ch: chapter number
    - vn: verse number

    Section headers are found in <h3 class="subhead"> tags within verse_export tags.

    Args:
        html_content: Raw HTML string from API

    Returns:
        List of verse dictionaries (including section headers) sorted by chapter and verse number
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    verses = []

    # Find all verse_export tags
    for verse_tag in soup.find_all('verse_export'):
        # Extract attributes
        book = verse_tag.get('bk', '').lower()
        chapter = verse_tag.get('ch', '')
        verse_num = verse_tag.get('vn', '')

        # Check for section header (h3 with class "subhead")
        subhead = verse_tag.find('h3', class_='subhead')
        if subhead:
            # Extract section header text
            header_text = subhead.get_text(strip=True)

            # Add section header as a special entry
            verses.append({
                'book': book,
                'chapter': chapter,
                'verse_num': verse_num,  # Same verse number to maintain order
                'text': header_text,
                'is_title': True
            })

            # Remove the subhead tag from the verse text
            subhead.decompose()

        # Also remove chapter number heading if present
        chapter_heading = verse_tag.find('h2', class_='chapter-number')
        if chapter_heading:
            chapter_heading.decompose()

        # Extract text content and clean it
        # Remove verse number spans
        for span in verse_tag.find_all('span', class_='vn'):
            span.decompose()

        # Remove footnote links and text
        for footnote in verse_tag.find_all('a', class_='a-tn'):
            footnote.decompose()
        for footnote in verse_tag.find_all('span', class_='tn'):
            footnote.decompose()

        # Get cleaned text
        text = verse_tag.get_text(strip=True)

        # Only add if we have all required fields
        if book and chapter and verse_num and text:
            verses.append({
                'book': book,
                'chapter': chapter,
                'verse_num': verse_num,
                'text': text,
                'is_title': False
            })

    # Sort by chapter and verse number
    verses.sort(key=lambda v: (int(v['chapter']), int(v['verse_num'])))

    return verses


def find_spanish_header_with_translation(english_header, spanish_text):
    """
    Use translation and fuzzy matching to find the Spanish header within verse text.

    Strategy:
    1. Translate English header to Spanish using Google Translate
    2. Use fuzzy string matching to find where translation appears in Spanish text
    3. Split Spanish text at that location

    Args:
        english_header: English section header text
        spanish_text: Spanish verse text that contains the header

    Returns:
        Tuple of (spanish_header, remaining_text) or (None, spanish_text) if not found
    """
    from deep_translator import GoogleTranslator
    from difflib import SequenceMatcher

    try:
        # Translate English header to Spanish
        translator = GoogleTranslator(source='en', target='es')
        translated_header = translator.translate(english_header)

        # Normalize both texts for comparison
        spanish_text_lower = spanish_text.lower()
        translated_lower = translated_header.lower()

        # Try exact match first
        if translated_lower in spanish_text_lower:
            # Find position and extract
            pos = spanish_text_lower.index(translated_lower)
            header = spanish_text[:pos + len(translated_header)].strip()
            remaining = spanish_text[pos + len(translated_header):].strip()
            return header, remaining

        # Try fuzzy matching - look for the best match in sliding windows
        best_match_ratio = 0
        best_match_pos = 0
        best_match_len = len(translated_header)

        # Try different window sizes around the expected length
        for window_size in range(len(translated_header) - 10, len(translated_header) + 30):
            if window_size > len(spanish_text) or window_size < 10:
                continue

            for i in range(len(spanish_text) - window_size + 1):
                window = spanish_text[i:i + window_size]
                ratio = SequenceMatcher(None, translated_lower, window.lower()).ratio()

                if ratio > best_match_ratio:
                    best_match_ratio = ratio
                    best_match_pos = i
                    best_match_len = window_size

        # If we found a good match (>0.6 similarity), use it
        if best_match_ratio > 0.6:
            header = spanish_text[:best_match_pos + best_match_len].strip()
            remaining = spanish_text[best_match_pos + best_match_len:].strip()
            return header, remaining

    except Exception as e:
        print(f"  Warning: Translation/matching failed for '{english_header}': {e}")

    # Fallback: use simple heuristic - take first sentence-like portion
    # Look for a capital letter after the first 15 characters
    for i in range(15, min(80, len(spanish_text))):
        if i < len(spanish_text) - 20 and spanish_text[i].isupper() and spanish_text[i-1] == ' ':
            header = spanish_text[:i].strip()
            remaining = spanish_text[i:].strip()
            return header, remaining

    return None, spanish_text


def read_spanish_from_csv(book_name):
    """
    Read Spanish verses for a Bible book from the NTV CSV file.

    Note: Section headers are NOT extracted here. They will be handled during
    alignment with English verses using translation + fuzzy matching.

    Args:
        book_name: English book name (e.g., "Genesis", "John")

    Returns:
        List of verse dictionaries with structure:
        {'book': 'genesis', 'chapter': '1', 'verse_num': '1', 'text': '...'}

    Raises:
        ValueError: If book not found or CSV file missing
    """
    # Get Spanish book name
    spanish_book = BOOK_NAMES_SPANISH.get(book_name, book_name)

    print(f"Reading NTV text for {book_name} from CSV...")

    # Check if CSV file exists
    csv_path = os.path.join(os.path.dirname(__file__), CSV_FILE)
    if not os.path.exists(csv_path):
        raise ValueError(f"CSV file not found: {csv_path}")

    verses = []

    # Read CSV file
    with open(csv_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig to handle BOM
        reader = csv.DictReader(f)

        for row in reader:
            # Check if this row is for our book
            if row['libro'] == spanish_book:
                # Clean the text - remove verse number if it's at the start
                text = row['texto'].strip()

                # Some verses have the number at the start like "1 Text..."
                # Try to remove it
                verse_num = row['verso']
                if text.startswith(verse_num + ' '):
                    text = text[len(verse_num) + 1:].strip()

                verses.append({
                    'book': book_name.lower().replace(' ', ''),
                    'chapter': row['capitulo'],
                    'verse_num': verse_num,
                    'text': text
                })

    if not verses:
        raise ValueError(f"No verses found for {spanish_book} in CSV file")

    # Sort by chapter and verse number
    verses.sort(key=lambda v: (int(v['chapter']), int(v['verse_num'])))

    print(f"  Retrieved {len(verses)} verses from CSV")
    return verses


# ============================================================================
# DATA PROCESSING LAYER
# ============================================================================

def align_verses(english_verses, spanish_verses):
    """
    Align English and Spanish verse lists, extracting Spanish headers using
    translation + fuzzy matching based on English headers.

    English verses may include section headers (is_title=True) extracted from the API.
    This function aligns Spanish verses to match, using translation to find and extract
    corresponding Spanish headers from verse text.

    Args:
        english_verses: List of English verse dictionaries (may include headers with is_title=True)
        spanish_verses: List of Spanish verse dictionaries (no headers extracted yet)

    Returns:
        Tuple of (english_verses, aligned_spanish_verses)

    Raises:
        ValueError: If verses cannot be aligned
    """
    print("Aligning verses and extracting Spanish section headers...")

    aligned_spanish = []
    spanish_index = 0

    for en_verse in english_verses:
        if spanish_index >= len(spanish_verses):
            raise ValueError(
                f"Ran out of Spanish verses while aligning at English verse "
                f"{en_verse['chapter']}:{en_verse['verse_num']}"
            )

        if en_verse.get('is_title', False):
            # English has a section header - find corresponding Spanish verse
            es_verse = spanish_verses[spanish_index]

            # Verify chapter:verse match
            if en_verse['chapter'] != es_verse['chapter'] or en_verse['verse_num'] != es_verse['verse_num']:
                raise ValueError(
                    f"Verse mismatch at header: English {en_verse['chapter']}:{en_verse['verse_num']} vs "
                    f"Spanish {es_verse['chapter']}:{es_verse['verse_num']}"
                )

            # Use translation + fuzzy matching to find Spanish header
            spanish_header, remaining_text = find_spanish_header_with_translation(
                en_verse['text'],
                es_verse['text']
            )

            if spanish_header:
                print(f"  Found header at {en_verse['chapter']}:{en_verse['verse_num']}: '{spanish_header}'")
                # Add Spanish header
                aligned_spanish.append({
                    'book': es_verse['book'],
                    'chapter': es_verse['chapter'],
                    'verse_num': es_verse['verse_num'],
                    'text': spanish_header,
                    'is_title': True
                })
                # Add remaining verse text
                aligned_spanish.append({
                    'book': es_verse['book'],
                    'chapter': es_verse['chapter'],
                    'verse_num': es_verse['verse_num'],
                    'text': remaining_text,
                    'is_title': False
                })
            else:
                # Couldn't extract header, use fallback
                print(f"  Warning: Could not extract Spanish header for {en_verse['chapter']}:{en_verse['verse_num']}")
                # Use first 50 chars as header
                if len(es_verse['text']) > 50:
                    break_point = es_verse['text'][:60].rfind(' ')
                    if break_point > 20:
                        header_text = es_verse['text'][:break_point].strip()
                        remaining_text = es_verse['text'][break_point:].strip()
                    else:
                        header_text = es_verse['text'][:50].strip()
                        remaining_text = es_verse['text']
                else:
                    header_text = es_verse['text']
                    remaining_text = es_verse['text']

                aligned_spanish.append({
                    'book': es_verse['book'],
                    'chapter': es_verse['chapter'],
                    'verse_num': es_verse['verse_num'],
                    'text': header_text,
                    'is_title': True
                })
                aligned_spanish.append({
                    'book': es_verse['book'],
                    'chapter': es_verse['chapter'],
                    'verse_num': es_verse['verse_num'],
                    'text': remaining_text,
                    'is_title': False
                })

            spanish_index += 1
        else:
            # Regular verse - check if we just processed a header for this verse
            # If so, skip because we already added the Spanish content when splitting
            if (len(aligned_spanish) >= 2 and
                aligned_spanish[-2]['chapter'] == en_verse['chapter'] and
                aligned_spanish[-2]['verse_num'] == en_verse['verse_num'] and
                aligned_spanish[-2].get('is_title', False) and
                aligned_spanish[-1]['chapter'] == en_verse['chapter'] and
                aligned_spanish[-1]['verse_num'] == en_verse['verse_num'] and
                not aligned_spanish[-1].get('is_title', False)):
                # We just added both header and content for this verse, skip this English entry
                continue

            # Regular verse - copy with validation
            es_verse = spanish_verses[spanish_index]

            if en_verse['chapter'] != es_verse['chapter'] or en_verse['verse_num'] != es_verse['verse_num']:
                raise ValueError(
                    f"Verse mismatch: English {en_verse['chapter']}:{en_verse['verse_num']} vs "
                    f"Spanish {es_verse['chapter']}:{es_verse['verse_num']}"
                )

            aligned_spanish.append(es_verse)
            spanish_index += 1

    if spanish_index != len(spanish_verses):
        raise ValueError(
            f"Alignment ended with unused Spanish verses: used {spanish_index} of {len(spanish_verses)}"
        )

    print(f"Alignment complete: {len(english_verses)} English, {len(aligned_spanish)} Spanish")
    return english_verses, aligned_spanish


# ============================================================================
# PDF GENERATION LAYER
# ============================================================================

def calculate_column_widths(english_verses, spanish_verses, x_offset=0):
    """
    Calculate dynamic column widths based on text length to balance page height.

    Strategy: Allocate more width to the language with more text content
    so both columns end up approximately the same height.

    Args:
        english_verses: List of English verse dictionaries
        spanish_verses: List of Spanish verse dictionaries
        x_offset: X offset for the page (0 for left page, PAGE_WIDTH for right page)

    Returns:
        Tuple of (english_width, spanish_width, english_x, spanish_x)
        where widths are in points and x positions are column start positions
    """
    # Calculate total character count for each language
    english_chars = sum(len(v['text']) for v in english_verses)
    spanish_chars = sum(len(v['text']) for v in spanish_verses)

    total_chars = english_chars + spanish_chars

    # Calculate available width for both columns
    available_width = PAGE_WIDTH - (2 * MARGIN) - COLUMN_GAP

    # Allocate width proportionally based on character count
    if total_chars > 0:
        english_ratio = english_chars / total_chars
        spanish_ratio = spanish_chars / total_chars
    else:
        english_ratio = 0.5
        spanish_ratio = 0.5

    english_width = available_width * english_ratio
    spanish_width = available_width * spanish_ratio

    # Calculate starting X positions (add x_offset for page positioning)
    english_x = x_offset + MARGIN
    spanish_x = x_offset + MARGIN + english_width + COLUMN_GAP

    return english_width, spanish_width, english_x, spanish_x


def draw_book_title(c, book_name_en, book_name_es, y_pos, col_widths):
    """
    Draw the bilingual book title in two columns.

    Format: English name in left column, Spanish name in right column, centered in crimson color

    Args:
        c: ReportLab canvas object
        book_name_en: English book name
        book_name_es: Spanish book name
        y_pos: Y position to draw at
        col_widths: Tuple of (english_width, spanish_width, english_x, spanish_x)

    Returns:
        New Y position after drawing (with spacing)
    """
    english_width, spanish_width, english_x, spanish_x = col_widths

    # Set font and color
    c.setFont(BOOK_TITLE_FONT, BOOK_TITLE_SIZE)
    c.setFillColor(CRIMSON)

    # English title - centered in English column
    english_title = book_name_en.upper()
    en_width = stringWidth(english_title, BOOK_TITLE_FONT, BOOK_TITLE_SIZE)
    en_x = english_x + (english_width - en_width) / 2
    c.drawString(en_x, y_pos, english_title)

    # Spanish title - centered in Spanish column
    spanish_title = book_name_es.upper()
    es_width = stringWidth(spanish_title, BOOK_TITLE_FONT, BOOK_TITLE_SIZE)
    es_x = spanish_x + (spanish_width - es_width) / 2
    c.drawString(es_x, y_pos, spanish_title)

    # Reset color to black
    c.setFillColor('black')

    # Return new Y position with spacing
    return y_pos - BOOK_TITLE_SIZE - BOOK_TITLE_SPACING


def draw_chapter_number(c, chapter_num, y_pos, col_widths):
    """
    Draw a large chapter number in both columns, like traditional Bibles, in crimson color.

    Args:
        c: ReportLab canvas object
        chapter_num: Chapter number to draw
        y_pos: Y position to draw at
        col_widths: Tuple of (english_width, spanish_width, english_x, spanish_x)

    Returns:
        New Y position after drawing (with spacing)
    """
    english_width, spanish_width, english_x, spanish_x = col_widths

    # Add spacing above chapter number
    y_pos -= CHAPTER_NUM_TOP_SPACING

    # Set font and color
    c.setFont(CHAPTER_NUM_FONT, CHAPTER_NUM_SIZE)
    c.setFillColor(CRIMSON)

    # Draw chapter number centered in each column
    text = str(chapter_num)
    text_width = stringWidth(text, CHAPTER_NUM_FONT, CHAPTER_NUM_SIZE)

    # English column
    en_x = english_x + (english_width - text_width) / 2
    c.drawString(en_x, y_pos, text)

    # Spanish column
    es_x = spanish_x + (spanish_width - text_width) / 2
    c.drawString(es_x, y_pos, text)

    # Reset color to black
    c.setFillColor('black')

    # Return new Y position with spacing below
    return y_pos - CHAPTER_NUM_SIZE - CHAPTER_NUM_BOTTOM_SPACING


def draw_header(c, book_name_en, book_name_es, chapter_num, page_num, x_offset=0):
    """
    Draw page header with book name, chapter, and page number, with a line underneath.

    Format:
    - Left: English book name and chapter (e.g., "Genesis 1")
    - Center: Page number
    - Right: Spanish book name and chapter (e.g., "Génesis 1")
    - Horizontal line below the header

    Args:
        c: ReportLab canvas object
        book_name_en: English book name
        book_name_es: Spanish book name
        chapter_num: Current chapter number
        page_num: Page number to display
        x_offset: X offset for the page (0 for left page, PAGE_WIDTH for right page)
    """
    # Set font for header
    c.setFont(HEADER_FONT, HEADER_SIZE)

    # Calculate header Y position (top of page)
    header_y = PAGE_HEIGHT - MARGIN + HEADER_MARGIN

    # Left: English book and chapter
    left_text = f"{book_name_en} {chapter_num}"
    left_x = x_offset + MARGIN
    c.drawString(left_x, header_y, left_text)

    # Center: Page number
    center_text = str(page_num)
    center_width = stringWidth(center_text, HEADER_FONT, HEADER_SIZE)
    center_x = x_offset + (PAGE_WIDTH - center_width) / 2
    c.drawString(center_x, header_y, center_text)

    # Right: Spanish book and chapter
    right_text = f"{book_name_es} {chapter_num}"
    right_width = stringWidth(right_text, HEADER_FONT, HEADER_SIZE)
    right_x = x_offset + PAGE_WIDTH - MARGIN - right_width
    c.drawString(right_x, header_y, right_text)

    # Draw horizontal line below header
    line_y = header_y - 3  # Small space below text
    c.setStrokeColor('black')
    c.setLineWidth(0.5)
    c.line(x_offset + MARGIN, line_y, x_offset + PAGE_WIDTH - MARGIN, line_y)


def draw_column_separator(c, spanish_x, x_offset=0):
    """
    Draw a vertical line separating English and Spanish columns.

    Args:
        c: ReportLab canvas object
        spanish_x: X position of the Spanish column start (absolute position)
        x_offset: X offset for the page (0 for left page, PAGE_WIDTH for right page)
    """
    # Calculate the midpoint between columns (adjust for x_offset)
    line_x = spanish_x - (COLUMN_GAP / 2)

    # Draw line from top to bottom of the content area
    c.setStrokeColor('gray')
    c.setLineWidth(0.5)
    c.line(line_x, MARGIN, line_x, PAGE_HEIGHT - MARGIN)
    c.setStrokeColor('black')  # Reset to black


def draw_verse_pair(c, verse_num, english_text, spanish_text, y_pos, col_widths, is_title=False):
    """
    Draw a single verse pair in both columns at the same Y position.

    Args:
        c: ReportLab canvas object
        verse_num: Verse number to display (or empty string for titles)
        english_text: English verse text
        spanish_text: Spanish verse text
        y_pos: Current Y position
        col_widths: Tuple of (english_width, spanish_width, english_x, spanish_x)
        is_title: If True, format as a subtitle/section heading

    Returns:
        New Y position after drawing this verse pair
    """
    english_width, spanish_width, english_x, spanish_x = col_widths

    if is_title:
        # Format as subtitle - centered, bold, no verse number, wrapped if needed
        c.setFont(VERSE_NUM_FONT, BODY_SIZE + 1)

        # Wrap English subtitle if needed
        english_lines = wrap_text(english_text, VERSE_NUM_FONT, BODY_SIZE + 1, english_width)

        # Wrap Spanish subtitle if needed
        spanish_lines = wrap_text(spanish_text, VERSE_NUM_FONT, BODY_SIZE + 1, spanish_width)

        # Use the maximum number of lines to keep alignment
        max_lines = max(len(english_lines), len(spanish_lines))

        # Draw each line centered
        current_y = y_pos
        for i in range(max_lines):
            # English line
            if i < len(english_lines):
                eng_line = english_lines[i]
                eng_width = stringWidth(eng_line, VERSE_NUM_FONT, BODY_SIZE + 1)
                eng_x = english_x + (english_width - eng_width) / 2
                c.drawString(eng_x, current_y, eng_line)

            # Spanish line
            if i < len(spanish_lines):
                span_line = spanish_lines[i]
                span_width = stringWidth(span_line, VERSE_NUM_FONT, BODY_SIZE + 1)
                span_x = spanish_x + (spanish_width - span_width) / 2
                c.drawString(span_x, current_y, span_line)

            # Move down for next line
            current_y -= (BODY_SIZE + 1) * LINE_SPACING

        # Return new Y position with extra spacing after title
        return current_y - VERSE_SPACING * 2

    # Format verse number
    verse_label = f"{verse_num} "

    # Calculate verse number width
    verse_num_width = stringWidth(verse_label, VERSE_NUM_FONT, VERSE_NUM_SIZE)

    # Calculate text width (subtract verse number width)
    english_text_width = english_width - verse_num_width - 2
    spanish_text_width = spanish_width - verse_num_width - 2

    # Split text into lines for wrapping
    english_lines = wrap_text(english_text, BODY_FONT, BODY_SIZE, english_text_width)
    spanish_lines = wrap_text(spanish_text, BODY_FONT, BODY_SIZE, spanish_text_width)

    # Calculate heights
    line_height = BODY_SIZE * LINE_SPACING
    english_height = len(english_lines) * line_height
    spanish_height = len(spanish_lines) * line_height
    max_height = max(english_height, spanish_height)

    # Draw verse numbers in bold
    c.setFont(VERSE_NUM_FONT, VERSE_NUM_SIZE)
    c.drawString(english_x, y_pos, verse_label)
    c.drawString(spanish_x, y_pos, verse_label)

    # Draw text lines
    c.setFont(BODY_FONT, BODY_SIZE)

    # English column
    current_y = y_pos
    for i, line in enumerate(english_lines):
        x_offset = verse_num_width if i == 0 else 0
        c.drawString(english_x + x_offset, current_y, line)
        current_y -= line_height

    # Spanish column
    current_y = y_pos
    for i, line in enumerate(spanish_lines):
        x_offset = verse_num_width if i == 0 else 0
        c.drawString(spanish_x + x_offset, current_y, line)
        current_y -= line_height

    # Return new Y position (maximum height used + spacing)
    return y_pos - max_height - VERSE_SPACING


def wrap_text(text, font_name, font_size, max_width):
    """
    Wrap text to fit within a maximum width.

    Args:
        text: Text to wrap
        font_name: Font name
        font_size: Font size
        max_width: Maximum width in points

    Returns:
        List of text lines that fit within max_width
    """
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        # Try adding word to current line
        test_line = ' '.join(current_line + [word])
        test_width = stringWidth(test_line, font_name, font_size)

        if test_width <= max_width:
            current_line.append(word)
        else:
            # Current line is full, start new line
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                # Single word is too long, add it anyway
                lines.append(word)

    # Add remaining words
    if current_line:
        lines.append(' '.join(current_line))

    return lines


def create_bilingual_pdf(book_name, english_verses, spanish_verses, output_path):
    """
    Generate the complete bilingual PDF with traditional Bible formatting.
    Uses A4 landscape with 2-up layout (two pages side-by-side).

    Args:
        book_name: Name of the Bible book
        english_verses: List of English verse dictionaries
        spanish_verses: List of Spanish verse dictionaries
        output_path: Path where PDF should be saved
    """
    print("Generating PDF...")

    # Create canvas with A4 landscape
    c = canvas.Canvas(output_path, pagesize=landscape(A4))

    # Get Spanish book name
    book_name_es = BOOK_NAMES_SPANISH.get(book_name, book_name)

    # Track page position (0 = left page, 1 = right page)
    page_position = 0
    page_num = 1
    is_first_page = True
    first_chapter_on_page = True

    # Track current chapter for chapter number rendering and headers
    current_chapter = None

    # Helper function to start a new page position
    def start_new_page_position():
        nonlocal page_position, page_num, x_offset, y_pos, col_widths, first_chapter_on_page
        page_position += 1
        if page_position > 1:
            c.showPage()
            page_position = 0

        page_num += 1
        x_offset = page_position * PAGE_WIDTH
        y_pos = PAGE_HEIGHT - MARGIN - HEADER_HEIGHT - HEADER_MARGIN
        col_widths = calculate_column_widths(english_verses, spanish_verses, x_offset)
        first_chapter_on_page = True

    # Helper function to draw page header and separator
    def draw_page_elements(chapter):
        draw_header(c, book_name, book_name_es, chapter, page_num, x_offset)
        draw_column_separator(c, col_widths[3], x_offset)

    # Initialize Y position and x_offset
    x_offset = 0
    y_pos = PAGE_HEIGHT - MARGIN - HEADER_HEIGHT - HEADER_MARGIN

    # Calculate column widths based on content
    col_widths = calculate_column_widths(english_verses, spanish_verses, x_offset)

    # Get first chapter number for the initial header
    first_chapter = english_verses[0]['chapter'] if english_verses else '1'

    # Draw header and separator on first page
    draw_page_elements(first_chapter)

    # Draw book title on first page
    y_pos = draw_book_title(c, book_name, book_name_es, y_pos, col_widths)

    # Loop through all verses
    for en_verse, es_verse in zip(english_verses, spanish_verses):
        chapter = en_verse['chapter']
        verse_num = en_verse['verse_num']

        # Check if we need to draw a chapter number
        if chapter != current_chapter:
            # Check if there's enough space for chapter number
            needed_space = CHAPTER_NUM_SIZE + CHAPTER_NUM_TOP_SPACING + CHAPTER_NUM_BOTTOM_SPACING
            if y_pos < MARGIN + needed_space:
                start_new_page_position()
                draw_page_elements(chapter)

            # Draw chapter number if it's the first chapter on this page or if we just started
            if first_chapter_on_page or is_first_page:
                y_pos = draw_chapter_number(c, chapter, y_pos, col_widths)
                first_chapter_on_page = False
                is_first_page = False

            current_chapter = chapter

        # Estimate space needed for this verse
        estimated_height = 60

        # Check if we need a new page
        if y_pos < MARGIN + estimated_height:
            start_new_page_position()
            draw_page_elements(current_chapter)

        # Draw the verse pair (check if it's a section header)
        is_title = en_verse.get('is_title', False)
        y_pos = draw_verse_pair(
            c,
            verse_num if not is_title else '',  # No verse number for titles
            en_verse['text'],
            es_verse['text'],
            y_pos,
            col_widths,
            is_title=is_title
        )

    # Save PDF
    c.save()
    print(f"Successfully created {output_path}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def normalize_book_name(user_input):
    """
    Normalize user input to match book names in BIBLE_BOOKS dictionary.

    Handles case-insensitive matching and common variations.

    Args:
        user_input: User's book name input

    Returns:
        Normalized book name if found, None otherwise
    """
    # Try exact match first (case-insensitive)
    for book_name in BIBLE_BOOKS.keys():
        if book_name.lower() == user_input.lower():
            return book_name

    # Try without spaces (e.g., "1John" -> "1 John")
    for book_name in BIBLE_BOOKS.keys():
        if book_name.lower().replace(' ', '') == user_input.lower().replace(' ', ''):
            return book_name

    return None


def main():
    """
    Main execution function.

    Handles command-line arguments, fetches Bible text, and generates PDF.
    """
    # Check command-line arguments
    if len(sys.argv) < 2:
        print("Usage: python bible_pdf.py <BookName>")
        print("\nExample:")
        print("  python bible_pdf.py Genesis")
        print("  python bible_pdf.py John")
        print('  python bible_pdf.py "1 John"')
        print("\nAvailable books:")
        for i, book in enumerate(BIBLE_BOOKS.keys(), 1):
            print(f"  {book}", end='')
            if i % 4 == 0:
                print()  # New line every 4 books
            else:
                print(', ', end='')
        print()
        sys.exit(1)

    # Get book name from command line
    user_input = sys.argv[1]
    book_name = normalize_book_name(user_input)

    if not book_name:
        print(f"Error: '{user_input}' is not a valid Bible book name.")
        print("\nDid you mean one of these?")
        # Show similar book names
        for book in BIBLE_BOOKS.keys():
            if user_input.lower() in book.lower():
                print(f"  {book}")
        sys.exit(1)

    try:
        # Fetch English version from NLT API
        english_verses = fetch_book_text(book_name, version="NLT")

        # Read Spanish version from CSV file
        spanish_verses = read_spanish_from_csv(book_name)

        # Align and validate verses
        english_verses, spanish_verses = align_verses(english_verses, spanish_verses)

        # Generate output filename
        output_filename = f"{book_name.replace(' ', '_')}_NLT_NTV.pdf"

        # Create PDF
        create_bilingual_pdf(book_name, english_verses, spanish_verses, output_filename)

        print(f"\nDone! Your bilingual Bible PDF is ready: {output_filename}")

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
