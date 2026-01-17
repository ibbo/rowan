#!/usr/bin/env python3
"""
Settings Storage Module

Manages persistent configuration settings for the SCD application,
including LLM provider and model selection.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Optional

# Settings database path (same directory as chat history)
SETTINGS_DB_PATH = "data/settings.db"


def _get_connection() -> sqlite3.Connection:
    """Get a connection to the settings database."""
    os.makedirs(os.path.dirname(SETTINGS_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SETTINGS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_settings_db():
    """Initialize the settings database tables."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Create settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Initialize default settings if not present
        defaults = {
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",  # Safe default that exists
            "llm_temperature": "0",
        }
        
        for key, value in defaults.items():
            cursor.execute("""
                INSERT OR IGNORE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, datetime.utcnow().isoformat()))
        
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a setting value by key.
    
    Args:
        key: Setting key
        default: Default value if not found
        
    Returns:
        Setting value or default
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str):
    """Set a setting value.
    
    Args:
        key: Setting key
        value: Setting value
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET 
                value = excluded.value,
                updated_at = excluded.updated_at
        """, (key, value, datetime.utcnow().isoformat()))
        conn.commit()
    finally:
        conn.close()


def get_all_settings() -> dict[str, str]:
    """Get all settings as a dictionary.
    
    Returns:
        Dictionary of all settings
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}
    finally:
        conn.close()


def get_llm_settings() -> dict[str, Any]:
    """Get LLM-specific settings.
    
    Returns:
        Dictionary with provider, model, and temperature
    """
    return {
        "provider": get_setting("llm_provider", "openai"),
        "model": get_setting("llm_model", "gpt-4o-mini"),
        "temperature": float(get_setting("llm_temperature", "0")),
    }


def set_llm_settings(provider: str, model: str, temperature: float = 0):
    """Set LLM settings.
    
    Args:
        provider: Provider name (openai, google)
        model: Model identifier
        temperature: Sampling temperature
    """
    set_setting("llm_provider", provider)
    set_setting("llm_model", model)
    set_setting("llm_temperature", str(temperature))


# Auto-initialize on import
init_settings_db()
