"""
Library package for reusable file processing utilities.

This package contains stateless, deterministic Python tools following the
Tool-First Principle - using Python for I/O operations while reserving
LLM for reasoning tasks.

Modules:
    file_processing: FileInspector class for S3 file structure analysis
"""

from core_tools.library.file_processing import FileInspector, FileStructure

__all__ = ["FileInspector", "FileStructure"]
