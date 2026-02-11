"""
Query Fanning Service

Uses Claude or OpenAI to generate semantically related queries for a given keyword.
Based on the Query Fan-Out Generator concept.
"""
import json
import requests
from typing import List, Tuple, Optional
from app.config import ANTHROPIC_API_KEY, OPENAI_API_KEY, LLM_PROVIDER


def get_active_provider():
    """Determine which LLM provider to use."""
    if LLM_PROVIDER == "claude" and ANTHROPIC_API_KEY:
        return "claude"
    elif OPENAI_API_KEY:
        return "openai"
    elif ANTHROPIC_API_KEY:
        return "claude"
    return None


async def generate_stage_queries(
    stage: str,
    topic: str,
    existing_queries: List[str],
    persona: Optional[dict] = None
) -> Tuple[List[str], str]:
    """
    Generate fan-out queries specific to a buyer journey stage.

    Args:
        stage: The buyer journey stage (e.g., "Decision / Action")
        topic: The core topic being analyzed
        existing_queries: List of queries already in this stage (to avoid duplicates)

    Returns:
        Tuple of (list of new queries, reasoning)
    """
    provider = get_active_provider()
    if not provider:
        raise ValueError("No LLM API key configured. Please set ANTHROPIC_API_KEY or OPENAI_API_KEY.")

    stage_context = {
        "Decision / Action": "Focus on queries where users are ready to buy, convert, or take action. Include queries with words like 'buy', 'order', 'schedule', 'book', 'get quote', 'pricing', 'cost', 'near me'.",
        "Validation / Trust": "Focus on queries where users are validating their choice. Include queries with 'reviews', 'testimonials', 'ratings', 'best', 'top rated', 'vs', 'comparison', 'pros and cons'.",
        "Narrowing / Evaluation": "Focus on queries where users are narrowing down options. Include queries with specific features, specifications, 'for [use case]', 'with [feature]', brand names, model numbers.",
        "Exploration / Consideration": "Focus on queries where users are exploring options. Include queries like 'types of', 'options for', 'alternatives to', 'how to choose', 'what to look for'.",
        "Trigger / Awareness": "Focus on early-stage queries where users are just becoming aware of a need. Include 'what is', 'why', 'how does', 'benefits of', 'signs of', informational queries."
    }

    context = stage_context.get(stage, "")

    persona_block = ""
    if persona and persona.get("expanded"):
        persona_block = f"""
Target Persona: {persona['expanded']}

Generate queries that this persona would actually search for, using their language and addressing their specific needs.
"""

    prompt = f"""You are an expert at generating search queries for SEO content strategy.
Your task is to generate new search queries that fit a specific buyer journey stage.

Stage: {stage}
Stage Description: {context}
Topic: {topic}
{persona_block}
Generate 6-8 NEW search queries that:
1. Are highly relevant to the topic "{topic}"
2. Match the intent of the buyer journey stage "{stage}"
3. Are NOT duplicates of existing queries
4. Represent real searches people make
5. Are specific and actionable for content creation
6. Do NOT include any years, dates, or time references (no "2023", "2024", "2025", etc.)

IMPORTANT: Never include years or dates in queries. Keep queries evergreen and timeless.

Existing queries to avoid duplicating:
{json.dumps(existing_queries[:20], indent=2)}

Return your response as a JSON object with exactly these fields:
{{
    "fan_out": ["query1", "query2", ...],
    "reasoning": "Brief explanation of why these queries were chosen"
}}

Return ONLY the JSON object, no other text."""

    if provider == "claude":
        response_text = _call_claude(prompt)
    else:
        response_text = _call_openai(prompt)

    # Parse the response
    parsed = _parse_json_response(response_text)

    fan_out = parsed.get("fan_out", [])
    reasoning = parsed.get("reasoning", "")

    # Filter out any duplicates
    existing_lower = {q.lower() for q in existing_queries}
    new_queries = [q for q in fan_out if q.lower() not in existing_lower]

    return new_queries, reasoning


def _call_claude(prompt: str) -> str:
    """Call Claude API."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
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
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return result["content"][0]["text"]


def _call_openai(prompt: str) -> str:
    """Call OpenAI API."""
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are an expert SEO content strategist. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1024
        },
        timeout=60
    )
    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"]


def _parse_json_response(response_text: str) -> dict:
    """Parse JSON from LLM response."""
    import re

    # Try direct parse
    try:
        return json.loads(response_text)
    except:
        pass

    # Try to extract from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            pass

    # Try to find JSON object
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            pass

    # Return empty if parsing fails
    return {"fan_out": [], "reasoning": "Failed to parse response"}
