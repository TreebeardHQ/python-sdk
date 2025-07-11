#!/usr/bin/env python3
"""Example demonstrating code snippet capture functionality."""

from treebeardhq import Treebeard
from treebeardhq.span import record_exception_on_span, start_span


def problematic_function():
    """A function that will cause an exception."""
    x = 10
    y = 0
    result = x / y  # This will raise ZeroDivisionError
    return result


def another_function():
    """Another function in the call stack."""
    return problematic_function()


def main():
    """Main function demonstrating code snippet capture."""
    # Initialize Treebeard with code snippet capture enabled
    treebeard = Treebeard(
        project_name="code-snippet-demo",
        code_snippet_enabled=True,
        code_snippet_context_lines=3,
        code_snippet_max_frames=10,
        code_snippet_exclude_patterns=['site-packages']
    )
    
    print("Code snippet capture example")
    print("=" * 40)
    
    # Start a span to capture the exception
    span = start_span("demo-operation")
    
    try:
        another_function()
    except Exception as e:
        print(f"Caught exception: {e}")
        
        # Record the exception with code snippets
        record_exception_on_span(e, span=span)
        
        # You can also disable code snippets for specific exceptions
        # record_exception_on_span(e, span=span, capture_code_snippets=False)
        
        # Or override the context lines
        # record_exception_on_span(e, span=span, context_lines=2)
        
        print("\nException recorded with code snippets!")
        print("In a real application, this would be sent to your monitoring system.")
    
    # Configuration can also be set via environment variables:
    # export TREEBEARD_CODE_SNIPPET_ENABLED=true
    # export TREEBEARD_CODE_SNIPPET_CONTEXT_LINES=5
    # export TREEBEARD_CODE_SNIPPET_MAX_FRAMES=20
    # export TREEBEARD_CODE_SNIPPET_EXCLUDE_PATTERNS=site-packages,venv,__pycache__


if __name__ == "__main__":
    main()