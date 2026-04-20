"""Tests for the blueprint JSON extractor used when the model returns raw text.

Covers fenced ```json blocks, bare objects, nested braces, strings that
contain braces, and garbage prefixes that the model sometimes prepends.
"""

from src.generator import _extract_json_object


def test_extract_fenced_json():
    text = 'Here you go:\n```json\n{"a": 1, "b": 2}\n```'
    assert _extract_json_object(text) == '{"a": 1, "b": 2}'


def test_extract_fenced_without_language():
    text = '```\n{"key": "value"}\n```'
    assert _extract_json_object(text) == '{"key": "value"}'


def test_extract_bare_object_with_prefix():
    text = "Sure, here is your JSON: {\"ok\": true}"
    assert _extract_json_object(text) == '{"ok": true}'


def test_extract_nested_braces():
    text = '{"outer": {"inner": {"deep": [1, 2, 3]}}}'
    assert _extract_json_object(text) == text


def test_extract_string_with_braces():
    """Braces inside strings must not close the object prematurely."""
    text = '{"msg": "this { should not close", "n": 1}'
    assert _extract_json_object(text) == text


def test_extract_string_with_escaped_quotes():
    text = r'{"escape": "he said \"hi\"", "ok": true}'
    assert _extract_json_object(text) == text


def test_extract_returns_none_when_no_object():
    assert _extract_json_object("just prose, no json here") is None


def test_extract_empty_string():
    assert _extract_json_object("") is None


def test_extract_none_input():
    assert _extract_json_object(None) is None  # type: ignore[arg-type]


def test_extract_stops_at_first_complete_object():
    """When the model emits two back-to-back JSON objects, return only the first."""
    text = '{"first": 1}{"second": 2}'
    assert _extract_json_object(text) == '{"first": 1}'
