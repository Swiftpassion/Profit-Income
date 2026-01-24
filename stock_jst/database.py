from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
import streamlit as st
from config import DATABASE_URL, SQLITE_URL

Base = declarative_base()

def get_engine():
    try:
        # Try connecting to PostgreSQL
        engine = create_engine(DATABASE_URL, echo=False)
        # Test connection
        with engine.connect() as conn:
            pass
        return engine
    except Exception as e:
        st.warning(f"⚠️ Could not connect to PostgreSQL: {e}. Falling back to SQLite.")
        # Fallback to SQLite
        engine = create_engine(SQLITE_URL, echo=False)
        return engine

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    import models # Import models to register them with Base
    try:
        Base.metadata.create_all(bind=engine)
        import time
        success_msg = st.success("✅ Database initialized successfully!")
        time.sleep(3)
        success_msg.empty()
    except Exception as e:
        st.error(f"❌ Error initializing database: {e}")
