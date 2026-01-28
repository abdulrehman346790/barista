"""
Matchmaker Agent
Analyzes profile compatibility and suggests matches
Uses call_llm instead of agents SDK
"""

from .config import call_llm_json
import json

MATCHMAKER_SYSTEM_PROMPT = """
You are the Basirat Matchmaker Agent - an intelligent Islamic matrimonial compatibility analyzer.

YOUR ROLE:
Analyze two user profiles and calculate their compatibility for marriage, considering Islamic values and practical life factors.

COMPATIBILITY CRITERIA (Weighted Scoring):

1. RELIGIOUS COMPATIBILITY (30%)
   - Same sect strongly preferred (Sunni/Shia)
   - Similar religiosity level (very_practicing, practicing, moderate, cultural)
   - Prayer habits alignment (five_daily, some, occasionally, rarely)
   - Hijab/Beard preferences if applicable

2. LIFE GOALS (25%)
   - Both want children or both don't
   - Career ambitions alignment
   - Relocation willingness match
   - Financial expectations

3. FAMILY VALUES (20%)
   - Marital status compatibility (never_married, divorced, widowed)
   - Views on family involvement
   - Traditional vs modern outlook
   - Children from previous marriage acceptance

4. PERSONALITY FIT (15%)
   - Communication style compatibility
   - Education level similarity
   - Age gap appropriateness (Islamic guidelines)
   - Shared interests from bio

5. PRACTICAL FACTORS (10%)
   - Location/distance
   - Profession compatibility
   - Income expectations

ZONE CLASSIFICATION:
- GREEN (70-100): Highly compatible, strong match potential
- YELLOW (40-69): Moderate compatibility, worth exploring with caution
- RED (0-39): Low compatibility, significant concerns

OUTPUT FORMAT (JSON only, no extra text):
{
    "compatibility_score": <number 0-100>,
    "zone": "<green/yellow/red>",
    "breakdown": {
        "religious": <score 0-100>,
        "life_goals": <score 0-100>,
        "family_values": <score 0-100>,
        "personality": <score 0-100>,
        "practical": <score 0-100>
    },
    "strengths": [
        "<specific strength 1>",
        "<specific strength 2>",
        "<specific strength 3>"
    ],
    "concerns": [
        "<specific concern if any>"
    ],
    "conversation_starters": [
        "<topic suggestion 1>",
        "<topic suggestion 2>"
    ],
    "advice": "<brief Islamic-appropriate advice for this match>"
}

IMPORTANT RULES:
1. Be objective and fair
2. Consider Islamic marriage principles
3. Don't discriminate based on appearance
4. Focus on compatibility for long-term marriage
5. Always output valid JSON only
"""


async def analyze_compatibility(profile_a: dict, profile_b: dict) -> dict:
    """
    Analyze compatibility between two profiles.

    Args:
        profile_a: First user's profile data
        profile_b: Second user's profile data

    Returns:
        Compatibility analysis with score, zone, and insights
    """
    prompt = f"""
Analyze the compatibility between these two profiles for marriage:

=== PROFILE A ===
Name: {profile_a.get('full_name', 'Unknown')}
Gender: {profile_a.get('gender', 'Unknown')}
Age: {calculate_age(profile_a.get('date_of_birth'))}
Location: {profile_a.get('city', 'Unknown')}, {profile_a.get('country', 'Unknown')}
Willing to Relocate: {profile_a.get('willing_to_relocate', False)}

Religious Background:
- Sect: {profile_a.get('sect', 'Not specified')}
- Religiosity: {profile_a.get('religiosity', 'Not specified')}
- Prayer: {profile_a.get('prayer_frequency', 'Not specified')}
- Hijab/Beard: {profile_a.get('hijab_preference') or profile_a.get('beard_preference', 'Not specified')}

Education & Career:
- Education: {profile_a.get('education_level', 'Not specified')}
- Profession: {profile_a.get('profession', 'Not specified')}
- Income: {profile_a.get('income_range', 'Not specified')}

Family:
- Marital Status: {profile_a.get('marital_status', 'Not specified')}
- Has Children: {profile_a.get('has_children', False)}
- Wants Children: {profile_a.get('wants_children', 'Not specified')}

Bio: {profile_a.get('bio', 'No bio provided')}

=== PROFILE B ===
Name: {profile_b.get('full_name', 'Unknown')}
Gender: {profile_b.get('gender', 'Unknown')}
Age: {calculate_age(profile_b.get('date_of_birth'))}
Location: {profile_b.get('city', 'Unknown')}, {profile_b.get('country', 'Unknown')}
Willing to Relocate: {profile_b.get('willing_to_relocate', False)}

Religious Background:
- Sect: {profile_b.get('sect', 'Not specified')}
- Religiosity: {profile_b.get('religiosity', 'Not specified')}
- Prayer: {profile_b.get('prayer_frequency', 'Not specified')}
- Hijab/Beard: {profile_b.get('hijab_preference') or profile_b.get('beard_preference', 'Not specified')}

Education & Career:
- Education: {profile_b.get('education_level', 'Not specified')}
- Profession: {profile_b.get('profession', 'Not specified')}
- Income: {profile_b.get('income_range', 'Not specified')}

Family:
- Marital Status: {profile_b.get('marital_status', 'Not specified')}
- Has Children: {profile_b.get('has_children', False)}
- Wants Children: {profile_b.get('wants_children', 'Not specified')}

Bio: {profile_b.get('bio', 'No bio provided')}

Provide your compatibility analysis in JSON format.
"""

    result = await call_llm_json(
        system_prompt=MATCHMAKER_SYSTEM_PROMPT,
        user_prompt=prompt,
        use_smart=True
    )

    # Parse JSON response
    try:
        # Clean up response if needed
        result = result.strip()
        if result.startswith("```json"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]

        return json.loads(result.strip())
    except json.JSONDecodeError:
        # Return default if parsing fails
        return {
            "compatibility_score": 50,
            "zone": "yellow",
            "breakdown": {
                "religious": 50,
                "life_goals": 50,
                "family_values": 50,
                "personality": 50,
                "practical": 50
            },
            "strengths": ["Analysis could not be completed"],
            "concerns": ["Please try again"],
            "conversation_starters": ["Share about your interests"],
            "advice": "Take time to get to know each other.",
            "raw_response": result
        }


def calculate_age(date_of_birth: str) -> int:
    """Calculate age from date of birth string"""
    if not date_of_birth:
        return 0
    try:
        from datetime import datetime
        birth_date = datetime.fromisoformat(date_of_birth.replace('Z', '+00:00'))
        today = datetime.now()
        age = today.year - birth_date.year
        if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
            age -= 1
        return age
    except:
        return 0
