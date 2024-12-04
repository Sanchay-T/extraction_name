import re

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_colored(text, color):
    """Print text in color"""
    print(f"{color}{text}{Colors.END}")

def clean_header_content(raw_content):
    """
    First cleaning stage - removes unnecessary information and formats text
    """
    if not raw_content:
        return ""
        
    print_colored("\n=== ORIGINAL TEXT ===", Colors.HEADER)
    print_colored(raw_content[:500] + "..." if len(raw_content) > 500 else raw_content, Colors.BLUE)
    
    # Split into lines
    lines = raw_content.split('\n')
    cleaned_lines = []
    
    # Words/patterns to remove completely (more comprehensive list)
    remove_patterns = [
        # Banking terms
        r'MICR\s*CODE[:\s]*\d+',
        r'IFSC[:\s]*[A-Z0-9]+',
        r'CIF\s*(?:NO|ID)?[:\s]*\d+',
        r'SOL\s*ID[:\s]*\d+',
        r'ACCOUNT[:\s]*\d+',
        r'BRANCH\s*CODE[:\s]*\d+',
        # Address indicators
        r'ADDRESS\s*LINE\s*\d+[:\s]*.*',
        r'(?:PLOT|FLAT|SHOP)\s*NO[:\s]*[\d/-]+',
        r'(?:SECTOR|BUILDING|FLOOR)[:\s]*[\d/-]+',
        r'PIN\s*CODE?[:\s]*\d{6}',
        r'(?:STREET|ROAD|LANE|NAGAR)[:\s]*[\w\s/-]+',
        # Contact info
        r'MOBILE[:\s]*\d+',
        r'PHONE[:\s]*\d+',
        r'EMAIL[:\s]*[\w@\.]+',
        # Transaction related
        r'OPENING\s*BAL[:\s]*[\d\.]+',
        r'CLOSING\s*BAL[:\s]*[\d\.]+',
        r'BALANCE[:\s]*[\d\.]+',
        # Dates
        r'FROM\s*DATE[:\s]*[\d/-]+',
        r'TO\s*DATE[:\s]*[\d/-]+',
        r'DATE[:\s]*[\d/-]+',
    ]
    
    # Common words to remove (expanded list)
    remove_words = {
        # Banking terms
        'STATEMENT', 'DETAILS', 'ACCOUNT', 'BRANCH', 'BANK',
        'TRANSACTION', 'BALANCE', 'CREDIT', 'DEBIT',
        'MICR', 'IFSC', 'CIF', 'SOL', 'ID', 'NO',
        # Status words
        'STATUS', 'ACTIVE', 'INACTIVE', 'CLOSED',
        # Address terms
        'ADDRESS', 'LINE', 'PLOT', 'FLAT', 'FLOOR',
        'SECTOR', 'BUILDING', 'STREET', 'ROAD',
        'COLONY', 'NAGAR', 'COMPLEX', 'TOWER',
        'CITY', 'STATE', 'COUNTRY', 'PIN', 'CODE',
        # Contact
        'MOBILE', 'PHONE', 'EMAIL', 'CONTACT',
        # Dates
        'DATE', 'PERIOD', 'FROM', 'TO',
        # Other
        'DETAILS', 'OF', 'FOR', 'THE', 'AND',
    }
    
    print_colored("\n=== CLEANING PROCESS ===", Colors.HEADER)
    print_colored("Original text:", Colors.BOLD)
    print_colored(raw_content[:200] + "..." if len(raw_content) > 200 else raw_content, Colors.BLUE)
    
    address_block_started = False
    consecutive_address_lines = 0
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            address_block_started = False
            consecutive_address_lines = 0
            continue
            
        # Remove known patterns
        for pattern in remove_patterns:
            line = re.sub(pattern, '', line, flags=re.IGNORECASE)
        
        # Remove common words if they're standalone
        words = line.split()
        filtered_words = []
        for word in words:
            if word.upper() not in remove_words:
                filtered_words.append(word)
        line = ' '.join(filtered_words)
        
        # Skip if line became empty after cleaning
        if not line.strip():
            continue
            
        # Check if this looks like an address line
        address_indicators = [
            r'\d+(?:ST|ND|RD|TH)?(?:\s+FLOOR|\s+CROSS)?',
            r'(?:NEAR|OPP|BEHIND|BESIDE)',
            r'\b[A-Z]+\s*(?:EAST|WEST|NORTH|SOUTH)\b',
            r'\d{6}\b',  # PIN code
        ]
        
        is_address = any(re.search(pattern, line, re.IGNORECASE) for pattern in address_indicators)
        
        if is_address:
            address_block_started = True
            consecutive_address_lines += 1
            continue
            
        # If we're in address block and line has numbers/commas, likely still address
        if address_block_started and (re.search(r'\d', line) or ',' in line):
            consecutive_address_lines += 1
            continue
            
        # Reset address block if we haven't seen address patterns
        if consecutive_address_lines == 0:
            address_block_started = False
            
        if not address_block_started:
            cleaned_lines.append(line)
    
    cleaned_text = '\n'.join(cleaned_lines)
    print_colored("\n=== CLEANED TEXT (Ready for Name Detection) ===", Colors.HEADER)
    print_colored(cleaned_text[:200] + "..." if len(cleaned_text) > 200 else cleaned_text, Colors.GREEN)
    
    return cleaned_text

