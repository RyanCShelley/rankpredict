"""
Dynamic Outline/Brief Service using Claude or OpenAI
Generates intelligent, SERP-driven content briefs
"""
import json
import requests
from typing import Dict, List, Optional
from app.config import OPENAI_API_KEY, ANTHROPIC_API_KEY, LLM_PROVIDER


class OutlineService:
    """
    Service for generating dynamic, SERP-driven content briefs using LLM.
    Supports both Claude (Anthropic) and OpenAI.
    """

    def __init__(self):
        self.openai_api_key = OPENAI_API_KEY
        self.anthropic_api_key = ANTHROPIC_API_KEY
        self.provider = LLM_PROVIDER

        # Determine which provider to use
        if self.provider == "claude" and self.anthropic_api_key:
            self.active_provider = "claude"
        elif self.openai_api_key:
            self.active_provider = "openai"
        elif self.anthropic_api_key:
            self.active_provider = "claude"
        else:
            self.active_provider = None

    def generate_outline(
        self,
        keyword: str,
        serp_results: List[Dict],
        serp_medians: Dict[str, float],
        intent_analysis: Dict,
        content_type: str = "new",
        serp_features: Optional[Dict] = None,
        existing_content: Optional[Dict] = None
    ) -> Dict:
        """
        Generate dynamic content brief using LLM based on SERP analysis

        Args:
            keyword: Search keyword
            serp_results: Enriched SERP results with content
            serp_medians: SERP median values
            intent_analysis: Intent analysis from IntentService
            content_type: "new" or "existing"
            serp_features: Extracted SERP features (PAA, related, etc.)
            existing_content: For existing content mode, the analyzed content data

        Returns:
            Dictionary with dynamic brief structure
        """
        if not self.active_provider:
            raise Exception("No LLM API key configured. Please set ANTHROPIC_API_KEY or OPENAI_API_KEY.")

        # Prepare comprehensive SERP data for LLM
        serp_context = self._prepare_comprehensive_serp_context(
            keyword, serp_results, serp_medians, serp_features
        )

        if content_type == "existing":
            return self._generate_optimization_plan(keyword, serp_context, serp_medians, existing_content, serp_features)
        else:
            return self._generate_content_brief(keyword, serp_context, serp_medians, intent_analysis, serp_features)

    def _prepare_comprehensive_serp_context(
        self,
        keyword: str,
        serp_results: List[Dict],
        serp_medians: Dict[str, float],
        serp_features: Optional[Dict]
    ) -> str:
        """Prepare comprehensive SERP context including all features"""
        lines = [
            f"# SERP Analysis for: {keyword}",
            "",
            "## SERP Metrics (Top 10 Medians)",
            f"- Median Word Count: {serp_medians.get('word_count', 0):.0f}",
            f"- Median Domain Trust: {serp_medians.get('dt', 0):.1f}",
            f"- Median Referring Domains: {serp_medians.get('referring_domains', 0):.0f}",
            f"- Median Flesch Reading Ease: {serp_medians.get('flesch_reading_ease_score', 0):.1f}",
            f"- Median Schema Types: {serp_medians.get('total_schema_types', 0):.0f}",
            "",
        ]

        # SERP Features Present
        if serp_features:
            lines.append("## SERP Features Present")
            features_present = serp_features.get("serp_features_present", [])
            if features_present:
                for feature in features_present:
                    lines.append(f"- {feature.replace('_', ' ').title()}")
            else:
                lines.append("- Standard organic results only")
            lines.append("")

            # Featured Snippet
            if serp_features.get("featured_snippet"):
                fs = serp_features["featured_snippet"]
                lines.append("## Featured Snippet")
                lines.append(f"**Type:** {fs.get('type', 'paragraph')}")
                if fs.get("title"):
                    lines.append(f"**Title:** {fs.get('title')}")
                if fs.get("snippet"):
                    lines.append(f"**Content:** {fs.get('snippet')[:500]}...")
                if fs.get("list"):
                    lines.append("**List Items:**")
                    for item in fs.get("list", [])[:5]:
                        lines.append(f"  - {item}")
                lines.append("")

            # People Also Ask
            if serp_features.get("people_also_ask"):
                lines.append("## People Also Ask (PAA)")
                lines.append("These questions MUST be addressed in your content:")
                for paa in serp_features["people_also_ask"]:
                    question = paa.get("question", "")
                    snippet = paa.get("snippet", "")[:200]
                    if question:
                        lines.append(f"- **Q:** {question}")
                        if snippet:
                            lines.append(f"  **A:** {snippet}...")
                lines.append("")

            # Related Searches
            if serp_features.get("related_searches"):
                lines.append("## Related Searches")
                lines.append("These topics indicate related user intent:")
                for rs in serp_features["related_searches"][:10]:
                    lines.append(f"- {rs}")
                lines.append("")

            # Knowledge Panel
            if serp_features.get("knowledge_panel"):
                kp = serp_features["knowledge_panel"]
                lines.append("## Knowledge Panel")
                if kp.get("title"):
                    lines.append(f"**Entity:** {kp.get('title')}")
                if kp.get("type"):
                    lines.append(f"**Type:** {kp.get('type')}")
                if kp.get("description"):
                    lines.append(f"**Description:** {kp.get('description')[:300]}...")
                if kp.get("people_also_search_for"):
                    lines.append("**Related entities:**")
                    for entity in kp.get("people_also_search_for", [])[:5]:
                        lines.append(f"  - {entity}")
                lines.append("")

            # Local Pack
            if serp_features.get("local_pack"):
                lines.append("## Local Pack Present")
                lines.append("This indicates local intent - consider local optimization.")
                lines.append("")

            # Video Results
            if serp_features.get("video_results"):
                lines.append("## Video Results")
                lines.append("Video content is ranking - consider video content or embedding.")
                for v in serp_features["video_results"][:3]:
                    lines.append(f"- {v.get('title', '')} ({v.get('platform', '')})")
                lines.append("")

        # Top Ranking Results
        lines.append("## Top 10 Ranking Results")
        for i, result in enumerate(serp_results[:10], 1):
            title = result.get("title", "")
            url = result.get("url", result.get("link", ""))
            snippet = result.get("snippet", "")[:200]
            wc = result.get("word_count", 0)
            dt = result.get("dt", 0)

            lines.append(f"### {i}. {title}")
            lines.append(f"**URL:** {url}")
            lines.append(f"**Snippet:** {snippet}...")
            lines.append(f"**Word Count:** {wc} | **Domain Trust:** {dt:.1f}")
            lines.append("")

        return "\n".join(lines)

    def _generate_content_brief(
        self,
        keyword: str,
        serp_context: str,
        serp_medians: Dict[str, float],
        intent_analysis: Dict,
        serp_features: Optional[Dict]
    ) -> Dict:
        """Generate comprehensive content brief using Claude or OpenAI"""

        # Build PAA questions list for explicit inclusion
        paa_questions = []
        if serp_features and serp_features.get("people_also_ask"):
            paa_questions = [p.get("question", "") for p in serp_features["people_also_ask"] if p.get("question")]

        related_searches = []
        if serp_features and serp_features.get("related_searches"):
            related_searches = serp_features["related_searches"][:10]

        prompt = f"""You are a senior SEO content strategist. Analyze the following SERP data and create a comprehensive content brief that will help the content rank in the top 10.

{serp_context}

## Intent Analysis
- **TARGET Intent Type:** {intent_analysis.get('intent_type', 'informational')} {"(USER SPECIFIED - build content for THIS intent)" if intent_analysis.get('user_override') else "(detected from SERP)"}
- **Content Format:** {intent_analysis.get('content_format', 'article')}
- **Reasoning:** {intent_analysis.get('reasoning', '')}

CRITICAL INSTRUCTION - PAGE FORMAT BY INTENT:
The TARGET intent type OVERRIDES what the SERP shows. Even if the SERP is full of listicles/comparisons, you MUST create content matching the TARGET intent:

**TRANSACTIONAL** (Service/Product Page):
- DO NOT create a listicle or "best of" list
- Create a SERVICE PAGE structure: Hero section → What we do → How we help → Our process → Why choose us → Case studies/results → Pricing/packages → FAQ → CTA
- H1 should be benefit-focused, NOT "X Best..." (e.g., "AI Search Optimization Services" not "15 Best AI Search Agencies")
- Include conversion elements: testimonials, trust badges, guarantees, clear CTAs
- Focus on YOUR service, not comparing others

**COMMERCIAL** (Comparison/Research Content):
- Create comparison content, "best of" lists, buying guides, reviews
- Help users evaluate options and make decisions
- Include pros/cons, pricing comparisons, feature tables

**INFORMATIONAL** (Educational Content):
- Create how-to guides, explanations, definitions, tutorials
- Focus on teaching and answering questions
- Include examples, step-by-step instructions, visuals

**NAVIGATIONAL** (Brand/Direct Answer):
- Direct answers, brand-focused content
- Contact information, location, credentials

## Your Task

Create a detailed content brief that addresses:

1. **Content Strategy Summary**
   - Recommended word count: Use EXACTLY the SERP median word count of {serp_medians.get('word_count', 1500):.0f} words
   - Target readability: Use EXACTLY the SERP median Flesch score of {serp_medians.get('flesch_reading_ease_score', 60):.0f} (give range ±5)
   - Schema markup to implement
   - Key differentiators from existing content

2. **Search Intent Matching**
   - What the searcher REALLY wants (based on SERP analysis)
   - Content format that will best serve this intent
   - User journey stage and expectations

3. **Must-Answer Questions**
   - All People Also Ask questions MUST be addressed
   - Additional questions identified from SERP analysis
   - Format recommendations for each (paragraph, list, table, etc.)

4. **Content Outline**
   - H1 title (optimized for search AND click-through, matching the TARGET intent format)
   - H2 sections with brief descriptions (USE SERVICE PAGE STRUCTURE for transactional: Hero, Services, Process, Results, Pricing, FAQ, CTA)
   - H3 subsections where appropriate
   - Suggested content elements per section (for transactional: testimonials, case studies, CTAs, trust signals)

5. **Semantic Coverage**
   - Topics that MUST be covered (from competitor analysis)
   - Related topics to include for topical authority
   - Entities to mention for semantic relevance

6. **SERP Feature Optimization**
   - How to optimize for featured snippet (if applicable)
   - FAQ schema opportunities
   - Other SERP feature opportunities

7. **Competitive Differentiation**
   - What competitors are missing
   - Unique angles to explore
   - How to make content more comprehensive/useful

Return the brief as JSON with this exact structure:
{{
  "title_recommendation": "<optimized H1 title>",
  "meta_description": "<compelling meta description under 160 chars>",
  "content_strategy": {{
    "target_word_count": {serp_medians.get('word_count', 1500):.0f},
    "min_word_count": {serp_medians.get('word_count', 1500) * 0.9:.0f},
    "readability_target": "{max(serp_medians.get('flesch_reading_ease_score', 60) - 5, 0):.0f}-{min(serp_medians.get('flesch_reading_ease_score', 60) + 5, 100):.0f}",
    "schema_types": ["<type1>", "<type2>"],
    "key_differentiators": ["<diff1>", "<diff2>"]
  }},
  "search_intent": {{
    "primary_intent": "<intent>",
    "user_expectation": "<what they want>",
    "content_format": "<best format>",
    "user_journey_stage": "<awareness/consideration/decision>"
  }},
  "questions_to_answer": [
    {{
      "question": "<question>",
      "priority": "<high/medium/low>",
      "format": "<paragraph/list/table/definition>",
      "placement": "<section to place in>"
    }}
  ],
  "outline": {{
    "sections": [
      {{
        "h2": "<section heading>",
        "description": "<what to cover>",
        "word_count_target": <number>,
        "h3_subsections": ["<sub1>", "<sub2>"],
        "content_elements": ["<element type>"],
        "key_points": ["<point1>", "<point2>"]
      }}
    ]
  }},
  "semantic_coverage": {{
    "must_cover_topics": ["<topic1>", "<topic2>"],
    "related_topics": ["<topic1>", "<topic2>"],
    "entities_to_mention": ["<entity1>", "<entity2>"]
  }},
  "serp_optimization": {{
    "featured_snippet_strategy": "<how to win it>",
    "faq_schema_questions": ["<q1>", "<q2>"],
    "other_opportunities": ["<opportunity1>"]
  }},
  "competitive_gaps": {{
    "missing_from_competitors": ["<gap1>", "<gap2>"],
    "unique_angles": ["<angle1>", "<angle2>"],
    "comprehensiveness_improvements": ["<improvement1>"]
  }}
}}

Return ONLY valid JSON, no markdown code blocks or other formatting."""

        try:
            if self.active_provider == "claude":
                response_text = self._call_claude(prompt)
            else:
                response_text = self._call_openai(prompt)

            # Parse JSON response
            brief_data = self._parse_json_response(response_text)

            # Format into our standard response
            return self._format_brief_response(keyword, brief_data, serp_medians, intent_analysis, serp_features)

        except Exception as e:
            print(f"Error generating brief: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Error generating content brief: {str(e)}")

    def _call_claude(self, prompt: str) -> str:
        """Call Claude API"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.anthropic_api_key)

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            return message.content[0].text

        except ImportError:
            # Fallback to requests if anthropic not installed
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"]

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are an expert SEO content strategist. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 4000
            },
            timeout=120
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]

    def _parse_json_response(self, response_text: str) -> Dict:
        """Parse JSON from LLM response"""
        import re

        # Try direct parse
        try:
            return json.loads(response_text)
        except:
            pass

        # Try to extract from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Try to find JSON object
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        raise ValueError("Could not parse JSON from LLM response")

    def _format_brief_response(
        self,
        keyword: str,
        brief_data: Dict,
        serp_medians: Dict[str, float],
        intent_analysis: Dict,
        serp_features: Optional[Dict]
    ) -> Dict:
        """Format LLM response into our standard brief structure"""

        # Build sections from outline
        sections = []
        for section in brief_data.get("outline", {}).get("sections", []):
            sections.append({
                "heading": section.get("h2", ""),
                "h3_subsections": section.get("h3_subsections", []),
                "topics": section.get("content_elements", []),
                "word_count_target": section.get("word_count_target", 0),
                "entities": [],
                "semantic_focus": section.get("description", ""),
                "key_points": section.get("key_points", [])
            })

        return {
            "keyword": keyword,
            "intent_analysis": intent_analysis,
            "title_recommendation": brief_data.get("title_recommendation", f"Complete Guide to {keyword}"),
            "meta_description": brief_data.get("meta_description", ""),
            "content_strategy": brief_data.get("content_strategy", {}),
            "search_intent": brief_data.get("search_intent", {}),
            "questions_to_answer": brief_data.get("questions_to_answer", []),
            "serp_patterns": {
                "content_strategy": brief_data.get("content_strategy", {}),
                "gap_analysis": brief_data.get("competitive_gaps", {})
            },
            "sections": sections,
            "word_count_target": brief_data.get("content_strategy", {}).get("target_word_count", int(serp_medians.get("word_count", 2000) * 1.15)),
            "topics": brief_data.get("semantic_coverage", {}).get("must_cover_topics", []),
            "related_topics": brief_data.get("semantic_coverage", {}).get("related_topics", []),
            "entities": brief_data.get("semantic_coverage", {}).get("entities_to_mention", []),
            "structure_type": intent_analysis.get("content_format", "article"),
            "structure_reasoning": brief_data.get("competitive_gaps", {}).get("unique_angles", []),
            "serp_optimization": brief_data.get("serp_optimization", {}),
            "competitive_gaps": brief_data.get("competitive_gaps", {}),
            # Include raw SERP features for frontend display
            "serp_features": serp_features or {}
        }

    def _generate_optimization_plan(
        self,
        keyword: str,
        serp_context: str,
        serp_medians: Dict[str, float],
        existing_content: Optional[Dict] = None,
        serp_features: Optional[Dict] = None
    ) -> Dict:
        """Generate comprehensive optimization plan for existing content"""

        # If we don't have existing content data, return basic structure
        if not existing_content:
            return {
                "keyword": keyword,
                "optimization_mode": True,
                "serp_analysis": serp_context,
                "sections": [],
                "word_count_target": int(serp_medians.get("word_count", 1500))
            }

        # Build comprehensive optimization prompt
        current_wc = existing_content.get("word_count", 0)
        target_wc = serp_medians.get("word_count", 1500)
        current_flesch = existing_content.get("flesch_reading_ease_score", 50)
        target_flesch = serp_medians.get("flesch_reading_ease_score", 60)

        # Word count strategy
        if current_wc < target_wc * 0.8:
            wc_strategy = f"INCREASE word count by {int(target_wc - current_wc)} words to match competitors"
        elif current_wc > target_wc * 1.3:
            wc_strategy = f"Consider TRIMMING content - you have {int(current_wc - target_wc)} more words than competitors"
        else:
            wc_strategy = "Word count is competitive - focus on quality over quantity"

        # Readability strategy
        if current_flesch < target_flesch - 10:
            readability_strategy = f"SIMPLIFY content - current readability ({current_flesch:.0f}) is harder than competitors ({target_flesch:.0f}). Use shorter sentences and simpler words."
        elif current_flesch > target_flesch + 10:
            readability_strategy = f"Content may be TOO simple ({current_flesch:.0f} vs {target_flesch:.0f}). Consider adding more technical depth."
        else:
            readability_strategy = "Readability aligns with competitor content"

        # Current headings
        current_h2s = existing_content.get("h2_headings", [])
        h2_context = "\n".join([f"- {h}" for h in current_h2s[:10]]) if current_h2s else "No H2 headings found"

        # Page content for annotation
        page_text = existing_content.get("page_text", "")[:5000]

        prompt = f"""You are a senior SEO content strategist. Analyze this EXISTING content and create a detailed optimization plan to improve rankings.

