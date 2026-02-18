-- Initialize the document registry database
-- This script runs automatically when the PostgreSQL container first starts

-- Create processed_documents table (matches the SQLAlchemy model)
CREATE TABLE IF NOT EXISTS processed_documents (
    id SERIAL PRIMARY KEY,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    filename VARCHAR(500) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    source_path TEXT,
    file_size INTEGER,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'completed',
    error_message TEXT,
    extraction_data TEXT
);

-- Create index on file_hash for fast lookups
CREATE INDEX IF NOT EXISTS idx_processed_documents_file_hash ON processed_documents(file_hash);

-- Create index on processed_at for sorting
CREATE INDEX IF NOT EXISTS idx_processed_documents_processed_at ON processed_documents(processed_at DESC);

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE processed_documents TO docanalyzer;
GRANT USAGE, SELECT ON SEQUENCE processed_documents_id_seq TO docanalyzer;


