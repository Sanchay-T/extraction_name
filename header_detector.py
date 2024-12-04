import re
import os
from typing import List, Tuple
import pdfplumber
import traceback

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'
    OKGREEN = '\033[92m'

def print_colored(text: str, color: str) -> None:
    """Print text in color"""
    print(f"{color}{text}{Colors.END}")

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        print_colored(f"Error extracting text from PDF: {str(e)}", Colors.FAIL)
        return ""

def is_table_header(line: str) -> bool:
    """
    Specifically detect if a line is likely to be a table header.
    This is different from table content detection.
    """
    line = line.lower()
    
    # Common table header combinations
    header_combinations = [
        ['date', 'particulars'],
        ['date', 'description'],
        ['date', 'narration'],
        ['date', 'transaction'],
        ['txn', 'date'],
        ['value', 'date'],
        ['transaction', 'details'],
    ]
    
    # Check for common header combinations
    for combo in header_combinations:
        if all(term in line for term in combo):
            return True
            
    # Check for column-like structure with common banking terms
    columns = [col.strip() for col in line.split() if col.strip()]
    column_terms = {
        'date', 'particulars', 'description', 'debit', 'credit',
        'withdrawal', 'deposit', 'balance', 'amount', 'chq', 'ref',
        'narration', 'transaction', 'details'
    }
    
    matching_terms = sum(1 for col in columns if col in column_terms)
    if matching_terms >= 3:  # If line has 3 or more column headers
        return True
        
    return False

def is_transaction_line(line: str) -> bool:
    """
    Detect if a line is likely to be a transaction entry.
    """
    line = line.lower()
    
    # Check for date patterns at start of line
    date_pattern = r'^\s*\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}'
    has_date_prefix = bool(re.match(date_pattern, line))
    
    # Check for amount patterns
    amount_patterns = [
        r'\d+,\d{3}\.\d{2}',  # 1,234.56
        r'\d+\.\d{2}\s*(?:cr|dr)?',  # 1234.56 CR
        r'(?:cr|dr)\s*\d+\.\d{2}',  # CR 1234.56
    ]
    has_amount = any(re.search(pattern, line, re.IGNORECASE) for pattern in amount_patterns)
    
    # If line has both date and amount, likely a transaction
    if has_date_prefix and has_amount:
        return True
        
    return False

def is_address_line(line: str) -> bool:
    """
    Check if a line is likely part of an address.
    """
    line = line.lower()
    
    # Common address indicators
    address_indicators = [
        r'\b(?:flat|room|shop)\s*(?:no|number)?\.?\s*\d+',
        r'\b(?:floor|ground)\s*(?:no|number)?\.?\s*\d+',
        r'\b(?:building|bldg|apt|apartment|complex)\b',
        r'\b(?:road|rd|street|st|lane|ln|sector|plot|highway|nagar|colony|society|chs|chsl)\b',
        r'\b(?:near|opp|opposite|behind|beside|next to)\b',
        r'\b(?:village|town|city|district|taluka|tehsil)\b',
        r'\b(?:maharashtra|gujarat|delhi|mumbai|thane|india)\b',
        r'\b(?:east|west|north|south|central)\b',
        r'(?:\d+(?:\/[A-Za-z0-9-]+)+)',  # Address number patterns like 123/A, 45/2/B
        r'\d{6}',  # PIN code
    ]
    
    # Check for address indicators
    for pattern in address_indicators:
        if re.search(pattern, line):
            return True
            
    return False

def remove_address_block(lines: List[str]) -> List[str]:
    """
    Remove address blocks from the header lines.
    """
    cleaned_lines = []
    skip_mode = False
    address_line_count = 0
    
    for i, line in enumerate(lines):
        # Check if this line is an address line
        is_address = is_address_line(line)
        
        if is_address:
            address_line_count += 1
            if address_line_count >= 2:  # If we found multiple address lines
                skip_mode = True
                continue
        else:
            # If we were in skip mode and found a non-address line
            if skip_mode:
                address_line_count = 0
                skip_mode = False
            
            # Only add non-address lines
            if not is_address:
                cleaned_lines.append(line)
    
    return cleaned_lines

