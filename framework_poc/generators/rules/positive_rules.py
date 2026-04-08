"""Positive test rules for generating valid input tests."""

from typing import List, Any
from framework_poc.core.models import SchemaAnalysis, TestCase, Parameter


def generate_basic_call_test(schema: SchemaAnalysis, test_data: dict = None) -> TestCase:
    """
    Test tool with all required parameters filled in.

    For tools with no required params (e.g. list_users), sends empty params.
    For tools with required params (e.g. get_user needs user_id), injects
    real IDs from test_data so the call actually succeeds.

    Args:
        schema: Tool schema analysis
        test_data: Optional dict with provisioned resource IDs (e.g., {"user_id": "00uxyz123"})

    Returns:
        TestCase for basic tool call
    """
    # Build params from all required parameters
    params = {}
    for param in schema.get_required_parameters():
        params[param.name] = _generate_valid_value(param, test_data)

    return TestCase(
        id=f"L3_{schema.tool_name}_basic",
        layer=3,
        category="positive",
        description="Basic call with required parameters" if params else "Basic call with no parameters",
        params=params,
        expected_result="success",
        assertions=["response_present"],
        validate_against_api=True
    )


def generate_single_param_tests(schema: SchemaAnalysis, test_data: dict = None) -> List[TestCase]:
    """
    Test each parameter individually with a valid value.

    Covers both required and optional parameters. Required params always get
    real IDs injected from test_data so the call can succeed.

    Args:
        schema: Tool schema analysis
        test_data: Optional dict with provisioned resource IDs (e.g., {"user_id": "00uxyz123"})

    Returns:
        List of test cases, one per parameter
    """
    tests = []

    # Build a base of required params so every test satisfies required constraints
    required_params = {
        p.name: _generate_valid_value(p, test_data)
        for p in schema.get_required_parameters()
    }

    # Test required params (each in isolation — others absent to verify each is truly required)
    for param in schema.get_required_parameters():
        valid_value = _generate_valid_value(param, test_data)
        tests.append(TestCase(
            id=f"L3_{schema.tool_name}_{param.name}_valid",
            layer=3,
            category="positive",
            description=f"Call with valid {param.name}",
            params={param.name: valid_value},
            expected_result="success",
            assertions=["response_present"]
        ))

    # Test optional params (always include required params alongside so the call is valid)
    for param in schema.get_optional_parameters():
        valid_value = _generate_valid_value(param, test_data)
        params = dict(required_params)   # include all required params
        params[param.name] = valid_value

        tests.append(TestCase(
            id=f"L3_{schema.tool_name}_{param.name}_valid",
            layer=3,
            category="positive",
            description=f"Call with valid {param.name}",
            params=params,
            expected_result="success",
            assertions=["response_present"]
        ))

    return tests


def generate_pagination_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Generate pagination-specific tests if applicable.

    Args:
        schema: Tool schema analysis

    Returns:
        List of pagination test cases
    """
    if not schema.has_pagination:
        return []

    tests = []

    # Build required params to include in all tests
    required_params = {
        p.name: _generate_valid_value(p)
        for p in schema.get_required_parameters()
    }

    # Test with limit at minimum
    limit_param = schema.get_parameter("limit")
    if limit_param and "minimum" in limit_param.constraints:
        min_limit = limit_param.constraints["minimum"]
        params = dict(required_params)
        params["limit"] = min_limit
        tests.append(TestCase(
            id=f"L3_{schema.tool_name}_pagination_limit_min",
            layer=3,
            category="positive",
            description=f"Fetch with limit={min_limit}",
            params=params,
            expected_result="success",
            assertions=["response_present", "pagination_info_present"]
        ))

    # Test with limit at maximum
    if limit_param and "maximum" in limit_param.constraints:
        max_limit = limit_param.constraints["maximum"]
        params = dict(required_params)
        params["limit"] = max_limit
        tests.append(TestCase(
            id=f"L3_{schema.tool_name}_pagination_limit_max",
            layer=3,
            category="positive",
            description=f"Fetch with limit={max_limit}",
            params=params,
            expected_result="success",
            assertions=["response_present", "pagination_info_present"]
        ))

    # Test with fetch_all
    if schema.get_parameter("fetch_all"):
        params = dict(required_params)
        params["fetch_all"] = True
        tests.append(TestCase(
            id=f"L3_{schema.tool_name}_pagination_fetch_all",
            layer=3,
            category="positive",
            description="Fetch all pages",
            params=params,
            expected_result="success",
            assertions=["response_present", "all_pages_fetched"]
        ))

    # Test with after parameter
    if schema.get_parameter("after"):
        params = dict(required_params)
        params["after"] = "test_cursor_value"
        tests.append(TestCase(
            id=f"L3_{schema.tool_name}_pagination_after",
            layer=3,
            category="positive",
            description="Fetch with after cursor",
            params=params,
            expected_result="success",
            assertions=["response_present"]
        ))

    return tests


def generate_filtering_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Generate filtering-specific tests if applicable.

    Args:
        schema: Tool schema analysis

    Returns:
        List of filtering test cases
    """
    if not schema.has_filtering:
        return []

    tests = []

    # Build required params to include in all tests
    required_params = {
        p.name: _generate_valid_value(p)
        for p in schema.get_required_parameters()
    }

    # Test search parameter
    if schema.get_parameter("search"):
        params = dict(required_params)
        params["search"] = 'profile.email eq "user@example.com"'
        tests.append(TestCase(
            id=f"L3_{schema.tool_name}_filter_search",
            layer=3,
            category="positive",
            description="Search with valid query",
            params=params,
            expected_result="success",
            assertions=["response_present"]
        ))

    # Test filter parameter
    if schema.get_parameter("filter"):
        params = dict(required_params)
        params["filter"] = 'status eq "ACTIVE"'
        tests.append(TestCase(
            id=f"L3_{schema.tool_name}_filter_filter",
            layer=3,
            category="positive",
            description="Filter with valid expression",
            params=params,
            expected_result="success",
            assertions=["response_present"]
        ))

    # Test q parameter (simple query)
    if schema.get_parameter("q"):
        params = dict(required_params)
        params["q"] = "test"
        tests.append(TestCase(
            id=f"L3_{schema.tool_name}_filter_q",
            layer=3,
            category="positive",
            description="Query with simple search",
            params=params,
            expected_result="success",
            assertions=["response_present"]
        ))

    return tests


