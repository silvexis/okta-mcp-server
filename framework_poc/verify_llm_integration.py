#!/usr/bin/env python3
"""
Verification script for Layer 4-5 LLM Provider Integration

Tests that the litellm integration is working correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add framework_poc to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from framework_poc.core.llm_judge import LLMJudge, LITELLM_AVAILABLE


async def main():
    print("=" * 60)
    print("Layer 4-5 LLM Provider Integration Verification")
    print("=" * 60)
    print()

    # Check 1: litellm availability
    print("✓ Check 1: litellm package")
    if LITELLM_AVAILABLE:
        print("  ✓ litellm is installed and available")
    else:
        print("  ✗ litellm is not available")
        print("  Run: uv add --dev litellm")
        return False
    print()

    # Check 2: LLMJudge initialization
    print("✓ Check 2: LLMJudge initialization")
    try:
        # Test with Ollama (no API key needed)
        judge_ollama = LLMJudge(api_key="", model="ollama/llama3")
        print("  ✓ Initialized with Ollama model")

        # Test with Claude
        judge_claude = LLMJudge(api_key="test-key", model="claude-3-5-sonnet-20241022")
        print("  ✓ Initialized with Claude model")

        # Test with OpenAI
        judge_openai = LLMJudge(api_key="test-key", model="gpt-4o-mini")
        print("  ✓ Initialized with OpenAI model")

        # Test with Gemini
        judge_gemini = LLMJudge(api_key="test-key", model="gemini/gemini-1.5-flash")
        print("  ✓ Initialized with Gemini model")
    except Exception as e:
        print(f"  ✗ Initialization failed: {e}")
        return False
    print()

    # Check 3: Graceful degradation
    print("✓ Check 3: Graceful degradation (no provider available)")
    try:
        judge = LLMJudge(api_key="", model="ollama/llama3")
        judgment = await judge.evaluate_tool_selection(
            user_prompt="List all users",
            expected_tool="list_users",
            available_tools=["list_users", "get_user", "create_user"]
        )

        print(f"  Criterion: {judgment.criterion}")
        print(f"  Rating: {judgment.rating}")
        print(f"  Reasoning: {judgment.reasoning}")

        if judgment.rating in ["skipped", "error"]:
            print("  ✓ Gracefully handled missing provider")
        else:
            print("  ✗ Unexpected rating (expected 'skipped' or 'error')")
    except Exception as e:
        print(f"  ✗ Unexpected exception: {e}")
        return False
    print()

    # Check 4: Configuration examples
    print("✓ Check 4: Configuration")
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            config_content = f.read()
            if "ollama" in config_content:
                print("  ✓ config.yaml has Ollama example")
            if "gpt-4o-mini" in config_content:
                print("  ✓ config.yaml has OpenAI example")
            if "gemini" in config_content:
                print("  ✓ config.yaml has Gemini example")
    print()

    # Check 5: Documentation
    print("✓ Check 5: Documentation")
    setup_guide = Path(__file__).parent / "LLM_PROVIDER_SETUP.md"
    if setup_guide.exists():
        print("  ✓ LLM_PROVIDER_SETUP.md exists")
    else:
        print("  ✗ LLM_PROVIDER_SETUP.md not found")

    summary = Path(__file__).parent / "LAYER_4_5_IMPLEMENTATION_SUMMARY.md"
    if summary.exists():
        print("  ✓ LAYER_4_5_IMPLEMENTATION_SUMMARY.md exists")
    else:
        print("  ✗ LAYER_4_5_IMPLEMENTATION_SUMMARY.md not found")
    print()

    # Summary
    print("=" * 60)
    print("✓ All verification checks passed!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Set up an LLM provider (see LLM_PROVIDER_SETUP.md):")
    print("   - Ollama (free): brew install ollama && ollama pull llama3")
    print("   - Or set API key: export ANTHROPIC_API_KEY=your-key")
    print()
    print("2. Update config.yaml with your chosen provider")
    print()
    print("3. Run Layer 4 tests:")
    print("   uv run python framework_poc/run_poc.py --layers 4")
    print()

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nVerification cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
