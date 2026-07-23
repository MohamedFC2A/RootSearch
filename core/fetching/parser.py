import trafilatura
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

class ContentCleaner:
    @staticmethod
    def extract_clean_text(raw_html: str, url: str) -> Optional[Dict[str, Any]]:
        if not raw_html:
            return None

        # Primary extraction using Trafilatura (State-of-the-art text extraction)
        try:
            extracted_text = trafilatura.extract(
                raw_html,
                url=url,
                include_links=False,
                include_images=False,
                include_tables=True,
                output_format="markdown",
                favor_precision=True
            )

            if extracted_text and len(extracted_text.strip()) > 100:
                return {
                    "text": extracted_text,
                    "cleaner": "trafilatura"
                }
        except Exception:
            pass

        # Fallback to BeautifulSoup DOM Pruning if Trafilatura fails
        soup = BeautifulSoup(raw_html, "html.parser")
        
        # Remove noisy HTML elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
            element.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 30]
        cleaned_text = "\n".join(lines)

        if len(cleaned_text) > 100:
            return {
                "text": cleaned_text,
                "cleaner": "bs4_fallback"
            }

        return None