{serp_context}

## CURRENT PAGE ANALYSIS
**URL:** {existing_content.get('url', 'Unknown')}
**Current Word Count:** {current_wc}
**Target Word Count:** {target_wc:.0f}
**Word Count Strategy:** {wc_strategy}

**Current Readability (Flesch):** {current_flesch:.0f}
**Target Readability:** {target_flesch:.0f}
**Readability Strategy:** {readability_strategy}

**Current H2 Headings:**
{h2_context}

**Current Page Content (excerpt):**
{page_text[:3000]}

## YOUR TASK

Create a comprehensive optimization brief for this EXISTING content that includes:

1. **Recommended Title** - An optimized H1 that will perform better for this keyword

2. **Content Strategy Analysis**
   - Word count: Current vs Target with action (increase/decrease/maintain)
   - Readability: Current vs Target with specific suggestions
   - Schema types needed

3. **Annotated Content Improvements**
   - List specific text changes needed with the format:
     - ORIGINAL: "current text excerpt"
     - IMPROVED: "suggested replacement text"
     - REASON: "why this change helps SEO"
   - Include 5-10 specific text improvements

4. **Content Outline** - What the optimized page structure should look like:
   - H2 sections (mark existing sections to KEEP, REMOVE, or MODIFY)
   - NEW sections to ADD
   - Target word count per section

