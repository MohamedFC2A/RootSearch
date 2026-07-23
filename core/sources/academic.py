import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import logging

logger = logging.getLogger("RootSearch.Sources.Academic")

class HeterogeneousDataExtractor:
    @staticmethod
    async def fetch_arxiv_papers(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        url = f"http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results={max_results}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []
                
                root = ET.fromstring(resp.text)
                ns = {'arxiv': 'http://www.w3.org/2005/Atom'}
                papers = []
                for entry in root.findall('arxiv:entry', ns):
                    title_elem = entry.find('arxiv:title', ns)
                    summary_elem = entry.find('arxiv:summary', ns)
                    id_elem = entry.find('arxiv:id', ns)

                    title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else ""
                    summary = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else ""
                    paper_id = id_elem.text if id_elem is not None and id_elem.text else ""

                    pdf_link = ""
                    for link in entry.findall('arxiv:link', ns):
                        if link.attrib.get('title') == 'pdf':
                            pdf_link = link.attrib.get('href', '')
                    papers.append({
                        "title": f"[Academic Paper] {title}",
                        "url": pdf_link or paper_id,
                        "content": summary,
                        "is_pdf": True,
                        "engine": "arxiv"
                    })
                return papers
        except Exception as e:
            logger.warning(f"ArXiv fetch failed: {e}")
            return []
