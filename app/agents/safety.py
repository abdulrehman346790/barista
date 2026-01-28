"""
Safety Agent
Protects users by detecting red flags, scams, and inappropriate behavior
"""

from agents import Agent
from .config import run_with_fallback
import json

SAFETY_INSTRUCTIONS = """
You are the Basirat Safety Guardian - protecting users on a Muslim matrimonial app.

YOUR MISSION:
Analyze conversations and profiles to detect potential threats while respecting privacy and avoiding false accusations.

THREAT CATEGORIES TO DETECT:

1. 🚨 SCAM PATTERNS (HIGH SEVERITY):
   - Requests for money, loans, or gifts
   - Investment opportunities or business proposals
   - Sob stories followed by financial requests
   - Cryptocurrency or forex schemes
   - "Emergency" situations requiring money
   - Requests for bank/financial information

2. 🎭 CATFISHING SIGNS (MEDIUM-HIGH SEVERITY):
   - Repeatedly refuses video calls with excuses
   - Photos look too professional/model-like
   - Inconsistent personal details across conversations
   - Story details that don't add up
   - Claims to be in military/oil rig/overseas work (common scam)
   - Avoids meeting in person after extended chat
   - Limited or no social media presence

3. ⚠️ MANIPULATION TACTICS (MEDIUM SEVERITY):
   - Love bombing (excessive affection too soon)
   - "I've never felt this way before" very early
   - Guilt tripping or emotional manipulation
   - Isolation attempts ("don't tell your family about us")
   - Controlling language ("you should/must...")
   - Jealousy or possessiveness early on
   - Rushing commitment ("let's get married next month")

4. 🔴 INAPPROPRIATE BEHAVIOR (VARIES):
   - Explicit or sexual messages
   - Harassment or persistent unwanted contact
   - Threats or intimidation
   - Disrespectful language about religion/family
   - Pressuring for photos or personal meetings
   - Asking inappropriate questions too early

5. 🟡 MINOR CONCERNS (LOW SEVERITY):
   - Vague or evasive answers to reasonable questions
   - Inconsistent online times vs claimed schedule
   - Reluctance to share basic info after good rapport
   - Only texting at odd hours

ALERT LEVELS:
- 🟢 GREEN (80-100): All normal, healthy conversation
- 🟡 YELLOW (50-79): Minor concerns, worth monitoring
- 🟠 ORANGE (30-49): Notable concerns, warn user
- 🔴 RED (10-29): Serious concerns, strong warning needed
- ⚫ BLACK (0-9): Severe threat, recommend blocking/reporting

OUTPUT FORMAT (JSON only):
{
    "safety_score": <0-100>,
    "alert_level": "<green/yellow/orange/red/black>",
    "concerns": [
        {
            "type": "<scam/catfish/manipulation/inappropriate/minor>",
            "severity": "<low/medium/high/critical>",
            "evidence": "<specific observation>",
            "explanation": "<why this is concerning>"
        }
    ],
    "positive_signs": [
        "<good sign observed>"
    ],
    "recommendation": "<what user should do>",
    "detailed_warning": "<if needed, a clear warning message for the user>"
}

IMPORTANT GUIDELINES:
1. Be thorough but avoid false positives
2. Consider cultural context (arranged marriage discussions are normal)
3. One red flag alone may not be conclusive - look for patterns
4. Protect users without creating unnecessary fear
5. Family involvement questions are NORMAL in Muslim context
6. Don't flag normal getting-to-know-you questions
7. Always output valid JSON only
"""

safety_agent = Agent(
    name="Safety",
    instructions=SAFETY_INSTRUCTIONS
)

async def check_safety(
    messages: list,
    user_id: str,
    user_name: str,
    other_user_name: str,
    other_user_profile: dict = None
) -> dict:
    """
    Analyze conversation for safety concerns.

    Args:
        messages: Conversation messages
        user_id: ID of the user we're protecting
        user_name: Name of the user we're protecting
        other_user_name: Name of the other person
        other_user_profile: Profile data of the other person

    Returns:
        Safety analysis with score, alert level, and recommendations
    """

    # Format conversation
    formatted_messages = []
    for msg in messages[-50:]:  # Last 50 messages
        sender = user_name if msg.get('sender_id') == user_id else other_user_name
        formatted_messages.append(f"{sender}: {msg.get('text', '')}")

    conversation_text = "\n".join(formatted_messages)

    # Build profile context if available
    profile_context = ""
    if other_user_profile:
        profile_context = f"""
{other_user_name}'s Profile:
- Claimed Location: {other_user_profile.get('city', 'Unknown')}, {other_user_profile.get('country', 'Unknown')}
- Claimed Profession: {other_user_profile.get('profession', 'Unknown')}
- Account Verified: {other_user_profile.get('verification_status', 'Unknown')}
- Profile Completeness: {other_user_profile.get('is_complete', False)}
"""

    prompt = f"""
Analyze this conversation for safety concerns.
We are protecting {user_name} - analyze {other_user_name}'s behavior.

{profile_context}

=== CONVERSATION ===
{conversation_text}
=== END CONVERSATION ===

Total messages analyzed: {len(messages)}
Messages from {other_user_name}: {sum(1 for m in messages if m.get('sender_id') != user_id)}

Provide your safety analysis in JSON format.
Look for any red flags, scam patterns, or concerning behavior from {other_user_name}.
Also note positive signs if the conversation seems healthy.
"""

    result = await run_with_fallback(safety_agent, prompt, use_smart=True)

    # Parse JSON response
    try:
        result = result.strip()
        if result.startswith("```json"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]

        analysis = json.loads(result.strip())

        # Ensure required fields
        analysis.setdefault("safety_score", 75)
        analysis.setdefault("alert_level", "green")
        analysis.setdefault("concerns", [])
        analysis.setdefault("positive_signs", [])
        analysis.setdefault("recommendation", "Continue getting to know each other naturally.")

        return analysis

    except json.JSONDecodeError:
        return {
            "safety_score": 75,
            "alert_level": "green",
            "concerns": [],
            "positive_signs": ["Analysis pending"],
            "recommendation": "Continue the conversation naturally. Contact support if you notice anything concerning.",
            "raw_response": result
        }


async def quick_message_check(message_text: str, sender_name: str) -> dict:
    """
    Quick safety check on a single message.
    Used for real-time flagging of obviously problematic content.

    Args:
        message_text: The message to check
        sender_name: Who sent it

    Returns:
        Quick safety assessment
    """

    quick_agent = Agent(
        name="QuickSafety",
        instructions="""
You quickly assess if a single message contains obvious red flags.
Only flag CLEAR violations, not ambiguous content.

Check for:
- Explicit/sexual content
- Money/financial requests
- Threats or harassment
- Obvious scam language

Respond with JSON:
{"flagged": true/false, "reason": "brief reason if flagged", "severity": "low/medium/high/critical"}
"""
    )

    prompt = f'{sender_name} sent: "{message_text}"\n\nQuick safety check:'

    try:
        result = await run_with_fallback(quick_agent, prompt, use_smart=False)
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        return json.loads(result.strip())
    except:
        return {"flagged": False, "reason": None, "severity": None}
