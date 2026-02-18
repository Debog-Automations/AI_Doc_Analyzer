"""
Universal Schema - Pydantic models for AI extraction

Defines the universal field set for all document types.
No document-type-specific routing - one schema for everything.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import date


class DatedValue(BaseModel):
    """A date value with its source location."""
    date: str = Field(description="The date in YYYY-MM-DD format")
    source: str = Field(description="Source sheet/section/page where this was found")


class BusinessValue(BaseModel):
    """A business term and its value extracted from the document."""
    term: str = Field(description="The business term name (e.g., 'Policy Limit', 'Deductible')")
    value: str = Field(description="The value (e.g., '$1,000,000', '32.5%')")
    context: Optional[str] = Field(default=None, description="Where this was found (section, page)")


class PartyInfo(BaseModel):
    """Information about a party to the agreement."""
    name: str = Field(description="Full legal name of the party")
    role: Optional[str] = Field(default=None, description="Role in agreement (e.g., 'Cedent', 'Reinsurer', 'Broker')")


class UniversalAIFields(BaseModel):
    """
    Universal AI extraction fields.
    
    This single schema is used for ALL document types.
    No type-specific routing needed.
    """
    
    # Core Document Info
    title: Optional[str] = Field(default=None, description="Document title")
    document_type: Optional[str] = Field(default=None, description="Type of document (e.g., 'MGA Agreement', 'Quota Share Contract')")
    summary: Optional[str] = Field(default=None, description="2-3 sentence summary of the document")
    
    # Dates - as_of_dates captures ALL occurrences with their source locations
    as_of_dates: List[DatedValue] = Field(default_factory=list, description="All 'Data as of' or 'As of' dates found, with source sheet/section")
    effective_dates: List[DatedValue] = Field(default_factory=list, description="All effective/inception dates found, with source sheet/section")
    executed_date: Optional[str] = Field(default=None, description="When signed (YYYY-MM-DD format)")
    expiration_date: Optional[str] = Field(default=None, description="When terms end (YYYY-MM-DD format)")
    
    # Currency
    currency: Optional[str] = Field(default=None, description="Primary currency (e.g., 'USD', 'EUR')")
    
    # Named Entities
    broker_name: Optional[str] = Field(default=None, description="Broker entity name")
    carrier_name: Optional[str] = Field(default=None, description="Carrier/Insurer entity name")
    mga_name: Optional[str] = Field(default=None, description="MGA entity name")
    intermediary_name: Optional[str] = Field(default=None, description="Intermediary entity name")
    
    # Financial Terms
    ceded_percent: Optional[str] = Field(default=None, description="Quota share/ceded percentage")
    commission_rates: Optional[str] = Field(default=None, description="Commission percentages")
    gwp_actual: Optional[str] = Field(default=None, description="Gross Written Premium (actual)")
    gwp_estimated: Optional[str] = Field(default=None, description="Gross Written Premium (estimated)")
    nwp_actual: Optional[str] = Field(default=None, description="Net Written Premium (actual)")
    nwp_estimated: Optional[str] = Field(default=None, description="Net Written Premium (estimated)")
    
    # Business Terms
    lines_of_business: Optional[str] = Field(default=None, description="Lines of business covered")
    key_entities: Optional[str] = Field(default=None, description="Other significant entities mentioned")
    
    # Dynamic Lists
    parties: List[PartyInfo] = Field(default_factory=list, description="All parties to the agreement")
    signers: List[str] = Field(default_factory=list, description="Names of people who signed")
    sections_chapters: List[str] = Field(default_factory=list, description="Major sections/chapters in document")
    table_names: List[str] = Field(default_factory=list, description="Names of tables in document")
    
    # Geography
    countries: List[str] = Field(default_factory=list, description="Countries mentioned")
    states: List[str] = Field(default_factory=list, description="States/jurisdictions mentioned")
    
    # All Values - Comprehensive extraction
    all_values: List[BusinessValue] = Field(
        default_factory=list, 
        description="All business terms and values found in the document"
    )
    
    def to_flat_dict(self) -> dict:
        """Convert to flat dictionary for Excel/CSV output."""
        # Format as_of_dates with sources
        as_of_formatted = "; ".join(
            f"{d.date} ({d.source})" for d in self.as_of_dates
        ) if self.as_of_dates else ""
        
        # Format effective_dates with sources
        effective_formatted = "; ".join(
            f"{d.date} ({d.source})" for d in self.effective_dates
        ) if self.effective_dates else ""
        
        result = {
            "Title": self.title or "",
            "Type": self.document_type or "",
            "AI Summary": self.summary or "",
            "AsOfDt": as_of_formatted,
            "Effective Date": effective_formatted,
            "Executed Date": self.executed_date or "",
            "Expiration Date": self.expiration_date or "",
            "Currency": self.currency or "",
            "Broker Name": self.broker_name or "",
            "Carrier Name": self.carrier_name or "",
            "MGA Name": self.mga_name or "",
            "Intermediary Name": self.intermediary_name or "",
            "Ceded Percent": self.ceded_percent or "",
            "Commission Rates": self.commission_rates or "",
            "GWP Actual": self.gwp_actual or "",
            "GWP Estimated": self.gwp_estimated or "",
            "NWP Actual": self.nwp_actual or "",
            "NWP Estimated": self.nwp_estimated or "",
            "Lines of Business": self.lines_of_business or "",
            "Key Entities": self.key_entities or "",
            "Parties": ", ".join(f"{p.name} ({p.role})" if p.role else p.name for p in self.parties) if self.parties else "",
            "Signers": ", ".join(self.signers) if self.signers else "",
            "Sections/Chapters": ", ".join(self.sections_chapters) if self.sections_chapters else "",
            "Table Names": ", ".join(self.table_names) if self.table_names else "",
            "Countries": ", ".join(self.countries) if self.countries else "",
            "States": ", ".join(self.states) if self.states else "",
            "All Values": str([{"term": v.term, "value": v.value} for v in self.all_values]) if self.all_values else "",
        }
        return result


class ExtractionResult(BaseModel):
    """Wrapper for extraction result with metadata."""
    fields: UniversalAIFields
    sources: dict = Field(default_factory=dict, description="Source locations for extracted fields")
    confidence: str = Field(default="medium", description="Overall extraction confidence")
    missing_fields: List[str] = Field(default_factory=list, description="Fields that couldn't be extracted")


def validate_extraction(data: dict) -> tuple[UniversalAIFields, List[str]]:
    """
    Validate extraction data against the schema.
    
    Args:
        data: Dictionary of extracted fields
        
    Returns:
        Tuple of (validated UniversalAIFields, list of missing required fields)
    """
    missing = []
    
    # Required fields that should always be present
    required_simple_fields = ["title", "document_type"]
    required_list_fields = ["effective_dates"]  # Now a list
    
    for field in required_simple_fields:
        if not data.get(field):
            missing.append(field)
    
    for field in required_list_fields:
        if not data.get(field) or len(data.get(field, [])) == 0:
            missing.append(field)
    
    # Create the model (will use defaults for missing optional fields)
    try:
        fields = UniversalAIFields(**data)
    except Exception as e:
        # Log the actual error for debugging
        import logging
        logging.getLogger(__name__).warning(f"Pydantic validation failed: {e}")
        
        # Build safe_data by parsing each field individually
        safe_data = {}
        
        # Simple string/optional fields - these rarely fail
        simple_fields = [
            "title", "document_type", "summary", "as_of_date", "effective_date",
            "executed_date", "expiration_date", "currency", "broker_name",
            "carrier_name", "mga_name", "intermediary_name", "ceded_percent",
            "commission_rates", "gwp_actual", "gwp_estimated", "nwp_actual",
            "nwp_estimated", "lines_of_business", "key_entities"
        ]
        
        for key in simple_fields:
            if key in data:
                value = data[key]
                # Only copy if it's actually a string (AI sometimes returns [] for empty strings)
                if isinstance(value, str):
                    safe_data[key] = value
                # Skip None, [], {}, and other non-string types
        
        # Simple list fields (List[str])
        simple_list_fields = ["signers", "sections_chapters", "table_names", "countries", "states"]
        for key in simple_list_fields:
            if key in data and isinstance(data[key], list):
                # Filter to only strings
                safe_data[key] = [item for item in data[key] if isinstance(item, str)]
        
        # Complex list fields - try to parse, skip if invalid
        # parties: List[PartyInfo]
        if "parties" in data and isinstance(data["parties"], list):
            valid_parties = []
            for item in data["parties"]:
                if isinstance(item, dict) and "name" in item:
                    try:
                        valid_parties.append(PartyInfo(**item))
                    except Exception:
                        pass  # Skip invalid party entries
            if valid_parties:
                safe_data["parties"] = valid_parties
        
        # all_values: List[BusinessValue]
        if "all_values" in data and isinstance(data["all_values"], list):
            valid_values = []
            for item in data["all_values"]:
                if isinstance(item, dict) and "term" in item and "value" in item:
                    try:
                        valid_values.append(BusinessValue(**item))
                    except Exception:
                        pass  # Skip invalid value entries
            if valid_values:
                safe_data["all_values"] = valid_values
        
        # as_of_dates: List[DatedValue]
        if "as_of_dates" in data and isinstance(data["as_of_dates"], list):
            valid_dates = []
            for item in data["as_of_dates"]:
                if isinstance(item, dict) and "date" in item and "source" in item:
                    try:
                        valid_dates.append(DatedValue(**item))
                    except Exception:
                        pass  # Skip invalid date entries
            if valid_dates:
                safe_data["as_of_dates"] = valid_dates
        
        # effective_dates: List[DatedValue]
        if "effective_dates" in data and isinstance(data["effective_dates"], list):
            valid_dates = []
            for item in data["effective_dates"]:
                if isinstance(item, dict) and "date" in item and "source" in item:
                    try:
                        valid_dates.append(DatedValue(**item))
                    except Exception:
                        pass  # Skip invalid date entries
            if valid_dates:
                safe_data["effective_dates"] = valid_dates
        
        fields = UniversalAIFields(**safe_data)
    
    return fields, missing


# Universal extraction prompt
UNIVERSAL_EXTRACTION_PROMPT = """You are a document data extraction assistant specializing in insurance and reinsurance documents.

