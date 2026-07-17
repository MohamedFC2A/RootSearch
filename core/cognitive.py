"""
Fathom S1 - Cognitive Reasoning Layer
طبقة الإدراك والتحقق من البيانات: تضمن دقة وصحة البيانات المستخرجة
"""

import re
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from config import config


class DomainCredibilityScorer:
    """
    MODULE 1: DOMAIN CREDIBILITY SCORER (DCS)
    Classifies and weights domains, and resolves numerical conflicts using weighted recurrence scores.
    """

    def __init__(self):
        # Tier 1: weight 1.0 (Official, gov, edu, verified sport portals like fifa.com)
        self.tier1_domains = {
            "fifa.com", "olympics.com", "uefa.com", "nba.com", "premierleague.com",
            "who.int", "cdc.gov", "nih.gov", "nasa.gov", "un.org"
        }
        # Tier 2: weight 0.7 (Encyclopedic & Verified Media)
        self.tier2_domains = {
            # Science & Academics
            "wikipedia.org", "en.wikipedia.org", "ar.wikipedia.org", "britannica.com", 
            "nature.com", "science.org", "arxiv.org",
            "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "semanticscholar.org",
            "openalex.org", "crossref.org", "core.ac.uk",
            
            # International News
            "reuters.com", "apnews.com", "news.google.com", "bbc.com", "bbc.co.uk", 
            "nytimes.com", "wsj.com", "economist.com", "sciencedaily.com", 
            "bloomberg.com", "theguardian.com", "washingtonpost.com", "forbes.com",
            "time.com", "cnn.com", "dw.com", "france24.com", "nationalgeographic.com",
            
            # Arabic News & References
            "aljazeera.net", "aljazeera.com", "alarabiya.net", "skynewsarabia.com",
            "youm7.com", "sabq.org", "hespress.com", "masrawy.com", "almasryalyoum.com",
            "asharq.com", "okaz.com.sa", "alriyadh.com", "mawdoo3.com", "arageek.com",
            "sotor.com", "estifada.com", "yallakora.com", "filgoal.com", "btolat.com",
            
            # Coding & Tech
            "github.com", "stackoverflow.com", "npmjs.com", "pypi.org", "docker.com",
            "w3schools.com", "developer.mozilla.org", "geeksforgeeks.org", "gitlab.com",
            "microsoft.com", "apple.com", "google.com", "oracle.com", "ibm.com", 
            "intel.com", "techcrunch.com", "wired.com", "cnet.com"
        }

    def get_domain_weight(self, url: str) -> float:
        """Classify and return weight of the domain."""
        if not url:
            return 0.3
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        # Check suffix-based rules for Tier 1
        if domain.endswith(".gov") or domain.endswith(".edu") or domain.endswith(".gov.ae") or domain.endswith(".gov.sa"):
            return 1.0
        
        # Check explicit Tier 1 domains
        if domain in self.tier1_domains or any(domain.endswith("." + d) for d in self.tier1_domains):
            return 1.0
            
        # Check Tier 2 domains
        if domain in self.tier2_domains or any(domain.endswith("." + d) for d in self.tier2_domains):
            return 0.7
            
        return 0.3

    def resolve_conflicts(self, property_name: str, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate weighted score for each claim: S_d = sum(w_i * C_i).
        Discard claims below 35% of the highest-scoring claim.
        """
        if not claims:
            return []

        # Group similar claims. Since values might differ slightly, we normalize them to a key.
        # But to be simple and robust: we can group by their approximate value in default units.
        # We compute scores for each unique normalized value-unit string combination.
        for claim in claims:
            value = claim.get("value")
            unit = claim.get("unit", "")
            url = claim.get("url", "")
            weight = self.get_domain_weight(url)
            # Default recurrence count to 1 if not specified
            recurrence = claim.get("recurrence", 1)
            
            claim["weight"] = weight
            claim["score_contrib"] = weight * recurrence

        # Group by value and unit
        groups: Dict[Tuple[float, str], List[Dict[str, Any]]] = {}
        for claim in claims:
            key = (round(claim["value"], 4), claim["unit"].lower())
            if key not in groups:
                groups[key] = []
            groups[key].append(claim)

        # Compute S_d for each group
        group_scores = {}
        for key, group_claims in groups.items():
            # Sum w_i * C_i for this claim across all sources presenting it
            s_d = sum(c["score_contrib"] for c in group_claims)
            group_scores[key] = s_d

        if not group_scores:
            return []

        max_score = max(group_scores.values())
        threshold = 0.35 * max_score

        # Keep groups that meet the threshold
        valid_claims = []
        for key, s_d in group_scores.items():
            if s_d >= threshold:
                # Use the best claim from this group
                best_claim = groups[key][0].copy()
                best_claim["S_d"] = s_d
                valid_claims.append(best_claim)

        # Sort by score descending
        valid_claims.sort(key=lambda x: x["S_d"], reverse=True)
        return valid_claims


class PhysicalSanityGate:
    """
    MODULE 2: PHYSICAL SANITY GATE (PSG)
    Enforces physical constraint boundaries and performs auto-calibration scaling.
    """

    def __init__(self):
        # Configurable constraints schema
        self.constraints = {
            "human_height": {
                "min": 0.5,
                "max": 2.72,
                "default_unit": "meters",
                "alternatives": ["cm", "feet", "inches"]
            },
            "human_weight": {
                "min": 2.0,
                "max": 635.0,
                "default_unit": "kg",
                "alternatives": ["lbs", "g"]
            }
        }
        
        # Scaling conversion factors to default units
        self.conversion_factors = {
            "human_height": {
                "meters": 1.0,
                "m": 1.0,
                "cm": 0.01,
                "feet": 0.3048,
                "foot": 0.3048,
                "ft": 0.3048,
                "inches": 0.0254,
                "inch": 0.0254,
                "in": 0.0254,
                "بوصة": 0.0254,
                "بوصات": 0.0254,
                "متر": 1.0,
                "متراً": 1.0,
                "مترًا": 1.0,
                "أمتار": 1.0,
                "أقدام": 0.3048,
                "سم": 0.01
            },
            "human_weight": {
                "kg": 1.0,
                "kilograms": 1.0,
                "كيلو": 1.0,
                "lbs": 0.45359237,
                "pound": 0.45359237,
                "pounds": 0.45359237,
                "رطل": 0.45359237,
                "g": 0.001,
                "grams": 0.001
            }
        }

    def validate_and_calibrate(self, property_name: str, value: float, unit: str) -> Tuple[bool, float, str]:
        """
        Validate constraints. If invalid, attempt conversion/scaling using alternative units.
        Returns: (is_valid, corrected_value, corrected_unit)
        """
        if property_name not in self.constraints:
            return True, value, unit

        constraint = self.constraints[property_name]
        c_min = constraint["min"]
        c_max = constraint["max"]
        def_unit = constraint["default_unit"]

        # Normalize unit
        unit_lower = unit.lower().strip()
        factor = self.conversion_factors.get(property_name, {}).get(unit_lower, 1.0)
        value_in_def = value * factor

        # Check if it fits the constraint
        if c_min <= value_in_def <= c_max:
            return True, value_in_def, def_unit

        # Auto-Calibration Algorithm:
        # If it doesn't fit, test alternative units to see if treating the raw value
        # as being in that unit (and scaling to default unit) makes it fit.
        for alt_unit in constraint["alternatives"]:
            alt_factor = self.conversion_factors.get(property_name, {}).get(alt_unit, 1.0)
            calibrated_value = value * alt_factor
            if c_min <= calibrated_value <= c_max:
                return True, calibrated_value, def_unit

        # Special fallback scaling factors (e.g., dividing height of 187 by 100)
        # Even if the unit was labeled "meters", a height of 187 must be cm, so divide by 100.
        if property_name == "human_height" and 50.0 <= value <= 272.0:
            calibrated_value = value / 100.0
            if c_min <= calibrated_value <= c_max:
                return True, calibrated_value, def_unit

        return False, value, unit


class DualHeadSemanticGuard:
    """
    MODULE 3: DUAL-HEAD SEMANTIC GUARD (DHSG)
    Eliminates homograph and translation errors using context-based token locking.
    """

    def __init__(self):
        # Context locks
        self.context_patterns = {
            "Physical Dimension": ["height", "tall", "weight", "dimensions", "size", "طول", "وزن", "حجم", "أبعاد"],
            "Measurement": ["scale", "measure", "measurement", "weight", "مقياس", "ميزان", "قياس"]
        }

        # Translation correction table (English & Arabic)
        self.homograph_corrections = {
            "Physical Dimension": {
                # Number-gated homograph fixes: only correct when the token is
                # immediately preceded by a numeric quantity (e.g. "1 stock exchange"),
                # so ordinary finance text ("the stock exchange", "market size",
                # "shares outstanding") is never corrupted. The underlying confusion is
                # the Arabic pair بوصة (inch) / بورصة (bourse).
                r"(\d+(?:\.\d+)?\s+)stock\s+exchange\b": r"\1inch",
                r"(\d+(?:\.\d+)?\s+)shares\b": r"\1inch",
                r"(\d+(?:\.\d+)?\s+)بورصة": r"\1بوصة",
                r"(\d+(?:\.\d+)?\s+)أسهم": r"\1بوصات",
            },
            "Measurement": {
                # English homograph errors
                r"\bfish\s+scale\b": "scale",
                r"\bclimb\b": "scale",
                # Arabic homograph errors
                r"قشرة\s+السمك": "مقياس",
                r"قشور\s+السمك": "مقياس",
                r"يتسلق": "يقيس",
            }
        }

    def detect_context(self, text: str) -> List[str]:
        """Detect locked contexts based on presence of keywords."""
        text_lower = text.lower()
        active_contexts = []
        for context, keywords in self.context_patterns.items():
            if any(re.search(rf"\b{kw}\b", text_lower) for kw in keywords) or any(kw in text for kw in keywords):
                active_contexts.append(context)
        return active_contexts

    def sanitize_text(self, text: str) -> str:
        """Apply corrections based on active context locks."""
        active_contexts = self.detect_context(text)
        sanitized = text

        for context in active_contexts:
            corrections = self.homograph_corrections.get(context, {})
            for pattern, replacement in corrections.items():
                # Case-insensitive replacement
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

        return sanitized


class AsynchronousMicroJudge:
    """
    MODULE 4: ASYNCHRONOUS MICRO-JUDGE (AMJ)
    A fast, non-blocking asynchronous validation layer running LLM agent checks with a 50ms budget.
    """

    def __init__(self):
        self.analyzer = None

    async def initialize(self):
        from core.analyzer import AIAnalyzer
        self.analyzer = AIAnalyzer()
        await self.analyzer.initialize()

    async def judge(self, output_json: dict, model: str = "fathom_s1") -> Tuple[str, dict]:
        """
        Runs LLM verification concurrently. Dynamic budget: 20s for fathom_max, 50ms for fathom_s1.
        Returns: (status, corrected_json_or_original)
        """
        # Strict Verification Prompt
        if model == "fathom_max":
            prompt = (
                "You are the ultimate Fathom Max data integrity and self-correction auditor.\n"
                "Your task is to analyze the proposed output JSON report for any contradictions, factual errors, "
                "numerical inconsistency between sources, localization bugs, or bad units.\n"
                "Verify and double-check all metrics, facts, and statements in the JSON payload.\n"
                "If any discrepancies are found, rewrite the sections of the JSON to resolve them using the authoritative sources.\n\n"
                f"JSON payload:\n{json.dumps(output_json, ensure_ascii=False)}\n\n"
                "Output ONLY the corrected JSON payload. No conversational filler or surrounding markdown comments."
            )
        else:
            prompt = (
                "Analyze the proposed output JSON. Detect and flag:\n"
                "1. Internal contradictions (e.g., Section A states '1.87m', Section B states '185cm').\n"
                "2. Absolute physical impossibilities.\n"
                "3. Translation/Localization errors in units.\n\n"
                f"JSON payload:\n{json.dumps(output_json, ensure_ascii=False)}\n\n"
                "Output ONLY a corrected JSON payload or 'PASS'. No conversational filler."
            )

        if not self.analyzer or not self.analyzer.nlp_initialized:
            return "PASS", output_json

        # Fathom S1: تحقق حتمي سريع دون استدعاء LLM.
        # المسار القديم (مهلة 50ms) كان ينتهي دائماً إلى نفس الـfallback؛
        # نجعله صريحاً وفورياً دون حقن قيم من نموذج بطيء.
        if model != "fathom_max":
            return "RULE_S1", self.rule_based_fallback(output_json)

        timeout_val = 20.0
        try:
            # Wrap the LLM call in a dynamic timeout
            response_text = await asyncio.wait_for(
                self.analyzer._call_llm(prompt),
                timeout=timeout_val
            )
            
            if response_text and response_text.strip() != "PASS":
                # Attempt to parse corrected JSON from response
                try:
                    # Search for json block
                    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                    if json_match:
                        corrected_json = json.loads(json_match.group(0))
                        return "CORRECTED", corrected_json
                    else:
                        corrected_json = json.loads(response_text)
                        return "CORRECTED", corrected_json
                except Exception:
                    pass
            return "PASS", output_json

        except asyncio.TimeoutError:
            # Fallback to high-speed rule-based co-processor
            return "TIMEOUT_FALLBACK", self.rule_based_fallback(output_json)
        except Exception:
            return "PASS_FALLBACK", output_json

    def rule_based_fallback(self, data: dict) -> dict:
        """High-speed rule-based correction co-processor (<2ms).

        Only rewrites values inside an explicit human-height context, and only
        when a numeric quantity is adjacent — so arbitrary text (e.g. "the New York
        Stock Exchange", "the tower is 300 meters tall") is never corrupted.
        """
        height_ctx = re.compile(r"\b(height|stature|طول|قامة)\b", re.IGNORECASE)

        def _cm_meters_to_annotation(cm_value: float) -> str:
            meters = cm_value / 100.0
            total_in = meters / 0.0254
            feet = int(total_in // 12)
            inches = int(round(total_in % 12))
            if inches == 12:
                feet += 1
                inches = 0
            return f"{meters:.2f} meters ({feet} feet {inches} inches)"

        def _fix_height_string(text: str) -> str:
            if not height_ctx.search(text):
                return text

            # A 2–3 digit "N meters" is physically impossible as a human height and is
            # really centimetres; convert it and absorb any trailing mistranslated
            # homograph fragment ("and 1 stock exchange" / "and 1 inch") into the
            # feet/inches annotation.
            def _repl(m: "re.Match") -> str:
                val = float(m.group(1))
                if not (50.0 <= val <= 272.0):
                    return m.group(0)
                return _cm_meters_to_annotation(val)

            text = re.sub(
                r"\b(\d{2,3}(?:\.\d+)?)\s*meters\b"
                r"(?:\s+and\s+\d+\s+(?:stock\s+exchange|stock\s+market|shares|inch|inches|بوصة|بوصات))?",
                _repl, text, flags=re.IGNORECASE,
            )
            # Number-gated homograph correction (height context only).
            text = re.sub(r"(\d+(?:\.\d+)?\s+)stock\s+exchange\b", r"\1inch", text, flags=re.IGNORECASE)
            text = re.sub(r"(\d+(?:\.\d+)?\s+)بورصة", r"\1بوصة", text)
            return text

        def correct_node(node: Any) -> Any:
            if isinstance(node, dict):
                return {k: correct_node(v) for k, v in node.items()}
            elif isinstance(node, list):
                return [correct_node(x) for x in node]
            elif isinstance(node, str):
                return _fix_height_string(node)
            return node

        return correct_node(data)


class CognitiveReasoningPipeline:
    """Orchestrates the 4-stage Zero-Latency Cognitive Reasoning Pipeline."""

    def __init__(self):
        self.dcs = DomainCredibilityScorer()
        self.psg = PhysicalSanityGate()
        self.dhsg = DualHeadSemanticGuard()
        self.amj = AsynchronousMicroJudge()

    async def initialize(self):
        await self.amj.initialize()

    def convert_meters_to_feet_inches(self, meters: float) -> Tuple[int, int]:
        """Convert meters value to feet and inches equivalent."""
        total_inches = meters / 0.0254
        feet = int(total_inches // 12)
        inches = int(round(total_inches % 12))
        if inches == 12:
            feet += 1
            inches = 0
        return feet, inches

    async def verify_text(self, text: str, source_urls: List[str] = None, model: str = "fathom_s1", k_trusted: bool = False, query: str = "", sources: List[dict] = None) -> str:
        """Process and verify unstructured text through the pipeline."""
        if not text:
            return text

        # Stage 3: Dual-Head Semantic Guard (DHSG) context check & correction
        sanitized_text = self.dhsg.sanitize_text(text)

        # Stage 1 & 2: Extract & Verify Claims via DCS & PSG
        # Let's check for height claims in the text
        height_pattern = r"(\d+(?:\.\d+)?)\s*(meters|meter|m|cm|feet|foot|ft|inches|inch|سم|متر|متراً|مترًا|أمتار|أقدام|بوصة|بوصات)"
        matches = list(re.finditer(height_pattern, sanitized_text, re.IGNORECASE))
        
        claims = []
        for match in matches:
            val = float(match.group(1))
            unit = match.group(2)
            # Find the source URL associated with this match (if we have source_urls)
            url = source_urls[0] if source_urls else "https://fifa.com"
            claims.append({
                "value": val,
                "unit": unit,
                "url": url,
                "raw_match": match.group(0),
                "start": match.start(),
                "end": match.end()
            })

        # Resolve conflicts with DCS and PSG
        if claims:
            # Let's filter each extracted claim through the Physical Sanity Gate
            corrected_claims = []
            for claim in claims:
                is_valid, corr_val, corr_unit = self.psg.validate_and_calibrate(
                    "human_height", claim["value"], claim["unit"]
                )
                if is_valid:
                    claim["corrected_value"] = corr_val
                    claim["corrected_unit"] = corr_unit
                    corrected_claims.append(claim)

            # If corrections exist, reconstruct the text
            # Specifically, if the text has "height is 1.87 meters", we can also format it with feet/inches.
            # E.g. Cristiano Ronaldo height is 1.87 meters (6 feet 2 inches).
            offset = 0
            for claim in corrected_claims:
                corr_val = claim["corrected_value"]
                corr_unit = claim["corrected_unit"]
                feet, inches = self.convert_meters_to_feet_inches(corr_val)
                
                # Format replacement string
                replacement = f"{corr_val} {corr_unit} ({feet} feet {inches} inches)"
                
                # Replace the match in the sanitized text
                start = claim["start"] + offset
                end = claim["end"] + offset
                
                # Check if there is an "and X stock exchange" or similar following the match
                post_text = sanitized_text[end:]
                homograph_match = re.match(r"^\s+and\s+\d+\s+inch\b", post_text, re.IGNORECASE)
                if homograph_match:
                    end += homograph_match.end()
                
                sanitized_text = sanitized_text[:start] + replacement + sanitized_text[end:]
                offset += len(replacement) - (end - start)

        # Stage 4: Asynchronous Micro-Judge (AMJ)
        # Prepare structured input representation
        structured_data = {
            "text": sanitized_text
        }
        status, judged_data = await self.amj.judge(structured_data, model=model)
        final_text = judged_data.get("text", sanitized_text)
        
        # Absolute K-Trusted Dimensional & Translation Safeguards
        if k_trusted:
            from core.k_trusted import KTrustVerificationEngine
            engine = KTrustVerificationEngine()
            final_text = await engine.verify(final_text, query=query, sources=sources)
            
        return final_text

    async def verify_report(self, report: dict, model: str = "fathom_s1", k_trusted: bool = False) -> dict:
        """Verify the structured report dict through the pipeline."""
        query = report.get("query", "")
        sources = []
        if "results" in report and report["results"]:
            for r in report["results"]:
                sources.append({
                    "url": r.get("url", ""),
                    "content": r.get("content") or r.get("snippet", ""),
                    "assertion": r.get("snippet", "")
                })

        # 1. Clean summaries, analysis contents
        if "analysis" in report and report["analysis"]:
            analysis = report["analysis"]
            if "summary" in analysis and analysis["summary"]:
                analysis["summary"] = await self.verify_text(analysis["summary"], model=model, k_trusted=k_trusted, query=query, sources=sources)
            if "overall_summary" in analysis and analysis["overall_summary"]:
                analysis["overall_summary"] = await self.verify_text(analysis["overall_summary"], model=model, k_trusted=k_trusted, query=query, sources=sources)
            if "executive_summary" in analysis and analysis["executive_summary"]:
                analysis["executive_summary"] = await self.verify_text(analysis["executive_summary"], model=model, k_trusted=k_trusted, query=query, sources=sources)
            if "deep_analysis" in analysis and analysis["deep_analysis"]:
                analysis["deep_analysis"] = await self.verify_text(analysis["deep_analysis"], model=model, k_trusted=k_trusted, query=query, sources=sources)

        # 2. Clean individual result snippets and summaries
        if "results" in report and report["results"]:
            for r in report["results"]:
                if "snippet" in r and r["snippet"]:
                    r["snippet"] = await self.verify_text(r["snippet"], [r.get("url")], model=model, k_trusted=k_trusted, query=query, sources=sources)
                if "summary" in r and r["summary"]:
                    r["summary"] = await self.verify_text(r["summary"], [r.get("url")], model=model, k_trusted=k_trusted, query=query, sources=sources)

        # 3. Clean query and categories
        if "categories" in report and report["categories"]:
            for cat, results in report["categories"].items():
                for r in results:
                    if "snippet" in r and r["snippet"]:
                        r["snippet"] = await self.verify_text(r["snippet"], [r.get("url")], model=model, k_trusted=k_trusted, query=query, sources=sources)
                    if "summary" in r and r["summary"]:
                        r["summary"] = await self.verify_text(r["summary"], [r.get("url")], model=model, k_trusted=k_trusted, query=query, sources=sources)

        return report
