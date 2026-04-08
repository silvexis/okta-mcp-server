"""Main test generator that orchestrates schema analysis and rule application."""

from typing import Dict, List
from framework_poc.core.models import ToolDefinition, TestCase, SchemaAnalysis
from framework_poc.generators.schema_analyzer import SchemaAnalyzer
from framework_poc.generators.rule_engine import RuleEngine


class TestGenerator:
    """Generates test cases from tool schemas using rules."""

    def __init__(self):
        """Initialize test generator with schema analyzer and rule engine."""
        self.schema_analyzer = SchemaAnalyzer()
        self.rule_engine = RuleEngine()

    async def generate_tests_for_tool(
        self,
        tool_definition: ToolDefinition,
        test_data: dict = None
    ) -> Dict[int, List[TestCase]]:
        """
        Generate all tests for a tool, organized by layer.

        Args:
            tool_definition: Tool definition from MCP
            test_data: Optional dict with provisioned resource IDs (e.g., {"user_id": "00uxyz123"})

        Returns:
            Dictionary mapping layer number to list of test cases
        """
        # Step 1: Analyze schema
        schema = self.schema_analyzer.analyze_tool(tool_definition)

        # Step 2: Generate tests via rules (Layers 2-4), passing test_data
        all_tests = self.rule_engine.generate_all_tests(schema, test_data)

        # Step 3: Organize by layer
        tests_by_layer = {}
        for test in all_tests:
            layer = test.layer
            if layer not in tests_by_layer:
                tests_by_layer[layer] = []
            tests_by_layer[layer].append(test)

        # Step 4: Add Layer 0-1 tests (not parameter-driven)
        tests_by_layer[0] = self._generate_layer_0_tests(schema)
        tests_by_layer[1] = self._generate_layer_1_tests(schema)

        return tests_by_layer

    def _generate_layer_0_tests(self, schema: SchemaAnalysis) -> List[TestCase]:
        """
        Generate contract integrity tests (Layer 0).

        Args:
            schema: Tool schema analysis

        Returns:
            List of Layer 0 test cases
        """
        return [
            TestCase(
                id=f"L0_{schema.tool_name}_tool_registered",
                layer=0,
                category="contract",
                description="Tool appears in tools/list",
                assertions=["tool_name in registered_tools"]
            ),
            TestCase(
                id=f"L0_{schema.tool_name}_schema_valid",
                layer=0,
                category="contract",
                description="inputSchema is well-formed",
                assertions=["schema_has_properties", "schema_valid_json"]
            ),
            TestCase(
                id=f"L0_{schema.tool_name}_description_quality",
                layer=0,
                category="contract",
                description="Description is meaningful",
                assertions=["description_length_sufficient", "description_mentions_functionality"]
            ),
        ]

    def _generate_layer_1_tests(self, schema: SchemaAnalysis) -> List[TestCase]:
        """
        Generate startup/auth tests (Layer 1).

        Args:
            schema: Tool schema analysis

        Returns:
            List of Layer 1 test cases
        """
        return [
            TestCase(
                id=f"L1_{schema.tool_name}_server_startup",
                layer=1,
                category="infrastructure",
                description="Server starts and reaches ready state",
                assertions=["server_started", "tools_list_available"]
            ),
            TestCase(
                id=f"L1_{schema.tool_name}_auth_success",
                layer=1,
                category="infrastructure",
                description="Auth succeeds with valid credentials",
                assertions=["auth_manager_authenticated"]
            ),
        ]

    def get_test_summary(
        self,
        tests_by_layer: Dict[int, List[TestCase]]
    ) -> Dict[str, any]:
        """
        Get summary statistics for generated tests.

        Args:
            tests_by_layer: Tests organized by layer

        Returns:
            Dictionary with summary statistics
        """
        total_tests = sum(len(tests) for tests in tests_by_layer.values())

        category_counts = {}
        for tests in tests_by_layer.values():
            for test in tests:
                category = test.category
                category_counts[category] = category_counts.get(category, 0) + 1

        return {
            "total_tests": total_tests,
            "layer_counts": {layer: len(tests) for layer, tests in tests_by_layer.items()},
            "category_counts": category_counts
        }
