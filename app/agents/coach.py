"""
Relationship Coach Agent
Provides PRIVATE coaching to individual users
Each user gets their own personalized, confidential advice
"""

from agents import Agent
from .config import run_with_fallback
import json

def get_coach_instructions(user_name: str) -> str:
    """Generate personalized coach instructions for a specific user"""
    return f"""
You are a PRIVATE Relationship Coach for {user_name} on Basirat - a Muslim matrimonial app.

🔒 CRITICAL PRIVACY RULES:
1. Everything you say is 100% PRIVATE to {user_name} only
2. The other person will NEVER see your advice to {user_name}
3. NEVER reveal what the other person might be thinking privately
4. NEVER write messages for {user_name} to send
5. Be like a wise, trusted friend giving honest advice

YOUR ROLE:
You are like a perceptive psychologist who can read people well. You observe conversations and help {user_name} understand:
- What the other person's behavior might indicate
- What {user_name} is doing well
- Areas where {user_name} could improve
- Red flags to watch for
- Topics worth exploring

WHAT YOU CAN DO:

1. PROVIDE INSIGHTS (based on observed behavior):
   ✅ "Based on their quick responses, they seem engaged"
   ✅ "They've mentioned family three times - it's important to them"
   ✅ "Notice how they asked about your career - show genuine interest back"

2. GIVE GENTLE WARNINGS:
   ✅ "I noticed some inconsistency when they talked about..."
   ✅ "They're moving quite fast - it's okay to slow down"
   ✅ "Trust your instincts if something feels off"

3. OFFER ENCOURAGEMENT:
   ✅ "Great question! That shows emotional intelligence"
   ✅ "You're being authentic - that's attractive"
   ✅ "The conversation is flowing naturally, well done"

4. SUGGEST TOPICS (not full messages):
   ✅ "Consider asking about their relationship with their parents"
   ✅ "Good time to discuss: views on working after marriage"
   ✅ "Topic idea: How they handle disagreements"

WHAT YOU MUST NEVER DO:
❌ Write full messages for {user_name} to copy-paste
❌ Tell {user_name} exactly what to say word-for-word
❌ Reveal the other person's private feelings/thoughts
❌ Make promises about the outcome
❌ Be judgmental or harsh
❌ Encourage manipulation tactics

RESPONSE STYLE:
- Warm and supportive like a wise friend
- Honest but kind
- Practical and actionable
- Culturally aware (Islamic context)
- Use occasional emojis for warmth (but not excessive)

RESPONSE FORMAT:
Respond naturally in conversational paragraphs. Be helpful and specific to their question.
If they ask something you can't answer, be honest about it.
"""

async def get_coach_response(
    user_id: str,
    user_name: str,
    match_name: str,
    conversation: list,
    question: str,
    user_profile: dict = None,
    match_profile: dict = None
) -> str:
    """
    Get personalized coaching response for a user's question.

    Args:
        user_id: The user asking for coaching
        user_name: Name of the user
        match_name: Name of their match
        conversation: Recent conversation messages
        question: User's question to the coach
        user_profile: Optional profile data of the user
        match_profile: Optional profile data of the match

    Returns:
        Personalized coaching response (string)
    """

    # Create personalized coach for this user
    coach_agent = Agent(
        name=f"Coach_{user_id}",
        instructions=get_coach_instructions(user_name)
    )

    # Format recent conversation
    formatted_convo = []
    for msg in conversation[-30:]:  # Last 30 messages for context
        sender = user_name if msg.get('sender_id') == user_id else match_name
        formatted_convo.append(f"{sender}: {msg.get('text', '')}")

    conversation_text = "\n".join(formatted_convo) if formatted_convo else "No messages yet"

    # Build context
    context_parts = [f"You are privately coaching {user_name} about their conversation with {match_name}."]

    if user_profile:
        context_parts.append(f"""
{user_name}'s Profile:
- Religiosity: {user_profile.get('religiosity', 'Unknown')}
- Looking for: A compatible Muslim spouse
""")

    if match_profile:
        context_parts.append(f"""
{match_name}'s Profile (public info only):
- Age: {match_profile.get('age', 'Unknown')}
- Location: {match_profile.get('city', 'Unknown')}
- Profession: {match_profile.get('profession', 'Unknown')}
- Religiosity: {match_profile.get('religiosity', 'Unknown')}
""")

    context = "\n".join(context_parts)

    prompt = f"""
{context}

=== RECENT CONVERSATION ===
{conversation_text}
=== END CONVERSATION ===

{user_name}'s question to you (PRIVATE - {match_name} cannot see this):
"{question}"

Provide your helpful, private coaching response to {user_name}.
Remember: Be supportive, honest, and helpful. Suggest topics, not full messages.
"""

    result = await run_with_fallback(coach_agent, prompt, use_smart=True)
    return result


async def get_auto_insight(
    user_id: str,
    user_name: str,
    match_name: str,
    conversation: list,
    last_message_from_match: str
) -> str:
    """
    Generate automatic insight/tip after match sends a message.
    This powers the auto-insights bar in the UI.

    Args:
        user_id: The user receiving the insight
        user_name: Name of the user
        match_name: Name of their match
        conversation: Recent conversation
        last_message_from_match: The most recent message from match

    Returns:
        Brief, helpful insight (1-2 sentences)
    """

    coach_agent = Agent(
        name=f"AutoCoach_{user_id}",
        instructions=f"""
You provide brief, helpful tips to {user_name} during their conversation.
Keep responses to 1-2 short sentences maximum.
Be encouraging and insightful.
Never write messages for them - just give quick tips or observations.
"""
    )

    # Get last few messages for context
    recent = conversation[-10:] if len(conversation) > 10 else conversation
    formatted = [f"{user_name if m.get('sender_id') == user_id else match_name}: {m.get('text', '')}"
                 for m in recent]

    prompt = f"""
Recent conversation:
{chr(10).join(formatted)}

Latest message from {match_name}: "{last_message_from_match}"

Give {user_name} a brief, helpful tip (1-2 sentences only). Examples:
- "They asked about your family - they're interested in your background!"
- "Good opportunity to ask about their career goals."
- "They seem excited about this topic - explore it more!"

Your brief tip:
"""

    result = await run_with_fallback(coach_agent, prompt, use_smart=False)  # Fast model for quick tips
    return result.strip()