def is_likely_name_line(line: str) -> bool:
    """Check if line is likely to contain a name based on strong indicators"""
    line = line.strip().upper()
    
    # Strong name indicators - these are almost guaranteed to be name lines
    name_indicators = [
        "NAME OF CUSTOMER",
        "NAME :",
        "ACCOUNT NAME :",
        "M/S.",
        "M/S",
        "MR.",
        "MR ",
        "MS.",
        "MS "
    ]
    
    return any(indicator in line for indicator in name_indicators)

def clean_name_line(line: str) -> str:
    """Extract name from a line containing a name"""
    line = line.strip()
    
    # Remove everything after these terms
    cut_terms = ['BRANCH', 'ADDRESS', 'PHONE', 'EMAIL', 'ACCOUNT NO', 'CUSTOMER ID']
    for term in cut_terms:
        if term in line.upper():
            line = line.split(term)[0]
            
    # Remove known prefixes
    prefixes = ['NAME OF CUSTOMER', 'NAME:', 'ACCOUNT NAME :', 'M/S.', 'M/S', 'MR.', 'MR', 'MS.', 'MS']
    for prefix in prefixes:
        if line.upper().startswith(prefix):
            line = line[len(prefix):].strip()
            
    # Keep only UPPERCASE words that aren't banking terms
    banking_terms = {'BANK', 'STATEMENT', 'ACCOUNT', 'BRANCH', 'IFSC', 'CODE', 'PERIOD'}
    words = line.split()
    name_words = []
    
    for word in words:
        if word.isupper() and word not in banking_terms:
            name_words.append(word)
            
    return ' '.join(name_words)

def clean_header_line(line: str) -> str:
    """
    Clean header line by removing specific unwanted information.
    Shows each step of the cleaning process.
    """
    print_colored("\nHeader cleaning process:", Colors.CYAN)
    print_colored(f"INPUT > {line}", Colors.CYAN)
    
    # Skip empty lines
    if not line.strip():
        print_colored("SKIPPED: Empty line", Colors.WARNING)
        return ""
        
    # Skip if it's a table header or transaction
    if is_table_header(line) or is_transaction_line(line):
        print_colored("SKIPPED: Table/Transaction line", Colors.WARNING)
        return ""
        
    # Check if it's a likely name line
    if is_likely_name_line(line):
        cleaned_name = clean_name_line(line)
        if cleaned_name:
            print_colored(f"FOUND NAME: {cleaned_name}", Colors.GREEN)
            return cleaned_name
    
    print_colored("SKIPPED: No recognized name pattern", Colors.WARNING)
    return ""

def is_common_word(word: str) -> bool:
    """
    Check if a word is a common word that should be removed.
    Excludes the word 'Name' from removal.
    """
    common_words = {
        'the', 'and', 'or', 'of', 'to', 'in', 'for', 'with', 'by', 'at', 'from',
        'on', 'about', 'into', 'over', 'after', 'before', 'between', 'under',
        'above', 'below', 'up', 'down', 'out', 'off', 'through', 'statement',
        'account', 'banking', 'saving', 'current', 'joint', 'details', 'information',
        'customer', 'branch', 'date', 'period', 'summary', 'balance'
    }
    return word.lower() in common_words and word.lower() != 'name'

def detect_header_section(text: str) -> Tuple[List[str], List[str]]:
    """
    Detect and separate header content from table content.
    Returns tuple of (header_lines, table_lines)
    """
    if not text:
        return [], []

    # Split text into lines and remove empty lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    header_lines = []
    table_lines = []
    table_started = False
    
    for i, line in enumerate(lines):
        # If we already found table section, add to table lines
        if table_started:
            table_lines.append(line)
            continue
            
        # Check if this line starts a table section
        if is_table_header(line) or (i > 0 and is_transaction_line(line)):
            table_started = True
            table_lines.append(line)
            continue
            
        # Clean and add non-empty lines to header
        cleaned_line = clean_header_line(line)
        if cleaned_line:
            header_lines.append(cleaned_line)
    
    # Remove address blocks from header lines
    header_lines = remove_address_block(header_lines)
    
    return header_lines, table_lines

