"""Negative test rules for generating invalid input tests."""

from typing import List
from framework_poc.core.models import SchemaAnalysis, TestCase, Parameter


def generate_type_mismatch_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Test invalid parameter types.

    Args:
        schema: Tool schema analysis

    Returns:
        List of type mismatch test cases
    """
    tests = []

    for param in schema.parameters:
        # String param with int value
        if param.type == "string":
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_type_int",
                layer=2,
                category="negative",
                description=f"Invalid type (int) for {param.name}",
                params={param.name: 12345},
                expected_result="error",
                assertions=["error_type_validation"]
            ))

        # Int param with string value
        if param.type == "integer":
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_type_str",
                layer=2,
                category="negative",
                description=f"Invalid type (string) for {param.name}",
                params={param.name: "not_an_int"},
                expected_result="error",
                assertions=["error_type_validation"]
            ))

        # Boolean param with string value
        if param.type == "boolean":
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_type_str",
                layer=2,
                category="negative",
                description=f"Invalid type (string) for {param.name}",
                params={param.name: "yes"},
                expected_result="error",
                assertions=["error_type_validation"]
            ))

        # Array param with non-array value
        if param.type == "array":
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_type_str",
                layer=2,
                category="negative",
                description=f"Invalid type (string) for {param.name}",
                params={param.name: "not_an_array"},
                expected_result="error",
                assertions=["error_type_validation"]
            ))

    return tests


def generate_missing_required_params_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Test missing required parameters.

    Args:
        schema: Tool schema analysis

    Returns:
        List of missing parameter test cases
    """
    tests = []

    for param in schema.get_required_parameters():
        tests.append(TestCase(
            id=f"L2_{schema.tool_name}_missing_{param.name}",
            layer=2,
            category="negative",
            description=f"Call without required {param.name}",
            params={},  # Omit the required param
            expected_result="error",
            assertions=["error_missing_required_param"]
        ))

    return tests


def generate_invalid_enum_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Test invalid enum values.

    Args:
        schema: Tool schema analysis

    Returns:
        List of invalid enum test cases
    """
    tests = []

    for param in schema.parameters:
        if param.enum_values:
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_invalid_enum",
                layer=2,
                category="negative",
                description=f"Invalid enum value for {param.name}",
                params={param.name: "INVALID_ENUM_VALUE"},
                expected_result="error",
                assertions=["error_type_validation"]
            ))

    return tests


def generate_null_value_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Test null/None values for parameters.

    Args:
        schema: Tool schema analysis

    Returns:
        List of null value test cases
    """
    tests = []

    # Test null for required parameters
    for param in schema.get_required_parameters():
        tests.append(TestCase(
            id=f"L2_{schema.tool_name}_{param.name}_null",
            layer=2,
            category="negative",
            description=f"Null value for required {param.name}",
            params={param.name: None},
            expected_result="error",
            assertions=["error_type_validation"]
        ))

    return tests


def generate_malformed_value_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Test malformed values for specific parameter types.

    Args:
        schema: Tool schema analysis

    Returns:
        List of malformed value test cases
    """
    tests = []

    for param in schema.parameters:
        # Malformed ID
        if param.type == "string" and "id" in param.name.lower():
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_malformed",
                layer=2,
                category="negative",
                description=f"Malformed ID for {param.name}",
                params={param.name: "invalid_id_format"},
                expected_result="error",
                assertions=["error_type_validation"]
            ))

        # Invalid email format
        if param.type == "string" and "email" in param.name.lower():
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_invalid_email",
                layer=2,
                category="negative",
                description=f"Invalid email format for {param.name}",
                params={param.name: "not-an-email"},
                expected_result="error",
                assertions=["error_type_validation"]
            ))

        # Invalid URL format
        if param.type == "string" and "url" in param.name.lower():
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_invalid_url",
                layer=2,
                category="negative",
                description=f"Invalid URL format for {param.name}",
                params={param.name: "not-a-url"},
                expected_result="error",
                assertions=["error_type_validation"]
            ))

    return tests