def generate_combination_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Generate tests with multiple parameters combined.

    Args:
        schema: Tool schema analysis

    Returns:
        List of combination test cases
    """
    tests = []

    # Pagination + filtering
    if schema.has_pagination and schema.has_filtering:
        # Build required params to include in all tests
        required_params = {
            p.name: _generate_valid_value(p)
            for p in schema.get_required_parameters()
        }
        params = dict(required_params)

        if schema.get_parameter("limit"):
            params["limit"] = 50

        if schema.get_parameter("search"):
            params["search"] = 'status eq "ACTIVE"'

        if params:
            tests.append(TestCase(
                id=f"L3_{schema.tool_name}_combo_pagination_filtering",
                layer=3,
                category="positive",
                description="Pagination with filtering",
                params=params,
                expected_result="success",
                assertions=["response_present"]
            ))

    return tests


def _generate_valid_value(param: Parameter, test_data: dict = None) -> Any:
    """
    Generate a valid value for a parameter based on its type.

    Args:
        param: Parameter to generate value for
        test_data: Optional dictionary with real test data (e.g., {"user_id": "00uxyz123"})

    Returns:
        Valid value for the parameter
    """
    # Check enum values first (if present and non-empty)
    if param.enum_values and len(param.enum_values) > 0:
        return param.enum_values[0]

    # Check for integer type (by parameter name if type not explicitly set)
    # Common integer param names: limit, count, size, offset, page
    integer_param_names = ['limit', 'count', 'size', 'offset', 'page', 'max', 'min']
    is_likely_integer = any(name in param.name.lower() for name in integer_param_names)

    if param.type == "integer" or is_likely_integer:
        # Return smart defaults for common integer parameters
        if "limit" in param.name.lower():
            return 20
        elif "count" in param.name.lower():
            return 10
        elif "size" in param.name.lower():
            return 100
        elif "offset" in param.name.lower() or "page" in param.name.lower():
            return 0
        # Check for minimum constraint
        elif "minimum" in param.constraints:
            return param.constraints["minimum"]
        # Default integer value
        return 50

    if param.type == "boolean":
        return True

    if param.type == "array":
        return []

    if param.type == "object":
        return {}

    # String type or fallback
    if param.type == "string" or not param.type:
        if "id" in param.name.lower():
            # Use real test data if available
            if test_data:
                # Try to find matching ID in test_data
                for key in [param.name, f"{param.name}_id", param.name.replace("_id", "_id")]:
                    if key in test_data:
                        return test_data[key]
            # Fallback to mock (will likely fail, but that's expected without real data)
            return "00u1234567890abcdef"  # Mock Okta ID format

        # For known enum-like params without enum values defined, provide sensible defaults
        if param.name.lower() == "type":
            return "OKTA_POLICY"  # Common Okta policy type
        elif param.name.lower() == "status":
            return "ACTIVE"
        elif param.name.lower() == "state":
            return "ACTIVE"

        return "test_value"

    return None
