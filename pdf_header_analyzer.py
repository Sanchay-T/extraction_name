import re
import os
from typing import List, Tuple
import pdfplumber
import traceback


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_colored(text: str, color: str) -> None:
    print(f"{color}{text}{Colors.END}")


class PDFHeaderAnalyzer:
    def __init__(self):
        # Address trigger words that typically START an address block
        self.address_triggers = {
            "address",
            "communication address",
            "branch address",
            "address line 1",
            "address line 2",
            "address line 3",
            "registered address",
            "correspondence address",
            "customer address",
            "address of customer",
        }

        # Words that typically appear IN address lines
        self.address_content_markers = [
            # Building/Property identifiers
            r"\b(?:flat|room|shop|gala|plot)\s*(?:no|number)?\.?\s*[a-z0-9/-]+",
            r"\b(?:floor|ground)\s*(?:no|number)?\.?\s*[a-z0-9-]+",
            r"\b(?:building|bldg|tower|wing|complex|plaza|arcade|chawl|society|chs)\b",
            # Location identifiers
            r"\b(?:sector|phase|block)\s*[-:]?\s*[a-z0-9]+",
            r"\b(?:near|opp|opposite|behind|beside|next to)\b",
            r"\b(?:road|rd|street|st|lane|ln|marg|highway)\b",
            r"\b(?:nagar|colony|society|chs|chsl|apartment|premises)\b",
            # Area identifiers
            r"\b(?:east|west|north|south|central)\s+[a-z]+\b",
            r"\b(?:industrial|midc|commercial|residential)\s+(?:area|zone|estate)\b",
            # PIN code patterns
            r"\b\d{6}\b",
            r"\bpin\s*(?:code)?[:.-]?\s*\d{6}\b",
        ]

        # Common address ending indicators
        self.address_end_markers = {
            "phone",
            "mobile",
            "tel",
            "email",
            "account",
            "customer id",
            "branch code",
            "ifsc",
            "micr",
            "statement period",
            "currency",
            "nominee",
            "joint holder",
        }

        # Additional patterns to identify address lines
        self.address_line_patterns = [
            r".*(?:mumbai|thane|pune|delhi|bangalore).*\d{6}",
            r".*(?:maharashtra|gujarat|delhi|karnataka).*(?:-|,|\s+)india",
            r".*\b(?:room|flat|shop)\s*no\b.*",
            r".*\b(?:near|opp|behind)\b.*",
            r".*\b(?:road|street|lane|nagar)\b.*\d{6}",
            r".*\b(?:branch|communication)\s*address\b.*",
        ]

        # Table header indicators
        self.table_header_combinations = [
            ["date", "particulars"],
            ["date", "description"],
            ["date", "narration"],
            ["date", "transaction"],
            ["txn", "date"],
            ["value", "date"],
            ["transaction", "details"],
        ]

        self.table_column_terms = {
            "date",
            "particulars",
            "description",
            "debit",
            "credit",
            "withdrawal",
            "deposit",
            "balance",
            "amount",
            "chq",
            "ref",
            "narration",
            "transaction",
            "details",
        }

        # Add new banned words and patterns
        self.banned_words = {
            "account",
            "statement",
            "date",
            "currency",
            "type",
            "no",
            "number",
            "nominee",
            "registered",
            "ifsc",
            "micr",
            "code",
            "phone",
            "branch",
            "base",
            "mobile",
            "email",
            "id",
            "cif",
            "customer",
            "period",
            "status",
            "active",
            "balance",
            "inr",
            "savings",
            "current",
            "joint",
            "holder",
            "scheme",
            "banking",
            "smart",
            "details",
            "address",
            "gstin",
            "sac",
        }

        # Name indicators to preserve names
        self.name_indicators = {
            "mr",
            "mrs",
            "ms",
            "dr",
            "shri",
            "smt",
            "m/s",
            "miss",
            "kumar",
            "kumari",
            "sri",
            "smt",
        }

        # Patterns to remove
        self.remove_patterns = [
            r"\d+[/-]\d+[/-]\d+",  # Dates
            r"\b\d{6}\b",  # PIN codes
            r"\b\d{10,}\b",  # Long numbers (account, phone)
            r"\b\d+\b",  # Any standalone numbers
            r"\b[A-Z0-9]{8,}\b",  # Alphanumeric codes (IFSC etc)
            r"\b[A-Z]{4}\d{7}\b",  # Specific code patterns
            r"branch.*$",  # Remove everything after "branch"
            r":[^:]*",  # Remove everything after colon
            r"-[^-]*",  # Remove everything after hyphen
            r"[(),.]",  # Remove punctuation
            r"\s+",  # Multiple spaces
        ]

    def extract_text_from_pdf(self, pdf_path: str) -> str:
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

    def is_address_trigger(self, line: str) -> bool:
        """Check if line contains a word that typically starts an address block"""
        line = line.lower().strip()
        return any(trigger in line for trigger in self.address_triggers)

    def is_address_content(self, line: str) -> bool:
        """Check if line contains typical address content"""
        line = line.lower().strip()

        # Check for address patterns
        if any(re.search(pattern, line) for pattern in self.address_content_markers):
            return True

        # Check for city/state/country pattern (Comma separated location info)
        location_pattern = r"(?:[a-z\s]+,\s*)*(?:india|maharashtra|gujarat|delhi)"
        if re.search(location_pattern, line):
            return True

        return False

    def is_address_end(self, line: str) -> bool:
        """Check if line likely indicates end of address block"""
        line = line.lower().strip()
        return any(marker in line for marker in self.address_end_markers)

    def is_address_line(self, line: str) -> bool:
        """Enhanced check if line is likely part of an address"""
        line = line.lower().strip()

        # Check for explicit address markers
        if any(re.search(pattern, line) for pattern in self.address_content_markers):
            return True

        # Check for additional address patterns
        if any(
            re.search(pattern, line, re.IGNORECASE)
            for pattern in self.address_line_patterns
        ):
            return True

        # Check for city/state combinations
        if re.search(r".*(?:mumbai|thane|pune).*(?:maharashtra|gujarat|delhi)", line):
            return True

        # Check for PIN code pattern
        if re.search(r"\b\d{6}\b", line):
            return True

        return False

    def find_address_block(self, lines: List[str]) -> Tuple[int, int]:
        """Find start and end of address block using improved logic"""
        start_idx = -1
        end_idx = -1
        in_address_block = False
        consecutive_address_lines = 0

        for i, line in enumerate(lines):
            line_lower = line.lower().strip()

            # Check for address trigger or content
            is_trigger = any(trigger in line_lower for trigger in self.address_triggers)
            is_address = self.is_address_line(line)

            if is_trigger or is_address:
                if not in_address_block:
                    start_idx = i
                    in_address_block = True
                consecutive_address_lines += 1
                end_idx = i
            else:
                if in_address_block:
                    # If we hit a non-address line and have enough context
                    if consecutive_address_lines >= 2:
                        break
                    # Reset if we don't have enough consecutive lines
                    else:
                        start_idx = -1
                        end_idx = -1
                        in_address_block = False
                consecutive_address_lines = 0

        return start_idx, end_idx

    def remove_address_block(self, lines: List[str]) -> List[str]:
        """Remove address block from text"""
        if not lines:
            return lines

        start_idx, end_idx = self.find_address_block(lines)

        # If we found an address block
        if start_idx != -1 and end_idx != -1:
            # Remove the entire block including the trigger line
            return lines[:start_idx] + lines[end_idx + 1 :]

        return lines

    def is_table_header(self, line: str) -> bool:
        """Check if line is likely a table header"""
        line = line.lower()

        # Check for common header combinations
        for combo in self.table_header_combinations:
            if all(term in line for term in combo):
                return True

        # Check for column-like structure with common banking terms
        columns = [col.strip() for col in line.split() if col.strip()]
        matching_terms = sum(1 for col in columns if col in self.table_column_terms)
        return matching_terms >= 3

    def is_transaction_line(self, line: str) -> bool:
        """Check if line is likely a transaction entry"""
        line = line.lower()

        # Check for date pattern at start
        date_pattern = r"^\s*\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
        has_date = bool(re.match(date_pattern, line))

        # Check for amount patterns
        amount_patterns = [
            r"\d+,\d{3}\.\d{2}",  # 1,234.56
            r"\d+\.\d{2}\s*(?:cr|dr)?",  # 1234.56 CR
            r"(?:cr|dr)\s*\d+\.\d{2}",  # CR 1234.56
        ]
        has_amount = any(
            re.search(pattern, line, re.IGNORECASE) for pattern in amount_patterns
        )

        return has_date and has_amount

    def extract_name(self, lines: List[str]) -> str:
        """Extract name from the header lines"""
        for line in lines:
            line_lower = line.lower()
            # Check for name indicators
            if any(indicator in line_lower for indicator in self.name_indicators):
                # Clean up the name line
                name = line.strip()
                # Remove any numbers or special characters
                name = re.sub(r"[0-9(),.:/-]", "", name)
                # Remove extra spaces
                name = re.sub(r"\s+", " ", name).strip()
                return name
        return ""

    def clean_header_content(self, lines: List[str]) -> List[str]:
        """Clean header content by removing banned words and patterns while maintaining natural text flow"""
        cleaned_lines = []

        for line in lines:
            if not line.strip():
                continue

            # Skip lines with too many numbers
            if len(re.findall(r"[0-9/-]", line)) > len(line) / 3:
                continue

            working_line = line

            # First remove banned patterns
            for pattern in self.remove_patterns:
                working_line = re.sub(pattern, " ", working_line)

            # Split into words, remove banned words, and rejoin naturally
            words = working_line.split()
            cleaned_words = [
                word for word in words if word.lower() not in self.banned_words
            ]
            working_line = " ".join(cleaned_words)

            # Clean up any extra whitespace while maintaining single spaces between words
            working_line = " ".join(working_line.split())

            # Only add non-empty lines that aren't just special characters
            if working_line.strip() and not re.match(
                r"^[\s\W]+$", working_line.strip()
            ):
                cleaned_lines.append(working_line)

        return cleaned_lines

    def analyze_pdf(self, pdf_path: str) -> None:
        """Analyze a single PDF file"""
        try:
            text = self.extract_text_from_pdf(pdf_path)
            if not text:
                print_colored(f"No text extracted from {pdf_path}", Colors.FAIL)
                return

            print_colored(f"\n{'='*50}", Colors.HEADER)
            print_colored(f"Analyzing PDF: {os.path.basename(pdf_path)}", Colors.HEADER)
            print_colored(f"{'='*50}\n", Colors.HEADER)

            # Get raw lines and remove "ACCOUNT STATEMENT"
            raw_lines = [
                line.strip() 
                for line in text.split("\n") 
                if line.strip() and not re.match(r"(?i)^\s*ACCOUNT\s+STATEMENT\s*$", line.strip())
            ]

            # Print first 10 raw lines
            print_colored("FIRST 10 RAW LINES:", Colors.BOLD)
            for i, line in enumerate(raw_lines[:10]):
                print_colored(f"{i+1}. {line}", Colors.BLUE)

            print_colored("\n" + "-" * 50, Colors.HEADER)

            # First try one-shot patterns on entire text
            print_colored("ATTEMPTING ONE-SHOT PATTERN MATCHING:", Colors.BOLD)
            full_text = "\n".join(raw_lines)
            
            one_shot_patterns = [
                # Name of Customer cases (must be first)
                (r"(?i)name\s+of\s+customer\s*:?\s*([A-Z]+(?:\s+[A-Z]+){1,3})(?=\s*$|\s+[a-z]|\s*[,.])", "Name of Customer pattern"),
                # Customer Name cases - fixed to capture full name after colon
                (r"(?i)customer\s+name\s*:\s*(.*?)(?=\s*(?:address|details|statement|$))", "Customer Name pattern"),
                # Direct MR/MRS cases (case insensitive)
                (r"(?i)^(?:mr|mrs|ms|dr)\.?\s+([A-Z\s]+?)(?:\s+(?:acc|branch|your)|$)", "Title pattern"),
                # Account Name cases
                (r"(?i)account\s+name\s*:?\s*([A-Z\s]+?)(?:\s+|$)", "Account Name pattern"),
            ]

            # Try one-shot patterns on full text
            extracted_name = ""
            for pattern, pattern_name in one_shot_patterns:
                print_colored(f"\nTrying {pattern_name}:", Colors.WARNING)
                matches = re.finditer(pattern, full_text, re.MULTILINE)
                for match in matches:
                    if pattern_name == "Customer Name pattern":
                        line = match.group(0)
                        name = line.split(":", 1)[1].strip()  # Get everything after colon
                        if name and all(word[0].isupper() for word in name.split()):  # Ensure all words are capitalized
                            print_colored(f"Match found! Extracted name: {name}", Colors.GREEN)
                            extracted_name = name
                            break
                    else:
                        name = match.group(1).strip()
                        if name.upper() not in {"ACCOUNT", "STATEMENT", "DETAILS", "BRANCH", "BANK"}:
                            print_colored(f"Match found! Extracted name: {name}", Colors.GREEN)
                            extracted_name = name
                            break

            if extracted_name:
                print_colored("\nFINAL EXTRACTION RESULTS:", Colors.BOLD)
                print_colored(f"Entity Type: INDIVIDUAL", Colors.BLUE)
                print_colored(f"Name: {extracted_name}", Colors.GREEN)
                return

            # If no one-shot matches found, proceed with regular flow
            print_colored("\nNo one-shot patterns matched, proceeding with regular flow", Colors.WARNING)

            # Process header content
            header_lines = []
            for line in raw_lines:
                if self.is_table_header(line) or self.is_transaction_line(line):
                    break
                header_lines.append(line)

            # Continue with address block detection
            start_idx, end_idx = self.find_address_block(header_lines)

            print_colored("DETECTED ADDRESS BLOCK:", Colors.BOLD)
            if start_idx != -1 and end_idx != -1:
                for i in range(start_idx, end_idx + 1):
                    print_colored(f"REMOVED: {header_lines[i]}", Colors.WARNING)
                cleaned_lines = header_lines[:start_idx] + header_lines[end_idx + 1 :]
            else:
                print_colored("No address block detected", Colors.WARNING)
                cleaned_lines = header_lines

            print_colored("\nPROCESSED HEADER CONTENT (AFTER ADDRESS REMOVAL):", Colors.BOLD)
            if cleaned_lines:
                for line in cleaned_lines:
                    print_colored(line, Colors.GREEN)

                # Clean and extract name
                print_colored("\nEXTRACTED AND CLEANED CONTENT:", Colors.BOLD)
                final_cleaned_lines = self.clean_header_content(cleaned_lines)
                for line in final_cleaned_lines:
                    print_colored(line, Colors.BLUE)
                
                extracted_name = self.extract_name(final_cleaned_lines)
                
                # Print final results
                print_colored("\nFINAL EXTRACTION RESULTS:", Colors.BOLD)
                if extracted_name:
                    print_colored(f"Entity Type: UNKNOWN", Colors.BLUE)
                    print_colored(f"Name: {extracted_name}", Colors.GREEN)
                else:
                    print_colored("No name could be extracted", Colors.FAIL)
            else:
                print_colored("No header content after processing", Colors.WARNING)

        except Exception as e:
            print_colored(f"Error processing {pdf_path}: {str(e)}", Colors.FAIL)
            print_colored(traceback.format_exc(), Colors.FAIL)

    def analyze_pdf_directory(self, pdf_dir: str) -> None:
        """Analyze all PDFs in a directory"""
        if not os.path.exists(pdf_dir):
            print_colored(f"Directory {pdf_dir} not found!", Colors.FAIL)
            return

        pdfs = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]

        if not pdfs:
            print_colored(f"No PDF files found in {pdf_dir}", Colors.FAIL)
            return

        print_colored(f"\nProcessing {len(pdfs)} PDF files in {pdf_dir}", Colors.HEADER)

        for i, pdf_file in enumerate(pdfs, 1):
            pdf_path = os.path.join(pdf_dir, pdf_file)
            self.analyze_pdf(pdf_path)
            
            # If not the last PDF, wait for user input
            if i < len(pdfs):
                input("\nPress Enter to process next PDF...")


def main():
    analyzer = PDFHeaderAnalyzer()
    pdf_dirs = ["pdfs1", "pdfs2"]

    for pdf_dir in pdf_dirs:
        analyzer.analyze_pdf_directory(pdf_dir)


if __name__ == "__main__":
    main()
