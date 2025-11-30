import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath("src"))

from denavy_common import CycleState, PluginResult
from plugins.prompt_refiner import PromptRefinerPlugin

def test_prompt_refiner():
    print("Testing PromptRefinerPlugin...")
    
    # Setup
    plugin = PromptRefinerPlugin()
    state = CycleState(
        cycle_id="test-cycle",
        created_at=datetime.now(),
        user_input="Fix the error in auth",
        file_contents="def login():\n    raise ValueError('Invalid token')",
    )
    config = {
        "model": "gpt-4o-mini",
        "prompt_template": "Refine: {user_input} Context: {file_contents}",
    }
    
    # Mock litellm.completion
    mock_response = MagicMock()
    mock_response.choices = [{"message": {"content": "Update auth.py to handle ValueError in login()"}}]
    
    with patch("plugins.prompt_refiner.completion", return_value=mock_response) as mock_completion:
        # Execute
        result = plugin.run(state, config)
        
        # Verify
        print(f"Original Input: {result.output['original_input']}")
        print(f"Refined Input: {result.output['refined_input']}")
        
        assert result.status == "success"
        assert result.user_input == "Update auth.py to handle ValueError in login()"
        assert state.user_input == "Update auth.py to handle ValueError in login()"
        assert state.get_scratchpad("original_user_input") == "Fix the error in auth"
        
        print("[PASS] PromptRefinerPlugin verification successful.")

if __name__ == "__main__":
    test_prompt_refiner()
