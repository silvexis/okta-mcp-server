"""Boundary test rules for generating edge case tests."""

from typing import List
from framework_poc.core.models import SchemaAnalysis, TestCase


def generate_boundary_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Test boundary conditions for parameters.

    Args:
        schema: Tool schema analysis

    Returns:
        List of boundary test cases
    """
    tests = []

    for param in schema.parameters:
        # Detect integer-like params by name even if type is "string" in schema
        integer_param_names = ['limit', 'count', 'size', 'offset', 'page', 'max', 'min']
        is_likely_integer = any(name in param.name.lower() for name in integer_param_names)

        # Integer boundaries
        if param.type == "integer" or is_likely_integer:
            tests.extend(_generate_integer_boundary_tests(schema, param))

        # String boundaries (skip for integer-like params)
        elif param.type == "string":
            tests.extend(_generate_string_boundary_tests(schema, param))

        # Array boundaries
        elif param.type == "array":
            tests.extend(_generate_array_boundary_tests(schema, param))

    return tests


def _generate_integer_boundary_tests(schema: SchemaAnalysis, param) -> List[TestCase]:
    """Generate boundary tests for integer parameters."""
    tests = []

    # Below minimum
    if "minimum" in param.constraints:
        min_val = param.constraints["minimum"]
        tests.append(TestCase(
            id=f"L2_{schema.tool_name}_{param.name}_below_min",
            layer=2,
            category="boundary",
            description=f"{param.name} below minimum ({min_val})",
            params={param.name: min_val - 1},
            expected_result="auto_corrected",
            assertions=["auto_corrected_to_min"]
        ))

        # At minimum
        tests.append(TestCase(
            id=f"L2_{schema.tool_name}_{param.name}_at_min",
            layer=2,
            category="boundary",
            description=f"{param.name} at minimum ({min_val})",
            params={param.name: min_val},
            expected_result="success",
            assertions=["response_present"]
        ))

    # Above maximum
    if "maximum" in param.constraints:
        max_val = param.constraints["maximum"]
        tests.append(TestCase(
            id=f"L2_{schema.tool_name}_{param.name}_above_max",
            layer=2,
            category="boundary",
            description=f"{param.name} above maximum ({max_val})",
            params={param.name: max_val + 1},
            expected_result="auto_corrected",
            assertions=["auto_corrected_to_max"]
        ))

        # At maximum
        tests.append(TestCase(
            id=f"L2_{schema.tool_name}_{param.name}_at_max",
            layer=2,
            category="boundary",
            description=f"{param.name} at maximum ({max_val})",
            params={param.name: max_val},
            expected_result="success",
            assertions=["response_present"]
        ))

    # Zero value
    if param.name in ["limit", "count", "size"]:
        tests.append(TestCase(
            id=f"L2_{schema.tool_name}_{param.name}_zero",
            layer=2,
            category="boundary",
            description=f"{param.name} with zero value",
            params={param.name: 0},
            expected_result="error",
            assertions=["error_invalid_value"]
        ))

    # Negative value
    tests.append(TestCase(
        id=f"L2_{schema.tool_name}_{param.name}_negative",
        layer=2,
        category="boundary",
        description=f"{param.name} with negative value",
        params={param.name: -1},
        expected_result="error",
        assertions=["error_invalid_value"]
    ))

    # Very large value
    # API may either auto-correct to max or reject outright
    tests.append(TestCase(
        id=f"L2_{schema.tool_name}_{param.name}_very_large",
        layer=2,
        category="boundary",
        description=f"{param.name} with very large value",
        params={param.name: 999999},
        expected_result="auto_corrected_or_error",
        assertions=["auto_corrected_or_error"]
    ))

    return tests


def _generate_string_boundary_tests(schema: SchemaAnalysis, param) -> List[TestCase]:
    """Generate boundary tests for string parameters."""
    tests = []

    # Empty string
    tests.append(TestCase(
        id=f"L2_{schema.tool_name}_{param.name}_empty",
        layer=2,
        category="boundary",
        description=f"{param.name} with empty string",
        params={param.name: ""},
        expected_result="error",
        assertions=["handled_gracefully"]
    ))

    # Whitespace only
    tests.append(TestCase(
        id=f"L2_{schema.tool_name}_{param.name}_whitespace",
        layer=2,
        category="boundary",
        description=f"{param.name} with whitespace only",
        params={param.name: "   "},
        expected_result="error",
        assertions=["handled_gracefully"]
    ))

    # Very long string
    if "maxLength" not in param.constraints:
        tests.append(TestCase(
            id=f"L2_{schema.tool_name}_{param.name}_very_long",
            layer=2,
            category="boundary",
            description=f"{param.name} with very long value",
            params={param.name: "x" * 10000},
            expected_result="error",
            assertions=["error_or_truncated"]
        ))

    # Special characters
    # Expect error for enum-like params, query/cursor params; success for free-text params
    is_strict_param = any(keyword in param.name.lower() for keyword in [
        "type", "status", "role", "state",  # enum-like
        "after", "before", "cursor",  # pagination cursors
        "q", "query"  # search queries
    ])
    special_chars_result = "error" if is_strict_param else "success"
    tests.append(TestCase(
        id=f"L2_{schema.tool_name}_{param.name}_special_chars",
        layer=2,
        category="boundary",
        description=f"{param.name} with special characters",
        params={param.name: "!@#$%^&*(){}[]|\\:;\"'<>,.?/~`"},
        expected_result=special_chars_result,
        assertions=["handled_gracefully"]
    ))

    # Unicode characters
    unicode_result = "error" if is_strict_param else "success"
    tests.append(TestCase(
        id=f"L2_{schema.tool_name}_{param.name}_unicode",
        layer=2,
        category="boundary",
        description=f"{param.name} with Unicode characters",
        params={param.name: "用户名αβγ🚀"},
        expected_result=unicode_result,
        assertions=["handled_gracefully"]
    ))

    # Single character
    # Enum-like params and query/cursor params typically reject single characters
    is_strict_param = any(keyword in param.name.lower() for keyword in [
        "type", "status", "role", "state",  # enum-like
        "after", "before", "cursor",  # pagination cursors
        "q", "query"  # search queries
    ])
    single_char_result = "error" if is_strict_param else "success"
    tests.append(TestCase(
        id=f"L2_{schema.tool_name}_{param.name}_single_char",
        layer=2,
        category="boundary",
        description=f"{param.name} with single character",
        params={param.name: "a"},
        expected_result=single_char_result,
        assertions=["response_present"]
    ))

    return tests


def _generate_array_boundary_tests(schema: SchemaAnalysis, param) -> List[TestCase]:
    """Generate boundary tests for array parameters."""
    tests = []

    # Empty array
    tests.append(TestCase(
        id=f"L2_{schema.tool_name}_{param.name}_empty_array",
        layer=2,
        category="boundary",
        description=f"{param.name} with empty array",
        params={param.name: []},
        expected_result="success_or_clarification",
        assertions=["handled_gracefully"]
    ))

    # Single item array
    tests.append(TestCase(
        id=f"L2_{schema.tool_name}_{param.name}_single_item",
        layer=2,
        category="boundary",
        description=f"{param.name} with single item",
        params={param.name: ["item1"]},
        expected_result="success",
        assertions=["response_present"]
    ))

    # Very large array
    if "maxItems" not in param.constraints:
        tests.append(TestCase(
            id=f"L2_{schema.tool_name}_{param.name}_large_array",
            layer=2,
            category="boundary",
            description=f"{param.name} with large array",
            params={param.name: ["item"] * 1000},
            expected_result="error",
            assertions=["error_or_truncated"]
        ))

    return tests
