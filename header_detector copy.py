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
    """
    Check if a line is likely to contain a name based on prefixes or the word 'name'.
    """
    # Common name indicators
    name_indicators = [
        r'\b(?:mr|mrs|ms|dr|shri|smt|m/s)\b',  # Common titles
        r'\bname\s*(?::|of|is)?\s*',  # Name indicators
        r'\b(?:proprietor|director|partner|trustee|owner)\s*(?:name)?\s*:?\s*',  # Business roles
    ]
    
    line_lower = line.lower()
    return any(re.search(pattern, line_lower) for pattern in name_indicators)

def clean_name_line(line: str) -> str:
    """
    Clean a line that's been identified as containing a name.
    Preserves the actual name while removing unwanted parts.
    """
    # Step 1: Save titles by replacing them temporarily
    title_patterns = [
        (r'\bM/S\b', '___MS___'),
        (r'\bMR\.\s', '___MR___'),
        (r'\bMRS\.\s', '___MRS___'),
        (r'\bMS\.\s', '___MS___'),
        (r'\bDR\.\s', '___DR___'),
        (r'\bSHRI\s', '___SHRI___'),
        (r'\bSMT\.\s', '___SMT___'),
    ]
    
    for pattern, placeholder in title_patterns:
        line = re.sub(pattern, placeholder, line, flags=re.IGNORECASE)
    
    # Step 2: Remove everything before "Name:" if it exists
    if 'name' in line.lower():
        line = re.sub(r'^.*?name\s*:?\s*', '', line, flags=re.IGNORECASE)
    
    # Step 3: Remove unwanted characters
    line = re.sub(r'[?.,:\(\)\[\]\{\}/\\"\'-]', ' ', line)
    
    # Step 4: Remove alphanumeric words (but not pure alphabetic words)
    words = line.split()
    cleaned_words = []
    for word in words:
        # Keep words that are either:
        # 1. All uppercase (potential name)
        # 2. Title case and not in common word list (potential name)
        # 3. One of our preserved titles
        if (word.isupper() or  # ALL CAPS
            word.startswith('___') or  # Preserved title
            (word.istitle() and not is_common_word(word))):  # Title case, not common word
            cleaned_words.append(word)
    
    line = ' '.join(cleaned_words)
    
    # Step 5: Restore titles
    for pattern, placeholder in title_patterns:
        original_title = pattern.replace(r'\b', '').replace(r'\s', ' ').replace('\\', '')
        line = line.replace(placeholder, original_title)
    
    return line.strip()

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

def clean_header_line(line: str) -> str:
    """
    Clean header line by removing specific unwanted information.
    Preserves names, titles (Mr/Mrs/Ms) and other important content.
    """
    # Skip empty or very short lines
    if not line or len(line.strip()) < 2:
        return ""
        
    # First check if this is likely a name line
    if not is_likely_name_line(line):
        return ""  # Skip non-name lines
    
    # Clean name line specifically
    cleaned_line = clean_name_line(line)
    if not cleaned_line:
        return ""
        
    # Remove email addresses and web links
    cleaned_line = re.sub(r'\S+@\S+\.\S+', '', cleaned_line)
    cleaned_line = re.sub(r'www\.\S+', '', cleaned_line)
    cleaned_line = re.sub(r'https?://\S+', '', cleaned_line)
    
    # Remove Indian states and territories
    states = [
        r'andhra\s*pradesh', r'arunachal\s*pradesh', r'assam', r'bihar', 
        r'chhattisgarh', r'goa', r'gujarat', r'haryana', r'himachal\s*pradesh', 
        r'j(?:ammu)?\s*&?\s*k(?:ashmir)?', r'jharkhand', r'karnataka', r'kerala', 
        r'madhya\s*pradesh', r'maharashtra', r'manipur', r'meghalaya', r'mizoram', 
        r'nagaland', r'odisha', r'punjab', r'rajasthan', r'sikkim', r'tamil\s*nadu', 
        r'telangana', r'tripura', r'uttar\s*pradesh', r'uttarakhand', r'west\s*bengal',
        r'andaman\s*(?:and|&)\s*nicobar', r'chandigarh', r'dadra\s*(?:and|&)\s*nagar\s*haveli',
        r'daman\s*(?:and|&)\s*diu', r'delhi', r'lakshadweep', r'puducherry'
    ]
    
    for state in states:
        cleaned_line = re.sub(state, '', cleaned_line, flags=re.IGNORECASE)
    
    # Remove specific banking terms and their values
    remove_terms = [
        # Account related
        r'account\s*(?:no|number|type)?[:\s]+[^,\n]*',
        r'acc(?:ount)?\s*(?:no|number|type)?[:\s]+[^,\n]*',
        r'a/c\s*(?:no|number|type)?[:\s]+[^,\n]*',
        r'saving\s*(?:account)?[:\s]+[^,\n]*',
        r'current\s*(?:account)?[:\s]+[^,\n]*',
        r'joint\s*(?:account)?[:\s]+[^,\n]*',
        
        # Banking codes
        r'ifsc\s*(?:code)?[:\s]+[A-Z0-9]+',
        r'micr\s*(?:code)?[:\s]+\d+',
        r'swift\s*(?:code)?[:\s]+[^,\n]*',
        r'branch\s*(?:name|code)?[:\s]+[^,\n]*',
        
        # Customer info
        r'customer\s*(?:id|no|number)?[:\s]+[^,\n]*',
        r'nominee[:\s]+[^,\n]*',
        r'phone\s*(?:no|number)?[:\s]+[^,\n]*',
        r'mobile\s*(?:no|number)?[:\s]+[^,\n]*',
        r'telephone[:\s]+[^,\n]*',
    ]
    
    for term in remove_terms:
        cleaned_line = re.sub(term, '', cleaned_line, flags=re.IGNORECASE)
    
    # Final cleanup
    cleaned_line = re.sub(r'\s+', ' ', cleaned_line).strip()
    
    # Only return if we have something meaningful left
    return cleaned_line if len(cleaned_line) > 2 else ""

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

def analyze_pdf(pdf_path: str) -> None:
    """Analyze a single PDF file"""
    try:
        # Extract text from PDF
        text = extract_text_from_pdf(pdf_path)
        
        if not text:
            print_colored(f"No text extracted from {pdf_path}", Colors.FAIL)
            return
            
        print_colored(f"\n{'='*50}", Colors.HEADER)
        print_colored(f"Analyzing PDF: {os.path.basename(pdf_path)}", Colors.HEADER)
        print_colored(f"{'='*50}\n", Colors.HEADER)
        
        # Detect header and table sections
        header_lines, table_lines = detect_header_section(text)
        
        # Print header content
        print_colored("\nHEADER CONTENT:", Colors.BOLD)
        for line in header_lines:
            # Skip lines that look like they might be part of table
            if not is_transaction_line(line) and not is_table_header(line):
                print_colored(line, Colors.GREEN)
            
        # Print where table starts
        if table_lines:
            print_colored("\nTABLE STARTS HERE:", Colors.WARNING)
            print_colored(table_lines[0], Colors.WARNING)
            if len(table_lines) > 1:
                print_colored(table_lines[1], Colors.WARNING)
                print_colored(f"... and {len(table_lines)-2} more lines", Colors.BLUE)
    except Exception as e:
        print_colored(f"Error processing {pdf_path}: {str(e)}", Colors.FAIL)
        print_colored(traceback.format_exc(), Colors.FAIL)

def main():
    pdf_dir = "pdfs2"
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
