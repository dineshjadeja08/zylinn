"""
Database Migration Script
Ensures all tables including the new Appointment table are created.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from models import DatabaseManager
import structlog

logger = structlog.get_logger(__name__)

def migrate():
    """Run database migration"""
    print("🔄 Running database migration...")
    
    try:
        db_manager = DatabaseManager()
        
        print("📊 Creating/updating tables...")
        db_manager.create_tables()
        
        print("✅ Migration completed successfully!")
        print(f"📁 Database location: {db_manager.database_url}")
        
        # Verify tables exist
        from sqlalchemy import inspect
        inspector = inspect(db_manager.engine)
        tables = inspector.get_table_names()
        
        print(f"\n📋 Tables in database: {', '.join(tables)}")
        
        expected_tables = ['call_records', 'transcript_chunks', 'agent_replies', 'appointments']
        missing_tables = [t for t in expected_tables if t not in tables]
        
        if missing_tables:
            print(f"⚠️  Warning: Missing tables: {', '.join(missing_tables)}")
        else:
            print("✅ All expected tables present!")
            
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        raise

if __name__ == "__main__":
    migrate()
