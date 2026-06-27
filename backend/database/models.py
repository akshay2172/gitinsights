import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.database import Base

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    owner = Column(String(255), nullable=False)
    github_url = Column(String(512), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    primary_language = Column(String(50), nullable=True)
    status = Column(String(50), default="importing", nullable=False)  # importing, cloned, parsing, indexing, ready, failed
    error_message = Column(Text, nullable=True)
    
    # Generated summaries (AI Overview)
    summary = Column(Text, nullable=True)
    tech_stack = Column(Text, nullable=True)       # HTML/Markdown list or description
    folder_overview = Column(Text, nullable=True)  # Overview of folder structure
    important_modules = Column(Text, nullable=True)
    starting_point = Column(Text, nullable=True)
    
    # Parsed structure metadata
    languages_json = Column(Text, nullable=True)     # JSON dict: {lang: percentage/bytes}
    dependencies_json = Column(Text, nullable=True)  # JSON list: ["fastapi", "numpy", ...]
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    files = relationship("FileRecord", back_populates="repository", cascade="all, delete-orphan")


class FileRecord(Base):
    __tablename__ = "file_records"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    path = Column(String(1024), nullable=False)  # relative path e.g. "src/main.py"
    name = Column(String(255), nullable=False)   # filename e.g. "main.py"
    language = Column(String(50), nullable=True)  # python, javascript, typescript, etc.
    size = Column(Integer, nullable=False)       # size in bytes
    content = Column(Text, nullable=False)       # full source file content
    
    # AI explanation cache
    purpose_explanation = Column(Text, nullable=True)
    
    # Extracted code symbols (serialized JSON)
    functions_json = Column(Text, nullable=True)  # JSON list of dicts: [{"name": "foo", "start_line": 1, "end_line": 10, "args": [...]}]
    classes_json = Column(Text, nullable=True)    # JSON list of dicts: [{"name": "Bar", "start_line": 11, "end_line": 50}]
    imports_json = Column(Text, nullable=True)    # JSON list of strings: ["os", "sys"]

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    repository = relationship("Repository", back_populates="files")
