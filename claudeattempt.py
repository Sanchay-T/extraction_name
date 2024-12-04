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


class PDFNameExtractor:
    def __init__(self):
        # Priority patterns for name extraction
        self.name_patterns = {
            # Direct name indicators with CAPS
            "direct_name": [
                r"Name\s*:\s*([A-Z][A-Z\s]+(?:LIMITED|PVT\.?\s*LTD\.?)?)",
                r"Name of Customer\s*:\s*([A-Z][A-Z\s]+(?:LIMITED|PVT\.?\s*LTD\.?)?)",
                r"Customer Name\s*:\s*([A-Z][A-Z\s]+(?:LIMITED|PVT\.?\s*LTD\.?)?)",
                r"A/c Name\s*:\s*([A-Z][A-Z\s]+(?:LIMITED|PVT\.?\s*LTD\.?)?)",
                r"Account Name\s*:\s*([A-Z][A-Z\s]+(?:LIMITED|PVT\.?\s*LTD\.?)?)",
            ],
            # Business identifiers with CAPS
            "business": [
                r"M/[Ss]\.\s*([A-Z][A-Z\s]+(?:LIMITED|PVT\.?\s*LTD\.?)?)",
                r"M/[Ss]\s+([A-Z][A-Z\s]+(?:LIMITED|PVT\.?\s*LTD\.?)?)",
                r"^([A-Z][A-Z\s]+(?:LIMITED|PRIVATE LIMITED))$",
            ],
        }

        # Fallback patterns and indicators
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

        # Words to exclude
        self.excluded_words = {
            "address",
            "branch",
            "account",
            "customer",
            "details",
            "statement",
            "bank",
            "ifsc",
            "mobile",
            "email",
        }

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

    def clean_name(self, name: str) -> str:
        """Clean extracted name"""
        # Remove any leading/trailing special characters and spaces
        name = name.strip()
        name = re.sub(r"^[^a-zA-Z]+|[^a-zA-Z]+$", "", name)
        # Remove multiple spaces
        name = re.sub(r"\s+", " ", name)
        return name

    def extract_name_from_priority_patterns(self, line: str) -> str:
        """Extract name using priority patterns"""
        # Check direct name patterns
        for pattern in self.name_patterns["direct_name"]:
            match = re.search(pattern, line)
            if match:
                return self.clean_name(match.group(1))

        # Check business patterns
        for pattern in self.name_patterns["business"]:
            match = re.search(pattern, line)
            if match:
                name = self.clean_name(match.group(1))
                if pattern.startswith(r"M/[Ss]"):
                    return f"M/S. {name}"
                return name

        return ""

    def extract_name_from_fallback(self, lines: List[str]) -> str:
        """Fallback name extraction logic"""
        for line in lines:
            line_lower = line.lower()

            # Skip lines with excluded words
            if any(word in line_lower for word in self.excluded_words):
                continue

            # Check for name indicators
            if any(indicator in line_lower for indicator in self.name_indicators):
                name = line.strip()
                # Remove any numbers or special characters
                name = re.sub(r"[0-9(),.:/-]", "", name)
                # Remove extra spaces
                name = self.clean_name(name)
                if name:
                    return name

        return ""

    def analyze_pdf(self, pdf_path: str) -> None:
        """Analyze a single PDF file to extract account holder name"""
        try:
            text = self.extract_text_from_pdf(pdf_path)

            if not text:
                print_colored(f"No text extracted from {pdf_path}", Colors.FAIL)
                return

            print_colored(
                f"\nAnalyzing PDF: {os.path.basename(pdf_path)}", Colors.HEADER
            )

            # Get raw lines
            lines = [line.strip() for line in text.split("\n") if line.strip()]

            # First check first 10 lines for priority patterns
            extracted_name = ""
            for line in lines[:10]:
                extracted_name = self.extract_name_from_priority_patterns(line)
                if extracted_name:
                    break

            # If no name found with priority patterns, try fallback
            if not extracted_name:
                extracted_name = self.extract_name_from_fallback(lines[:10])

            if extracted_name:
                print_colored(f"Extracted Name: {extracted_name}", Colors.GREEN)
            else:
                print_colored("No name found in document", Colors.WARNING)

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

        for pdf_file in pdfs:
            pdf_path = os.path.join(pdf_dir, pdf_file)
            self.analyze_pdf(pdf_path)


def main():
    extractor = PDFNameExtractor()
    pdf_dirs = ["pdfs1"]  # Add your PDF directories here

    for pdf_dir in pdf_dirs:
        extractor.analyze_pdf_directory(pdf_dir)


if __name__ == "__main__":
    main()