def extract_account_number(text):
    """
    Extract account number using various patterns
    """
    # Patterns to find account numbers (ordered by reliability)
    account_patterns = [
        r'(?i).*account.*?(?:no|number|#).*?(\d{10,})',  # Account No/Number followed by 10+ digits
        r'(?i)a/c.*?(?:no|number|#).*?(\d{10,})',       # A/C No followed by 10+ digits
        r'(?i)(?:acc|account).*?:.*?(\d{10,})',         # Account: followed by 10+ digits
    ]
    
    for pattern in account_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1), match.group(0)
    
    # If no match with explicit account patterns, look for any 10+ digit number
    # But avoid lines with common transaction-related words
    lines = text.split('\n')
    for line in lines:
        if not re.search(r'(?i)(balance|credit|debit|amount|date|transaction)', line):
            match = re.search(r'\b(\d{10,})\b', line)
            if match:
                return match.group(1), line
                
    return None, None

def is_indian_phone(number):
    """Check if a number matches common Indian phone number patterns"""
    # Common Indian mobile prefixes (excluding when part of account number)
    MOBILE_PREFIXES = {'88', '89', '90', '99', '98', '97', '96', '95', '93', '94', '92', '70', 
                      '71', '72', '73', '74', '75', '76', '77', '78', '79', '80', '81', '82', 
                      '83', '84', '85', '86', '87'}
    
    # Remove any spaces or special chars
    number = ''.join(filter(str.isdigit, number))
    
    # If number starts with 91 and is 12 digits, check the next two digits
    if len(number) == 12 and number.startswith('91'):
        next_two = number[2:4]
        # Only consider it a phone if the next two digits match mobile prefixes
        return next_two in MOBILE_PREFIXES
    
    # For 10 digit numbers, check first two digits
    if len(number) == 10:
        prefix = number[:2]
        return prefix in MOBILE_PREFIXES
        
    return False

# Comprehensive list of words to ignore when detecting names
IGNORE_WORDS = {
    # Banking terms
    'BANK', 'BRANCH', 'STATEMENT', 'ACCOUNT', 'DETAILS', 'SUPPLY', 'BILL',
    'FATCA', 'CRS', 'COMPLIANCE', 'IFSC', 'MICR', 'CODE', 'SWIFT', 'IBAN',
    'SAVINGS', 'CURRENT', 'FIXED', 'DEPOSIT', 'FD', 'RD', 'LOAN',
    
    # Document/Form terms
    'FORM', 'APPLICATION', 'DOCUMENT', 'COPY', 'ORIGINAL', 'DUPLICATE',
    'SUMMARY', 'DETAILS', 'INFORMATION', 'STATUS', 'TYPE', 'CATEGORY',
    
    # Address terms - Enhanced for Indian addresses
    'ADDRESS', 'ROAD', 'STREET', 'LANE', 'BUILDING', 'FLOOR', 'HOUSE',
    'APARTMENT', 'FLAT', 'PLOT', 'SECTOR', 'AREA', 'DISTRICT', 'CITY',
    'STATE', 'COUNTRY', 'PINCODE', 'PIN', 'ZIP', 'POSTAL',
    # Common Indian address terms
    'NAGAR', 'COLONY', 'SOCIETY', 'CHS', 'CHAWL', 'MARG', 'PATH',
    'COMPLEX', 'TOWER', 'HEIGHTS', 'PALACE', 'VILLA', 'BUNGALOW',
    'APARTMENT', 'RESIDENCY', 'NEAR', 'OPP', 'BEHIND', 'ABOVE',
    'BESIDES', 'FRONT', 'BACK', 'SIDE', 'CROSS', 'MAIN',
    # Directional terms
    'EAST', 'WEST', 'NORTH', 'SOUTH', 'EASTERN', 'WESTERN', 'NORTHERN', 'SOUTHERN',
    # Common place identifiers
    'MARKET', 'BAZAAR', 'CIRCLE', 'JUNCTION', 'STATION', 'TEMPLE', 'MASJID',
    'CHURCH', 'HOSPITAL', 'SCHOOL', 'COLLEGE', 'UNIVERSITY', 'PARK',
    'GARDEN', 'GROUND', 'MALL', 'PLAZA', 'CENTRE', 'CENTER',
    
    # Transaction terms
    'CREDIT', 'DEBIT', 'BALANCE', 'AMOUNT', 'OPENING', 'CLOSING',
    'WITHDRAWAL', 'DEPOSIT', 'TRANSFER', 'TRANSACTION', 'PAYMENT',
    
    # Identification terms
    'ID', 'NUMBER', 'NO', 'NUM', 'CUSTOMER', 'HOLDER', 'NOMINEE',
    'PRIMARY', 'SECONDARY', 'JOINT', 'CIF', 'KYC', 'PAN', 'AADHAR',
    
    # Contact terms
    'MOBILE', 'PHONE', 'TEL', 'EMAIL', 'FAX', 'CONTACT',
    
    # Business terms
    'LIMITED', 'LTD', 'PVT', 'PRIVATE', 'CORPORATION', 'CORP', 'INC',
    'ENTERPRISE', 'ENTERPRISES', 'TRADING', 'TRADERS', 'COMPANY',
    
    # Date/Time terms
    'DATE', 'TIME', 'PERIOD', 'FROM', 'TO', 'SINCE', 'UNTIL',
    
    # Currency terms
    'INR', 'RS', 'RUPEE', 'RUPEES', 'PAISA', 'CURRENCY',
    
    # Status terms
    'ACTIVE', 'INACTIVE', 'CLOSED', 'SUSPENDED', 'DORMANT',
}

