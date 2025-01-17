import re
import os
from typing import List, Tuple, Dict
import pdfplumber
import traceback
import pandas as pd
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    filename: str
    stage0_headers: List[str]
    stage1_cleaned: List[str]
    oneshot_detection: str
    stage2_address: List[str]
    stage3_cleaned: List[str]
    stage4_cleaned: List[str]
    final_content: List[str]


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

        # Initialize guaranteed remove words
        self.guaranteed_remove_words = {
            "STATEMENT",
            "ACCOUNT",
            "CURRENCY",
            "INR",
            "TYPE",
            "SAVINGS",
            "NOMINEE",
            "REGISTERED",
            "IFSC",
            "MICR",
            "CODE",
            "GSTIN",
            "NA",
            "SAC",
            "SUMMARY",
            "UNQ",
            "SRL",
            "NO",
            "ID",
            "CUSTOMER",
            "BRANCH",
            "NUMBER",
            "A/C",
            "BALANCE",
            "CLOSING",
            "OF",
            "TO",
            "DATE",
        }

        # Add Indian states and union territories
        self.indian_states = {
            "ANDHRA PRADESH",
            "ARUNACHAL PRADESH",
            "ASSAM",
            "BIHAR",
            "CHHATTISGARH",
            "GOA",
            "GUJARAT",
            "HARYANA",
            "HIMACHAL PRADESH",
            "JHARKHAND",
            "KARNATAKA",
            "KERALA",
            "MADHYA PRADESH",
            "MAHARASHTRA",
            "MANIPUR",
            "MEGHALAYA",
            "MIZORAM",
            "NAGALAND",
            "ODISHA",
            "PUNJAB",
            "RAJASTHAN",
            "SIKKIM",
            "TAMIL NADU",
            "TELANGANA",
            "TRIPURA",
            "UTTAR PRADESH",
            "UTTARAKHAND",
            "WEST BENGAL",
            # Union Territories
            "DELHI",
            "PUDUCHERRY",
            "CHANDIGARH",
            "ANDAMAN AND NICOBAR",
            "DADRA AND NAGAR HAVELI",
            "DAMAN AND DIU",
            "JAMMU AND KASHMIR",
            "LADAKH",
            "LAKSHADWEEP",
        }

        # Add state names to guaranteed remove words
        self.guaranteed_remove_words.update(self.indian_states)

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

        # Check if line contains a state name
        if any(state.lower() in line for state in self.indian_states):
            return True

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

    def extract_name_from_pattern(
        self, line: str, next_line: str = ""
    ) -> Tuple[str, str]:
        """Extract name and type based on title patterns followed by ALL CAPS words"""

        # Define title patterns (case insensitive)
        title_patterns = [
            r"\b(?:mr|mrs|ms|dr)\.?\s+",  # Mr. Mrs. Ms. Dr.
            r"\bm/s\.?\s+",  # M/s.
            r"\bshri\s+",  # Shri
            r"\bsmt\.?\s+",  # Smt.
            r"\bkumar[i]?\s+",  # Kumar/Kumari
            r"\bsri\s+",  # Sri
            r"\bmiss\s+",  # Miss
            r"\b(?:name\s+of\s+customer|customer\s+name)[:\s]+",
        ]

        print_colored(f"\nChecking line for titles: {line}", Colors.BLUE)

        for pattern in title_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                title_end = match.end()
                remaining_text = line[title_end:]
                title = line[match.start() : title_end].strip()

                words = remaining_text.split()
                caps_words = []

                for word in words:
                    if (
                        pattern.lower().find("name of customer") != -1
                        or pattern.lower().find("customer name") != -1
                    ):
                        if re.match(r"^[A-Z][A-Za-z]*$", word) or word.isupper():
                            caps_words.append(word)
                        else:
                            break
                    else:
                        if word.isupper() and len(word) > 1:
                            caps_words.append(word)
                        else:
                            break

                if len(caps_words) >= 2:
                    # Include the title in the final name
                    name = f"{title} {' '.join(caps_words)}"
                    print_colored(f"Found title: {title}", Colors.GREEN)
                    print_colored(f"Found name: {name}", Colors.GREEN)

                    entity_type = "company" if "m/s" in title.lower() else "individual"

                    return name, entity_type

        return "", ""

    def analyze_pdf(self, pdf_path: str) -> Dict:
        """Analyze a single PDF file and return the terminal output for each stage"""
        try:
            text = self.extract_text_from_pdf(pdf_path)
            if not text:
                print_colored(f"No text extracted from {pdf_path}", Colors.FAIL)
                return None

            result = {
                "filename": os.path.basename(pdf_path),
                "stage0": [],
                "stage1": [],
                "oneshot": [],
                "stage2": [],
                "stage3": [],
                "stage4": [],
                "final": [],
            }

            print_colored(f"\n{'='*50}", Colors.HEADER)
            print_colored(f"Analyzing PDF: {os.path.basename(pdf_path)}", Colors.HEADER)
            print_colored(f"{'='*50}\n", Colors.HEADER)

            # STAGE 0: Separate Header from Table Content
            current_output = []
            print_colored("\nSTAGE 0: SEPARATING HEADER FROM TABLE", Colors.BOLD)
            current_output.append("STAGE 0: SEPARATING HEADER FROM TABLE")

            lines = text.split("\n")
            header_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if self.is_table_header(line) or self.is_transaction_line(line):
                    msg = f"Found table marker, stopping header collection: {line}"
                    print_colored(msg, Colors.WARNING)
                    current_output.append(msg)
                    break

                header_lines.append(line)

            print_colored("\nExtracted Header Lines:", Colors.BLUE)
            current_output.append("\nExtracted Header Lines:")
            for i, line in enumerate(header_lines[:10]):
                msg = f"{i+1}. {line}"
                print_colored(msg, Colors.GREEN)
                current_output.append(msg)

            result["stage0"] = "\n".join(current_output)

            # STAGE 1: Clean Header Content
            current_output = []
            print_colored("\nSTAGE 1: REMOVING GUARANTEED WORDS", Colors.BOLD)
            current_output.append("\nSTAGE 1: REMOVING GUARANTEED WORDS")
            raw_lines = []
            for line in header_lines:
                words = line.split()
                cleaned_words = []

                for word in words:
                    clean_word = word.strip(".:/-")
                    if clean_word.upper() in self.guaranteed_remove_words:
                        msg = f"Removing word: {word}"
                        print_colored(msg, Colors.WARNING)
                        current_output.append(msg)
                        continue
                    cleaned_words.append(word)

                if cleaned_words:
                    cleaned_line = " ".join(cleaned_words)
                    raw_lines.append(cleaned_line)
                    msg = f"Cleaned line: {cleaned_line}"
                    print_colored(msg, Colors.GREEN)
                    current_output.append(msg)

            result["stage1"] = "\n".join(current_output)

            # One-shot name detection
            current_output = []
            print_colored("\nTrying ONE-SHOT name detection:", Colors.BOLD)
            current_output.append("\nTrying ONE-SHOT name detection:")

            for line in raw_lines:
                msg = f"\nChecking line for titles: {line}"
                print_colored(msg, Colors.BLUE)
                current_output.append(msg)

                name, type_ = self.extract_name_from_pattern(line)
                if name:
                    msg = f"Found title: {name.split()[0]}"
                    print_colored(msg, Colors.GREEN)
                    current_output.append(msg)

                    msg = f"Found name: {name}"
                    print_colored(msg, Colors.GREEN)
                    current_output.append(msg)

                    msg = f"Found {type_} name using one-shot detection:"
                    print_colored(msg, Colors.GREEN)
                    current_output.append(msg)

                    msg = f"Full line: {line}"
                    print_colored(msg, Colors.BLUE)
                    current_output.append(msg)

                    msg = f"Extracted name: {name}"
                    print_colored(msg, Colors.GREEN)
                    current_output.append(msg)
                    break

            result["oneshot"] = "\n".join(current_output)

            # STAGE 2: Address Block Detection
            current_output = []
            print_colored("\nSTAGE 2: ADDRESS BLOCK DETECTION", Colors.BOLD)
            current_output.append("\nSTAGE 2: ADDRESS BLOCK DETECTION")

            start_idx, end_idx = self.find_address_block(raw_lines)

            print_colored("\nDetected Address Block:", Colors.BOLD)
            current_output.append("\nDetected Address Block:")
            if start_idx != -1 and end_idx != -1:
                msg = "Address lines being removed:"
                print_colored(msg, Colors.WARNING)
                current_output.append(msg)
                for i in range(start_idx, end_idx + 1):
                    msg = f"REMOVED: {raw_lines[i]}"
                    print_colored(msg, Colors.FAIL)
                    current_output.append(msg)
                cleaned_lines = raw_lines[:start_idx] + raw_lines[end_idx + 1 :]
            else:
                msg = "No address block detected"
                print_colored(msg, Colors.WARNING)
                current_output.append(msg)
                cleaned_lines = raw_lines

            result["stage2"] = "\n".join(current_output)

            # STAGE 3: Number and Special Character Removal
            current_output = []
            print_colored(
                "\nSTAGE 3: REMOVING NUMBERS AND SPECIAL CHARACTERS", Colors.BOLD
            )
            current_output.append("\nSTAGE 3: REMOVING NUMBERS AND SPECIAL CHARACTERS")

            number_cleaned_lines = []
            for line in cleaned_lines:
                original_line = line
                # Remove numbers
                cleaned = re.sub(r"\d+", "", line)
                if cleaned != original_line:
                    msg = f"Removing numbers: {original_line} -> {cleaned}"
                    print_colored(msg, Colors.WARNING)
                    current_output.append(msg)

                # Remove special characters
                original_line = cleaned
                cleaned = re.sub(r"[^\w\s]", "", cleaned)
                if cleaned != original_line:
                    msg = f"Removing special chars: {original_line} -> {cleaned}"
                    print_colored(msg, Colors.WARNING)
                    current_output.append(msg)

                if cleaned.strip():
                    number_cleaned_lines.append(cleaned)

            result["stage3"] = "\n".join(current_output)

            # STAGE 4: Mixed Case Word Removal
            current_output = []
            print_colored("\nSTAGE 4: REMOVING MIXED CASE WORDS", Colors.BOLD)
            current_output.append("\nSTAGE 4: REMOVING MIXED CASE WORDS")

            final_cleaned_lines = []
            for line in number_cleaned_lines:
                words = line.split()
                cleaned_words = []
                for word in words:
                    if word.isupper():
                        cleaned_words.append(word)
                    else:
                        msg = f"Removing non-uppercase word: {word}"
                        print_colored(msg, Colors.WARNING)
                        current_output.append(msg)
                if cleaned_words:
                    final_cleaned_lines.append(" ".join(cleaned_words))

            result["stage4"] = "\n".join(current_output)

            # Final content
            current_output = []
            print_colored("\nFINAL CLEANED CONTENT:", Colors.BOLD)
            current_output.append("\nFINAL CLEANED CONTENT:")
            if final_cleaned_lines:
                for line in final_cleaned_lines:
                    print_colored(line, Colors.GREEN)
                    current_output.append(line)
            else:
                msg = "No content remained after cleaning"
                print_colored(msg, Colors.FAIL)
                current_output.append(msg)

            result["final"] = "\n".join(current_output)
            return result

        except Exception as e:
            print_colored(f"Error processing {pdf_path}: {str(e)}", Colors.FAIL)
            print_colored(traceback.format_exc(), Colors.FAIL)
            return None

    def analyze_pdf_directory(self, pdf_dir: str) -> None:
        """Analyze all PDFs in a directory and export results to Excel"""
        if not os.path.exists(pdf_dir):
            print_colored(f"Directory {pdf_dir} not found!", Colors.FAIL)
            return

        pdfs = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]

        if not pdfs:
            print_colored(f"No PDF files found in {pdf_dir}", Colors.FAIL)
            return

        print_colored(f"\nFound {len(pdfs)} PDF files in {pdf_dir}", Colors.HEADER)

        results = []
        for i, pdf_file in enumerate(pdfs, 1):
            print_colored(f"\nProcessing PDF {i} of {len(pdfs)}", Colors.HEADER)
            pdf_path = os.path.join(pdf_dir, pdf_file)
            result = self.analyze_pdf(pdf_path)
            if result:
                results.append(result)

        # Export results to Excel
        self.export_to_excel(results, pdf_dir)

    def export_to_excel(self, results: List[Dict], pdf_dir: str) -> None:
        """Export analysis results to Excel"""
        data = []
        for result in results:
            data.append(
                {
                    "Filename": result["filename"],
                    "Stage 0": result["stage0"],
                    "Stage 1": result["stage1"],
                    "One-Shot Detection": result["oneshot"],
                    "Stage 2": result["stage2"],
                    "Stage 3": result["stage3"],
                    "Stage 4": result["stage4"],
                    "Final Content": result["final"],
                }
            )

        df = pd.DataFrame(data)
        output_file = os.path.join(pdf_dir, "analysis_results.xlsx")

        with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
            worksheet = writer.sheets["Sheet1"]
            worksheet.set_column("A:H", 50)  # Set width for all columns

            # Add text wrapping
            wrap_format = writer.book.add_format({"text_wrap": True})
            for idx in range(len(data)):
                worksheet.set_row(idx + 1, 300, wrap_format)

        print_colored(f"\nResults exported to: {output_file}", Colors.GREEN)


def main():
    analyzer = PDFHeaderAnalyzer()
    pdf_dirs = ["pdfs1", "pdfs2"]

    for pdf_dir in pdf_dirs:
        analyzer.analyze_pdf_directory(pdf_dir)


if __name__ == "__main__":
    main()
