"""Smart resource provisioning for test data generation.

Automatically provisions test resources based on tool patterns:
- Detects resource type from tool name (user, group, app, etc.)
- Lists existing resources first (prefer reuse)
- Creates temporary resources if needed
- Handles cleanup based on provisioning strategy

Adding a new resource type:
    1. Add a ResourceConfig entry to RESOURCE_CONFIGS with:
       - list_tool / list_params: how to list one existing resource
       - create_tool / create_params: how to create a temp resource
       - delete_tool / deactivate_tool: how to clean up
       - id_field: the JSON key that holds the ID in list/create responses
       - id_param: the parameter name the tool expects (e.g. "user_id", "group_id")
    2. Optionally add an explicit entry to TOOL_MAPPINGS to override
       pattern-based detection for a specific tool name.
"""

import uuid
import json
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


class ProvisioningStrategy(Enum):
    """Resource lifecycle strategy for different tool types."""

    SHARED = "shared"
    # Create once, reuse for all tests, cleanup at end
    # Use for: GET, LIST, SEARCH (read-only tools)

    PER_TEST_CONSUMED = "per_test_consumed"
    # Create before each test, test consumes it, no cleanup needed
    # Use for: DELETE, DEACTIVATE, REMOVE (destructive tools)

    PER_TEST_ISOLATED = "per_test_isolated"
    # Create before each test, cleanup after each test
    # Use for: UPDATE, PATCH (when mutation affects subsequent tests)

    NONE = "none"
    # No provisioning needed
    # Use for: CREATE tools (they create their own resources)


@dataclass
class ProvisionedResource:
    """A provisioned test resource."""
    resource_type: str       # user, group, app, etc.
    resource_id: str         # Actual ID in Okta org
    cleanup_needed: bool     # Whether to delete after tests
    cleanup_tool: Optional[str] = None       # MCP tool name for deletion
    deactivate_tool: Optional[str] = None    # MCP tool name for deactivation (if required before delete)
    id_param: str = "id"                     # Parameter name the delete/deactivate tool expects
    strategy: ProvisioningStrategy = ProvisioningStrategy.SHARED


@dataclass
class ResourceConfig:
    """
    Configuration for a single resource type.

    To add support for a new Okta resource (e.g. policy, app, factor):
      - Set list_tool + list_params so list_existing() can fetch one real ID.
      - Set create_tool + create_params so create_temp_resource() can make one.
      - Set delete_tool (and deactivate_tool if Okta requires it) for cleanup.
      - id_field: the key in the JSON response that contains the resource ID.
      - id_param: the parameter name used by delete/deactivate/get tools
                  (e.g. Okta uses "user_id" not "id" in most MCP tool schemas).
    """
    resource_type: str
    list_tool: str
    create_tool: Optional[str]
    delete_tool: Optional[str]
    id_field: str                          # Key in API response JSON (e.g. "id")
    id_param: str                          # Param name for tools (e.g. "user_id")
    create_params: Dict[str, Any] = field(default_factory=dict)
    list_params: Dict[str, Any] = field(default_factory=dict)   # Extra params required by list_tool
    deactivate_tool: Optional[str] = None  # For Okta: must deactivate before delete


