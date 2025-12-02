
import sys
import os
from pathlib import Path

# Add src to sys.path
src_path = Path("src").absolute()
sys.path.insert(0, str(src_path))

from denavy_core.template_loader import TemplateLoader

# Set env vars for testing
os.environ["DENAVY_MODEL_FAST"] = "test-fast-model"
os.environ["DENAVY_MODEL_SMART"] = "test-smart-model"

# Load template
loader = TemplateLoader(Path("templates"))
try:
    data = loader.load("default_template")
    print(f"Judge Model: {data['template']['judge']['model']}")
    
    steps = data["template"]["steps"]
    for step in steps:
        if "config" in step and "model" in step["config"]:
            print(f"Step {step['plugin']} Model: {step['config']['model']}")
            
except Exception as e:
    print(f"Error: {e}")
