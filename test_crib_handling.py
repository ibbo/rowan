#!/usr/bin/env python3
"""
Test for lesson_tools.py - specifically testing crib type handling.
"""


def test_extract_crib_text():
    """Test helper function to extract text from various crib formats."""
    from lesson_tools import _extract_crib_text
    
    # String crib
    assert _extract_crib_text("Simple crib text") == "Simple crib text", "String test failed"
    print("✅ String crib: PASSED")
    
    # None
    assert _extract_crib_text(None) == "", "None test failed"
    print("✅ None crib: PASSED")
    
    # Dict with 'text' key
    assert _extract_crib_text({"text": "Crib text", "source": "RSCDS"}) == "Crib text", "Dict with text key failed"
    print("✅ Dict with 'text' key: PASSED")
    
    # Dict with 'crib' key
    assert _extract_crib_text({"crib": "Another crib"}) == "Another crib", "Dict with crib key failed"
    print("✅ Dict with 'crib' key: PASSED")
    
    # Dict with neither - should stringify
    result = _extract_crib_text({"foo": "bar"})
    assert result and "foo" in result, "Dict stringify failed"
    print("✅ Dict stringify: PASSED")
    
    # List
    result = _extract_crib_text(["Step 1", "Step 2"])
    assert "Step 1" in result, "List test failed"
    print("✅ List crib: PASSED")
    
    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    test_extract_crib_text()
