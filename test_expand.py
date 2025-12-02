
import os

os.environ["DENAVY_MODEL_FAST"] = "test-fast-model"
os.environ["DENAVY_MODEL_SMART"] = "test-smart-model"

text = """
[template.judge]
model = "${DENAVY_MODEL_FAST}"

[[template.steps]]
plugin = "simple_llm_resolver"
config.model = "${DENAVY_MODEL_SMART}"
"""

expanded = os.path.expandvars(text)
print(expanded)