Extract ALL available information from this document into the following categories. Be thorough but accurate.

**IMPORTANT - For Dates with Multiple Occurrences:**
Documents (especially Excel files) often have the SAME date field appearing in multiple sheets/sections with DIFFERENT values.
- Extract ALL occurrences of "Data as of" / "As of" dates → as_of_dates (include the sheet name or section as source)
- Extract ALL occurrences of "Effective Date" / "Inception Date" → effective_dates (include the sheet name or section as source)
- Return dates in YYYY-MM-DD format

**For Single Dates:**
- "executed on", "signed on" → executed_date  
- "remain in effect until", "expire on", "termination date" → expiration_date

**For Financial Amounts:** Include currency symbol/code and commas (e.g., $1,000,000 or USD 1,000,000)

**For Percentages:** Return as number with % (e.g., 25%, 32.5%)

**For Lists:** Be comprehensive - include ALL parties, signers, sections, tables found

**For all_values:** Extract EVERY business term and value you find. This includes:
- Limits, deductibles, retentions
- Premium amounts (written, earned, estimated, actual)
- Percentages (quota share, commission, ceding)
- Fee amounts
- Coverage limits
- Any numerical or monetary values with their business context

**If information is not found:** Leave the field empty or as an empty list - do NOT make up information.

Return your response as a JSON object matching this exact structure:
{
    "title": "Document title",
    "document_type": "Type of document",
    "summary": "2-3 sentence summary",
    "as_of_dates": [
        {"date": "2023-12-31", "source": "Master Inputs sheet"},
        {"date": "2022-12-31", "source": "Program Overview sheet"}
    ],
    "effective_dates": [
        {"date": "2024-03-01", "source": "Cover sheet"},
        {"date": "2023-03-01", "source": "Historical Experience sheet"}
    ],
    "executed_date": "YYYY-MM-DD or null", 
    "expiration_date": "YYYY-MM-DD or null",
    "currency": "USD or other currency code",
    "broker_name": "Broker name or null",
    "carrier_name": "Carrier/insurer name or null",
    "mga_name": "MGA name or null",
    "intermediary_name": "Intermediary name or null",
    "ceded_percent": "Percentage or null",
    "commission_rates": "Commission info or null",
    "gwp_actual": "Amount or null",
    "gwp_estimated": "Amount or null",
    "nwp_actual": "Amount or null",
    "nwp_estimated": "Amount or null",
    "lines_of_business": "Lines of business covered",
    "key_entities": "Other important entities",
    "parties": [{"name": "Party name", "role": "Their role"}],
    "signers": ["Signer name 1", "Signer name 2"],
    "sections_chapters": ["Section 1 name", "Section 2 name"],
    "table_names": ["Table 1 title", "Table 2 title"],
    "countries": ["Country 1", "Country 2"],
    "states": ["State 1", "State 2"],
    "all_values": [
        {"term": "Policy Limit", "value": "$1,000,000", "context": "Article II"},
        {"term": "Deductible", "value": "$5,000", "context": "Schedule A"}
    ]
}"""

