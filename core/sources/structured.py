import json
from bs4 import BeautifulSoup
from typing import List, Dict, Any

class StructuredDataExtractor:
    @staticmethod
    def extract_json_ld(html_content: str) -> List[Dict[str, Any]]:
        """Extract JSON-LD microdata scripts from HTML."""
        if not html_content:
            return []
        
        soup = BeautifulSoup(html_content, "html.parser")
        structured_items = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if script.string:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        structured_items.extend(data)
                    elif isinstance(data, dict):
                        structured_items.append(data)
            except Exception:
                continue
        return structured_items

    @staticmethod
    def extract_open_graph(html_content: str) -> Dict[str, str]:
        """Extract OpenGraph metadata tags from HTML."""
        if not html_content:
            return {}

        soup = BeautifulSoup(html_content, "html.parser")
        og_data = {}
        for tag in soup.find_all("meta"):
            prop = tag.get("property", "") or tag.get("name", "")
            if prop.startswith("og:"):
                og_data[prop[3:]] = tag.get("content", "")
        return og_data
