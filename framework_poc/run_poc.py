#!/usr/bin/env python3
"""Demo entrypoint for the MCP E2E Testing Framework POC."""

import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directory to path to import framework modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from framework_poc.core.models import Config
from framework_poc.pipeline import TestPipeline


async def main():
    """Main entry point for the POC demo."""
    parser = argparse.ArgumentParser(
        description="MCP E2E Testing Framework POC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all layers for list_users
  python run_poc.py

  # Run only deterministic layers
  python run_poc.py --layers 0,1,2,3

  # Run only semantic layer
  python run_poc.py --layers 4

  # Test a different tool
  python run_poc.py --tool get_user

  # Verify setup without running tests
  python run_poc.py --verify-only
        """
    )

    parser.add_argument(
        "--tool",
        type=str,
        default=None,
        help="Tool name to test (default: from config.yaml)"
    )

    parser.add_argument(
        "--layers",
        type=str,
        default=None,
        help="Comma-separated list of layers to run (e.g., '0,1,2,3')"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="framework_poc/config.yaml",
        help="Path to configuration file"
    )

    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify setup, don't run tests"
    )

    args = parser.parse_args()

    # Load configuration
    print("Loading configuration...")
    try:
        config = Config.from_yaml(args.config)
        print(f"✓ Configuration loaded from {args.config}\n")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return 1

    # Override tool if specified
    tool_name = args.tool or config.poc.focus_tool

    # Override layers if specified
    if args.layers:
        layers = [int(l.strip()) for l in args.layers.split(",")]
    else:
        layers = config.poc.focus_layers

    # Initialize pipeline
    pipeline = TestPipeline(config)

    # Verify setup
    setup_ok = await pipeline.verify_setup()
    if not setup_ok:
        print("✗ Setup verification failed")
        return 1

    if args.verify_only:
        print("Setup verification complete. Exiting.")
        return 0

    # Run tests
    print(f"Starting test pipeline for tool: {tool_name}")
    print(f"Layers to run: {layers}\n")

    try:
        report = await pipeline.run_full_pipeline(tool_name, layers)

        # Print summary
        print("\n" + "="*60)
        print("FINAL SUMMARY")
        print("="*60)
        print(f"Tool: {report.tool_name}")
        print(f"Timestamp: {report.timestamp}")
        print(f"Overall Status: {'PASSED ✅' if report.overall_passed else 'FAILED ❌'}")
        print()

        # Layer summaries
        for layer, summary in sorted(report.layer_summaries.items()):
            layer_names = {
                0: "Contract Integrity",
                1: "Server Startup & Auth",
                2: "Input Validation",
                3: "Tool Execution",
                4: "LLM Behavior",
                5: "Destructive Ops Safety"
            }
            layer_name = layer_names.get(layer, f"Layer {layer}")
            print(f"Layer {layer} ({layer_name}):")
            print(f"  Total: {summary['total']}")
            print(f"  Passed: {summary['passed']}")
            print(f"  Failed: {summary['failed']}")
            print(f"  Pass Rate: {summary['pass_rate']:.1f}%")
            print()

        # Report locations
        print("Reports saved to:")
        print(f"  - HTML: {config.reporting.output_dir}/report.html")
        print(f"  - JSON: {config.reporting.output_dir}/report.json")
        print()

        return 0 if report.overall_passed else 1

    except Exception as e:
        print(f"\n✗ Pipeline execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
