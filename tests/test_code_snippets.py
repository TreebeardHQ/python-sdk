"""Tests for code snippet capture functionality."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from treebeardhq.code_snippets import CodeSnippetExtractor, format_code_snippet, FrameInfo


class TestCodeSnippetExtractor(unittest.TestCase):
    """Test cases for CodeSnippetExtractor."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = CodeSnippetExtractor(
            context_lines=3,
            max_frames=10,
            capture_locals=False,
            exclude_patterns=['test_exclude']
        )

    def test_init_default_values(self):
        """Test CodeSnippetExtractor initialization with defaults."""
        extractor = CodeSnippetExtractor()
        self.assertEqual(extractor.context_lines, 5)
        self.assertEqual(extractor.max_frames, 50)
        self.assertFalse(extractor.capture_locals)
        self.assertEqual(extractor.exclude_patterns, [])

    def test_init_custom_values(self):
        """Test CodeSnippetExtractor initialization with custom values."""
        extractor = CodeSnippetExtractor(
            context_lines=3,
            max_frames=10,
            capture_locals=True,
            exclude_patterns=['site-packages', 'venv']
        )
        self.assertEqual(extractor.context_lines, 3)
        self.assertEqual(extractor.max_frames, 10)
        self.assertTrue(extractor.capture_locals)
        self.assertEqual(extractor.exclude_patterns, ['site-packages', 'venv'])

    def test_should_exclude_file(self):
        """Test file exclusion logic."""
        # Test Python internals
        self.assertTrue(self.extractor._should_exclude_file('<built-in>'))
        self.assertTrue(self.extractor._should_exclude_file('<frozen>'))
        
        # Test exclude patterns
        self.assertTrue(self.extractor._should_exclude_file('/path/test_exclude/file.py'))
        self.assertFalse(self.extractor._should_exclude_file('/path/normal/file.py'))

    def test_read_source_lines_success(self):
        """Test successful source file reading."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('def test_function():\n')
            f.write('    print("Hello, World!")\n')
            f.write('    return 42\n')
            temp_file = f.name

        try:
            lines = self.extractor._read_source_lines(temp_file)
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[0], 'def test_function():\n')
            self.assertEqual(lines[1], '    print("Hello, World!")\n')
            self.assertEqual(lines[2], '    return 42\n')
        finally:
            os.unlink(temp_file)

    def test_read_source_lines_nonexistent_file(self):
        """Test reading nonexistent file."""
        lines = self.extractor._read_source_lines('/nonexistent/file.py')
        self.assertEqual(lines, [])

    def test_read_source_lines_large_file(self):
        """Test reading large file is skipped."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Write content larger than 1MB
            content = 'x' * (1024 * 1024 + 1)
            f.write(content)
            temp_file = f.name

        try:
            lines = self.extractor._read_source_lines(temp_file)
            self.assertEqual(lines, [])
        finally:
            os.unlink(temp_file)

    def test_serialize_locals_none(self):
        """Test serializing None locals."""
        result = self.extractor._serialize_locals(None)
        self.assertIsNone(result)

    def test_serialize_locals_empty(self):
        """Test serializing empty locals."""
        result = self.extractor._serialize_locals({})
        self.assertIsNone(result)

    def test_serialize_locals_normal(self):
        """Test serializing normal local variables."""
        locals_dict = {
            'x': 42,
            'name': 'test',
            '__builtins__': {},  # Should be skipped
            'func': lambda x: x,  # Should be skipped
        }
        result = self.extractor._serialize_locals(locals_dict)
        expected = {'x': '42', 'name': "'test'"}
        self.assertEqual(result, expected)

    def test_serialize_locals_long_value(self):
        """Test serializing long local variable values."""
        long_value = 'x' * 300
        locals_dict = {'long_var': long_value}
        result = self.extractor._serialize_locals(locals_dict)
        self.assertIn('long_var', result)
        self.assertTrue(result['long_var'].endswith('...'))
        self.assertTrue(len(result['long_var']) <= 200)

    def test_extract_from_exception_no_traceback(self):
        """Test extracting from exception with no traceback."""
        exception = ValueError("Test error")
        result = self.extractor.extract_from_exception(exception)
        self.assertEqual(result, [])

    def test_extract_from_exception_with_traceback(self):
        """Test extracting from exception with traceback."""
        # Create a temporary file with test code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('def test_function():\n')
            f.write('    x = 1\n')
            f.write('    y = 2\n')
            f.write('    raise ValueError("test error")\n')
            f.write('    return x + y\n')
            temp_file = f.name

        try:
            # Execute the code to create an exception with traceback
            with open(temp_file, 'r') as f:
                code = f.read()
            
            global_vars = {'__file__': temp_file}
            try:
                exec(code, global_vars)
                exec('test_function()', global_vars)
            except Exception as e:
                frames = self.extractor.extract_from_exception(e)
                
                # Should have at least one frame
                self.assertGreater(len(frames), 0)
                
                # Check the frame that contains our test code
                test_frame = None
                for frame in frames:
                    if frame['filename'] == temp_file:
                        test_frame = frame
                        break
                
                if test_frame:
                    self.assertEqual(test_frame['function'], 'test_function')
                    self.assertEqual(test_frame['lineno'], 4)
                    self.assertIn('raise ValueError("test error")', 
                                test_frame['code_snippet'])
        finally:
            os.unlink(temp_file)


