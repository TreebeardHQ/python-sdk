"""Tests for code snippet integration in span exception recording."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from treebeardhq.core import Treebeard
from treebeardhq.span import record_exception_on_span
from treebeardhq.spans import Span, SpanStatus, SpanStatusCode


class TestSpanCodeSnippetIntegration(unittest.TestCase):
    """Test cases for code snippet integration in span exception recording."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset Treebeard singleton
        Treebeard.reset()
        
        # Create a mock span
        self.mock_span = Mock(spec=Span)
        self.mock_span.status = Mock()
        self.mock_span.status.code = SpanStatusCode.UNSET
        self.mock_span.add_event = Mock()

    def test_record_exception_with_code_snippets_enabled(self):
        """Test recording exception with code snippets enabled."""
        # Initialize Treebeard with code snippets enabled
        treebeard = Treebeard(
            project_name="test",
            code_snippet_enabled=True,
            code_snippet_context_lines=3
        )
        
        # Create an exception with a known traceback
        def test_function():
            x = 1
            y = 0
            result = x / y  # Error line
            return result
        
        exception = None
        try:
            test_function()
        except Exception as e:
            exception = e

        # Record exception on span
        record_exception_on_span(exception, span=self.mock_span)

        # Verify add_event was called
        self.mock_span.add_event.assert_called_once()
        event_name, attributes = self.mock_span.add_event.call_args[0]
        
        self.assertEqual(event_name, "exception")
        self.assertIn("exception.type", attributes)
        self.assertIn("exception.message", attributes)
        self.assertIn("exception.stacktrace", attributes)
        
        # Check for frame information
        frame_keys = [key for key in attributes.keys() if key.startswith("exception.frames.")]
        self.assertGreater(len(frame_keys), 0)
        
        # Check for code snippet containing the error line
        found_code_snippet = False
        for key, value in attributes.items():
            if key.endswith('.code_snippet') and 'x / y' in str(value):
                found_code_snippet = True
                break
        self.assertTrue(found_code_snippet, "Code snippet not found in attributes")

    def test_record_exception_with_code_snippets_disabled(self):
        """Test recording exception with code snippets disabled."""
        # Initialize Treebeard with code snippets disabled
        treebeard = Treebeard(
            project_name="test",
            code_snippet_enabled=False
        )
        
        exception = ValueError("Test error")
        record_exception_on_span(exception, span=self.mock_span)

        # Verify add_event was called
        self.mock_span.add_event.assert_called_once()
        event_name, attributes = self.mock_span.add_event.call_args[0]
        
        self.assertEqual(event_name, "exception")
        self.assertIn("exception.type", attributes)
        self.assertIn("exception.message", attributes)
        self.assertIn("exception.stacktrace", attributes)
        
        # Check that no frame information was added
        frame_keys = [key for key in attributes.keys() if key.startswith("exception.frames.")]
        self.assertEqual(len(frame_keys), 0)

    def test_record_exception_override_capture_snippets_parameter(self):
        """Test overriding code snippet capture with function parameter."""
        # Initialize Treebeard with code snippets enabled
        treebeard = Treebeard(
            project_name="test",
            code_snippet_enabled=True
        )
        
        exception = ValueError("Test error")
        
        # Override to disable code snippets for this call
        record_exception_on_span(
            exception, 
            span=self.mock_span,
            capture_code_snippets=False
        )

        # Verify add_event was called
        self.mock_span.add_event.assert_called_once()
        event_name, attributes = self.mock_span.add_event.call_args[0]
        
        # Check that no frame information was added despite global setting
        frame_keys = [key for key in attributes.keys() if key.startswith("exception.frames.")]
        self.assertEqual(len(frame_keys), 0)

    def test_record_exception_override_context_lines_parameter(self):
        """Test overriding context lines with function parameter."""
        # Initialize Treebeard with default context lines
        treebeard = Treebeard(
            project_name="test",
            code_snippet_enabled=True,
            code_snippet_context_lines=5
        )
        
        # Create a temporary file with many lines
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            for i in range(20):
                f.write(f'# Line {i+1}\n')
            f.write('def test_function():\n')  # Line 21
            f.write('    raise ValueError("test")\n')  # Line 22
            temp_file = f.name

        try:
            # Execute code to create exception with traceback
            with open(temp_file, 'r') as f:
                code = f.read()
            
            global_vars = {'__file__': temp_file}
            exception = None
            try:
                exec(code, global_vars)
                exec('test_function()', global_vars)
            except Exception as e:
                exception = e

            # Override context lines to 2
            record_exception_on_span(
                exception, 
                span=self.mock_span,
                context_lines=2
            )

            # Verify context lines were limited
            self.mock_span.add_event.assert_called_once()
            event_name, attributes = self.mock_span.add_event.call_args[0]
            
            # Find the code snippet
            code_snippet = None
            for key, value in attributes.items():
                if key.endswith('.code_snippet') and 'test_function' in str(value):
                    code_snippet = str(value)
                    break
            
            if code_snippet:
                lines = code_snippet.split('\n')
                # Should have 5 lines max (2 before + error line + 2 after)
                self.assertLessEqual(len(lines), 5)

        finally:
            os.unlink(temp_file)

    def test_record_exception_escaped_parameter(self):
        """Test recording exception with escaped parameter."""
        treebeard = Treebeard(project_name="test")
        exception = ValueError("Test error")
        
        record_exception_on_span(
            exception, 
            span=self.mock_span,
            escaped=True
        )

        # Verify escaped attribute was added
        self.mock_span.add_event.assert_called_once()
        event_name, attributes = self.mock_span.add_event.call_args[0]
        
        self.assertEqual(attributes.get("exception.escaped"), "true")

    def test_record_exception_configuration_from_environment(self):
        """Test code snippet configuration from environment variables."""
        # Set environment variables
        env_vars = {
            'TREEBEARD_CODE_SNIPPET_ENABLED': 'true',
            'TREEBEARD_CODE_SNIPPET_CONTEXT_LINES': '3',
            'TREEBEARD_CODE_SNIPPET_MAX_FRAMES': '10',
            'TREEBEARD_CODE_SNIPPET_EXCLUDE_PATTERNS': 'test_exclude,venv'
        }
        
        with patch.dict(os.environ, env_vars):
            # Reset and reinitialize Treebeard
            Treebeard.reset()
            treebeard = Treebeard(project_name="test")
            
            self.assertTrue(treebeard.code_snippet_enabled)
            self.assertEqual(treebeard.code_snippet_context_lines, 3)
            self.assertEqual(treebeard.code_snippet_max_frames, 10)
            self.assertEqual(treebeard.code_snippet_exclude_patterns, ['test_exclude', 'venv'])

    def test_record_exception_exclude_patterns(self):
        """Test exception recording with exclude patterns."""
        # Initialize with exclude patterns
        treebeard = Treebeard(
            project_name="test",
            code_snippet_enabled=True,
            code_snippet_exclude_patterns=['test_exclude']
        )
        
        # Create a temporary file in excluded directory
        temp_dir = tempfile.mkdtemp()
        exclude_dir = os.path.join(temp_dir, 'test_exclude')
        os.makedirs(exclude_dir)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', 
                                       dir=exclude_dir, delete=False) as f:
            f.write('def test_function():\n')
            f.write('    raise ValueError("test")\n')
            temp_file = f.name

        try:
            # Execute code to create exception
            with open(temp_file, 'r') as f:
                code = f.read()
            
            global_vars = {'__file__': temp_file}
            exception = None
            try:
                exec(code, global_vars)
                exec('test_function()', global_vars)
            except Exception as e:
                exception = e

            record_exception_on_span(exception, span=self.mock_span)

            # Verify add_event was called
            self.mock_span.add_event.assert_called_once()
            event_name, attributes = self.mock_span.add_event.call_args[0]
            
            # Check that excluded file frames don't have code snippets
            excluded_frame_found = False
            for key, value in attributes.items():
                if key.endswith('.filename') and 'test_exclude' in str(value):
                    excluded_frame_found = True
                    # Check that this frame doesn't have a code snippet
                    frame_prefix = key.replace('.filename', '')
                    code_snippet_key = f"{frame_prefix}.code_snippet"
                    self.assertNotIn(code_snippet_key, attributes)
            
            # We might not find the excluded frame due to the exclusion logic

        finally:
            os.unlink(temp_file)
            os.rmdir(exclude_dir)
            os.rmdir(temp_dir)

    @patch('treebeardhq.span.LoggingContext.get_current_span')
    def test_record_exception_no_span_provided(self, mock_get_current_span):
        """Test recording exception when no span is provided."""
        mock_get_current_span.return_value = None
        
        exception = ValueError("Test error")
        
        # Should not raise an error
        record_exception_on_span(exception)
        
        # Verify get_current_span was called
        mock_get_current_span.assert_called_once()

    @patch('treebeardhq.span.LoggingContext.get_current_span')
    def test_record_exception_uses_current_span(self, mock_get_current_span):
        """Test recording exception uses current span when none provided."""
        mock_get_current_span.return_value = self.mock_span
        
        treebeard = Treebeard(project_name="test")
        exception = ValueError("Test error")
        
        record_exception_on_span(exception)
        
        # Verify the current span was used
        mock_get_current_span.assert_called_once()
        self.mock_span.add_event.assert_called_once()


if __name__ == '__main__':
    unittest.main()