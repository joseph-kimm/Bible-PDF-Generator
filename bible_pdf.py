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
import json
import re
import requests
from bs4 import BeautifulSoup
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.colors import HexColor

# ============================================================================
# CONFIGURATION
# ============================================================================

# API Configuration
API_BASE_URL = "https://api.nlt.to/api/passages"
API_KEY = "a28921c8-45d5-40e1-b11a-90723f427a72"
REQUEST_DELAY = 1.0
MAX_RETRIES = 3

# File paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIBLE_BOOKS_JSON = os.path.join(SCRIPT_DIR, "bible_books.json")
CSV_FILE = os.path.join(SCRIPT_DIR, "biblia_ntv_.csv")

# PDF Layout (A4 landscape, 2-up)
FULL_PAGE_WIDTH, FULL_PAGE_HEIGHT = landscape(A4)
PAGE_WIDTH = FULL_PAGE_WIDTH / 2
PAGE_HEIGHT = FULL_PAGE_HEIGHT
MARGIN = 0.4 * inch
COLUMN_GAP = 0.25 * inch
HEADER_HEIGHT = 0.3 * inch
HEADER_MARGIN = 0.15 * inch

# Typography
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
LINE_SPACING = 1.3

# Colors and Spacing
CRIMSON = HexColor('#781c2e')
BOOK_TITLE_SPACING = 25
CHAPTER_NUM_TOP_SPACING = 30
CHAPTER_NUM_BOTTOM_SPACING = 5
VERSE_SPACING = 4

# ============================================================================
# BIBLE DATA LOADING
# ============================================================================

def load_bible_books():
    """Load Bible book metadata from JSON file."""
    with open(BIBLE_BOOKS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['books']

BIBLE_BOOKS = load_bible_books()

def get_spanish_name(book_name):
    """Get Spanish name for a book."""
    return BIBLE_BOOKS.get(book_name, {}).get('spanish', book_name)

# ============================================================================
# SEMANTIC SIMILARITY (using sentence-transformers)
# ============================================================================

_similarity_model = None

def get_similarity_model():
    """Lazy-load the sentence transformer model."""
    global _similarity_model
    if _similarity_model is None:
        from sentence_transformers import SentenceTransformer
        _similarity_model = SentenceTransformer('all-MiniLM-L12-v2')
    return _similarity_model

def semantic_similarity(text1, text2):
    """Calculate semantic similarity between two texts using sentence embeddings."""
    from sklearn.metrics.pairwise import cosine_similarity
    model = get_similarity_model()
    embeddings = model.encode([text1.lower(), text2.lower()])
    return cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]

# ============================================================================
# API INTERACTION
# ============================================================================

def fetch_book_text(book_name, version="NLT", start_chapter=None, end_chapter=None):
    """Fetch verses for a Bible book from the NLT API."""
    if book_name not in BIBLE_BOOKS:
        raise ValueError(f"Invalid book name: {book_name}")

    api_ref = BIBLE_BOOKS[book_name]['api_ref']
    num_chapters = BIBLE_BOOKS[book_name]['chapters']

    start = start_chapter or 1
    end = end_chapter or num_chapters

    if start < 1 or end > num_chapters or start > end:
        raise ValueError(f"Invalid chapter range: {start}-{end} (book has {num_chapters} chapters)")

    chapter_info = f"chapters {start}-{end}" if start != 1 or end != num_chapters else f"{num_chapters} chapters"
    print(f"Fetching {version} text for {book_name} ({chapter_info})...")

    all_verses = []

    for chapter in range(start, end + 1):
        url = f"{API_BASE_URL}?key={API_KEY}&version={version}&ref={api_ref}+{chapter}"

        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                verses = parse_html_response(response.text)

                if verses:
                    all_verses.extend(verses)
                    print(f"  Chapter {chapter}: {len(verses)} verses")
                else:
                    print(f"  Warning: No verses returned for chapter {chapter}")
                break

            except requests.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"  Chapter {chapter} attempt {attempt + 1} failed, retrying...")
                    time.sleep(REQUEST_DELAY * (attempt + 1))
                else:
                    raise Exception(f"Failed to fetch {book_name} chapter {chapter}: {e}")

        time.sleep(REQUEST_DELAY)

    if not all_verses:
        raise ValueError(f"No verses returned for {book_name}")

    print(f"  Total: {len(all_verses)} verses retrieved")
    return all_verses