def score_potential_name(line: str) -> tuple[float, str]:
    """
    Score a line based on how likely it is to contain a company/person name.
    Returns (score, cleaned_line)
    """
    score = 0
    original_line = line
    line = line.strip()
    
    # Immediate disqualifiers (return 0 score)
    if not line or len(line) < 5:
        return 0, ""
    if any(char.isdigit() for char in line):
        return 0, ""
    if is_table_header(line) or is_transaction_line(line):
        return 0, ""
        
    # Split into words
    words = [w.strip() for w in line.split() if w.strip()]
    
    # Count uppercase words (excluding common banking terms)
    banking_terms = {'BANK', 'STATEMENT', 'ACCOUNT', 'BRANCH', 'IFSC', 'CODE', 'PERIOD'}
    uppercase_words = [w for w in words if w.isupper() and w not in banking_terms]
    
    if len(uppercase_words) < 2:  # Need at least 2 uppercase words
        return 0, ""
        
    # Basic score from uppercase words
    score += len(uppercase_words) * 10
    
    # Bonus for company indicators
    company_indicators = {'LIMITED', 'LTD', 'PVT', 'PRIVATE', 'CORPORATION', 'CORP', 'LLC', 'LLP'}
    if any(ind in uppercase_words for ind in company_indicators):
        score += 20
        
    # Penalty for address indicators
    address_indicators = {'ROAD', 'STREET', 'LANE', 'AVENUE', 'BUILDING', 'FLOOR', 'COMPLEX', 'PLAZA', 'TOWER'}
    if any(ind in uppercase_words for ind in address_indicators):
        score -= 30
        
    # Clean the line
    cleaned_line = ' '.join(uppercase_words)
    
    # Position-based scoring
    if ':' in original_line and any(name_prefix in original_line.upper() for name_prefix in ['NAME:', 'M/S:', 'MESSRS:']):
        score += 15
        
    # Length reasonability check
    if len(cleaned_line) > 50:  # Too long, probably not a name
        score -= 20
    
    return score, cleaned_line

def analyze_header_for_name(header_lines: List[str]) -> str:
    """
    Analyze header lines to find the most likely name using scoring system.
    """
    candidates = []
    
    for i, line in enumerate(header_lines[:10]):  # Only check first 10 lines
        score, cleaned_line = score_potential_name(line)
        if score > 0:
            # Add position bonus for earlier lines
            position_bonus = max(0, (10 - i) * 2)
            candidates.append((score + position_bonus, cleaned_line))
            
    # Sort by score and get best candidate
    if not candidates:
        return ""
        
    candidates.sort(reverse=True)
    return candidates[0][1]

def analyze_pdf(pdf_path: str) -> None:
    """Analyze a single PDF file"""
    try:
        print_colored(f"\nAnalyzing {os.path.basename(pdf_path)}:", Colors.HEADER)
        
        text = extract_text_from_pdf(pdf_path)
        if not text:
            print_colored("No text extracted from PDF!", Colors.FAIL)
            return

        header_lines, _ = detect_header_section(text)
        
        print_colored("\n=== PROCESSING HEADER LINES ===", Colors.CYAN)
        
        # First pass: Look for guaranteed name lines
        for line in header_lines:
            if is_likely_name_line(line):
                cleaned_name = clean_name_line(line)
                if cleaned_name:
                    print_colored(f"Found name (strong indicator): {cleaned_name}", Colors.GREEN)
                    print_colored(f"Original line: {line}", Colors.CYAN)
                    return
                    
        # Second pass: Look for UPPERCASE name patterns
        for line in header_lines:
            # Skip if line has numbers or looks like address
            if any(c.isdigit() for c in line) or is_address_line(line):
                continue
                
            words = line.split()
            uppercase_words = [w for w in words if w.isupper() and len(w) > 1]
            
            # Need at least 2 uppercase words
            if len(uppercase_words) >= 2:
                cleaned_name = clean_name_line(line)
                if cleaned_name:
                    print_colored(f"Found name (uppercase pattern): {cleaned_name}", Colors.GREEN)
                    print_colored(f"Original line: {line}", Colors.CYAN)
                    return
                    
        print_colored("No name found with high confidence", Colors.WARNING)
            
    except Exception as e:
        print_colored(f"Error processing {pdf_path}: {str(e)}", Colors.FAIL)
        traceback.print_exc()

def main():
    pdf_dir = "pdfs1"
    if not os.path.exists(pdf_dir):
        print_colored(f"Directory {pdf_dir} not found!", Colors.FAIL)
        return
        
    pdfs = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    
    if not pdfs:
        print_colored(f"No PDF files found in {pdf_dir}", Colors.FAIL)
        return
        
    print_colored(f"Found {len(pdfs)} PDF files", Colors.HEADER)
    
    for pdf_file in pdfs:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        analyze_pdf(pdf_path)

if __name__ == "__main__":
    main()
