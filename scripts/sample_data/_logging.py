"""Tiny logging helpers shared by every sample-data creator."""

from datetime import datetime


def log_info(message: str) -> None:
    """Log an info message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def log_progress(current: int, total: int, entity_name: str) -> None:
    """Log progress for entity creation."""
    percentage = (current / total * 100) if total > 0 else 0
    log_info(f"  {entity_name}: {current:,}/{total:,} ({percentage:.1f}%)")


def log_section(message: str) -> None:
    """Log a section header."""
    print()
    log_info("=" * 60)
    log_info(message)
    log_info("=" * 60)