def parse_html_response(html_content):
    """Parse HTML response from NLT API and extract verses and section headers."""
    soup = BeautifulSoup(html_content, 'html.parser')
    verses = []

    for verse_tag in soup.find_all('verse_export'):
        book = verse_tag.get('bk', '').lower()
        chapter = verse_tag.get('ch', '')
        verse_num = verse_tag.get('vn', '')

        # Check for section header
        subhead = verse_tag.find('h3', class_='subhead')
        if subhead:
            header_text = subhead.get_text(strip=True)
            verses.append({
                'book': book,
                'chapter': chapter,
                'verse_num': verse_num,
                'text': header_text,
                'is_title': True
            })
            subhead.decompose()

        # Remove chapter heading if present
        chapter_heading = verse_tag.find('h2', class_='chapter-number')
        if chapter_heading:
            chapter_heading.decompose()

        # Remove verse numbers and footnotes
        for span in verse_tag.find_all('span', class_='vn'):
            span.decompose()
        for footnote in verse_tag.find_all('a', class_='a-tn'):
            footnote.decompose()
        for footnote in verse_tag.find_all('span', class_='tn'):
            footnote.decompose()

        text = verse_tag.get_text(strip=True)

        if book and chapter and verse_num and text:
            verses.append({
                'book': book,
                'chapter': chapter,
                'verse_num': verse_num,
                'text': text,
                'is_title': False
            })

    verses.sort(key=lambda v: (int(v['chapter']), int(v['verse_num'])))
    return verses


def read_spanish_from_csv(book_name, start_chapter=None, end_chapter=None):
    """Read Spanish verses for a Bible book from the NTV CSV file."""
    spanish_book = get_spanish_name(book_name)
    start = start_chapter or 1
    end = end_chapter or BIBLE_BOOKS[book_name]['chapters']

    chapter_info = f"chapters {start}-{end}" if start != 1 or end != BIBLE_BOOKS[book_name]['chapters'] else "all chapters"
    print(f"Reading NTV text for {book_name} ({chapter_info}) from CSV...")

    if not os.path.exists(CSV_FILE):
        raise ValueError(f"CSV file not found: {CSV_FILE}")

    verses = []

    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['libro'] == spanish_book:
                chapter_num = int(row['capitulo'])
                if chapter_num < start or chapter_num > end:
                    continue

                text = row['texto'].strip()
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

    verses.sort(key=lambda v: (int(v['chapter']), int(v['verse_num'])))
    print(f"  Retrieved {len(verses)} verses from CSV")
    return verses

# ============================================================================
# HEADER EXTRACTION
# ============================================================================

def find_spanish_header_with_translation(english_header, spanish_text):
    """
    Extract Spanish header using semantic similarity with sentence-transformers.

    Strategy:
    1. Check if entire text is the header (short text, high similarity)
    2. Find split points at capital letters and score each candidate
    3. Use semantic similarity to find best match
    """
    from deep_translator import GoogleTranslator

    try:
        # Strip leading verse numbers
        spanish_text_clean = re.sub(r'^\d+\s+', '', spanish_text).strip()
        translator_es_en = GoogleTranslator(source='es', target='en')

        # FIRST: Check if entire text IS the header (common case)
        if len(spanish_text_clean) < 80:
            try:
                back_translation = translator_es_en.translate(spanish_text_clean)
                similarity = semantic_similarity(english_header, back_translation)
                if similarity > 0.7:
                    return spanish_text_clean, ""
            except Exception:
                pass

        # SECOND: Find split points at capital letters
        candidates = []
        for i in range(10, min(120, len(spanish_text_clean))):
            if (i < len(spanish_text_clean) - 10 and
                spanish_text_clean[i].isupper() and
                spanish_text_clean[i-1] == ' '):
                candidates.append(i)

        # Score each candidate
        best_header = None
        best_similarity = 0

        for split_pos in candidates:
            candidate_header = spanish_text_clean[:split_pos].strip()

            if len(candidate_header) < 8 or len(candidate_header) > 150:
                continue

            try:
                back_translation = translator_es_en.translate(candidate_header)
                similarity = semantic_similarity(english_header, back_translation)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_header = candidate_header
            except Exception:
                continue

        if best_header and best_similarity > 0.7:
            remaining = spanish_text_clean[len(best_header):].strip()
            return best_header, remaining

    except Exception as e:
        print(f"  Warning: Header extraction failed for '{english_header}': {e}")

    # Fallback: simple heuristic
    spanish_text_clean = re.sub(r'^\d+\s+', '', spanish_text).strip()
    for i in range(15, min(100, len(spanish_text_clean))):
        if (i < len(spanish_text_clean) - 10 and
            spanish_text_clean[i].isupper() and
            spanish_text_clean[i-1] == ' '):
            return spanish_text_clean[:i].strip(), spanish_text_clean[i:].strip()

    return None, spanish_text

