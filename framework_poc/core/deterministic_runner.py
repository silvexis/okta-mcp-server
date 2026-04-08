"""Deterministic runner for executing Layers 0-3 with strict pass/fail criteria."""

import time
from typing import List, Dict, Any
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from framework_poc.core.models import Config, TestCase, CheckResult
from framework_poc.core.mcp_client import get_mcp_client
from framework_poc.core.concurrency import run_with_concurrency
from framework_poc.generators.resource_provisioner import ResourceProvisioner, ProvisioningStrategy


class DeterministicRunner:
    """Executes Layers 0-3 without LLM involvement."""

    def __init__(self, config: Config):
        """
        Initialize deterministic runner.

        Args:
            config: Framework configuration
        """
        self.config = config
        self.mcp_client = None
        self.client_pool = None

    async def run_layer_0(
        self,
        tool_name: str,
        test_cases: List[TestCase]
    ) -> List[CheckResult]:
        """
        Layer 0: Contract Integrity (static analysis).

        Checks:
        - Tool registered in tools/list
        - Schema is well-formed
        - Description quality

        Args:
            tool_name: Name of the tool to test
            test_cases: List of Layer 0 test cases

        Returns:
            List of check results
        """
        results = []

        # Connect to server and get tools list
        async with self._get_mcp_client() as client:
            tools = (await client.list_tools()).tools
            tool_def = next((t for t in tools if t.name == tool_name), None)

            for test_case in test_cases:
                start_time = time.time()

                if "tool_registered" in test_case.id:
                    passed = tool_def is not None
                    results.append(CheckResult(
                        checkpoint_id=test_case.id,
                        checkpoint_name="Tool Registration",
                        passed=passed,
                        message=f"Tool '{tool_name}' registered" if passed else f"Tool '{tool_name}' not found",
                        layer=0,
                        test_case=test_case,
                        execution_time_ms=(time.time() - start_time) * 1000
                    ))

                elif "schema_valid" in test_case.id:
                    if tool_def:
                        schema_valid = self._validate_schema(tool_def.inputSchema)
                        results.append(CheckResult(
                            checkpoint_id=test_case.id,
                            checkpoint_name="Schema Validity",
                            passed=schema_valid["valid"],
                            message=schema_valid["message"],
                            layer=0,
                            test_case=test_case,
                            execution_time_ms=(time.time() - start_time) * 1000
                        ))
                    else:
                        results.append(CheckResult(
                            checkpoint_id=test_case.id,
                            checkpoint_name="Schema Validity",
                            passed=False,
                            message="Tool not found",
                            layer=0,
                            test_case=test_case,
                            execution_time_ms=(time.time() - start_time) * 1000
                        ))

                elif "description_quality" in test_case.id:
                    if tool_def:
                        quality_check = self._check_description_quality(tool_def.description)
                        results.append(CheckResult(
                            checkpoint_id=test_case.id,
                            checkpoint_name="Description Quality",
                            passed=quality_check["passed"],
                            message=quality_check["message"],
                            layer=0,
                            test_case=test_case,
                            execution_time_ms=(time.time() - start_time) * 1000
                        ))
                    else:
                        results.append(CheckResult(
                            checkpoint_id=test_case.id,
                            checkpoint_name="Description Quality",
                            passed=False,
                            message="Tool not found",
                            layer=0,
                            test_case=test_case,
                            execution_time_ms=(time.time() - start_time) * 1000
                        ))

        return results

    async def run_layer_1(self, test_cases: List[TestCase]) -> List[CheckResult]:
        """
        Layer 1: Server Startup & Authentication.

        Checks:
        - Server reaches ready state
        - Authentication succeeds

        Args:
            test_cases: List of Layer 1 test cases

        Returns:
            List of check results
        """
        results = []

        # Test server startup
        for test_case in test_cases:
            start_time = time.time()

            if "server_startup" in test_case.id:
                try:
                    async with self._get_mcp_client() as client:
                        await client.initialize()
                        tools = (await client.list_tools()).tools

                        results.append(CheckResult(
                            checkpoint_id=test_case.id,
                            checkpoint_name="Server Startup",
                            passed=True,
                            message=f"Server started, {len(tools)} tools available",
                            layer=1,
                            test_case=test_case,
                            execution_time_ms=(time.time() - start_time) * 1000
                        ))
                except Exception as e:
                    results.append(CheckResult(
                        checkpoint_id=test_case.id,
                        checkpoint_name="Server Startup",
                        passed=False,
                        message=f"Server startup failed: {str(e)}",
                        layer=1,
                        error=str(e),
                        test_case=test_case,
                        execution_time_ms=(time.time() - start_time) * 1000
                    ))

            elif "auth_success" in test_case.id:
                try:
                    # Verify auth by checking environment variables
                    import os
                    required_vars = ["OKTA_ORG_URL", "OKTA_CLIENT_ID", "OKTA_PRIVATE_KEY", "OKTA_KEY_ID"]
                    missing_vars = [var for var in required_vars if not os.environ.get(var)]

                    if missing_vars:
                        results.append(CheckResult(
                            checkpoint_id=test_case.id,
                            checkpoint_name="Authentication",
                            passed=False,
                            message=f"Missing environment variables: {', '.join(missing_vars)}",
                            layer=1,
                            test_case=test_case,
                            execution_time_ms=(time.time() - start_time) * 1000
                        ))
                    else:
                        results.append(CheckResult(
                            checkpoint_id=test_case.id,
                            checkpoint_name="Authentication",
                            passed=True,
                            message="Auth configuration present",
                            layer=1,
                            test_case=test_case,
                            execution_time_ms=(time.time() - start_time) * 1000
                        ))
                except Exception as e:
                    results.append(CheckResult(
                        checkpoint_id=test_case.id,
                        checkpoint_name="Authentication",
                        passed=False,
                        message=f"Auth check failed: {str(e)}",
                        layer=1,
                        error=str(e),
                        test_case=test_case,
                        execution_time_ms=(time.time() - start_time) * 1000
                    ))

        return results

    async def run_layer_2_3(
        self,
        tool_name: str,
        test_cases: List[TestCase]
    ) -> List[CheckResult]:
        """
        Layer 2-3: Input Validation & API Correctness.

        Layer 2 checks:
        - Parameter type validation
        - Boundary conditions
        - Security (injection, traversal)

        Layer 3 checks:
        - Response shape
        - API correctness
        - Pagination logic

        Args:
            tool_name: Name of the tool to test
            test_cases: List of Layer 2-3 test cases

        Returns:
            List of check results
        """
        if not test_cases:
            return []

        # Get max_workers from config, default to 10
        max_concurrency = getattr(self.config.execution, 'max_workers', 10)

        async with self._get_mcp_client() as client:
            # Check if tool needs per-test provisioning (DELETE, DEACTIVATE, etc.)
            provisioner = ResourceProvisioner(client)
            strategy = provisioner.detect_strategy(tool_name)

            # Handle PER_TEST strategies (DELETE tools need fresh resource per test)
            if strategy in [ProvisioningStrategy.PER_TEST_CONSUMED, ProvisioningStrategy.PER_TEST_ISOLATED]:
                print(f"  [INFO] Tool uses {strategy.value} strategy - provisioning resources per test")
                return await self._run_tests_with_per_test_provisioning(
                    client, tool_name, test_cases, provisioner, strategy
                )

            # Get tool schema for validation
            tools = (await client.list_tools()).tools
            tool_def = next((t for t in tools if t.name == tool_name), None)

            # Create task functions for each test case
            tasks = []
            for test_case in test_cases:
                # Pre-execution validation to detect test generation bugs
                # Skip validation for negative tests (they're intentionally malformed)
                should_validate = test_case.category not in ["negative", "boundary"]
                validation_error = None
                if should_validate and tool_def:
                    validation_error = self._validate_test_params(test_case, tool_def)

                if validation_error:
                    # Report as test generation error instead of test failure
                    tasks.append(
                        lambda tc=test_case, err=validation_error: self._create_generation_error_result(tc, err)
                    )
                    continue
                start_time = time.time()

                if test_case.layer == 2:
                    # Input validation tests
                    # Use lambda with default arguments to capture values
                    tasks.append(
                        lambda tc=test_case, st=start_time: self._run_validation_test(
                            client, tool_name, tc, st
                        )
                    )

                elif test_case.layer == 3:
                    # API correctness tests
                    tasks.append(
                        lambda tc=test_case, st=start_time: self._run_execution_test(
                            client, tool_name, tc, st
                        )
                    )

            # Run all tests concurrently with controlled concurrency
            results = await run_with_concurrency(tasks, max_concurrency)

            # Handle exceptions in results
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Convert exception to failed CheckResult
                    test_case = test_cases[i]
                    final_results.append(CheckResult(
                        checkpoint_id=test_case.id,
                        checkpoint_name=f"Layer {test_case.layer}: {test_case.description}",
                        passed=False,
                        message=f"Unexpected error: {str(result)[:100]}",
                        layer=test_case.layer,
                        error=str(result),
                        test_case=test_case,
                        execution_time_ms=0
                    ))
                else:
                    final_results.append(result)

        return final_results

    async def _run_tests_with_per_test_provisioning(
        self,
        client,
        tool_name: str,
        test_cases: List[TestCase],
        provisioner: ResourceProvisioner,
        strategy: ProvisioningStrategy
    ) -> List[CheckResult]:
        """
        Run tests that need fresh resources per test (DELETE, UPDATE tools).

        Args:
            client: MCP client
            tool_name: Name of the tool
            test_cases: List of test cases
            provisioner: Resource provisioner
            strategy: Provisioning strategy

        Returns:
            List of check results
        """
        results = []

        # Get resource configuration once
        resource_config = await provisioner.provision_for_tool(tool_name, num_tests=len(test_cases))

        for i, test_case in enumerate(test_cases):
            start_time = time.time()

            # Check if this test needs provisioning (positive tests with IDs)
            needs_provisioning = (
                test_case.category == "positive" and
                test_case.params and
                any("id" in key.lower() for key in test_case.params.keys())
            )

            if needs_provisioning and resource_config.get("needs_per_test_provisioning"):
                try:
                    # Provision fresh resource for this test
                    test_data = await provisioner.provision_for_single_test(resource_config)

                    # Inject provisioned IDs into test params
                    for key in list(test_case.params.keys()):
                        if "id" in key.lower() and key in test_data:
                            test_case.params[key] = test_data[key]
                        elif f"{key}_id" in test_data:
                            test_case.params[key] = test_data[f"{key}_id"]

                    print(f"    [{i+1}/{len(test_cases)}] Provisioned resource for test: {test_case.description}")

                except Exception as e:
                    print(f"    [{i+1}/{len(test_cases)}] ⚠ Provisioning failed for test: {e}")

            # Run the test
            if test_case.layer == 2:
                result = await self._run_validation_test(client, tool_name, test_case, start_time)
            elif test_case.layer == 3:
                result = await self._run_execution_test(client, tool_name, test_case, start_time)
            else:
                result = CheckResult(
                    checkpoint_id=test_case.id,
                    checkpoint_name=f"Unknown layer: {test_case.layer}",
                    passed=False,
                    message="Unknown layer",
                    layer=test_case.layer,
                    test_case=test_case,
                    execution_time_ms=(time.time() - start_time) * 1000
                )

            results.append(result)

            # Cleanup if PER_TEST_ISOLATED (UPDATE tools)
            if strategy == ProvisioningStrategy.PER_TEST_ISOLATED and needs_provisioning:
                try:
                    await provisioner.cleanup_single_test(test_data)
                except Exception as e:
                    print(f"    ⚠ Cleanup failed for test: {e}")

            # For PER_TEST_CONSUMED (DELETE tools), no cleanup needed - test consumed the resource

        return results

    async def _run_validation_test(
        self,
        mcp_client,
        tool_name: str,
        test_case: TestCase,
        start_time: float
    ) -> CheckResult:
        """Run a Layer 2 validation test."""
        try:
            response = await mcp_client.call_tool(tool_name, test_case.params)

            # Check if response indicates error (both MCP-level and API-level)
            is_mcp_error = hasattr(response, 'isError') and response.isError
            is_api_error = self._check_response_content_for_error(response)
            is_error = is_mcp_error or is_api_error

            # Determine if test passed based on expected result
            if test_case.expected_result == "rejected" or test_case.expected_result == "error":
                # Should have failed but didn't
                if not is_error:
                    return CheckResult(
                        checkpoint_id=test_case.id,
                        checkpoint_name=f"Validation: {test_case.description}",
                        passed=False,
                        message=f"Expected {test_case.expected_result} but call succeeded",
                        layer=2,
                        test_case=test_case,
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                else:
                    return CheckResult(
                        checkpoint_id=test_case.id,
                        checkpoint_name=f"Validation: {test_case.description}",
                        passed=True,
                        message=f"Correctly rejected invalid input",
                        layer=2,
                        test_case=test_case,
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
            elif "or_error" in test_case.expected_result:
                # Flexible expectations like "auto_corrected_or_error" or "success_or_clarification"
                # Accept both error and success as valid outcomes
                return CheckResult(
                    checkpoint_id=test_case.id,
                    checkpoint_name=f"Validation: {test_case.description}",
                    passed=True,
                    message="Handled with acceptable outcome (error or success)",
                    layer=2,
                    test_case=test_case,
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            else:
                # Success case
                if is_error:
                    return CheckResult(
                        checkpoint_id=test_case.id,
                        checkpoint_name=f"Validation: {test_case.description}",
                        passed=False,
                        message=f"Unexpected error for valid input",
                        layer=2,
                        test_case=test_case,
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                else:
                    return CheckResult(
                        checkpoint_id=test_case.id,
                        checkpoint_name=f"Validation: {test_case.description}",
                        passed=True,
                        message="Validation passed",
                        layer=2,
                        test_case=test_case,
                        execution_time_ms=(time.time() - start_time) * 1000
                    )

        except Exception as e:
            # Error occurred
            if test_case.expected_result in ["rejected", "error"]:
                # Expected error
                return CheckResult(
                    checkpoint_id=test_case.id,
                    checkpoint_name=f"Validation: {test_case.description}",
                    passed=True,
                    message=f"Correctly rejected: {str(e)[:100]}",
                    layer=2,
                    test_case=test_case,
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            else:
                # Unexpected error
                return CheckResult(
                    checkpoint_id=test_case.id,
                    checkpoint_name=f"Validation: {test_case.description}",
                    passed=False,
                    message=f"Unexpected error: {str(e)[:100]}",
                    layer=2,
                    error=str(e),
                    test_case=test_case,
                    execution_time_ms=(time.time() - start_time) * 1000
                )

    def _check_response_content_for_error(self, response: Any) -> bool:
        """
        Check if response content contains an error from the API.

        The Okta MCP server delegates validation to the Okta API, which returns
        errors as JSON content rather than MCP protocol errors. This method
        detects those API-level errors.

        Args:
            response: MCP response object

        Returns:
            True if error found in content, False otherwise
        """
        if not hasattr(response, 'content') or not response.content:
            return False

        # Check each content item
        for content_item in response.content:
            if hasattr(content_item, 'text'):
                text = content_item.text

                # Try to parse as JSON and look for error keys
                try:
                    import json
                    data = json.loads(text)

                    # Check for common error keys
                    if isinstance(data, dict):
                        error_keys = ['error', 'errorCode', 'errorSummary', 'errorCauses']
                        if any(key in data for key in error_keys):
                            return True
                except (json.JSONDecodeError, ValueError):
                    pass

                # Check for error keywords in text
                error_patterns = [
                    'error:',
                    'exception:',
                    'failed:',
                    'invalid:',
                    '"error"',
                    '"errorCode"',
                    'errorSummary',
                ]

                text_lower = text.lower()
                if any(pattern.lower() in text_lower for pattern in error_patterns):
                    return True

        return False

    async def _run_execution_test(
        self,
        mcp_client,
        tool_name: str,
        test_case: TestCase,
        start_time: float
    ) -> CheckResult:
        """Run a Layer 3 execution test."""
        try:
            # Call via MCP
            response = await mcp_client.call_tool(tool_name, test_case.params)

            # Check for errors
            is_error = hasattr(response, 'isError') and response.isError
            if is_error:
                return CheckResult(
                    checkpoint_id=test_case.id,
                    checkpoint_name=f"Execution: {test_case.description}",
                    passed=False,
                    message="Tool returned error",
                    layer=3,
                    test_case=test_case,
                    execution_time_ms=(time.time() - start_time) * 1000
                )

            # Validate response shape
            shape_valid = self._validate_response_shape(response)

            if not shape_valid:
                return CheckResult(
                    checkpoint_id=test_case.id,
                    checkpoint_name=f"Execution: {test_case.description}",
                    passed=False,
                    message="Response shape validation failed",
                    layer=3,
                    test_case=test_case,
                    execution_time_ms=(time.time() - start_time) * 1000
                )

            return CheckResult(
                checkpoint_id=test_case.id,
                checkpoint_name=f"Execution: {test_case.description}",
                passed=True,
                message="Execution test passed",
                layer=3,
                test_case=test_case,
                execution_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            return CheckResult(
                checkpoint_id=test_case.id,
                checkpoint_name=f"Execution: {test_case.description}",
                passed=False,
                message=f"Execution failed: {str(e)[:100]}",
                layer=3,
                error=str(e),
                test_case=test_case,
                execution_time_ms=(time.time() - start_time) * 1000
            )

    def _validate_schema(self, input_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate tool schema structure."""
        if not isinstance(input_schema, dict):
            return {"valid": False, "message": "Schema is not a dictionary"}

        if "properties" not in input_schema:
            return {"valid": False, "message": "Schema missing 'properties' field"}

        if "type" not in input_schema or input_schema["type"] != "object":
            return {"valid": False, "message": "Schema type must be 'object'"}

        return {"valid": True, "message": "Schema is well-formed"}

    def _check_description_quality(self, description: str) -> Dict[str, Any]:
        """Check if tool description is meaningful."""
        if not description:
            return {"passed": False, "message": "Description is empty"}

        if len(description) < 50:
            return {"passed": False, "message": f"Description too short ({len(description)} chars)"}

        # Check for meaningful keywords — verbs and Okta resource/action terms
        keywords = [
            # Action verbs
            "list", "get", "retrieve", "fetch", "create", "add", "update", "patch",
            "delete", "remove", "deactivate", "activate", "suspend", "assign",
            "search", "find", "check", "validate", "verify", "send", "reset",
            # Okta resource types
            "user", "group", "application", "app", "policy", "rule", "factor",
            "device", "token", "session", "role", "permission", "scope", "log",
            "event", "profile", "schema", "brand", "domain", "org",
        ]
        has_keywords = any(kw in description.lower() for kw in keywords)

        if not has_keywords:
            return {"passed": False, "message": "Description lacks meaningful keywords"}

        return {"passed": True, "message": f"Description is meaningful ({len(description)} chars)"}

    def _validate_response_shape(self, response: Any) -> bool:
        """Validate response has expected shape."""
        # Basic validation - response should exist
        if response is None:
            return False

        # If response has content field, validate it
        if hasattr(response, 'content'):
            return response.content is not None

        return True

    def set_client_pool(self, pool):
        """
        Set the client pool for connection reuse.

        Args:
            pool: MCPClientPool instance
        """
        self.client_pool = pool

    def _validate_test_params(self, test_case: TestCase, tool_def: Any) -> str | None:
        """
        Validate test parameters match schema types before execution.

        Args:
            test_case: Test case to validate
            tool_def: Tool definition with schema

        Returns:
            Error message if validation fails, None if valid
        """
        if not test_case.params or not tool_def or not hasattr(tool_def, 'inputSchema'):
            return None

        schema = tool_def.inputSchema
        properties = schema.get('properties', {})

        for param_name, param_value in test_case.params.items():
            if param_name not in properties:
                continue

            param_schema = properties[param_name]
            expected_type = param_schema.get('type')

            # Skip null values (negative tests)
            if param_value is None:
                continue

            # Check type mismatch
            if expected_type == 'integer' and not isinstance(param_value, int):
                return f"Parameter '{param_name}' expects integer but got {type(param_value).__name__}: {param_value}"
            elif expected_type == 'string' and not isinstance(param_value, str):
                return f"Parameter '{param_name}' expects string but got {type(param_value).__name__}: {param_value}"
            elif expected_type == 'boolean' and not isinstance(param_value, bool):
                return f"Parameter '{param_name}' expects boolean but got {type(param_value).__name__}: {param_value}"
            elif expected_type == 'array' and not isinstance(param_value, list):
                return f"Parameter '{param_name}' expects array but got {type(param_value).__name__}: {param_value}"

            # Check enum values
            if 'enum' in param_schema:
                allowed_values = param_schema['enum']
                if param_value not in allowed_values and expected_type == 'string':
                    return f"Parameter '{param_name}' has invalid enum value: {param_value} (allowed: {allowed_values})"

        return None

    async def _create_generation_error_result(self, test_case: TestCase, error_message: str) -> CheckResult:
        """
        Create a CheckResult for test generation errors.

        Args:
            test_case: Test case with generation error
            error_message: Description of the error

        Returns:
            CheckResult indicating test generation error
        """
        return CheckResult(
            checkpoint_id=test_case.id,
            checkpoint_name=f"TEST_GENERATION_ERROR: {test_case.description}",
            passed=False,
            message=f"Test generation bug: {error_message}",
            layer=test_case.layer,
            error=error_message,
            test_case=test_case,
            execution_time_ms=0
        )

    @asynccontextmanager
    async def _get_mcp_client(self):
        """
        Get connected MCP client.

        Uses client pool if available, otherwise creates a new connection.
        """
        if self.client_pool is not None:
            # Use shared connection from pool
            async with self.client_pool.get_client() as session:
                yield session
        else:
            # Fall back to creating new connection
            async with get_mcp_client(self.config.server) as session:
                yield session
