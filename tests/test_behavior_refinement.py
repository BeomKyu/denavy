import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath("src"))

from denavy_common import CycleState, PluginResult
from plugins.prompt_refiner import PromptRefinerPlugin

def test_behavior_refinement():
    print("Testing Behavioral Refinement...")
    
    # Setup
    plugin = PromptRefinerPlugin()
    
    # Case 1: Casual Request
    print("\n--- Case 1: Casual Request ---")
    state_casual = CycleState(
        cycle_id="test-casual",
        created_at=datetime.now(),
        user_input="Tell me a funny story",
        file_contents="",
    )
    config_casual = {
        "model": "gpt-4o-mini",
        "prompt_template": "Refine: {user_input} Context: {file_contents}", # Using simplified template for mock matching
    }
    
    # Mock response for casual request - should remain mostly same
    mock_response_casual = MagicMock()
    mock_response_casual.choices = [{"message": {"content": "Tell me a funny story about a programmer."}}]
    
    with patch("plugins.prompt_refiner.completion", return_value=mock_response_casual):
        result = plugin.run(state_casual, config_casual)
        print(f"Original: {result.output['original_input']}")
        print(f"Refined:  {result.output['refined_input']}")
        # We expect it NOT to be a JSON or technical spec
        assert "{" not in result.user_input
        assert "function" not in result.user_input.lower()

    # Case 2: Technical Request
    print("\n--- Case 2: Technical Request ---")
    state_tech = CycleState(
        cycle_id="test-tech",
        created_at=datetime.now(),
        user_input="Fix the error",
        file_contents="def foo(): raise ValueError()",
    )
    
    # Mock response for technical request - should be specific
    mock_response_tech = MagicMock()
    mock_response_tech.choices = [{"message": {"content": "Fix the ValueError in foo() function."}}]
    
    with patch("plugins.prompt_refiner.completion", return_value=mock_response_tech):
        result = plugin.run(state_tech, config_casual)
        print(f"Original: {result.output['original_input']}")
        print(f"Refined:  {result.output['refined_input']}")
        assert "ValueError" in result.user_input
        
    print("\n[PASS] Behavioral verification successful.")

if __name__ == "__main__":
    test_behavior_refinement()
