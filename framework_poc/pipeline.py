"""Main pipeline orchestrator for test generation and execution."""

from pathlib import Path
from typing import Optional, List

from framework_poc.core.models import Config, Report
from framework_poc.core.test_case_manager import TestCaseManager
from framework_poc.generators.test_generator import TestGenerator
from framework_poc.generators.resource_provisioner import ResourceProvisioner
from framework_poc.core.deterministic_runner import DeterministicRunner
from framework_poc.core.nondeterministic_runner import NonDeterministicRunner
from framework_poc.core.report_generator import ReportGenerator
from framework_poc.core.client_pool import MCPClientPool


class TestPipeline:
    """Main orchestrator for test generation and execution."""

    def __init__(self, config: Config):
        """
        Initialize test pipeline.

        Args:
            config: Framework configuration
        """
        self.config = config
        self.test_case_manager = TestCaseManager(config)
        self.test_generator = TestGenerator()
        self.deterministic_runner = DeterministicRunner(config)
        self.nondeterministic_runner = NonDeterministicRunner(config)
        self.report_generator = ReportGenerator()

    async def run_full_pipeline(
        self,
        tool_name: str,
        layers: Optional[List[int]] = None
    ) -> Report:
        """
        Run complete test pipeline for a tool.

        Steps:
        1. Fetch tool definition from server
        2. Generate tests (in-memory, not stored)
        3. Run deterministic layers (0-3)
        4. Run non-deterministic layers (4-5)
        5. Generate report
        6. Return results

        Args:
            tool_name: Name of the tool to test
            layers: Optional list of layers to run (default: all)

        Returns:
            Report object
        """
        if layers is None:
            layers = self.config.execution.layers

        print(f"{'='*60}")
        print(f"MCP E2E Test Pipeline - {tool_name}")
        print(f"{'='*60}\n")

        # Step 1: Get tool definition
        print("[1/6] Fetching tool definition...")
        try:
            tool_def = await self.test_case_manager.get_tool_definition(tool_name)
            print(f"✓ Tool fetched: {tool_def.description[:60]}...\n")
        except Exception as e:
            print(f"✗ Failed to fetch tool: {e}\n")
            raise

        # Step 1.5: Provision test resources
        print("[1.5/6] Provisioning test resources...")
        provisioner = None
        test_data = None

        try:
            # Get a client for provisioning
            async with self.test_case_manager._get_mcp_client() as client:
                provisioner = ResourceProvisioner(client)

                # Provision resources based on tool type
                test_data = await provisioner.provision_for_tool(tool_name)

                strategy = test_data.get("strategy")
                if strategy and strategy.value != "none":
                    if test_data.get("user_id"):
                        print(f"✓ Provisioned user: {test_data['user_id']}")
                    elif test_data.get("group_id"):
                        print(f"✓ Provisioned group: {test_data['group_id']}")
                    else:
                        print(f"✓ Resources provisioned (strategy: {strategy.value})")
                else:
                    print(f"✓ No provisioning needed (strategy: {strategy.value if strategy else 'none'})")
        except Exception as e:
            print(f"⚠ Provisioning failed (will use mock data): {e}")
            test_data = None

        print()

        # Step 2: Generate tests
        print("[2/6] Generating tests from schema...")
        tests_by_layer = await self.test_generator.generate_tests_for_tool(tool_def, test_data)

        # Filter by requested layers
        tests_by_layer = {
            layer: tests for layer, tests in tests_by_layer.items()
            if layer in layers
        }

        total_tests = sum(len(tests) for tests in tests_by_layer.values())
        print(f"✓ Generated {total_tests} tests across {len(tests_by_layer)} layers")
        for layer, tests in sorted(tests_by_layer.items()):
            print(f"  Layer {layer}: {len(tests)} tests")
        print()

        all_results = []
        all_judgments = []

        # Check if client pooling is enabled
        use_client_pool = getattr(self.config.execution, 'use_client_pool', True)

        # Create client pool if enabled
        if use_client_pool:
            print("[INFO] Using client pool for connection reuse\n")
            pool_cm = MCPClientPool(self.config.server)
        else:
            print("[INFO] Client pooling disabled, creating new connections per layer\n")
            pool_cm = None

        # Use client pool context manager if enabled
        async def run_tests():
            """Run all tests (with or without client pooling)."""
            nonlocal all_results, all_judgments

            # Set client pool on runners if enabled
            if pool_cm:
                self.deterministic_runner.set_client_pool(pool_cm)
                self.nondeterministic_runner.set_client_pool(pool_cm)

            # Step 3: Run Layer 0-1
            if 0 in layers or 1 in layers:
                print("[3/6] Running Layer 0-1 (Contract & Startup)...")

                if 0 in layers:
                    layer_0_results = await self.deterministic_runner.run_layer_0(
                        tool_name,
                        tests_by_layer.get(0, [])
                    )
                    all_results.extend(layer_0_results)
                    print(f"✓ Layer 0: {sum(1 for r in layer_0_results if r.passed)}/{len(layer_0_results)} passed")

                if 1 in layers:
                    layer_1_results = await self.deterministic_runner.run_layer_1(
                        tests_by_layer.get(1, [])
                    )
                    all_results.extend(layer_1_results)
                    print(f"✓ Layer 1: {sum(1 for r in layer_1_results if r.passed)}/{len(layer_1_results)} passed")

                print()

                # Check for blocking failures
                if self.config.execution.fail_fast_deterministic:
                    early_failures = [r for r in all_results if not r.passed]
                    if early_failures:
                        print("❌ Blocking failure in Layer 0-1. Stopping execution.\n")
                        report = self.report_generator.generate(all_results, [], tool_name)
                        self._save_report(report)
                        return report
            else:
                print("[3/6] Skipping Layer 0-1 (not requested)\n")

            # Step 4: Run Layer 2-3
            if 2 in layers or 3 in layers:
                print("[4/6] Running Layer 2-3 (Validation & Execution)...")
                layer_2_3_tests = tests_by_layer.get(2, []) + tests_by_layer.get(3, [])

                if layer_2_3_tests:
                    layer_2_3_results = await self.deterministic_runner.run_layer_2_3(
                        tool_name,
                        layer_2_3_tests
                    )
                    all_results.extend(layer_2_3_results)

                    layer_2_count = len([r for r in layer_2_3_results if r.layer == 2])
                    layer_3_count = len([r for r in layer_2_3_results if r.layer == 3])
                    layer_2_passed = sum(1 for r in layer_2_3_results if r.layer == 2 and r.passed)
                    layer_3_passed = sum(1 for r in layer_2_3_results if r.layer == 3 and r.passed)

                    if layer_2_count > 0:
                        print(f"✓ Layer 2: {layer_2_passed}/{layer_2_count} passed")
                    if layer_3_count > 0:
                        print(f"✓ Layer 3: {layer_3_passed}/{layer_3_count} passed")
                    print()

                    # Check for blocking failures
                    if self.config.execution.fail_fast_deterministic:
                        layer_2_3_failures = [r for r in layer_2_3_results if not r.passed]
                        if layer_2_3_failures:
                            print("❌ Blocking failure in Layer 2-3. Stopping execution.\n")
                            report = self.report_generator.generate(all_results, [], tool_name)
                            self._save_report(report)
                            return report
                else:
                    print("  No tests in Layer 2-3\n")
            else:
                print("[4/6] Skipping Layer 2-3 (not requested)\n")

            # Step 5: Run Layer 4-5 (non-blocking)
            if 4 in layers or 5 in layers:
                print("[5/6] Running Layer 4-5 (LLM Behavior)...")

                if 4 in layers:
                    layer_4_tests = tests_by_layer.get(4, [])
                    if layer_4_tests:
                        layer_4_judgments = await self.nondeterministic_runner.run_layer_4(
                            tool_name,
                            layer_4_tests
                        )
                        all_judgments.extend(layer_4_judgments)
                        layer_4_passed = sum(1 for j in layer_4_judgments if j.passed)
                        print(f"✓ Layer 4: {layer_4_passed}/{len(layer_4_judgments)} correct")
                    else:
                        print("✓ Layer 4: No tests")

                if 5 in layers:
                    layer_5_tests = tests_by_layer.get(5, [])
                    if layer_5_tests:
                        layer_5_judgments = await self.nondeterministic_runner.run_layer_5(
                            tool_name,
                            layer_5_tests,
                            test_data
                        )
                        all_judgments.extend(layer_5_judgments)
                        layer_5_passed = sum(1 for j in layer_5_judgments if j.passed)
                        print(f"✓ Layer 5: {layer_5_passed}/{len(layer_5_judgments)} correct")
                    else:
                        print("✓ Layer 5: N/A (read-only tool)")

                print()
            else:
                print("[5/6] Skipping Layer 4-5 (not requested)\n")

        # Execute tests with or without client pooling
        try:
            if use_client_pool:
                async with pool_cm:
                    await run_tests()
            else:
                await run_tests()
        finally:
            # Cleanup provisioned resources
            if provisioner:
                print("\n[Cleanup] Cleaning up provisioned resources...")
                try:
                    async with self.test_case_manager._get_mcp_client() as client:
                        # Re-attach client for cleanup
                        provisioner.mcp_client = client
                        await provisioner.cleanup_all()
                except Exception as e:
                    print(f"⚠ Cleanup failed (non-critical): {e}")

        # Step 6: Generate report
        print("[6/6] Generating report...")
        report = self.report_generator.generate(
            all_results,
            all_judgments,
            tool_name
        )
        self._save_report(report)
        print(f"✓ Reports saved to {self.config.reporting.output_dir}\n")

        # Final summary
        print(f"{'='*60}")
        if report.overall_passed:
            print("✅ ALL TESTS PASSED")
        else:
            print(f"❌ {len(report.failures)} FAILURES")
            for failure in report.failures[:5]:  # Show first 5
                print(f"  - {failure.checkpoint_name}: {failure.message}")
            if len(report.failures) > 5:
                print(f"  ... and {len(report.failures) - 5} more")
        print(f"{'='*60}")

        return report

    def _save_report(self, report: Report):
        """
        Save report to disk.

        Args:
            report: Report object to save
        """
        output_dir = self.config.reporting.output_dir
        self.report_generator.export_html(report, f"{output_dir}/report.html")
        self.report_generator.export_json(report, f"{output_dir}/report.json")

        # Save to history
        history_dir = self.config.reporting.history_dir
        timestamp = report.timestamp.replace(":", "-").replace(".", "-")
        self.report_generator.export_json(report, f"{history_dir}/{timestamp}.json")

    async def verify_setup(self) -> bool:
        """
        Verify framework setup and connectivity.

        Returns:
            True if setup is valid, False otherwise
        """
        print("Verifying framework setup...")

        # Check MCP server connection
        print("  - Checking MCP server connection...")
        connected = await self.test_case_manager.verify_connection()
        if not connected:
            print("    ✗ Failed to connect to MCP server")
            return False
        print("    ✓ MCP server connected")

        # Check environment variables
        print("  - Checking environment variables...")
        import os
        required_vars = ["OKTA_ORG_URL", "OKTA_CLIENT_ID", "OKTA_PRIVATE_KEY", "OKTA_KEY_ID"]
        missing_vars = [var for var in required_vars if not os.environ.get(var)]

        if missing_vars:
            print(f"    ✗ Missing variables: {', '.join(missing_vars)}")
            return False
        print("    ✓ All required environment variables present")

        # Check output directories
        print("  - Checking output directories...")
        Path(self.config.reporting.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.reporting.history_dir).mkdir(parents=True, exist_ok=True)
        print("    ✓ Output directories created")

        print("✓ Framework setup verified\n")
        return True