# ============================================================================
# VERSE ALIGNMENT
# ============================================================================

def align_verses(english_verses, spanish_verses):
    """Align English and Spanish verses, extracting Spanish headers."""
    print("Aligning verses and extracting Spanish section headers...")

    aligned_spanish = []
    spanish_index = 0

    for en_verse in english_verses:
        if spanish_index >= len(spanish_verses):
            raise ValueError(
                f"Ran out of Spanish verses at English verse {en_verse['chapter']}:{en_verse['verse_num']}"
            )

        if en_verse.get('is_title', False):
            es_verse = spanish_verses[spanish_index]

            # Handle verse mismatches
            while (spanish_index < len(spanish_verses) and
                   en_verse['chapter'] == es_verse['chapter'] and
                   int(en_verse['verse_num']) > int(es_verse['verse_num'])):
                print(f"  Skipping Spanish verse {es_verse['chapter']}:{es_verse['verse_num']}")
                spanish_index += 1
                if spanish_index < len(spanish_verses):
                    es_verse = spanish_verses[spanish_index]

            if en_verse['chapter'] != es_verse['chapter'] or en_verse['verse_num'] != es_verse['verse_num']:
                raise ValueError(
                    f"Verse mismatch: English {en_verse['chapter']}:{en_verse['verse_num']} vs "
                    f"Spanish {es_verse['chapter']}:{es_verse['verse_num']}"
                )

            # Extract Spanish header
            spanish_header, remaining_text = find_spanish_header_with_translation(
                en_verse['text'], es_verse['text']
            )

            if spanish_header:
                print(f"  Found header at {en_verse['chapter']}:{en_verse['verse_num']}: '{spanish_header}'")
                aligned_spanish.append({
                    'book': es_verse['book'],
                    'chapter': es_verse['chapter'],
                    'verse_num': es_verse['verse_num'],
                    'text': spanish_header,
                    'is_title': True
                })
                aligned_spanish.append({
                    'book': es_verse['book'],
                    'chapter': es_verse['chapter'],
                    'verse_num': es_verse['verse_num'],
                    'text': remaining_text,
                    'is_title': False
                })
            else:
                print(f"  Warning: Could not extract Spanish header for {en_verse['chapter']}:{en_verse['verse_num']}")
                # Fallback
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
            # Check if we just processed a header for this verse
            if (len(aligned_spanish) >= 2 and
                aligned_spanish[-2]['chapter'] == en_verse['chapter'] and
                aligned_spanish[-2]['verse_num'] == en_verse['verse_num'] and
                aligned_spanish[-2].get('is_title', False)):
                continue

            es_verse = spanish_verses[spanish_index]

            # Handle verse mismatches
            while (spanish_index < len(spanish_verses) and
                   en_verse['chapter'] == es_verse['chapter'] and
                   int(en_verse['verse_num']) > int(es_verse['verse_num'])):
                print(f"  Skipping Spanish verse {es_verse['chapter']}:{es_verse['verse_num']}")
                spanish_index += 1
                if spanish_index < len(spanish_verses):
                    es_verse = spanish_verses[spanish_index]

            if en_verse['chapter'] != es_verse['chapter'] or en_verse['verse_num'] != es_verse['verse_num']:
                raise ValueError(
                    f"Verse mismatch: English {en_verse['chapter']}:{en_verse['verse_num']} vs "
                    f"Spanish {es_verse['chapter']}:{es_verse['verse_num']}"
                )

            aligned_spanish.append(es_verse)
            spanish_index += 1

    if spanish_index < len(spanish_verses):
        remaining = len(spanish_verses) - spanish_index
        print(f"  Note: {remaining} Spanish verse(s) remain unused")

    print(f"Alignment complete: {len(english_verses)} English, {len(aligned_spanish)} Spanish")
    return english_verses, aligned_spanish

