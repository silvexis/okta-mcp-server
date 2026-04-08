"""Semantic test rules for generating Layer 4 LLM behavior tests."""

from typing import List, Dict, Any
from framework_poc.core.models import SchemaAnalysis, TestCase


def generate_semantic_prompts(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Generate natural language prompts for Layer 4 testing.

    Args:
        schema: Tool schema analysis

    Returns:
        List of semantic test cases
    """
    tests = []

    # Generate tests based on tool type
    if "list_users" in schema.tool_name:
        tests.extend(_generate_list_users_semantic_tests(schema))
    elif "get_user" in schema.tool_name:
        tests.extend(_generate_get_user_semantic_tests(schema))
    elif "list" in schema.tool_name:
        tests.extend(_generate_generic_list_semantic_tests(schema))
    elif "get" in schema.tool_name:
        tests.extend(_generate_generic_get_semantic_tests(schema))
    else:
        tests.extend(_generate_default_semantic_tests(schema))

    return tests


def _generate_list_users_semantic_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """Generate semantic tests specific to list_users tool."""
    templates = [
        {
            "prompt": "List all users in the Engineering department",
            "expected_tool": "list_users",
            "expected_params": {"search": 'profile.department eq "Engineering"'},
            "judge_criteria": ["tool_selection", "parameter_correctness"]
        },
        {
            "prompt": "Show me all active users",
            "expected_tool": "list_users",
            "expected_params": {"filter": 'status eq "ACTIVE"'},
            "judge_criteria": ["tool_selection", "parameter_correctness"]
        },
        {
            "prompt": "How many users do we have total?",
            "expected_tool": "list_users",
            "expected_params": {"fetch_all": True},
            "judge_criteria": ["tool_selection", "parameter_correctness"]
        },
        {
            "prompt": "Show me the first 50 users",
            "expected_tool": "list_users",
            "expected_params": {"limit": 50},
            "judge_criteria": ["tool_selection", "parameter_correctness"]
        },
        {
            "prompt": "Get users with email ending in @company.com",
            "expected_tool": "list_users",
            "expected_params": {"search": 'profile.email ew "@company.com"'},
            "judge_criteria": ["tool_selection", "parameter_correctness"]
        },
        {
            "prompt": "Find user John Doe",
            "expected_tool": "list_users",
            "expected_params": {"q": "John Doe"},
            "judge_criteria": ["tool_selection", "parameter_correctness"]
        },
        {
            "prompt": "Get user details",  # Ambiguous
            "expected_behavior": "clarification",
            "judge_criteria": ["clarification_requested"]
        },
        {
            "prompt": "List all suspended users in Sales",
            "expected_tool": "list_users",
            "expected_params": {
                "filter": 'status eq "SUSPENDED"',
                "search": 'profile.department eq "Sales"'
            },
            "judge_criteria": ["tool_selection", "parameter_correctness"]
        },
    ]

    tests = []
    for i, template in enumerate(templates):
        tests.append(_create_semantic_test_case(schema, template, i))

    return tests


def _generate_get_user_semantic_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """Generate semantic tests specific to get_user tool."""
    templates = [
        {
            "prompt": "Get details for user 00u1234567890abcdef",
            "expected_tool": "get_user",
            "expected_params": {"user_id": "00u1234567890abcdef"},
            "judge_criteria": ["tool_selection", "parameter_correctness"]
        },
        {
            "prompt": "Show me John Doe's profile",
            "expected_behavior": "clarification",  # Need user ID
            "judge_criteria": ["clarification_requested"]
        },
        {
            "prompt": "Get user",
            "expected_behavior": "clarification",
            "judge_criteria": ["clarification_requested"]
        },
    ]

    tests = []
    for i, template in enumerate(templates):
        tests.append(_create_semantic_test_case(schema, template, i))

    return tests


def _generate_generic_list_semantic_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """Generate generic semantic tests for list-type tools."""
    resource_name = schema.tool_name.replace("list_", "").replace("_", " ")

    templates = [
        {
            "prompt": f"Show me all {resource_name}",
            "expected_tool": schema.tool_name,
            "expected_params": {},
            "judge_criteria": ["tool_selection"]
        },
        {
            "prompt": f"How many {resource_name} are there?",
            "expected_tool": schema.tool_name,
            "expected_params": {"fetch_all": True} if schema.has_pagination else {},
            "judge_criteria": ["tool_selection", "parameter_correctness"]
        },
    ]

    tests = []
    for i, template in enumerate(templates):
        tests.append(_create_semantic_test_case(schema, template, i))

    return tests


def _generate_generic_get_semantic_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """Generate generic semantic tests for get-type tools."""
    resource_name = schema.tool_name.replace("get_", "").replace("_", " ")

    templates = [
        {
            "prompt": f"Get {resource_name}",
            "expected_behavior": "clarification",  # Need ID
            "judge_criteria": ["clarification_requested"]
        },
    ]

    tests = []
    for i, template in enumerate(templates):
        tests.append(_create_semantic_test_case(schema, template, i))

    return tests


def _generate_default_semantic_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """Generate default semantic tests for any tool."""
    templates = [
        {
            "prompt": f"Use {schema.tool_name}",
            "expected_tool": schema.tool_name,
            "expected_params": {},
            "judge_criteria": ["tool_selection"]
        },
    ]

    tests = []
    for i, template in enumerate(templates):
        tests.append(_create_semantic_test_case(schema, template, i))

    return tests


def _create_semantic_test_case(
    schema: SchemaAnalysis,
    template: Dict[str, Any],
    index: int
) -> TestCase:
    """
    Create a semantic test case from template.

    Args:
        schema: Tool schema analysis
        template: Test template dictionary
        index: Test index for unique ID

    Returns:
        TestCase for semantic testing
    """
    prompt_hash = abs(hash(template["prompt"])) % 10000

    return TestCase(
        id=f"L4_{schema.tool_name}_semantic_{index}_{prompt_hash}",
        layer=4,
        category="semantic",
        description=f"Semantic test: {template['prompt']}",
        prompt=template["prompt"],
        expected_tool=template.get("expected_tool"),
        expected_params=template.get("expected_params", {}),
        expected_behavior=template.get("expected_behavior"),
        judge_criteria=template.get("judge_criteria", [])
    )
