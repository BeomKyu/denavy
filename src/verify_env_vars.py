
import os
from pathlib import Path
from denavy_core.template_loader import TemplateLoader

# Set env vars for testing
os.environ["DENAVY_MODEL_FAST"] = "test-fast-model"
os.environ["DENAVY_MODEL_SMART"] = "test-smart-model"

# Load template
loader = TemplateLoader(Path("../templates"))
try:
    data = loader.load("default_template")
    print("Judge Model:", data["template"]["judge"]["model"])
    
    steps = data["template"]["steps"]
    for step in steps:
        if step["plugin"] == "simple_llm_resolver":
            print("Resolver Model:", step["config"]["model"])
            
except Exception as e:
    print(f"Error: {e}")
