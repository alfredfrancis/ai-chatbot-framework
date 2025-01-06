from datetime import datetime, UTC

def utc_now() -> datetime:
    """Get current UTC datetime with timezone information"""
    return datetime.now(UTC) 