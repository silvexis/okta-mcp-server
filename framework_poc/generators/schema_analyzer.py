"""Schema analyzer for extracting structured metadata from tool definitions."""

from typing import Dict, Any, List, Optional
from framework_poc.core.models import SchemaAnalysis, Parameter, ToolDefinition


class SchemaAnalyzer:
    """Analyzes MCP tool schemas and extracts structured metadata."""

    def analyze_tool(self, tool_definition: ToolDefinition) -> SchemaAnalysis:
        """
        Parse MCP tool schema and extract metadata.

        Args:
            tool_definition: Tool definition from MCP tools/list

        Returns:
            SchemaAnalysis object with structured metadata
        """
        tool_name = tool_definition.name
        description = tool_definition.description
        input_schema = tool_definition.inputSchema

        # Extract parameters
        parameters = self._extract_parameters(input_schema)

        # Detect tool characteristics
        characteristics = self._detect_tool_characteristics(tool_name, parameters, description)

        return SchemaAnalysis(
            tool_name=tool_name,
            description=description,
            parameters=parameters,
            has_pagination=characteristics["has_pagination"],
            has_filtering=characteristics["has_filtering"],
            is_destructive=characteristics["is_destructive"],
            is_read_only=characteristics["is_read_only"],
            return_type="object",
            validation_decorators=characteristics["validation_decorators"]
        )

    def _extract_parameters(self, input_schema: Dict[str, Any]) -> List[Parameter]:
        """
        Extract parameters from JSON schema.

        Args:
            input_schema: inputSchema from tool definition

        Returns:
            List of Parameter objects
        """
        parameters = []

        if "properties" not in input_schema:
            return parameters

        properties = input_schema["properties"]
        required = input_schema.get("required", [])

        for param_name, param_schema in properties.items():
            param_type = param_schema.get("type", "string")
            param_description = param_schema.get("description", "")
            param_default = param_schema.get("default")
            enum_values = param_schema.get("enum")

            # Extract constraints
            constraints = self._extract_constraints(param_schema)

            parameters.append(Parameter(
                name=param_name,
                type=param_type,
                required=param_name in required,
                default=param_default,
                constraints=constraints,
                description=param_description,
                enum_values=enum_values
            ))

        return parameters

    def _extract_constraints(self, param_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract min/max/pattern constraints from JSON schema.

        Args:
            param_schema: Parameter schema object

        Returns:
            Dictionary of constraints
        """
        constraints = {}

        # Numeric constraints
        if "minimum" in param_schema:
            constraints["minimum"] = param_schema["minimum"]
        if "maximum" in param_schema:
            constraints["maximum"] = param_schema["maximum"]
        if "exclusiveMinimum" in param_schema:
            constraints["exclusiveMinimum"] = param_schema["exclusiveMinimum"]
        if "exclusiveMaximum" in param_schema:
            constraints["exclusiveMaximum"] = param_schema["exclusiveMaximum"]

        # String constraints
        if "minLength" in param_schema:
            constraints["minLength"] = param_schema["minLength"]
        if "maxLength" in param_schema:
            constraints["maxLength"] = param_schema["maxLength"]
        if "pattern" in param_schema:
            constraints["pattern"] = param_schema["pattern"]

        # Array constraints
        if "minItems" in param_schema:
            constraints["minItems"] = param_schema["minItems"]
        if "maxItems" in param_schema:
            constraints["maxItems"] = param_schema["maxItems"]

        return constraints

    def _detect_tool_characteristics(
        self,
        tool_name: str,
        parameters: List[Parameter],
        description: str
    ) -> Dict[str, Any]:
        """
        Detect tool characteristics from name, parameters, and description.

        Args:
            tool_name: Name of the tool
            parameters: List of parameters
            description: Tool description

        Returns:
            Dictionary of tool characteristics
        """
        param_names = [p.name for p in parameters]
        tool_lower = tool_name.lower()
        desc_lower = description.lower()

        # Detect pagination
        has_pagination = any(name in param_names for name in ["fetch_all", "after", "limit", "cursor"])

        # Detect filtering
        has_filtering = any(name in param_names for name in ["search", "filter", "q", "query"])

        # Detect destructive operations
        destructive_keywords = ["delete", "remove", "deactivate", "suspend", "clear", "revoke", "reset"]
        is_destructive = any(kw in tool_lower for kw in destructive_keywords)

        # Determine if read-only
        is_read_only = not is_destructive and any(kw in tool_lower for kw in ["list", "get", "search", "find", "show"])

        # Detect validation decorators (would need source code analysis in real implementation)
        # For now, infer from parameter names
        validation_decorators = []
        if any("id" in p.name.lower() for p in parameters):
            validation_decorators.append("validate_ids")

        return {
            "has_pagination": has_pagination,
            "has_filtering": has_filtering,
            "is_destructive": is_destructive,
            "is_read_only": is_read_only,
            "validation_decorators": validation_decorators
        }

    def get_parameter_by_name(
        self,
        schema: SchemaAnalysis,
        name: str
    ) -> Optional[Parameter]:
        """Get parameter by name from schema analysis."""
        return next((p for p in schema.parameters if p.name == name), None)