def clean_line_for_name_detection(line):
    """Remove known non-name patterns and clean the line"""
    line = line.upper()
    
    # Remove common non-name patterns with more aggressive matching
    patterns_to_remove = [
        r'BRANCH.*',
        r'BANK.*',
        r'STATEMENT.*',
        r'PIN.*',
        r'MICR.*',
        r'IFSC.*',
        r'ACCOUNT.*',
        r'CUSTOMER.*',
        r'EMAIL.*',
        r'PHONE.*',
        r'MOBILE.*',
        r'ADDRESS.*',
        r'BALANCE.*',
        r'TRANSACTION.*',
        r'DATE.*',
        r'PERIOD.*',
        r'NOMINEE.*',
        r'PURPOSE.*',
        r'SCHEME.*',
        r'STATUS.*',
        r'DETAILS.*',
        r'GST.*',
        r'REGISTRATION.*',
        r'CIF.*',
        r'YOUR.*',
        r'CITY.*',
        r'STATE.*',
        r'COUNTRY.*',
        r'ZIP.*',
        r'LINE \d.*',
        r'CODE.*',
        r'OPEN.*',
        r'TYPE.*',
        r'TOTAL.*'
    ]
    
    # Remove each pattern
    for pattern in patterns_to_remove:
        line = re.sub(pattern, '', line)
    
    # Remove numbers and special characters but preserve dots in initials
    line = re.sub(r'(?<!\w)\d+(?!\w)', '', line)  # Numbers not part of words
    line = re.sub(r'[^\w\s\.]', '', line)  # Keep dots for initials
    
    # Special handling for initials - preserve them
    line = re.sub(r'(?<=[A-Z])\s+(?=[A-Z]\s|[A-Z]\.)', '', line)  # Remove spaces between initials
    
    # Remove extra spaces
    line = ' '.join(line.split())
    
    return line

