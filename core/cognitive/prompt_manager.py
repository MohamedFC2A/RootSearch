import os
import yaml
from jinja2 import Template
from typing import Dict, Any, List

class PromptManager:
    def __init__(self, templates_dir: str = "config/prompts"):
        self.templates_dir = templates_dir

    def render_prompt(self, template_name: str, context_vars: Dict[str, Any]) -> Dict[str, str]:
        file_path = os.path.join(self.templates_dir, f"{template_name}.yaml")
        if not os.path.exists(file_path):
            # Fallback if path relative to working dir
            alt_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "prompts", f"{template_name}.yaml")
            if os.path.exists(alt_path):
                file_path = alt_path
            else:
                raise FileNotFoundError(f"Prompt template missing: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        system_template = Template(data.get("system_prompt", ""))
        user_template = Template(data.get("user_prompt_template", ""))

        return {
            "system": system_template.render(**context_vars),
            "user": user_template.render(**context_vars)
        }
