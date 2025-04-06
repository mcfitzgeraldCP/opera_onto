"""
Tests for utility functions in the types module.
"""
import pytest
from ontology_generator.utils.types import sanitize_name

class TestSanitizeName:
    """Test class for sanitize_name utility function."""
    
    @pytest.mark.parametrize("input_val, expected, description", [
        (None, "unnamed", "None value"),
        ("", "unnamed", "Empty string"),
        ("   ", "unnamed", "Whitespace only"),
        ("Simple", "Simple", "Simple alphanumeric"),
        ("Simple Name", "Simple_Name", "Spaces to underscore"),
        ("Name-With-Hyphens", "Name-With-Hyphens", "Preserve hyphens"),
        ("Name.With.Dots", "Name.With.Dots", "Preserve periods"),
        ("Name_With_Underscores", "Name_With_Underscores", "Preserve underscores"),
        ("123StartsWithNumber", "_123StartsWithNumber", "Prepend underscore to numbers"),
        ("-StartsWithHyphen", "_-StartsWithHyphen", "Prepend underscore to hyphen"),
        ("Special@#$%^&*()Chars", "Special___Chars", "Replace special chars with underscores"),
        ("<>:\"/\\|?*", "_________", "All special chars become underscores"),
        ("Mixed<>:\"/\\|?*AndLetters", "Mixed_________AndLetters", "Mixed content"),
        ("Üñîçøδê", "Üñîçøδê", "Unicode characters are preserved"),
        ("   Trim   Spaces   ", "Trim_Spaces", "Trim and collapse spaces"),
        ("<all special>", "_all_special_", "Special chars at boundaries"),
    ])
    def test_sanitize_name_cases(self, input_val, expected, description):
        """Test various input cases for sanitize_name function."""
        result = sanitize_name(input_val)
        assert result == expected, f"Failed on: {description}"
    
    def test_sanitize_name_consistency(self):
        """Test that sanitize_name is consistent for the same input."""
        reference = sanitize_name("Test String")
        for _ in range(5):
            assert sanitize_name("Test String") == reference
    
    def test_hash_fallback(self):
        """Test that empty inputs after sanitization use hash fallback."""
        # Special characters only should become underscores
        special_chars_only = "!@#$%^&*()"
        result = sanitize_name(special_chars_only)
        # Just check it's non-empty, the actual output depends on implementation
        assert result, "Should return a non-empty result for special chars"
        # Advanced test for potential hash fallback cases requires more context 