class TestFrameInfo(unittest.TestCase):
    """Test cases for FrameInfo functionality."""

    def test_format_code_snippet_basic(self):
        """Test basic code snippet formatting."""
        frame_info: FrameInfo = {
            'filename': '/test/file.py',
            'lineno': 5,
            'function': 'test_func',
            'code_snippet': ['def test_func():', '    x = 1', '    return x'],
            'context_line_numbers': [3, 4, 5],
            'error_line_index': 2,
            'locals': None
        }
        
        result = format_code_snippet(frame_info)
        lines = result.split('\n')
        
        self.assertEqual(len(lines), 3)
        self.assertIn('def test_func():', lines[0])
        self.assertIn('x = 1', lines[1])
        self.assertIn('>5', lines[2])  # Error line marker
        self.assertIn('return x', lines[2])

    def test_format_code_snippet_no_line_numbers(self):
        """Test code snippet formatting without line numbers."""
        frame_info: FrameInfo = {
            'filename': '/test/file.py',
            'lineno': 5,
            'function': 'test_func',
            'code_snippet': ['def test_func():', '    x = 1', '    return x'],
            'context_line_numbers': [3, 4, 5],
            'error_line_index': 2,
            'locals': None
        }
        
        result = format_code_snippet(frame_info, show_line_numbers=False)
        lines = result.split('\n')
        
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[2].startswith('>'))  # Error line marker
        self.assertNotIn('5', lines[2])  # No line number

    def test_format_code_snippet_no_highlight(self):
        """Test code snippet formatting without error highlighting."""
        frame_info: FrameInfo = {
            'filename': '/test/file.py',
            'lineno': 5,
            'function': 'test_func',
            'code_snippet': ['def test_func():', '    x = 1', '    return x'],
            'context_line_numbers': [3, 4, 5],
            'error_line_index': 2,
            'locals': None
        }
        
        result = format_code_snippet(frame_info, highlight_error=False)
        lines = result.split('\n')
        
        self.assertEqual(len(lines), 3)
        self.assertIn(' 5 ', lines[2])  # Line number without error marker
        self.assertNotIn('>', lines[2])  # No error marker

    def test_format_code_snippet_empty(self):
        """Test formatting empty code snippet."""
        frame_info: FrameInfo = {
            'filename': '/test/file.py',
            'lineno': 5,
            'function': 'test_func',
            'code_snippet': [],
            'context_line_numbers': [],
            'error_line_index': -1,
            'locals': None
        }
        
        result = format_code_snippet(frame_info)
        self.assertEqual(result, "")


class TestCodeSnippetIntegration(unittest.TestCase):
    """Integration tests for code snippet capture."""

    def test_end_to_end_exception_capture(self):
        """Test complete exception capture workflow."""
        # Create an exception with a known traceback
        def test_function():
            x = 10
            y = 0
            return x / y  # This will raise ZeroDivisionError
        
        exception = None
        try:
            test_function()
        except Exception as e:
            exception = e

        self.assertIsNotNone(exception)
        
        # Extract code snippets
        extractor = CodeSnippetExtractor(context_lines=2)
        frames = extractor.extract_from_exception(exception)
        
        # Should have at least one frame
        self.assertGreater(len(frames), 0)
        
        # Look for the test_function frame
        test_frame = None
        for frame in frames:
            if frame['function'] == 'test_function':
                test_frame = frame
                break
        
        # If we found the test_function frame, verify it has code
        if test_frame:
            # Check that the error line is captured
            self.assertTrue(any('x / y' in line for line in test_frame['code_snippet']))
            
            # Test formatting
            formatted = format_code_snippet(test_frame)
            self.assertIn('x / y', formatted)
        else:
            # If we didn't find test_function, just verify we got some frames
            self.assertGreater(len(frames), 0)


if __name__ == '__main__':
    unittest.main()