5. **Semantic Coverage** - Topics and entities to add/improve

6. **SERP Feature Optimization** - How to win featured snippets, PAA, etc.

7. **Competitive Gaps** - What competitors do that this page doesn't

Return as JSON:
{{
  "title_recommendation": "<optimized H1>",
  "meta_description": "<optimized meta under 160 chars>",
  "content_strategy": {{
    "word_count_current": {current_wc},
    "word_count_target": {target_wc:.0f},
    "word_count_action": "<INCREASE/DECREASE/MAINTAIN>",
    "word_count_delta": <number to add or remove>,
    "readability_current": {current_flesch:.0f},
    "readability_target": "{max(target_flesch - 5, 0):.0f}-{min(target_flesch + 5, 100):.0f}",
    "readability_action": "<SIMPLIFY/ADD_DEPTH/MAINTAIN>",
    "schema_types": ["<type1>", "<type2>"]
  }},
  "content_annotations": [
    {{
      "original_text": "<current text excerpt>",
      "improved_text": "<suggested replacement>",
      "reason": "<why this helps>",
      "priority": "<high/medium/low>"
    }}
  ],
  "outline": {{
    "sections": [
      {{
        "h2": "<section heading>",
        "status": "<KEEP/MODIFY/ADD/REMOVE>",
        "description": "<what to do with this section>",
        "word_count_target": <number>,
        "h3_subsections": ["<sub1>", "<sub2>"],
        "key_points": ["<point1>", "<point2>"]
      }}
    ]
  }},
  "semantic_coverage": {{
    "must_cover_topics": ["<topic1>", "<topic2>"],
    "missing_entities": ["<entity1>", "<entity2>"],
    "topics_to_strengthen": ["<topic1>", "<topic2>"]
  }},
  "serp_optimization": {{
    "featured_snippet_strategy": "<how to win it>",
    "faq_schema_questions": ["<q1>", "<q2>"],
    "paa_questions_to_answer": ["<q1>", "<q2>"]
  }},
  "competitive_gaps": {{
    "missing_from_page": ["<gap1>", "<gap2>"],
    "strengths_to_keep": ["<strength1>", "<strength2>"],
    "quick_wins": ["<win1>", "<win2>"]
  }}
}}

