"""
Quick test script to verify PostgreSQL connection.
Run this after starting the Docker container.
"""

from services.dedup import DedupService

def main():
    print("Testing PostgreSQL connection...")
    print("-" * 40)
    
    # Create service with default Docker settings
    service = DedupService()
    
    # Test connection
    result = service.test_connection()
    
    if result['status'] == 'connected':
        print("✓ Connection successful!")
        print(f"  Database URL: {result['database_url']}")
        
        # Test basic operations
        print("\nTesting basic operations...")
        
        # Get document count
        count = service.get_document_count()
        print(f"✓ Document count: {count}")
        
        print("\n" + "=" * 40)
        print("PostgreSQL is ready to use!")
        
    else:
        print("✗ Connection failed!")
        print(f"  Error: {result['message']}")
        print("\nTroubleshooting:")
        print("  1. Make sure Docker container is running: docker ps")
        print("  2. Check container logs: docker logs doc_analyzer_postgres")
        print("  3. Wait a few seconds for PostgreSQL to fully start")

if __name__ == "__main__":
    main()


