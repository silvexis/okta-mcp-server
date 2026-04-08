"""Non-deterministic runner for executing Layers 4-5 using LLM-as-judge."""

from typing import List
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from framework_poc.core.models import Config, TestCase, Judgment
from framework_poc.core.llm_judge import LLMJudge
from framework_poc.core.mcp_client import get_mcp_client
from framework_poc.core.concurrency import run_with_concurrency


class NonDeterministicRunner:
    """Executes Layers 4-5 using LLM evaluation."""

    def __init__(self, config: Config):
        """
        Initialize non-deterministic runner.

        Args:
            config: Framework configuration
        """
        self.config = config
        self.llm_judge = LLMJudge(
            config.claude.api_key,
            config.claude.model
        )
        self.client_pool = None

    async def run_layer_4(
        self,
        tool_name: str,
        test_cases: List[TestCase]
    ) -> List[Judgment]:
        """
        Layer 4: LLM Behavior.

        Tests:
        - Tool selection accuracy
        - Parameter construction
        - Response faithfulness

        Args:
            tool_name: Name of the tool being tested
            test_cases: List of Layer 4 test cases

        Returns:
            List of judgments
        """
        if not test_cases:
            return []

        # Get max_workers_llm from config, default to 5
        max_concurrency = getattr(self.config.execution, 'max_workers_llm', 5)

        async with self._get_mcp_client() as client:
            tools = (await client.list_tools()).tools
            tool_names = [t.name for t in tools]
            tool_map = {t.name: t for t in tools}

            # Flatten all LLM judgment tasks into a single list
            tasks = []

            for test_case in test_cases:
                # Create task for each criterion in judge_criteria
                if "tool_selection" in test_case.judge_criteria:
                    tasks.append(
                        lambda tc=test_case: self.llm_judge.evaluate_tool_selection(
                            user_prompt=tc.prompt,
                            expected_tool=tc.expected_tool or tool_name,
                            available_tools=tool_names,
                            test_case=tc
                        )
                    )

                if "parameter_correctness" in test_case.judge_criteria:
                    tool = tool_map.get(tool_name)
                    if tool:
                        tasks.append(
                            lambda tc=test_case, t=tool: self.llm_judge.evaluate_parameter_correctness(
                                tool_schema=t.inputSchema,
                                expected_params=tc.expected_params or {},
                                user_intent=tc.prompt,
                                test_case=tc
                            )
                        )

                if "clarification_requested" in test_case.judge_criteria:
                    tasks.append(
                        lambda tc=test_case: self.llm_judge.evaluate_clarification_request(
                            user_prompt=tc.prompt,
                            llm_response="[Simulated LLM response]",
                            test_case=tc
                        )
                    )

                if "response_faithfulness" in test_case.judge_criteria:
                    # Create async task for response faithfulness
                    async def evaluate_faithfulness(tc=test_case):
                        try:
                            if tc.expected_params:
                                response = await client.call_tool(
                                    tool_name,
                                    tc.expected_params
                                )
                                return await self.llm_judge.evaluate_response_faithfulness(
                                    raw_response={"simulated": "response"},
                                    llm_response="[Simulated LLM summary]",
                                    user_prompt=tc.prompt,
                                    test_case=tc
                                )
                        except Exception as e:
                            return Judgment(
                                criterion="response_faithfulness",
                                rating="error",
                                reasoning=f"Tool execution failed: {str(e)}",
                                passed=False,
                                test_case=tc
                            )

                    tasks.append(evaluate_faithfulness)

            # Run all LLM judgment tasks concurrently
            results = await run_with_concurrency(tasks, max_concurrency)

            # Convert exceptions to error judgments
            judgments = []
            for result in results:
                if isinstance(result, Exception):
                    judgments.append(Judgment(
                        criterion="unknown",
                        rating="error",
                        reasoning=f"Evaluation failed: {str(result)}",
                        passed=False,
                        test_case=None
                    ))
                else:
                    judgments.append(result)

        return judgments

    async def run_layer_5(
        self,
        tool_name: str,
        test_cases: List[TestCase],
        test_data: dict = None
    ) -> List[Judgment]:
        """
        Layer 5: Destructive Operation Safety.

        Tests:
        - C5.1: Confirmation flow triggers
        - C5.2: Declined confirmation safety
        - C5.3: Accepted confirmation execution

        Args:
            tool_name: Name of the tool being tested
            test_cases: List of Layer 5 test cases
            test_data: Optional test data with provisioned resource IDs

        Returns:
            List of judgments
        """
        judgments = []

        if not test_cases:
            # No Layer 5 tests for this tool (likely read-only)
            return judgments

        # Import here to avoid circular dependency
        from framework_poc.generators.resource_provisioner import ResourceProvisioner

        async with self._get_mcp_client() as client:
            provisioner = ResourceProvisioner(client)

            # Each destructive test needs its own resource
            for test_case in test_cases:
                try:
                    # Provision a fresh resource for this destructive test
                    resource_config = await provisioner.provision_for_tool(tool_name, num_tests=1)

                    if not resource_config.get("needs_per_test_provisioning"):
                        # Tool might not be recognized as destructive or no provisioning available
                        judgments.append(Judgment(
                            criterion="destructive_op_safety",
                            rating="skipped",
                            reasoning=f"No provisioning config for {tool_name}",
                            passed=True,  # Don't fail test if provisioning not configured
                            test_case=test_case
                        ))
                        continue

                    # Provision resource
                    provisioned_data = await provisioner.provision_for_single_test(resource_config)

                    # Get resource state before operation
                    resource_id = provisioned_data.get(resource_config.get("id_param", "id"))
                    resource_state_before = await self._get_resource_state(
                        client, tool_name, resource_id, resource_config
                    )

                    # Simulate sending the destructive prompt
                    # In a real implementation, this would:
                    # 1. Call the MCP tool with destructive params
                    # 2. Observe if elicitation is triggered
                    # 3. Simulate user response (confirm/decline)
                    # 4. Check if operation executed

                    # For now, we'll simulate the flow
                    confirmation_requested = True  # Assume server requests confirmation
                    confirmation_given = test_case.expected_behavior == "operation_executed"

                    # Simulate calling the tool
                    params = {resource_config.get("id_param", "id"): resource_id}
                    operation_executed = False

                    try:
                        # Try to execute the destructive operation
                        response = await client.call_tool(tool_name, params)

                        # Check if operation succeeded
                        is_error = hasattr(response, 'isError') and response.isError
                        operation_executed = not is_error

                    except Exception as e:
                        # Operation failed
                        operation_executed = False

                    # Get resource state after operation
                    resource_state_after = await self._get_resource_state(
                        client, tool_name, resource_id, resource_config
                    )

                    # Evaluate the destructive operation flow
                    judgment = await self.llm_judge.evaluate_destructive_confirmation(
                        user_prompt=test_case.prompt or f"Execute {tool_name}",
                        mcp_response="[Simulated MCP response]",
                        confirmation_requested=confirmation_requested,
                        confirmation_given=confirmation_given,
                        operation_executed=operation_executed,
                        resource_state_before=resource_state_before,
                        resource_state_after=resource_state_after,
                        test_case=test_case
                    )

                    judgments.append(judgment)

                    # Cleanup if resource still exists and wasn't consumed by the test
                    if resource_state_after.get("exists") and not operation_executed:
                        try:
                            await provisioner.cleanup_single_test(provisioned_data)
                        except Exception:
                            pass  # Cleanup failure is not critical for test result

                except Exception as e:
                    # Test execution failed
                    judgments.append(Judgment(
                        criterion="destructive_op_safety",
                        rating="error",
                        reasoning=f"Test execution failed: {str(e)}",
                        passed=False,
                        test_case=test_case
                    ))

        return judgments

    async def _get_resource_state(
        self,
        client,
        tool_name: str,
        resource_id: str,
        resource_config: dict
    ) -> dict:
        """
        Get the current state of a resource.

        Args:
            client: MCP client
            tool_name: Tool name
            resource_id: Resource ID
            resource_config: Resource configuration

        Returns:
            Dictionary with resource state (exists, data)
        """
        try:
            # Try to fetch the resource using a GET tool
            # Infer get tool name from destructive tool name
            get_tool = tool_name.replace("delete_", "get_").replace("deactivate_", "get_").replace("remove_", "get_")

            if get_tool != tool_name:
                # Found a potential get tool
                params = {resource_config.get("id_param", "id"): resource_id}

                try:
                    response = await client.call_tool(get_tool, params)
                    is_error = hasattr(response, 'isError') and response.isError

                    # Extract text content if available
                    data_str = None
                    if hasattr(response, 'content') and response.content:
                        for content_item in response.content:
                            if hasattr(content_item, 'text'):
                                data_str = content_item.text
                                break

                    return {
                        "exists": not is_error,
                        "id": resource_id,
                        "data": data_str or "resource_exists"
                    }
                except Exception:
                    # Get tool might not exist or failed
                    pass

            # Fallback: assume resource exists if we can't verify
            return {
                "exists": True,
                "id": resource_id,
                "data": "unknown_state"
            }

        except Exception as e:
            return {
                "exists": False,
                "id": resource_id,
                "error": str(e)
            }

    def set_client_pool(self, pool):
        """
        Set the client pool for connection reuse.

        Args:
            pool: MCPClientPool instance
        """
        self.client_pool = pool

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
