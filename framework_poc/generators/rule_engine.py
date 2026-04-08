"""Rule engine for orchestrating test generation from multiple rule categories."""

from typing import List, Callable
from framework_poc.core.models import SchemaAnalysis, TestCase

# Import all rule generators
from framework_poc.generators.rules.positive_rules import (
    generate_basic_call_test,
    generate_single_param_tests,
    generate_pagination_tests,
    generate_filtering_tests,
    generate_combination_tests,
)
from framework_poc.generators.rules.negative_rules import (
    generate_type_mismatch_tests,
    generate_missing_required_params_tests,
    generate_invalid_enum_tests,
    generate_null_value_tests,
    generate_malformed_value_tests,
)
from framework_poc.generators.rules.boundary_rules import (
    generate_boundary_tests,
)
from framework_poc.generators.rules.security_rules import (
    generate_injection_tests,
    generate_id_validation_tests,
    generate_overflow_tests,
    generate_encoding_tests,
)
from framework_poc.generators.rules.semantic_rules import (
    generate_semantic_prompts,
)
from framework_poc.generators.rules.destructive_rules import (
    generate_destructive_operation_tests,
)


class RuleEngine:
    """Orchestrates all rule categories to generate complete test suites."""

    def __init__(self):
        """Initialize rule engine with all rule functions."""
        # Rules that return a single TestCase
        self.single_rules: List[Callable[[SchemaAnalysis], TestCase]] = [
            generate_basic_call_test,
        ]

        # Rules that return a list of TestCases
        self.multi_rules: List[Callable[[SchemaAnalysis], List[TestCase]]] = [
            # Positive rules
            generate_single_param_tests,
            generate_pagination_tests,
            generate_filtering_tests,
            generate_combination_tests,

            # Negative rules
            generate_type_mismatch_tests,
            generate_missing_required_params_tests,
            generate_invalid_enum_tests,
            generate_null_value_tests,
            generate_malformed_value_tests,

            # Boundary rules
            generate_boundary_tests,

            # Security rules
            generate_injection_tests,
            generate_id_validation_tests,
            generate_overflow_tests,
            generate_encoding_tests,

            # Semantic rules (Layer 4)
            generate_semantic_prompts,

            # Destructive rules (Layer 5)
            generate_destructive_operation_tests,
        ]

    def generate_all_tests(self, schema: SchemaAnalysis, test_data: dict = None) -> List[TestCase]:
        """
        Apply all rules and return complete test suite.

        Args:
            schema: Tool schema analysis
            test_data: Optional dict with provisioned resource IDs (e.g., {"user_id": "00uxyz123"})

        Returns:
            List of all generated test cases (deduplicated)
        """
        all_tests = []

        # Apply single-result rules
        for rule in self.single_rules:
            try:
                # Pass test_data to rules that accept it
                if rule.__name__ in ['generate_basic_call_test'] and test_data:
                    test = rule(schema, test_data)
                else:
                    test = rule(schema)
                all_tests.append(test)
            except Exception as e:
                print(f"Warning: Rule {rule.__name__} failed: {e}")

        # Apply multi-result rules
        for rule in self.multi_rules:
            try:
                # Pass test_data only to rules that accept it (positive rules)
                if rule.__name__ in ['generate_single_param_tests'] and test_data:
                    tests = rule(schema, test_data)
                else:
                    tests = rule(schema)
                all_tests.extend(tests)
            except Exception as e:
                print(f"Warning: Rule {rule.__name__} failed: {e}")

        # Deduplicate by ID
        seen = set()
        unique_tests = []
        for test in all_tests:
            if test.id not in seen:
                seen.add(test.id)
                unique_tests.append(test)
            else:
                print(f"Warning: Duplicate test ID: {test.id}")

        return unique_tests

    def generate_tests_for_layers(
        self,
        schema: SchemaAnalysis,
        layers: List[int]
    ) -> List[TestCase]:
        """
        Generate tests only for specified layers.

        Args:
            schema: Tool schema analysis
            layers: List of layer numbers to generate tests for

        Returns:
            List of test cases for specified layers
        """
        all_tests = self.generate_all_tests(schema)
        return [test for test in all_tests if test.layer in layers]

    def get_test_count_by_layer(self, schema: SchemaAnalysis) -> dict:
        """
        Get count of tests per layer without generating them.

        Args:
            schema: Tool schema analysis

        Returns:
            Dictionary mapping layer number to test count
        """
        all_tests = self.generate_all_tests(schema)
        counts = {}

        for test in all_tests:
            layer = test.layer
            counts[layer] = counts.get(layer, 0) + 1

        return counts