class ResourceProvisioner:
    """Provisions test resources automatically based on tool patterns."""

    # -------------------------------------------------------------------------
    # Resource type registry — add new resource types here
    # -------------------------------------------------------------------------
    RESOURCE_CONFIGS: Dict[str, ResourceConfig] = {
        "user": ResourceConfig(
            resource_type="user",
            list_tool="list_users",
            list_params={},
            create_tool="create_user",
            delete_tool="delete_deactivated_user",
            id_field="id",
            id_param="user_id",
            create_params={
                "profile": {
                    "email": "test_${uuid}@example.com",
                    "firstName": "Test",
                    "lastName": "User",
                    "login": "test_${uuid}@example.com"
                }
            },
            deactivate_tool="deactivate_user"
        ),
        "group": ResourceConfig(
            resource_type="group",
            list_tool="list_groups",
            list_params={},
            create_tool="create_group",
            delete_tool="delete_group",
            id_field="id",
            id_param="group_id",
            create_params={
                "profile": {
                    "name": "Test Group ${uuid}",
                    "description": "Temporary test group"
                }
            }
        ),
        "app": ResourceConfig(
            resource_type="app",
            list_tool="list_applications",
            list_params={},
            create_tool=None,   # Don't create apps in tests — too complex
            delete_tool=None,
            id_field="id",
            id_param="app_id",
            create_params={}
        ),
        "policy": ResourceConfig(
            resource_type="policy",
            list_tool="list_policies",
            list_params={"type": "OKTA_SIGN_ON"},  # list_policies requires a type param
            create_tool=None,   # Reuse existing policies, don't create temp ones
            delete_tool=None,
            id_field="id",
            id_param="policy_id",
            create_params={}
        ),
    }

    # -------------------------------------------------------------------------
    # Explicit tool-to-resource mappings
    # Pattern-based detection handles most cases automatically.
    # Add entries here only when the pattern doesn't work or you need
    # to specify multiple resource types for a single tool.
    # -------------------------------------------------------------------------
    TOOL_MAPPINGS: Dict[str, Dict[str, Any]] = {
        # Multi-resource tools
        "assign_user_to_app":      {"resources": ["user", "app"],   "strategy": ProvisioningStrategy.SHARED},
        "assign_user_to_group":    {"resources": ["user", "group"], "strategy": ProvisioningStrategy.SHARED},
        "remove_user_from_group":  {"resources": ["user", "group"], "strategy": ProvisioningStrategy.SHARED},
        "list_group_users":        {"resources": ["group"],         "strategy": ProvisioningStrategy.SHARED},
        "list_group_apps":         {"resources": ["group"],         "strategy": ProvisioningStrategy.SHARED},

        # Destructive tools — provision a fresh resource before each test
        "delete_user":             {"resources": ["user"],  "strategy": ProvisioningStrategy.PER_TEST_CONSUMED},
        "deactivate_user":         {"resources": ["user"],  "strategy": ProvisioningStrategy.PER_TEST_CONSUMED},
        "delete_group":            {"resources": ["group"], "strategy": ProvisioningStrategy.PER_TEST_CONSUMED},

        # Read-only single-resource tools — reuse an existing resource
        "get_user":                {"resources": ["user"],   "strategy": ProvisioningStrategy.SHARED},
        "get_group":               {"resources": ["group"],  "strategy": ProvisioningStrategy.SHARED},
        "get_application":         {"resources": ["app"],    "strategy": ProvisioningStrategy.SHARED},
        "get_policy":              {"resources": ["policy"], "strategy": ProvisioningStrategy.SHARED},
        "get_policy_rule":         {"resources": ["policy"], "strategy": ProvisioningStrategy.SHARED},
        "list_policy_rules":       {"resources": ["policy"], "strategy": ProvisioningStrategy.SHARED},

        # Creation tools — tool creates its own resource, no provisioning needed
        "create_user":             {"resources": [], "strategy": ProvisioningStrategy.NONE},
        "create_group":            {"resources": [], "strategy": ProvisioningStrategy.NONE},
    }

    def __init__(self, mcp_client):
        """
        Initialize provisioner.

        Args:
            mcp_client: MCP client for calling tools
        """
        self.mcp_client = mcp_client
        self.provisioned_resources: List[ProvisionedResource] = []

    # -------------------------------------------------------------------------
    # Generic MCP response parser
    # -------------------------------------------------------------------------

    def _parse_mcp_response(self, result: Any) -> Any:
        """
        Parse a raw MCP CallToolResult into a Python object (dict or list).

        MCP tools return a CallToolResult with a .content list of TextContent
        objects. The actual data is JSON-encoded in .content[0].text.
        This method handles that wrapping generically so all other methods
        don't need to know about the MCP wire format.

        Args:
            result: Raw value returned by mcp_client.call_tool()

        Returns:
            Parsed Python object (dict, list, str) or None if unparseable
        """
        # Already a plain Python object (e.g. in tests / mocks)
        if isinstance(result, (dict, list)):
            return result

        # Standard MCP CallToolResult — extract text from first content item
        if hasattr(result, 'content') and result.content:
            for item in result.content:
                if hasattr(item, 'text') and item.text:
                    text = item.text
                    # Try JSON first
                    try:
                        return json.loads(text)
                    except (json.JSONDecodeError, ValueError):
                        pass
                    # Okta SDK serialises objects as Python repr strings which contain
                    # enum values like <UserStatus.ACTIVE: 'ACTIVE'> that break ast.literal_eval.
                    # Return the raw text — _extract_id_from_parsed handles regex fallback.
                    return text

        return None

    def _extract_id_from_parsed(self, data: Any, id_field: str) -> Optional[str]:
        """
        Extract a resource ID from a parsed API response.

        Handles four response shapes:
          1. Single object dict:  {"id": "00u...", ...}
          2. Plain list:          [{"id": "00u..."}, ...]
          3. Wrapped list:        {"users": [...], "items": [...], ...}
          4. list_users tuples:   [[profile_dict, "00u..."], ...]
          5. Raw repr string:     "'id': '00u...'" (Okta SDK repr fallback)

        Args:
            data: Value from _parse_mcp_response() — dict, list, or str
            id_field: The JSON key that holds the ID (e.g. "id")

        Returns:
            Resource ID string, or None if not found
        """
        if data is None:
            return None

        # Shape 1: single object dict
        if isinstance(data, dict):
            if id_field in data:
                val = data[id_field]
                if val is not None:
                    return str(val)
            # Shape 3: wrapped list — look for the first list value
            for value in data.values():
                if isinstance(value, list) and value:
                    first = value[0]
                    if isinstance(first, dict) and id_field in first:
                        return str(first[id_field])

        # Shape 2 / 4: list
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict) and id_field in first:
                return str(first[id_field])
            # [profile_dict, id_string] tuples (list_users format)
            if isinstance(first, (list, tuple)) and len(first) >= 2:
                return str(first[1])

        # Shape 5: raw repr/text string — regex fallback
        if isinstance(data, str):
            import re
            # Matches both 'id': '00u...' and "id": "00u..."
            pattern = rf"""['"]{re.escape(id_field)}['"]\s*:\s*['"]([^'"]+)['"]"""
            match = re.search(pattern, data)
            if match:
                return match.group(1)

        return None

    # -------------------------------------------------------------------------
    # Strategy + resource type detection
    # -------------------------------------------------------------------------

    def detect_strategy(self, tool_name: str) -> ProvisioningStrategy:
        """
        Detect provisioning strategy for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Provisioning strategy
        """
        # Check explicit mapping first
        if tool_name in self.TOOL_MAPPINGS:
            return self.TOOL_MAPPINGS[tool_name]["strategy"]

        # Pattern-based detection
        tool_lower = tool_name.lower()

        # Destructive tools
        if any(word in tool_lower for word in ["delete", "remove", "deactivate", "suspend"]):
            return ProvisioningStrategy.PER_TEST_CONSUMED

        # Creation tools
        if tool_lower.startswith("create_") or tool_lower.startswith("add_"):
            return ProvisioningStrategy.NONE

        # Update tools (may need isolation to avoid side effects)
        if any(word in tool_lower for word in ["update", "patch", "modify", "set"]):
            return ProvisioningStrategy.PER_TEST_ISOLATED

        # Default: read-only, can share
        return ProvisioningStrategy.SHARED

    def detect_resource_types(self, tool_name: str) -> List[str]:
        """
        Detect which resource types are needed for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of resource types needed
        """
        # Check explicit mapping first
        if tool_name in self.TOOL_MAPPINGS:
            return self.TOOL_MAPPINGS[tool_name]["resources"]

        # Pattern-based detection
        resources = []
        tool_lower = tool_name.lower()

        if "user" in tool_lower:
            resources.append("user")
        if "group" in tool_lower:
            resources.append("group")
        if "app" in tool_lower or "application" in tool_lower:
            resources.append("app")
        if "policy" in tool_lower:
            resources.append("policy")

        return resources

    async def list_existing(self, resource_type: str) -> Optional[str]:
        """
        Find an existing resource of the given type and return its ID.

        Calls the resource's list_tool with limit=1 (plus any required
        list_params) and extracts the ID using the generic MCP response parser.

        Args:
            resource_type: Key in RESOURCE_CONFIGS (e.g. "user", "group")

        Returns:
            Resource ID string if one exists, None otherwise
        """
        config = self.RESOURCE_CONFIGS.get(resource_type)
        if not config or not config.list_tool:
            return None

        try:
            call_params = dict(config.list_params)
            call_params["limit"] = 1
            result = await self.mcp_client.call_tool(config.list_tool, call_params)
            data = self._parse_mcp_response(result)
            resource_id = self._extract_id_from_parsed(data, config.id_field)
            return resource_id
        except Exception as e:
            print(f"Warning: Could not list {resource_type}: {e}")

        return None

    async def create_temp_resource(self, resource_type: str) -> str:
        """
        Create a temporary test resource and return its ID.

        Uses the resource's create_tool with generated unique params
        (${uuid} placeholders are replaced with a random 8-char hex string).
        The created resource is tracked so cleanup_all() can remove it later.

        Args:
            resource_type: Key in RESOURCE_CONFIGS (e.g. "user", "group")

        Returns:
            Resource ID string

        Raises:
            ValueError: If no create_tool is configured for this resource type
            Exception: If creation fails or ID cannot be parsed from response
        """
        config = self.RESOURCE_CONFIGS.get(resource_type)
        if not config or not config.create_tool:
            raise ValueError(f"Cannot create resource of type '{resource_type}': "
                             f"no create_tool configured in RESOURCE_CONFIGS")

        # Replace ${uuid} placeholders with a unique suffix
        params = json.loads(
            json.dumps(config.create_params).replace("${uuid}", str(uuid.uuid4())[:8])
        )

        try:
            result = await self.mcp_client.call_tool(config.create_tool, params)
            data = self._parse_mcp_response(result)
            resource_id = self._extract_id_from_parsed(data, config.id_field)

            if resource_id:
                return resource_id

            raise ValueError(
                f"Could not extract '{config.id_field}' from {config.create_tool} response. "
                f"Parsed data: {str(data)[:200]}"
            )
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Failed to create {resource_type}: {e}")

    async def provision_for_tool(
        self,
        tool_name: str,
        num_tests: int = 1
    ) -> Dict[str, Any]:
        """
        Provision resources for testing a tool.

        Args:
            tool_name: Name of the tool to test
            num_tests: Number of tests (relevant for PER_TEST strategies)

        Returns:
            Dictionary mapping resource types to IDs
        """
        strategy = self.detect_strategy(tool_name)
        resource_types = self.detect_resource_types(tool_name)

        if strategy == ProvisioningStrategy.NONE:
            # No provisioning needed
            return {"strategy": strategy}

        resources = {}

        for resource_type in resource_types:
            config = self.RESOURCE_CONFIGS.get(resource_type)
            if not config:
                print(f"Warning: Unknown resource type: {resource_type}")
                continue

            if strategy == ProvisioningStrategy.SHARED:
                # Try existing first, create only if none exists
                resource_id = await self.list_existing(resource_type)
                cleanup_needed = False

                if not resource_id:
                    resource_id = await self.create_temp_resource(resource_type)
                    cleanup_needed = True

                provisioned = ProvisionedResource(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    cleanup_needed=cleanup_needed,
                    cleanup_tool=config.delete_tool if cleanup_needed else None,
                    deactivate_tool=config.deactivate_tool if cleanup_needed else None,
                    id_param=config.id_param,
                    strategy=strategy
                )
                self.provisioned_resources.append(provisioned)
                resources[f"{resource_type}_id"] = resource_id

            elif strategy == ProvisioningStrategy.PER_TEST_CONSUMED:
                # Will create fresh resource per test
                # Store config for later
                resources[f"{resource_type}_config"] = config
                resources["needs_per_test_provisioning"] = True

            elif strategy == ProvisioningStrategy.PER_TEST_ISOLATED:
                # Will create and cleanup per test
                resources[f"{resource_type}_config"] = config
                resources["needs_per_test_provisioning"] = True

        resources["strategy"] = strategy
        return resources

    async def provision_for_single_test(self, resource_configs: Dict[str, Any]) -> Dict[str, str]:
        """
        Provision resources for a single test (used with PER_TEST strategies).

        Args:
            resource_configs: Resource configurations from provision_for_tool

        Returns:
            Dictionary mapping resource types to IDs
        """
        resources = {}

        for key, value in resource_configs.items():
            if key.endswith("_config") and isinstance(value, ResourceConfig):
                resource_type = value.resource_type
                resource_id = await self.create_temp_resource(resource_type)
                resources[f"{resource_type}_id"] = resource_id

                # Track for potential cleanup (only for ISOLATED strategy)
                strategy = resource_configs.get("strategy")
                if strategy == ProvisioningStrategy.PER_TEST_ISOLATED:
                    provisioned = ProvisionedResource(
                        resource_type=resource_type,
                        resource_id=resource_id,
                        cleanup_needed=True,
                        cleanup_tool=value.delete_tool,
                        deactivate_tool=value.deactivate_tool,
                        id_param=value.id_param,
                        strategy=strategy
                    )
                    self.provisioned_resources.append(provisioned)

        return resources

    async def cleanup_single_test(self, resource_ids: Dict[str, str]):
        """
        Cleanup resources after a single test (for PER_TEST_ISOLATED).

        Args:
            resource_ids: Dict of {resource_type_id: resource_id} from provision_for_single_test()
        """
        for key, resource_id in resource_ids.items():
            if not key.endswith("_id"):
                continue

            resource_type = key[: -len("_id")]  # strip trailing "_id"
            config = self.RESOURCE_CONFIGS.get(resource_type)
            if not config or not config.delete_tool:
                continue

            try:
                if config.deactivate_tool:
                    try:
                        await self.mcp_client.call_tool(
                            config.deactivate_tool,
                            {config.id_param: resource_id}
                        )
                    except Exception as e:
                        print(f"Warning: Deactivate failed for {resource_type} {resource_id}: {e}")

                await self.mcp_client.call_tool(
                    config.delete_tool,
                    {config.id_param: resource_id}
                )
            except Exception as e:
                print(f"Warning: Failed to cleanup {resource_type} {resource_id}: {e}")

    async def cleanup_all(self):
        """Cleanup all provisioned resources that need cleanup."""
        for resource in self.provisioned_resources:
            if not resource.cleanup_needed or not resource.cleanup_tool:
                continue

            try:
                # Deactivate first if required (e.g. Okta users must be deactivated before delete)
                if resource.deactivate_tool:
                    try:
                        await self.mcp_client.call_tool(
                            resource.deactivate_tool,
                            {resource.id_param: resource.resource_id}
                        )
                        print(f"✓ Deactivated {resource.resource_type}: {resource.resource_id}")
                    except Exception as e:
                        print(f"Warning: Deactivate failed for {resource.resource_type} "
                              f"{resource.resource_id}: {e}")

                await self.mcp_client.call_tool(
                    resource.cleanup_tool,
                    {resource.id_param: resource.resource_id}
                )
                print(f"✓ Deleted {resource.resource_type}: {resource.resource_id}")
            except Exception as e:
                print(f"Warning: Failed to cleanup {resource.resource_type} "
                      f"{resource.resource_id}: {e}")

        self.provisioned_resources.clear()