# ============================================================================
# PDF GENERATION
# ============================================================================

def wrap_text(text, font_name, font_size, max_width):
    """Wrap text to fit within a maximum width."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        test_width = stringWidth(test_line, font_name, font_size)

        if test_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(word)

    if current_line:
        lines.append(' '.join(current_line))

    return lines


def calculate_column_widths(english_verses, spanish_verses, x_offset=0):
    """Calculate dynamic column widths based on text length."""
    english_chars = sum(len(v['text']) for v in english_verses)
    spanish_chars = sum(len(v['text']) for v in spanish_verses)
    total_chars = english_chars + spanish_chars

    available_width = PAGE_WIDTH - (2 * MARGIN) - COLUMN_GAP

    if total_chars > 0:
        english_ratio = english_chars / total_chars
    else:
        english_ratio = 0.5

    english_width = available_width * english_ratio
    spanish_width = available_width * (1 - english_ratio)

    english_x = x_offset + MARGIN
    spanish_x = x_offset + MARGIN + english_width + COLUMN_GAP

    return english_width, spanish_width, english_x, spanish_x


def draw_book_title(c, book_name_en, book_name_es, y_pos, col_widths):
    """Draw the bilingual book title."""
    english_width, spanish_width, english_x, spanish_x = col_widths

    c.setFont(BOOK_TITLE_FONT, BOOK_TITLE_SIZE)
    c.setFillColor(CRIMSON)

    english_title = book_name_en.upper()
    en_width = stringWidth(english_title, BOOK_TITLE_FONT, BOOK_TITLE_SIZE)
    c.drawString(english_x + (english_width - en_width) / 2, y_pos, english_title)

    spanish_title = book_name_es.upper()
    es_width = stringWidth(spanish_title, BOOK_TITLE_FONT, BOOK_TITLE_SIZE)
    c.drawString(spanish_x + (spanish_width - es_width) / 2, y_pos, spanish_title)

    c.setFillColor('black')
    return y_pos - BOOK_TITLE_SIZE - BOOK_TITLE_SPACING


def draw_chapter_number(c, chapter_num, y_pos, col_widths):
    """Draw chapter number in both columns."""
    english_width, spanish_width, english_x, spanish_x = col_widths

    y_pos -= CHAPTER_NUM_TOP_SPACING
    c.setFont(CHAPTER_NUM_FONT, CHAPTER_NUM_SIZE)
    c.setFillColor(CRIMSON)

    text = str(chapter_num)
    text_width = stringWidth(text, CHAPTER_NUM_FONT, CHAPTER_NUM_SIZE)

    c.drawString(english_x + (english_width - text_width) / 2, y_pos, text)
    c.drawString(spanish_x + (spanish_width - text_width) / 2, y_pos, text)

    c.setFillColor('black')
    return y_pos - CHAPTER_NUM_SIZE - CHAPTER_NUM_BOTTOM_SPACING


def draw_header(c, book_name_en, book_name_es, chapter_num, page_num, x_offset=0):
    """Draw page header with book name, chapter, and page number."""
    c.setFont(HEADER_FONT, HEADER_SIZE)
    header_y = PAGE_HEIGHT - MARGIN + HEADER_MARGIN

    c.drawString(x_offset + MARGIN, header_y, f"{book_name_en} {chapter_num}")

    center_text = str(page_num)
    center_width = stringWidth(center_text, HEADER_FONT, HEADER_SIZE)
    c.drawString(x_offset + (PAGE_WIDTH - center_width) / 2, header_y, center_text)

    right_text = f"{book_name_es} {chapter_num}"
    right_width = stringWidth(right_text, HEADER_FONT, HEADER_SIZE)
    c.drawString(x_offset + PAGE_WIDTH - MARGIN - right_width, header_y, right_text)

    line_y = header_y - 3
    c.setStrokeColor('black')
    c.setLineWidth(0.5)
    c.line(x_offset + MARGIN, line_y, x_offset + PAGE_WIDTH - MARGIN, line_y)


def draw_column_separator(c, spanish_x):
    """Draw vertical line between columns."""
    line_x = spanish_x - (COLUMN_GAP / 2)
    c.setStrokeColor('gray')
    c.setLineWidth(0.5)
    c.line(line_x, MARGIN, line_x, PAGE_HEIGHT - MARGIN)
    c.setStrokeColor('black')


def draw_verse_pair(c, verse_num, english_text, spanish_text, y_pos, col_widths, is_title=False):
    """Draw a verse pair in both columns."""
    english_width, spanish_width, english_x, spanish_x = col_widths

    if is_title:
        c.setFont(VERSE_NUM_FONT, BODY_SIZE + 1)

        english_lines = wrap_text(english_text, VERSE_NUM_FONT, BODY_SIZE + 1, english_width)
        spanish_lines = wrap_text(spanish_text, VERSE_NUM_FONT, BODY_SIZE + 1, spanish_width)
        max_lines = max(len(english_lines), len(spanish_lines))

        current_y = y_pos
        for i in range(max_lines):
            if i < len(english_lines):
                eng_line = english_lines[i]
                eng_width = stringWidth(eng_line, VERSE_NUM_FONT, BODY_SIZE + 1)
                c.drawString(english_x + (english_width - eng_width) / 2, current_y, eng_line)

            if i < len(spanish_lines):
                span_line = spanish_lines[i]
                span_width = stringWidth(span_line, VERSE_NUM_FONT, BODY_SIZE + 1)
                c.drawString(spanish_x + (spanish_width - span_width) / 2, current_y, span_line)

            current_y -= (BODY_SIZE + 1) * LINE_SPACING

        return current_y - VERSE_SPACING * 2

    verse_label = f"{verse_num} "
    verse_num_width = stringWidth(verse_label, VERSE_NUM_FONT, VERSE_NUM_SIZE)

    english_text_width = english_width - verse_num_width - 2
    spanish_text_width = spanish_width - verse_num_width - 2

    english_lines = wrap_text(english_text, BODY_FONT, BODY_SIZE, english_text_width)
    spanish_lines = wrap_text(spanish_text, BODY_FONT, BODY_SIZE, spanish_text_width)

    line_height = BODY_SIZE * LINE_SPACING
    max_height = max(len(english_lines), len(spanish_lines)) * line_height

    c.setFont(VERSE_NUM_FONT, VERSE_NUM_SIZE)
    c.drawString(english_x, y_pos, verse_label)
    c.drawString(spanish_x, y_pos, verse_label)

    c.setFont(BODY_FONT, BODY_SIZE)

    current_y = y_pos
    for i, line in enumerate(english_lines):
        x_off = verse_num_width if i == 0 else 0
        c.drawString(english_x + x_off, current_y, line)
        current_y -= line_height

    current_y = y_pos
    for i, line in enumerate(spanish_lines):
        x_off = verse_num_width if i == 0 else 0
        c.drawString(spanish_x + x_off, current_y, line)
        current_y -= line_height

    return y_pos - max_height - VERSE_SPACING


def create_bilingual_pdf(book_name, english_verses, spanish_verses, output_path):
    """Generate the bilingual PDF."""
    print("Generating PDF...")

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    book_name_es = get_spanish_name(book_name)

    page_position = 0
    page_num = 1
    is_first_page = True
    first_chapter_on_page = True
    current_chapter = None

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

    def draw_page_elements(chapter):
        draw_header(c, book_name, book_name_es, chapter, page_num, x_offset)
        draw_column_separator(c, col_widths[3])

    x_offset = 0
    y_pos = PAGE_HEIGHT - MARGIN - HEADER_HEIGHT - HEADER_MARGIN
    col_widths = calculate_column_widths(english_verses, spanish_verses, x_offset)
    first_chapter = english_verses[0]['chapter'] if english_verses else '1'

    draw_page_elements(first_chapter)
    y_pos = draw_book_title(c, book_name, book_name_es, y_pos, col_widths)

    for en_verse, es_verse in zip(english_verses, spanish_verses):
        chapter = en_verse['chapter']
        verse_num = en_verse['verse_num']

        if chapter != current_chapter:
            needed_space = CHAPTER_NUM_SIZE + CHAPTER_NUM_TOP_SPACING + CHAPTER_NUM_BOTTOM_SPACING
            if y_pos < MARGIN + needed_space:
                start_new_page_position()
                draw_page_elements(chapter)

            if first_chapter_on_page or is_first_page:
                y_pos = draw_chapter_number(c, chapter, y_pos, col_widths)
                first_chapter_on_page = False
                is_first_page = False

            current_chapter = chapter

        estimated_height = 60
        if y_pos < MARGIN + estimated_height:
            start_new_page_position()
            draw_page_elements(current_chapter)

        is_title = en_verse.get('is_title', False)
        y_pos = draw_verse_pair(
            c,
            verse_num if not is_title else '',
            en_verse['text'],
            es_verse['text'],
            y_pos,
            col_widths,
            is_title=is_title
        )

    c.save()
    print(f"Successfully created {output_path}")

# ============================================================================
# MAIN
# ============================================================================

def normalize_book_name(user_input):
    """Normalize user input to match book names."""
    for book_name in BIBLE_BOOKS.keys():
        if book_name.lower() == user_input.lower():
            return book_name

    for book_name in BIBLE_BOOKS.keys():
        if book_name.lower().replace(' ', '') == user_input.lower().replace(' ', ''):
            return book_name

    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python bible_pdf.py <BookName> [StartChapter] [EndChapter]")
        print("\nExamples:")
        print("  python bible_pdf.py Genesis              # Entire book")
        print("  python bible_pdf.py Matthew 1            # Just chapter 1")
        print("  python bible_pdf.py Matthew 1 3          # Chapters 1-3")
        print('  python bible_pdf.py "1 John"             # Book with number')
        print("\nAvailable books:")
        for i, book in enumerate(BIBLE_BOOKS.keys(), 1):
            print(f"  {book}", end='')
            if i % 4 == 0:
                print()
            else:
                print(', ', end='')
        print()
        sys.exit(1)

    user_input = sys.argv[1]
    book_name = normalize_book_name(user_input)

    if not book_name:
        print(f"Error: '{user_input}' is not a valid Bible book name.")
        print("\nDid you mean one of these?")
        for book in BIBLE_BOOKS.keys():
            if user_input.lower() in book.lower():
                print(f"  {book}")
        sys.exit(1)

    start_chapter = None
    end_chapter = None

    if len(sys.argv) >= 3:
        try:
            start_chapter = int(sys.argv[2])
            end_chapter = start_chapter
        except ValueError:
            print(f"Error: Invalid chapter number '{sys.argv[2]}'")
            sys.exit(1)

    if len(sys.argv) >= 4:
        try:
            end_chapter = int(sys.argv[3])
        except ValueError:
            print(f"Error: Invalid chapter number '{sys.argv[3]}'")
            sys.exit(1)

    try:
        english_verses = fetch_book_text(book_name, version="NLT",
                                         start_chapter=start_chapter,
                                         end_chapter=end_chapter)

        spanish_verses = read_spanish_from_csv(book_name,
                                               start_chapter=start_chapter,
                                               end_chapter=end_chapter)

        english_verses, spanish_verses = align_verses(english_verses, spanish_verses)

        book_part = book_name.replace(' ', '_')
        if start_chapter and end_chapter:
            if start_chapter == end_chapter:
                chapter_part = f"_Ch{start_chapter}"
            else:
                chapter_part = f"_Ch{start_chapter}-{end_chapter}"
        else:
            chapter_part = ""
        output_filename = f"{book_part}{chapter_part}_NLT_NTV.pdf"

        create_bilingual_pdf(book_name, english_verses, spanish_verses, output_filename)

        print(f"\nDone! Your bilingual Bible PDF is ready: {output_filename}")

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