Return ONLY valid JSON, no markdown code blocks."""

        try:
            if self.active_provider == "claude":
                response_text = self._call_claude(prompt)
            else:
                response_text = self._call_openai(prompt)

            brief_data = self._parse_json_response(response_text)

            # Format sections for response
            sections = []
            for section in brief_data.get("outline", {}).get("sections", []):
                sections.append({
                    "heading": section.get("h2", ""),
                    "status": section.get("status", "KEEP"),
                    "h3_subsections": section.get("h3_subsections", []),
                    "word_count_target": section.get("word_count_target", 0),
                    "semantic_focus": section.get("description", ""),
                    "key_points": section.get("key_points", []),
                    "topics": []
                })

            return {
                "keyword": keyword,
                "optimization_mode": True,
                "existing_url": existing_content.get("url", ""),
                "title_recommendation": brief_data.get("title_recommendation", ""),
                "meta_description": brief_data.get("meta_description", ""),
                "content_strategy": brief_data.get("content_strategy", {
                    "word_count_current": current_wc,
                    "word_count_target": int(target_wc),
                    "word_count_action": "INCREASE" if current_wc < target_wc else "MAINTAIN",
                    "readability_current": int(current_flesch),
                    "readability_target": f"{int(target_flesch-5)}-{int(target_flesch+5)}"
                }),
                "content_annotations": brief_data.get("content_annotations", []),
                "sections": sections,
                "word_count_target": int(target_wc),
                "topics": brief_data.get("semantic_coverage", {}).get("must_cover_topics", []),
                "related_topics": brief_data.get("semantic_coverage", {}).get("topics_to_strengthen", []),
                "entities": brief_data.get("semantic_coverage", {}).get("missing_entities", []),
                "structure_type": "optimization",
                "serp_optimization": brief_data.get("serp_optimization", {}),
                "competitive_gaps": brief_data.get("competitive_gaps", {}),
                "serp_features": serp_features or {},
                "intent_analysis": {"intent_type": "optimization", "content_format": "existing_page"}
            }

        except Exception as e:
            print(f"Error generating optimization plan: {e}")
            import traceback
            traceback.print_exc()

            # Return basic structure on error
            return {
                "keyword": keyword,
                "optimization_mode": True,
                "existing_url": existing_content.get("url", ""),
                "content_strategy": {
                    "word_count_current": current_wc,
                    "word_count_target": int(target_wc),
                    "word_count_action": "INCREASE" if current_wc < target_wc else "MAINTAIN",
                    "word_count_delta": int(target_wc - current_wc),
                    "readability_current": int(current_flesch),
                    "readability_target": f"{int(target_flesch-5)}-{int(target_flesch+5)}",
                    "readability_action": "SIMPLIFY" if current_flesch < target_flesch - 10 else "MAINTAIN"
                },
                "sections": [],
                "word_count_target": int(target_wc),
                "topics": [],
                "entities": [],
                "serp_features": serp_features or {},
                "intent_analysis": {"intent_type": "optimization"}
            }


def get_outline_service() -> OutlineService:
    """Get outline service instance"""
    return OutlineService()
