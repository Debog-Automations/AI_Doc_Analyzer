"""
Configuration for the AI Document Data Extractor.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o"

# Database Configuration (PostgreSQL via Docker)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "document_registry")
DB_USER = os.getenv("DB_USER", "docanalyzer")
DB_PASSWORD = os.getenv("DB_PASSWORD", "docanalyzer_secret")

# Database connection string
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Box API Configuration (CCG - Client Credentials Grant)
# Credentials are stored securely via the UI settings and keyring
BOX_CLIENT_ID = os.getenv("BOX_CLIENT_ID")
BOX_CLIENT_SECRET = os.getenv("BOX_CLIENT_SECRET")
BOX_ENTERPRISE_ID = os.getenv("BOX_ENTERPRISE_ID")
BOX_USER_ID = os.getenv("BOX_USER_ID")

# Output Configuration
OUTPUT_FILE = "extracted_data.xlsx"

# PDF Processing Configuration
# Maximum number of page images to include for visual reference
# Pages with tables/images are automatically detected and prioritized
MAX_VISION_PAGES = 10

# Programmatic Fields (extracted from file metadata, not AI)
PROGRAMMATIC_FIELDS = [
    "SourcePathFilenameWksName",
    "FileName",
    "FileName wo extension",
    "File Extension",
    "Comment",  # User-provided field
]

# Core questions asked for ALL document types
CORE_QUESTIONS = [
    "What is the document Title?",
    "What is the document Type? (e.g., Reinsurance Contract, MGA Agreement, Broker Agreement, Quota Share Agreement, etc.)",
    "What is the document As Of date (reporting date)?",
    "What is the document execution date (when it was signed)?",
    "What is the document effective date (when coverage/terms begin)? Look for phrases like 'take effect', 'effective as of', 'commence on'.",
    "What is the document expiration or termination date (when coverage/terms end)? Look for phrases like 'remain in effect until', 'shall expire on', 'termination date'.",
    "What is the primary Currency used in the document?",
]

# Questions specific to Reinsurance Contracts
REINSURANCE_CONTRACT_QUESTIONS = [
    "What is the Broker Name?",
    "What is the Intermediary Name?",
    "What is the MGA Name?",
    "What is the GWP Actual (Gross Written Premium Actual)?",
    "What is the GWP Est (Gross Written Premium Estimated)?",
    "What is the NWP Actual (Net Written Premium Actual)?",
    "What is the NWP Est (Net Written Premium Estimated)?",
    "What is the Ceded Percent or quota share percentage?",
    # Individual parties (up to 10)
    "What is Party 1 Name (main party)?",
    "What is Party 2 Name (if exists)?",
    "What is Party 3 Name (if exists)?",
    "What is Party 4 Name (if exists)?",
    "What is Party 5 Name (if exists)?",
    "What is Party 6 Name (if exists)?",
    "What is Party 7 Name (if exists)?",
    "What is Party 8 Name (if exists)?",
    "What is Party 9 Name (if exists)?",
    "What is Party 10 Name (if exists)?",
    # Individual tables (up to 10)
    "What is Table 1 Name or title (most significant table)?",
    "What is Table 2 Name or title (if exists)?",
    "What is Table 3 Name or title (if exists)?",
    "What is Table 4 Name or title (if exists)?",
    "What is Table 5 Name or title (if exists)?",
    "What is Table 6 Name or title (if exists)?",
    "What is Table 7 Name or title (if exists)?",
    "What is Table 8 Name or title (if exists)?",
    "What is Table 9 Name or title (if exists)?",
    "What is Table 10 Name or title (if exists)?",
    # Individual sections (up to 10)
    "What is Section 1 Name (first major section)?",
    "What is Section 2 Name (if exists)?",
    "What is Section 3 Name (if exists)?",
    "What is Section 4 Name (if exists)?",
    "What is Section 5 Name (if exists)?",
    "What is Section 6 Name (if exists)?",
    "What is Section 7 Name (if exists)?",
    "What is Section 8 Name (if exists)?",
    "What is Section 9 Name (if exists)?",
    "What is Section 10 Name (if exists)?",
]

# Questions specific to MGA Agreements
MGA_AGREEMENT_QUESTIONS = [
    "What is the MGA Name?",
    "What is the Carrier/Insurer Name?",
    "What is the Broker Name (if applicable)?",
    "What are the Commission rates or percentages?",
    "What is the Territory or jurisdiction covered?",
    "What are the lines of business covered?",
    # Individual parties
    "What is Party 1 Name (main party)?",
    "What is Party 2 Name (if exists)?",
    "What is Party 3 Name (if exists)?",
    "What is Party 4 Name (if exists)?",
    "What is Party 5 Name (if exists)?",
    "What is Party 6 Name (if exists)?",
    "What is Party 7 Name (if exists)?",
    "What is Party 8 Name (if exists)?",
    "What is Party 9 Name (if exists)?",
    "What is Party 10 Name (if exists)?",
    # Individual tables
    "What is Table 1 Name or title (most significant table)?",
    "What is Table 2 Name or title (if exists)?",
    "What is Table 3 Name or title (if exists)?",
    "What is Table 4 Name or title (if exists)?",
    "What is Table 5 Name or title (if exists)?",
    "What is Table 6 Name or title (if exists)?",
    "What is Table 7 Name or title (if exists)?",
    "What is Table 8 Name or title (if exists)?",
    "What is Table 9 Name or title (if exists)?",
    "What is Table 10 Name or title (if exists)?",
    # Individual sections
    "What is Section 1 Name (first major section)?",
    "What is Section 2 Name (if exists)?",
    "What is Section 3 Name (if exists)?",
    "What is Section 4 Name (if exists)?",
    "What is Section 5 Name (if exists)?",
    "What is Section 6 Name (if exists)?",
    "What is Section 7 Name (if exists)?",
    "What is Section 8 Name (if exists)?",
    "What is Section 9 Name (if exists)?",
    "What is Section 10 Name (if exists)?",
]

# Questions specific to Broker Agreements
BROKER_AGREEMENT_QUESTIONS = [
    "What is the Broker Name?",
    "What is the Carrier/Insurer Name?",
    "What are the Commission rates or percentages?",
    "What is the Territory or jurisdiction covered?",
    "What are the lines of business covered?",
    # Individual parties
    "What is Party 1 Name (main party)?",
    "What is Party 2 Name (if exists)?",
    "What is Party 3 Name (if exists)?",
    "What is Party 4 Name (if exists)?",
    "What is Party 5 Name (if exists)?",
    "What is Party 6 Name (if exists)?",
    "What is Party 7 Name (if exists)?",
    "What is Party 8 Name (if exists)?",
    "What is Party 9 Name (if exists)?",
    "What is Party 10 Name (if exists)?",
    # Individual tables
    "What is Table 1 Name or title (most significant table)?",
    "What is Table 2 Name or title (if exists)?",
    "What is Table 3 Name or title (if exists)?",
    "What is Table 4 Name or title (if exists)?",
    "What is Table 5 Name or title (if exists)?",
    "What is Table 6 Name or title (if exists)?",
    "What is Table 7 Name or title (if exists)?",
    "What is Table 8 Name or title (if exists)?",
    "What is Table 9 Name or title (if exists)?",
    "What is Table 10 Name or title (if exists)?",
    # Individual sections
    "What is Section 1 Name (first major section)?",
    "What is Section 2 Name (if exists)?",
    "What is Section 3 Name (if exists)?",
    "What is Section 4 Name (if exists)?",
    "What is Section 5 Name (if exists)?",
    "What is Section 6 Name (if exists)?",
    "What is Section 7 Name (if exists)?",
    "What is Section 8 Name (if exists)?",
    "What is Section 9 Name (if exists)?",
    "What is Section 10 Name (if exists)?",
]

# Default questions for unknown document types
DEFAULT_QUESTIONS = [
    "What are the key entities or parties mentioned?",
    "What are the main financial terms or amounts?",
    # Individual parties
    "What is Party 1 Name (main party)?",
    "What is Party 2 Name (if exists)?",
    "What is Party 3 Name (if exists)?",
    "What is Party 4 Name (if exists)?",
    "What is Party 5 Name (if exists)?",
    "What is Party 6 Name (if exists)?",
    "What is Party 7 Name (if exists)?",
    "What is Party 8 Name (if exists)?",
    "What is Party 9 Name (if exists)?",
    "What is Party 10 Name (if exists)?",
    # Individual tables
    "What is Table 1 Name or title (most significant table)?",
    "What is Table 2 Name or title (if exists)?",
    "What is Table 3 Name or title (if exists)?",
    "What is Table 4 Name or title (if exists)?",
    "What is Table 5 Name or title (if exists)?",
    "What is Table 6 Name or title (if exists)?",
    "What is Table 7 Name or title (if exists)?",
    "What is Table 8 Name or title (if exists)?",
    "What is Table 9 Name or title (if exists)?",
    "What is Table 10 Name or title (if exists)?",
    # Individual sections
    "What is Section 1 Name (first major section)?",
    "What is Section 2 Name (if exists)?",
    "What is Section 3 Name (if exists)?",
    "What is Section 4 Name (if exists)?",
    "What is Section 5 Name (if exists)?",
    "What is Section 6 Name (if exists)?",
    "What is Section 7 Name (if exists)?",
    "What is Section 8 Name (if exists)?",
    "What is Section 9 Name (if exists)?",
    "What is Section 10 Name (if exists)?",
]

# Document type routing
DOCUMENT_TYPE_QUESTIONS = {
    "reinsurance contract": REINSURANCE_CONTRACT_QUESTIONS,
    "quota share": REINSURANCE_CONTRACT_QUESTIONS,
    "reinsurance agreement": REINSURANCE_CONTRACT_QUESTIONS,
    "mga agreement": MGA_AGREEMENT_QUESTIONS,
    "mga contract": MGA_AGREEMENT_QUESTIONS,
    "broker agreement": BROKER_AGREEMENT_QUESTIONS,
    "broker contract": BROKER_AGREEMENT_QUESTIONS,
    "default": DEFAULT_QUESTIONS,
}

# Summary question asked at the end
SUMMARY_QUESTION = "Provide a brief 2-3 sentence summary of this document, highlighting the key business terms and parties involved."

# Mapping from questions to field names (used as Excel column headers)
QUESTION_TO_FIELD = {
    # Core fields
    "What is the document Title?": "Title",
    "What is the document Type? (e.g., Reinsurance Contract, MGA Agreement, Broker Agreement, Quota Share Agreement, etc.)": "Type",
    "What is the document As Of date (reporting date)?": "AsOfDt",
    "What is the document execution date (when it was signed)?": "ExecutedDt",
    "What is the document effective date (when coverage/terms begin)? Look for phrases like 'take effect', 'effective as of', 'commence on'.": "EffDt",
    "What is the document expiration or termination date (when coverage/terms end)? Look for phrases like 'remain in effect until', 'shall expire on', 'termination date'.": "ExpDt",
    "What is the primary Currency used in the document?": "Currency",
    
    # Reinsurance specific
    "What is the Broker Name?": "Broker Name",
    "What is the Intermediary Name?": "Intermediary Name",
    "What is the MGA Name?": "MGA Name",
    "What is the GWP Actual (Gross Written Premium Actual)?": "GWP Actual",
    "What is the GWP Est (Gross Written Premium Estimated)?": "GWP Est",
    "What is the NWP Actual (Net Written Premium Actual)?": "NWP Actual",
    "What is the NWP Est (Net Written Premium Estimated)?": "NWP Est",
    "What is the Ceded Percent or quota share percentage?": "Ceded Percent",
    
    # MGA/Broker specific
    "What is the Carrier/Insurer Name?": "Carrier Name",
    "What are the Commission rates or percentages?": "Commission Rates",
    "What is the Territory or jurisdiction covered?": "Territory",
    "What are the lines of business covered?": "Lines of Business",
    
    # Generic fields
    "What are the key entities or parties mentioned?": "Key Entities",
    "What are the main financial terms or amounts?": "Financial Terms",
    
    # Individual parties (1-10)
    "What is Party 1 Name (main party)?": "Party 1 Name",
    "What is Party 2 Name (if exists)?": "Party 2 Name",
    "What is Party 3 Name (if exists)?": "Party 3 Name",
    "What is Party 4 Name (if exists)?": "Party 4 Name",
    "What is Party 5 Name (if exists)?": "Party 5 Name",
    "What is Party 6 Name (if exists)?": "Party 6 Name",
    "What is Party 7 Name (if exists)?": "Party 7 Name",
    "What is Party 8 Name (if exists)?": "Party 8 Name",
    "What is Party 9 Name (if exists)?": "Party 9 Name",
    "What is Party 10 Name (if exists)?": "Party 10 Name",
    
    # Individual tables (1-10)
    "What is Table 1 Name or title (most significant table)?": "Table 1 Name",
    "What is Table 2 Name or title (if exists)?": "Table 2 Name",
    "What is Table 3 Name or title (if exists)?": "Table 3 Name",
    "What is Table 4 Name or title (if exists)?": "Table 4 Name",
    "What is Table 5 Name or title (if exists)?": "Table 5 Name",
    "What is Table 6 Name or title (if exists)?": "Table 6 Name",
    "What is Table 7 Name or title (if exists)?": "Table 7 Name",
    "What is Table 8 Name or title (if exists)?": "Table 8 Name",
    "What is Table 9 Name or title (if exists)?": "Table 9 Name",
    "What is Table 10 Name or title (if exists)?": "Table 10 Name",
    
    # Individual sections (1-10)
    "What is Section 1 Name (first major section)?": "Section 1 Name",
    "What is Section 2 Name (if exists)?": "Section 2 Name",
    "What is Section 3 Name (if exists)?": "Section 3 Name",
    "What is Section 4 Name (if exists)?": "Section 4 Name",
    "What is Section 5 Name (if exists)?": "Section 5 Name",
    "What is Section 6 Name (if exists)?": "Section 6 Name",
    "What is Section 7 Name (if exists)?": "Section 7 Name",
    "What is Section 8 Name (if exists)?": "Section 8 Name",
    "What is Section 9 Name (if exists)?": "Section 9 Name",
    "What is Section 10 Name (if exists)?": "Section 10 Name",
    
    # Summary
    "Provide a brief 2-3 sentence summary of this document, highlighting the key business terms and parties involved.": "AI Summarize the Document",
}

def get_questions_for_document_type(doc_type: str) -> list:
    """
    Get the appropriate questions based on document type.
    
    Args:
        doc_type: Document type string from initial detection
        
    Returns:
        List of questions to ask for this document type
    """
    doc_type_lower = doc_type.lower()
    
    # Find matching question set
    specific_questions = None
    for key, questions in DOCUMENT_TYPE_QUESTIONS.items():
        if key in doc_type_lower:
            specific_questions = questions
            break
    
    if specific_questions is None:
        specific_questions = DOCUMENT_TYPE_QUESTIONS["default"]
    
    # Combine: core + specific + summary
    return CORE_QUESTIONS + specific_questions + [SUMMARY_QUESTION]

def get_field_names_for_questions(questions: list) -> list:
    """Get field names for a list of questions."""
    return [QUESTION_TO_FIELD.get(q, "Unknown Field") for q in questions]

def get_all_output_fields() -> list:
    """
    Get all possible output fields for Excel headers.
    This creates a superset of all fields across all document types.
    """
    all_fields = set()
    
    # Add core fields
    all_fields.update(get_field_names_for_questions(CORE_QUESTIONS))
    
    # Add all document-type-specific fields
    for questions in DOCUMENT_TYPE_QUESTIONS.values():
        all_fields.update(get_field_names_for_questions(questions))
    
    # Add summary
    all_fields.add(QUESTION_TO_FIELD[SUMMARY_QUESTION])
    
    # Convert to sorted list for consistent ordering
    return sorted(list(all_fields))

def get_field_names():
    """
    Legacy function for backward compatibility.
    Returns all possible fields.
    """
    return get_all_output_fields()

def get_all_field_names():
    """Get all field names including programmatic fields."""
    return PROGRAMMATIC_FIELDS + get_all_output_fields()

