"""
Database setup and session management for RankPredict v2
Supports SQLite (local dev) and PostgreSQL (production)
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

# Check for PostgreSQL connection string (Railway provides DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Production: Use PostgreSQL
    # Railway uses postgres:// but SQLAlchemy needs postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Verify connections before use
        echo=False
    )
    print(f"Using PostgreSQL database")
else:
    # Local development: Use SQLite
    BASE_DIR = Path(__file__).parent.parent
    DATABASE_FILE = BASE_DIR / "rankpredict_v2.db"
    DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        echo=False
    )
    print(f"Using SQLite database at {DATABASE_FILE}")

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session
    Use with FastAPI Depends()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables
    Call this on application startup
    """
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized")

    # Run migrations for new columns
    run_migrations()


def run_migrations():
    """
    Run any pending schema migrations.
    This handles adding new columns to existing tables.
    """
    from sqlalchemy import text, inspect

    inspector = inspect(engine)

    # Check if strategy_projects table exists
    if "strategy_projects" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("strategy_projects")]

        with engine.connect() as conn:
            # Add sync_status column if missing
            if "sync_status" not in columns:
                print("Adding sync_status column to strategy_projects...")
                conn.execute(text("ALTER TABLE strategy_projects ADD COLUMN sync_status VARCHAR"))
                conn.commit()

            # Add sync_message column if missing
            if "sync_message" not in columns:
                print("Adding sync_message column to strategy_projects...")
                conn.execute(text("ALTER TABLE strategy_projects ADD COLUMN sync_message VARCHAR"))
                conn.commit()

        # Add domain column if missing
        with engine.connect() as conn:
            if "domain" not in columns:
                print("Adding domain column to strategy_projects...")
                conn.execute(text("ALTER TABLE strategy_projects ADD COLUMN domain VARCHAR"))
                conn.commit()

            # Add persona column if missing
            if "persona" not in columns:
                print("Adding persona column to strategy_projects...")
                conn.execute(text("ALTER TABLE strategy_projects ADD COLUMN persona JSON"))
                conn.commit()

    # Check if keyword_lists table exists
    if "keyword_lists" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("keyword_lists")]

        with engine.connect() as conn:
            if "project_id" not in columns:
                print("Adding project_id column to keyword_lists...")
                conn.execute(text("ALTER TABLE keyword_lists ADD COLUMN project_id INTEGER"))
                conn.commit()

    # Check if strategy_keywords table exists
    if "strategy_keywords" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("strategy_keywords")]

        with engine.connect() as conn:
            # Add is_ai_generated column if missing
            if "is_ai_generated" not in columns:
                print("Adding is_ai_generated column to strategy_keywords...")
                conn.execute(text("ALTER TABLE strategy_keywords ADD COLUMN is_ai_generated BOOLEAN DEFAULT FALSE"))
                conn.commit()

    print("Migrations complete")

