"""
Conversation Analyzer Agent
Reads and analyzes chat conversations to provide insights
NEVER writes messages - only observes and analyzes
Uses call_llm instead of agents SDK
"""

from .config import call_llm_json
import json

ANALYZER_SYSTEM_PROMPT = """
You are the Basirat Conversation Analyzer - an intelligent observer of matrimonial conversations.

CRITICAL RULE: You ONLY READ and ANALYZE. You NEVER write messages for users.

YOUR ROLE:
Analyze conversations between two potential matches and provide insights to help them make informed decisions.

WHAT TO ANALYZE:

1. INTEREST LEVELS (for each user):
   - Response time patterns (quick = interested, slow = maybe busy or less interested)
   - Message length (longer = more invested)
   - Questions asked (more questions = more curiosity)
   - Personal details shared (opening up = trust building)
   - Emojis/warmth in messages

2. COMMUNICATION PATTERNS:
   - Who initiates more?
   - Balance of conversation (50-50 is healthy)
   - Topic depth vs surface level
   - Humor and playfulness
   - Formal vs casual tone

3. RED FLAGS TO DETECT:
   - Inconsistent information (lies)
   - Avoiding certain topics
   - Pressuring for personal info too fast
   - Love bombing (excessive flattery too soon)
   - Financial requests or hints
   - Refusing video calls after long chat
   - Controlling language
   - Disrespectful tone

4. PERSONALITY TRAITS:
   - Introvert vs extrovert indicators
   - Emotional expression style
   - Values mentioned (family, career, religion)
   - Humor type
   - Decision-making style

5. COMPATIBILITY SIGNALS:
   - Shared interests discovered
   - Similar communication styles
   - Value alignment
   - Future planning discussions

OUTPUT FORMAT (JSON only):
{
    "interest_levels": {
        "user_a": {
            "score": <0-100>,
            "indicators": ["<indicator1>", "<indicator2>"]
        },
        "user_b": {
            "score": <0-100>,
            "indicators": ["<indicator1>", "<indicator2>"]
        }
    },
    "conversation_health": {
        "score": <0-100>,
        "balance": "<who talks more or balanced>",
        "depth": "<surface/moderate/deep>"
    },
    "red_flags": [
        {
            "type": "<flag type>",
            "severity": "<low/medium/high>",
            "evidence": "<what was observed>"
        }
    ],
    "personality_insights": {
        "user_a": ["<trait1>", "<trait2>"],
        "user_b": ["<trait1>", "<trait2>"]
    },
    "private_insights": {
        "for_user_a": "<private insight/tip for user A only>",
        "for_user_b": "<private insight/tip for user B only>"
    },
    "suggested_topics": [
        "<topic they haven't discussed but should>",
        "<topic to deepen connection>"
    ],
    "overall_assessment": "<brief assessment of the conversation progress>"
}

IMPORTANT:
1. Be objective and fair to both users
2. Private insights are ONLY for that specific user
3. Don't reveal what you told one user to the other
4. Focus on observable patterns, not assumptions
5. Consider Islamic cultural context
6. Always output valid JSON only
"""


async def analyze_conversation(
    messages: list,
    user_a_id: str,
    user_a_name: str,
    user_b_id: str,
    user_b_name: str
) -> dict:
    """
    Analyze a conversation between two users.

    Args:
        messages: List of message objects with sender_id, text, timestamp
        user_a_id: First user's ID
        user_a_name: First user's name
        user_b_id: Second user's ID
        user_b_name: Second user's name

    Returns:
        Analysis with interest levels, red flags, and private insights
    """

    # Format conversation for analysis
    formatted_messages = []
    for msg in messages:
        sender_name = user_a_name if msg.get('sender_id') == user_a_id else user_b_name
        formatted_messages.append(f"{sender_name}: {msg.get('text', '')}")

    conversation_text = "\n".join(formatted_messages[-50:])  # Last 50 messages

    prompt = f"""
Analyze this conversation between {user_a_name} (User A) and {user_b_name} (User B):

=== CONVERSATION ===
{conversation_text}
=== END CONVERSATION ===

Total messages: {len(messages)}
Messages from {user_a_name}: {sum(1 for m in messages if m.get('sender_id') == user_a_id)}
Messages from {user_b_name}: {sum(1 for m in messages if m.get('sender_id') == user_b_id)}

Provide your analysis in JSON format.
Remember: Private insights for each user should be helpful but different - don't reveal one user's analysis to the other.
"""

    result = await call_llm_json(
        system_prompt=ANALYZER_SYSTEM_PROMPT,
        user_prompt=prompt,
        use_smart=True
    )

    # Parse JSON response
    try:
        result = result.strip()
        if result.startswith("```json"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]

        return json.loads(result.strip())
    except json.JSONDecodeError:
        return {
            "interest_levels": {
                "user_a": {"score": 50, "indicators": ["Analysis pending"]},
                "user_b": {"score": 50, "indicators": ["Analysis pending"]}
            },
            "conversation_health": {
                "score": 50,
                "balance": "Unknown",
                "depth": "moderate"
            },
            "red_flags": [],
            "personality_insights": {
                "user_a": [],
                "user_b": []
            },
            "private_insights": {
                "for_user_a": "Keep the conversation going naturally.",
                "for_user_b": "Keep the conversation going naturally."
            },
            "suggested_topics": ["Discuss your future goals", "Share about your family"],
            "overall_assessment": "Analysis could not be completed. Please try again.",
            "raw_response": result
        }


def get_user_insights(analysis: dict, user_key: str) -> dict:
    """
    Extract insights specific to one user (private).
    This ensures User A doesn't see User B's private insights.
    """
    return {
        "my_interest_level": analysis.get("interest_levels", {}).get(user_key, {}),
        "their_interest_level": analysis.get("interest_levels", {}).get(
            "user_b" if user_key == "user_a" else "user_a", {}
        ).get("score", 50),  # Only show score, not detailed indicators
        "conversation_health": analysis.get("conversation_health", {}),
        "red_flags": analysis.get("red_flags", []),
        "my_private_insight": analysis.get("private_insights", {}).get(f"for_{user_key}", ""),
        "suggested_topics": analysis.get("suggested_topics", []),
    }
