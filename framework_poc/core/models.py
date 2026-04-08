"""Core data models for the MCP E2E testing framework."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
import os


class LayerType(Enum):
    """Test layer types."""
    CONTRACT = 0
    STARTUP = 1
    VALIDATION = 2
    EXECUTION = 3
    LLM_BEHAVIOR = 4
    DESTRUCTIVE_OPS = 5


class TestCategory(Enum):
    """Test category types."""
    CONTRACT = "contract"
    INFRASTRUCTURE = "infrastructure"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    SECURITY = "security"
    SEMANTIC = "semantic"
    DESTRUCTIVE = "destructive"


class ExpectedResult(Enum):
    """Expected test results."""
    SUCCESS = "success"
    ERROR = "error"
    REJECTED = "rejected"
    CLARIFICATION_REQUESTED = "clarification_requested"
    AUTO_CORRECTED = "auto_corrected"
    SUCCESS_OR_CLARIFICATION = "success_or_clarification"


@dataclass
class Parameter:
    """Represents a tool parameter with metadata."""
    name: str
    type: str  # "string" | "integer" | "boolean" | "object" | "array"
    required: bool
    default: Optional[Any] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    enum_values: Optional[List[Any]] = None


@dataclass
class SchemaAnalysis:
    """Analysis results from a tool schema."""
    tool_name: str
    description: str
    parameters: List[Parameter]
    has_pagination: bool = False
    has_filtering: bool = False
    is_destructive: bool = False
    is_read_only: bool = True
    return_type: str = "object"
    validation_decorators: List[str] = field(default_factory=list)

    def get_parameter(self, name: str) -> Optional[Parameter]:
        """Get parameter by name."""
        return next((p for p in self.parameters if p.name == name), None)

    def get_string_parameters(self) -> List[Parameter]:
        """Get all string parameters."""
        return [p for p in self.parameters if p.type == "string"]

    def get_integer_parameters(self) -> List[Parameter]:
        """Get all integer parameters."""
        return [p for p in self.parameters if p.type == "integer"]

    def get_required_parameters(self) -> List[Parameter]:
        """Get all required parameters."""
        return [p for p in self.parameters if p.required]

    def get_optional_parameters(self) -> List[Parameter]:
        """Get all optional parameters."""
        return [p for p in self.parameters if not p.required]


@dataclass
class TestCase:
    """Represents a single test case."""
    id: str
    layer: int
    category: str
    description: str
    params: Dict[str, Any] = field(default_factory=dict)
    expected_result: str = "success"
    assertions: List[str] = field(default_factory=list)

    # Layer 4 specific fields
    prompt: Optional[str] = None
    expected_tool: Optional[str] = None
    expected_params: Optional[Dict[str, Any]] = None
    expected_behavior: Optional[str] = None
    judge_criteria: List[str] = field(default_factory=list)

    # Validation flags
    validate_against_api: bool = False
    expected_fields: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "layer": self.layer,
            "category": self.category,
            "description": self.description,
            "params": self.params,
            "expected_result": self.expected_result,
            "assertions": self.assertions,
            "prompt": self.prompt,
            "expected_tool": self.expected_tool,
            "expected_params": self.expected_params,
            "expected_behavior": self.expected_behavior,
            "judge_criteria": self.judge_criteria,
        }


@dataclass
class CheckResult:
    """Result from a deterministic test check."""
    checkpoint_id: str
    checkpoint_name: str
    passed: bool
    message: str
    layer: int
    error: Optional[str] = None
    test_case: Optional[TestCase] = None
    execution_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_name": self.checkpoint_name,
            "passed": self.passed,
            "message": self.message,
            "layer": self.layer,
            "error": self.error,
            "test_case": self.test_case.to_dict() if self.test_case else None,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class Judgment:
    """Result from a non-deterministic LLM evaluation."""
    criterion: str
    rating: str  # "correct" | "partial" | "wrong" for tool selection
                 # "accurate" | "partial" | "inaccurate" for faithfulness
    reasoning: str
    passed: bool
    test_case: Optional[TestCase] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "criterion": self.criterion,
            "rating": self.rating,
            "reasoning": self.reasoning,
            "passed": self.passed,
            "test_case": self.test_case.to_dict() if self.test_case else None,
        }


@dataclass
class LayerSummary:
    """Summary statistics for a test layer."""
    layer: int
    total: int
    passed: int
    failed: int
    pass_rate: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "layer": self.layer,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
        }


@dataclass
class Report:
    """Test execution report."""
    tool_name: str
    timestamp: str
    layer_summaries: Dict[int, Dict[str, Any]]
    all_results: List[CheckResult]
    all_judgments: List[Judgment]
    failures: List[CheckResult]
    overall_passed: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "timestamp": self.timestamp,
            "layer_summaries": self.layer_summaries,
            "all_results": [r.to_dict() for r in self.all_results],
            "all_judgments": [j.to_dict() for j in self.all_judgments],
            "failures": [f.to_dict() for f in self.failures],
            "overall_passed": self.overall_passed,
        }


@dataclass
class ServerConfig:
    """Server connection configuration."""
    name: str
    type: str
    command: str
    args: List[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServerConfig':
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=data["type"],
            command=data["command"],
            args=data["args"]
        )


@dataclass
class OktaConfig:
    """Okta credentials configuration."""
    org_url: str
    client_id: str
    private_key: str
    key_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OktaConfig':
        """Create from dictionary with environment variable expansion."""
        return cls(
            org_url=cls._expand_env(data["org_url"]),
            client_id=cls._expand_env(data["client_id"]),
            private_key=cls._expand_env(data["private_key"]),
            key_id=cls._expand_env(data["key_id"])
        )

    @staticmethod
    def _expand_env(value: str) -> str:
        """Expand environment variables in format ${VAR}."""
        if value.startswith("${") and value.endswith("}"):
            var_name = value[2:-1]
            return os.environ.get(var_name, "")
        return value


@dataclass
class ClaudeConfig:
    """Claude API configuration."""
    api_key: str
    model: str
    temperature: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClaudeConfig':
        """Create from dictionary with environment variable expansion."""
        api_key = data["api_key"]
        if api_key.startswith("${") and api_key.endswith("}"):
            var_name = api_key[2:-1]
            api_key = os.environ.get(var_name, "")

        return cls(
            api_key=api_key,
            model=data["model"],
            temperature=data["temperature"]
        )


@dataclass
class ExecutionConfig:
    """Execution settings."""
    layers: List[int]
    fail_fast_deterministic: bool
    max_workers: int
    timeouts: Dict[str, int]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionConfig':
        """Create from dictionary."""
        return cls(
            layers=data["layers"],
            fail_fast_deterministic=data["fail_fast_deterministic"],
            max_workers=data["max_workers"],
            timeouts=data["timeouts"]
        )


@dataclass
class ReportingConfig:
    """Reporting configuration."""
    output_dir: str
    history_dir: str
    formats: List[str]
    include_proposed_fixes: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReportingConfig':
        """Create from dictionary."""
        return cls(
            output_dir=data["output_dir"],
            history_dir=data["history_dir"],
            formats=data["formats"],
            include_proposed_fixes=data["include_proposed_fixes"]
        )


@dataclass
class POCConfig:
    """POC-specific configuration."""
    focus_tool: str
    focus_layers: List[int]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'POCConfig':
        """Create from dictionary."""
        return cls(
            focus_tool=data["focus_tool"],
            focus_layers=data["focus_layers"]
        )


@dataclass
class Config:
    """Main configuration object."""
    server: ServerConfig
    okta: OktaConfig
    claude: ClaudeConfig
    execution: ExecutionConfig
    reporting: ReportingConfig
    poc: POCConfig

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'Config':
        """Load configuration from YAML file."""
        import yaml

        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        return cls(
            server=ServerConfig.from_dict(data["server"]),
            okta=OktaConfig.from_dict(data["okta"]),
            claude=ClaudeConfig.from_dict(data["claude"]),
            execution=ExecutionConfig.from_dict(data["execution"]),
            reporting=ReportingConfig.from_dict(data["reporting"]),
            poc=POCConfig.from_dict(data["poc"])
        )


@dataclass
class ToolDefinition:
    """Represents an MCP tool definition."""
    name: str
    description: str
    inputSchema: Dict[str, Any]

    @classmethod
    def from_mcp_tool(cls, tool: Any) -> 'ToolDefinition':
        """Create from MCP Tool object."""
        return cls(
            name=tool.name,
            description=tool.description,
            inputSchema=tool.inputSchema
        )
