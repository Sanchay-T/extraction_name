from PyPDF2 import PdfReader
import re

def extract_header_content(pdf_path):
    """
    Extract all content before the transaction table starts.
    Uses transaction table indicators to find where the table starts.
    """
    try:
        print("Opening PDF file...")
        reader = PdfReader(pdf_path)
        
        print("Getting first page...")
        first_page = reader.pages[0]
        
        print("Extracting text from first page...")
        text = first_page.extract_text()
        if not text:
            return "No text found in PDF"

        # Split text into lines and clean them
        print("\nSplitting into lines...")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Common patterns that indicate transaction table
        transaction_patterns = [
            # Date patterns
            r'^\d{2}[-/]\d{2}[-/]\d{2,4}\s+\d{2}[-/]\d{2}[-/]\d{2,4}\s+',  # Date Date format
            r'^\d{2}[-/]\d{2}[-/]\d{2,4}\s+[A-Z]+',  # Date with description
            r'^Date\s+Narration|^Date\s+Particulars|^Date\s+Description|^Tran Date|^Trans Date',  # Date headers
            r'^Sl\.?\s*No\.?\s*Date',  # Serial number with date
            
            # Transaction indicators
            r'^OPENING\s+BALANCE',
            r'^Balance\s+Brought\s+Forward',
            r'Description\s+Withdrawal\s+Deposit',
            r'Debit\s+Credit\s+Balance',
            r'Chq\.?/Ref\.?\s*No\.',
            r'Withdrawals?\s+Deposits?',
            
            # Table headers
            r'^Sr\.\s*No\.',
            r'^Particulars\s+Amount',
            r'Value\s+Dt\s+Withdrawal'
        ]
        
        # Find where transaction table starts
        table_start = -1
        for i, line in enumerate(lines):
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in transaction_patterns):
                print(f"\nFound transaction table start at line {i + 1}:")
                print(f"Matching line: {line}")
                table_start = i
                break
        
        if table_start == -1:
            print("\nCould not find transaction table start, using full content")
            return '\n'.join(lines)
            
        # Get all content before transaction table
        header_content = lines[:table_start]
        if not header_content:
            print("\nNo header content found before transaction table")
            return "No header content found"
            
        print(f"\nExtracted {len(header_content)} lines before transaction table")
        return '\n'.join(header_content)

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return f"Error processing PDF: {str(e)}"

if __name__ == "__main__":
    pdf_path = r"C:\Users\Abcom\cyphersol-ats-native-app-1\poojan.pdf"
    print("\nStarting PDF header extraction...")
    print("-" * 50)
    content = extract_header_content(pdf_path)
    print("\nFinal Header Content:")
    print("-" * 50)
    print(content)
    print("-" * 50)
