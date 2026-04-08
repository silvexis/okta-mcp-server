"""Destructive operation test rules for Layer 5 testing."""

from typing import List
from framework_poc.core.models import SchemaAnalysis, TestCase


def generate_destructive_operation_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Generate Layer 5 tests for destructive operations.

    Layer 5 tests verify that destructive operations:
    - C5.1: Trigger confirmation via elicitation before executing
    - C5.2: Leave resource untouched when confirmation is declined
    - C5.3: Support fallback confirmation for non-elicitation clients

    Args:
        schema: Tool schema analysis

    Returns:
        List of Layer 5 test cases (empty if tool is not destructive)
    """
    if not schema.is_destructive:
        # Skip Layer 5 for read-only tools
        return []

    tests = []

    # C5.1: Test that confirmation is requested
    tests.append(TestCase(
        id=f"L5_{schema.tool_name}_confirmation_requested",
        layer=5,
        category="destructive",
        description=f"Destructive operation requests confirmation",
        prompt=_generate_destructive_prompt(schema.tool_name, "simple"),
        expected_behavior="confirmation_requested",
        judge_criteria=["confirmation_requested"],
        params={}  # Will be populated during test execution
    ))

    # C5.2: Test that declined confirmation leaves resource untouched
    tests.append(TestCase(
        id=f"L5_{schema.tool_name}_declined_confirmation",
        layer=5,
        category="destructive",
        description=f"Declined confirmation leaves resource intact",
        prompt=_generate_destructive_prompt(schema.tool_name, "explicit"),
        expected_behavior="resource_untouched",
        judge_criteria=["declined_confirmation_safety"],
        params={}  # Will be populated during test execution
    ))

    # C5.3: Test that accepted confirmation executes operation
    tests.append(TestCase(
        id=f"L5_{schema.tool_name}_accepted_confirmation",
        layer=5,
        category="destructive",
        description=f"Accepted confirmation executes operation",
        prompt=_generate_destructive_prompt(schema.tool_name, "with_reason"),
        expected_behavior="operation_executed",
        judge_criteria=["accepted_confirmation_execution"],
        params={}  # Will be populated during test execution
    ))

    return tests


def _generate_destructive_prompt(tool_name: str, style: str) -> str:
    """
    Generate a natural language prompt for a destructive operation.

    Args:
        tool_name: Name of the destructive tool
        style: Prompt style (simple, explicit, with_reason)

    Returns:
        Natural language prompt requesting the destructive operation
    """
    # Map tool names to resource types
    resource_map = {
        "delete": "this resource",
        "remove": "this item",
        "deactivate": "this account",
        "suspend": "this user",
        "clear": "these settings",
        "revoke": "this permission",
        "reset": "this configuration"
    }

    # Detect resource type from tool name
    resource_type = "this resource"
    for keyword, res_type in resource_map.items():
        if keyword in tool_name.lower():
            resource_type = res_type
            break

    # Extract specific resource from tool name
    if "user" in tool_name.lower():
        resource_type = "the test user"
    elif "group" in tool_name.lower():
        resource_type = "the test group"
    elif "app" in tool_name.lower() or "application" in tool_name.lower():
        resource_type = "the test application"
    elif "policy" in tool_name.lower():
        resource_type = "the test policy"

    # Generate prompts based on style
    if style == "simple":
        # Simple, direct prompt
        return f"Please {tool_name.replace('_', ' ')} for the test resource"

    elif style == "explicit":
        # Explicit destructive intent
        if "delete" in tool_name.lower():
            return f"Delete {resource_type} permanently"
        elif "deactivate" in tool_name.lower():
            return f"Deactivate {resource_type} immediately"
        elif "remove" in tool_name.lower():
            return f"Remove {resource_type} from the system"
        elif "suspend" in tool_name.lower():
            return f"Suspend {resource_type} now"
        elif "revoke" in tool_name.lower():
            return f"Revoke access for {resource_type}"
        elif "reset" in tool_name.lower():
            return f"Reset {resource_type} to defaults"
        else:
            return f"Execute {tool_name.replace('_', ' ')} on {resource_type}"

    elif style == "with_reason":
        # Destructive prompt with business reason
        if "delete" in tool_name.lower():
            return f"Delete {resource_type} because it's no longer needed for testing"
        elif "deactivate" in tool_name.lower():
            return f"Deactivate {resource_type} as the test is complete"
        elif "remove" in tool_name.lower():
            return f"Remove {resource_type} to clean up the test environment"
        elif "suspend" in tool_name.lower():
            return f"Suspend {resource_type} temporarily for security review"
        elif "revoke" in tool_name.lower():
            return f"Revoke {resource_type} permissions due to policy change"
        elif "reset" in tool_name.lower():
            return f"Reset {resource_type} settings to fix configuration issues"
        else:
            return f"Execute {tool_name.replace('_', ' ')} on {resource_type} for cleanup"

    # Default fallback
    return f"Please {tool_name.replace('_', ' ')}"


def should_run_layer_5(schema: SchemaAnalysis) -> bool:
    """
    Determine if Layer 5 tests should run for this tool.

    Layer 5 is only applicable to destructive tools (delete, deactivate, remove, etc.)
    Read-only tools (list, get, search) automatically skip Layer 5.

    Args:
        schema: Tool schema analysis

    Returns:
        True if Layer 5 should run, False otherwise
    """
    return schema.is_destructive
