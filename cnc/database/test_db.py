import asyncio
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
import sqlite3

async def test_database_connection():
    # Same pattern as your original code
    DB_PATH = Path(__file__).parent.parent / "pentest_hub.db"  # Adjusted path
    # NOTE: below path only works on windows
    # DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite+aiosqlite:///./{str(DB_PATH)}")
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite+aiosqlite:///{str(DB_PATH)}")
    
    print(f"Script location: {Path(__file__).resolve()}")
    print(f"Database path: {DB_PATH.resolve()}")
    print(f"Database exists: {DB_PATH.exists()}")
    print(f"Database URL: {DATABASE_URL}")
    print("-" * 50)
    
    # Check if file exists and create if it doesn't
    if not DB_PATH.exists():
        print("Database file doesn't exist. Creating empty database...")
        DB_PATH.touch()
    
    try:
        # Test with regular sqlite3 first (simpler)
        print("Testing with regular sqlite3:")
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables found: {[table[0] for table in tables]}")
        conn.close()
        print("✅ Regular sqlite3 connection successful")
        print("-" * 50)
        
    except Exception as e:
        print(f"❌ Regular sqlite3 failed: {e}")
        return
    
    # Now test with async SQLAlchemy (your pattern)
    try:
        print("Testing with async SQLAlchemy:")
        engine = create_async_engine(DATABASE_URL, echo=False)
        
        async with engine.begin() as conn:
            # Get all tables
            tables = await conn.run_sync(
                lambda c: c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            )
            print(f"Tables found: {[table[0] for table in tables]}")
            
            # Get table info for each table
            for table_row in tables:
                table_name = table_row[0]
                print(f"\nTable: {table_name}")
                try:
                    cols = await conn.run_sync(
                        lambda c: c.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
                    )
                    print(f"  Columns: {[col[1] for col in cols]}")
                except Exception as e:
                    print(f"  Error getting columns: {e}")
        
        await engine.dispose()
        print("✅ Async SQLAlchemy connection successful")
        
    except Exception as e:
        print(f"❌ Async SQLAlchemy failed: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_database_connection())