def find_name_line(cleaned_lines):
    """Find the most likely line containing the customer name"""
    
    print_colored("\n=== NAME LINE DETECTION PROCESS ===", Colors.HEADER)
    
    def print_context(idx, lines, context_lines=2):
        """Print lines before and after the detected line with color"""
        start = max(0, idx - context_lines)
        end = min(len(lines), idx + context_lines + 1)
        
        print_colored("\nContext around line:", Colors.BOLD)
        for i in range(start, end):
            prefix = ">" if i == idx else " "
            if i == idx:
                print_colored(f"{prefix} {i+1}: {lines[i]}", Colors.GREEN)
            else:
                print(f"{prefix} {i+1}: {lines[i]}")
    
    # First check for multi-line branch patterns to exclude
    def is_branch_line(idx, lines):
        if idx >= len(lines):
            return False
        current_line = lines[idx].strip().upper()
        next_line = lines[idx + 1].strip().upper() if idx + 1 < len(lines) else ""
        
        # Check if line contains branch-related content
        branch_indicators = [
            'BRANCH NAME', 'BRANCH CODE', 'BRANCH ADDRESS',
            'SOL ID', 'UMFB', 'ANKLESHWAR BRANCH'
        ]
        
        if any(indicator in current_line for indicator in branch_indicators):
            return True
            
        # Check for split BRANCH NAME patterns
        if ('BRANCH' in current_line and 'NAME' in next_line):
            return True
            
        return False

    def clean_extracted_name(name):
        """Clean and validate extracted name"""
        if not name:
            return None
            
        # Remove common prefixes that might be captured
        name = re.sub(r'^(?:YOUR\s+DETAILS?\s+(?:WITH\s+)?(?:US|ARE)?[:\s]+)', '', name, flags=re.IGNORECASE)
        name = re.sub(r'^(?:CUSTOMER|ACCOUNT)\s+DETAILS?\s*[:\s]+', '', name, flags=re.IGNORECASE)
        
        # Remove common non-name parts
        name = re.sub(r'FROM\s+DATE.*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'TO\s+DATE.*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'BRANCH.*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'UMFB.*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'ANKLESHWAR.*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'MICR.*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'IFSC.*', '', name, flags=re.IGNORECASE)
        
        # Clean up whitespace
        name = ' '.join(name.split())
        
        # Validate the cleaned name
        if len(name) < 2 or any(word in name.upper() for word in ['BRANCH', 'BANK', 'UMFB', 'DETAILS']):
            return None
            
        return name
    
    # Step 1: First look for explicit name indicators
    name_indicators = [
        # Handle cases where NAME is joined with text
        (r'(?i)NAME\s*([A-Z][A-Z\s\.&]+?)(?:\s+FROM|\s+MICR|\s+TO|\s+BRANCH|$)', 40),
        (r'(?i)CUSTOMER\s*NAME\s*([A-Z][A-Z\s\.&]+?)(?:\s+FROM|\s+MICR|\s+TO|\s+BRANCH|$)', 40),
        (r'(?i)A/C\s*NAME\s*([A-Z][A-Z\s\.&]+?)(?:\s+FROM|\s+MICR|\s+TO|\s+BRANCH|$)', 40),
        (r'(?i)ACCOUNT\s*NAME\s*([A-Z][A-Z\s\.&]+?)(?:\s+FROM|\s+MICR|\s+TO|\s+BRANCH|$)', 40),
    ]
    
    print_colored("\nStep 1: Checking for explicit name indicators...", Colors.BOLD)
    for i, line in enumerate(cleaned_lines):
        line = line.strip()
        if not line or is_branch_line(i, cleaned_lines):
            continue
            
        # Check each pattern
        for pattern, score in name_indicators:
            match = re.search(pattern, line)
            if match:
                name = clean_extracted_name(match.group(1))
                if name:
                    print_colored("\nFound explicit name indicator!", Colors.GREEN)
                    print_context(i, cleaned_lines)
                    print_colored(f"Extracted name: {name}", Colors.GREEN)
                    print(f"Score: {score}")
                    return line

    # Step 2: Look for business/personal prefixes
    print_colored("\nStep 2: Checking for business/personal prefixes...", Colors.BOLD)
    name_prefixes = [
        # Business prefixes with details prefix handling
        (r'(?:YOUR\s+DETAILS?\s+(?:WITH\s+)?(?:US|ARE)?[:\s]+)?M/S\.?\s+([A-Z][A-Z\s\.&,]+?)(?:\s+FROM|\s+MICR|\s+TO|\s+BRANCH|$)', 35),
        (r'(?:YOUR\s+DETAILS?\s+(?:WITH\s+)?(?:US|ARE)?[:\s]+)?MESSRS\.?\s+([A-Z][A-Z\s\.&,]+?)(?:\s+FROM|\s+MICR|\s+TO|\s+BRANCH|$)', 35),
        # Look for business entities
        (r'(?:YOUR\s+DETAILS?\s+(?:WITH\s+)?(?:US|ARE)?[:\s]+)?([A-Z][A-Z\s\.&,]+?\s+(?:ENTERPRISE|TRADING|CORPORATION|INDUSTRIES))(?:\s+FROM|\s+MICR|\s+TO|\s+BRANCH|$)', 35),
        # Personal prefixes
        (r'(?:YOUR\s+DETAILS?\s+(?:WITH\s+)?(?:US|ARE)?[:\s]+)?(?:MR|MRS|MS|MISS|DR|SHRI|SMT|KUM)\.?\s+([A-Z][A-Z\s\.&,]+?)(?:\s+FROM|\s+MICR|\s+TO|\s+BRANCH|$)', 30),
    ]
    
    for i, line in enumerate(cleaned_lines):
        line = line.strip()
        if not line or is_branch_line(i, cleaned_lines):
            continue
            
        for pattern, score in name_prefixes:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                # For business names, try to get the full name including M/S
                full_match = match.group(0)
                if 'M/S' in full_match.upper() or any(word in full_match.upper() for word in ['ENTERPRISE', 'TRADING', 'CORPORATION', 'INDUSTRIES']):
                    name = clean_extracted_name(full_match)
                else:
                    name = clean_extracted_name(match.group(1))
                    
                if name:
                    print_colored("\nFound name prefix!", Colors.GREEN)
                    print_context(i, cleaned_lines)
                    print_colored(f"Extracted name: {name}", Colors.GREEN)
                    print(f"Score: {score}")
                    return line
{{ ... }}

