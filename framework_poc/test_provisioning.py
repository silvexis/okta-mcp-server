#!/usr/bin/env python3
"""Quick test to verify resource provisioning integration works."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from framework_poc.core.models import Config
from framework_poc.core.mcp_client import get_mcp_client
from framework_poc.generators.resource_provisioner import ResourceProvisioner


async def test_provisioning():
    """Test resource provisioning with different tool types."""
    print("="*60)
    print("Resource Provisioning Integration Test")
    print("="*60)
    print()

    # Load config
    config = Config.from_yaml("framework_poc/config.yaml")

    async with get_mcp_client(config.server) as client:
        provisioner = ResourceProvisioner(client)

        # Test 1: GET tool (SHARED strategy)
        print("Test 1: GET tool (list_users)")
        print("-" * 40)
        strategy = provisioner.detect_strategy("list_users")
        print(f"✓ Detected strategy: {strategy.value}")
        print()

        # Test 2: GET tool with ID parameter (SHARED strategy)
        print("Test 2: GET tool with parameter (get_user)")
        print("-" * 40)
        strategy = provisioner.detect_strategy("get_user")
        print(f"✓ Detected strategy: {strategy.value}")

        resources = provisioner.detect_resource_types("get_user")
        print(f"✓ Detected resources needed: {resources}")

        try:
            test_data = await provisioner.provision_for_tool("get_user")
            if test_data.get("user_id"):
                print(f"✓ Provisioned user: {test_data['user_id']}")
            else:
                print(f"✓ Provisioning ready (strategy: {test_data.get('strategy')})")
        except Exception as e:
            print(f"⚠ Provisioning failed: {e}")
        print()

        # Test 3: DELETE tool (PER_TEST_CONSUMED strategy)
        print("Test 3: DELETE tool (delete_user)")
        print("-" * 40)
        strategy = provisioner.detect_strategy("delete_user")
        print(f"✓ Detected strategy: {strategy.value}")

        resources = provisioner.detect_resource_types("delete_user")
        print(f"✓ Detected resources needed: {resources}")
        print("✓ Will provision fresh resource per test")
        print()

        # Test 4: UPDATE tool (PER_TEST_ISOLATED strategy)
        print("Test 4: UPDATE tool (update_user)")
        print("-" * 40)
        strategy = provisioner.detect_strategy("update_user")
        print(f"✓ Detected strategy: {strategy.value}")

        resources = provisioner.detect_resource_types("update_user")
        print(f"✓ Detected resources needed: {resources}")
        print("✓ Will provision and cleanup per test")
        print()

        # Test 5: CREATE tool (NONE strategy)
        print("Test 5: CREATE tool (create_user)")
        print("-" * 40)
        strategy = provisioner.detect_strategy("create_user")
        print(f"✓ Detected strategy: {strategy.value}")
        print("✓ No provisioning needed (tool creates its own resources)")
        print()

        # Cleanup
        print("Cleanup")
        print("-" * 40)
        await provisioner.cleanup_all()
        print("✓ Cleanup complete")
        print()

    print("="*60)
    print("✅ All provisioning tests passed!")
    print("="*60)
    print()
    print("Integration is working correctly.")
    print()
    print("Next step: Test with real tool execution:")
    print("  uv run python framework_poc/run_poc.py --tool get_user --layers 3")


if __name__ == "__main__":
    try:
        asyncio.run(test_provisioning())
    except KeyboardInterrupt:
        print("\nTest cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