def extract_name_from_line(line):
    """Extract the actual name from a line containing the name"""
    if not line:
        return None
        
    line_upper = line.upper()
    
    # Try to find name after common prefixes
    name_patterns = [
        # After explicit name label with flexible spacing
        r'(?:CUSTOMER|ACCOUNT)?\s*NAME\s*[:. -]?\s*((?:[A-Z][A-Za-z\s\.&]+){1,6})',
        # After Mr/Mrs/Ms with flexible format
        r'(?:MR|MRS|MS|MISS|DR|SHRI|SMT)\.?\s+((?:[A-Z][A-Za-z\s\.&]+){1,6})',
        # Business names with M/S
        r'M/S\.?\s+((?:[A-Z][A-Za-z\s\.&]+){1,6})',
        # Business names with ENTERPRISE
        r'([A-Z][A-Za-z\s\.&]+\s+ENTERPRISE)',
        # Names with common Indian suffixes
        r'(?:^|\s)((?:[A-Z][A-Za-z]+\s+){1,3}(?:KUMAR|LAL|CHAND|RAJ|DEVI|BAI|SINGH|KAUR))',
        # Clean capital sequence allowing mixed case
        r'(?:^|\s)((?:[A-Z][A-Za-z]+\s+){1,5}[A-Z][A-Za-z]+)(?:\s|$)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, line_upper)
        if match:
            name = match.group(1).strip()
            # Clean the extracted name
            name = re.sub(r'FROM\s+DATE.*', '', name, flags=re.IGNORECASE)
            name = re.sub(r'TO\s+DATE.*', '', name, flags=re.IGNORECASE)
            name = re.sub(r'BRANCH.*', '', name, flags=re.IGNORECASE)
            name = re.sub(r'UMFB.*', '', name, flags=re.IGNORECASE)
            name = re.sub(r'ANKLESHWAR.*', '', name, flags=re.IGNORECASE)
            name = re.sub(r'MICR.*', '', name, flags=re.IGNORECASE)
            
            words = name.split()
            
            # Validate extracted name
            if (2 <= len(words) <= 6 and  # Increased max words for business names
                not any(word in ['BRANCH', 'BANK', 'STATEMENT', 'UMFB'] for word in words) and
                all(len(word) >= 2 for word in words)):
                return name
    
    return None

def filter_header_data(raw_content):
    """Filter header data to extract account number and customer name"""
    if not raw_content:
        return {
            'account_number': None,
            'customer_name': None,
            'account_line': None,
            'name_line': None,
            'cleaned_content': None,
            'detection_info': None
        }

    print_colored("\n=== NAME LINE DETECTION PROCESS ===", Colors.HEADER)
    print_colored("Processing each line with multiple validation checks...", Colors.BOLD)
    
    # Split content into lines and clean each line
    lines = raw_content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        cleaned = re.sub(r'[^\w\s.-:]', ' ', line).strip()
        if cleaned:
            cleaned_lines.append(cleaned)
    
    cleaned_content = '\n'.join(cleaned_lines)
    
    # Find account number (keeping existing logic)
    account_number = None
    account_line = None
    for line in cleaned_lines:
        acc_num = extract_account_number(line)
        if acc_num:
            account_number = acc_num
            account_line = line
            break
    
    # Find name line with detailed validation
    name_line = find_name_line(cleaned_lines)
    customer_name = extract_name_from_line(name_line) if name_line else None
    
    return {
        'account_number': account_number,
        'customer_name': customer_name,
        'account_line': account_line,
        'name_line': name_line,
        'cleaned_content': cleaned_content,
        'detection_info': None
    }
