"""
Test Script for Basirat AI Agents
Tests Groq and Cerebras connectivity and agent functionality
"""

import asyncio
import os
import sys

# Fix encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 60)
print("[TEST] BASIRAT AI AGENTS TEST")
print("=" * 60)

# Check API keys
groq_key = os.getenv("GROQ_API_KEY")
cerebras_key = os.getenv("CEREBRAS_API_KEY")

print(f"\n[CHECK] Environment Check:")
print(f"   GROQ_API_KEY: {'[OK] Set' if groq_key and len(groq_key) > 10 else '[X] Missing'}")
print(f"   CEREBRAS_API_KEY: {'[OK] Set' if cerebras_key and len(cerebras_key) > 10 else '[X] Missing'}")

if not groq_key or len(groq_key) < 10:
    print("\n[ERROR] GROQ_API_KEY not set properly in .env")
    print("   Get your key from: https://console.groq.com")
    exit(1)


async def test_groq_connection():
    """Test direct Groq API connection"""
    print("\n" + "-" * 40)
    print("[TEST 1] Groq API Connection")
    print("-" * 40)

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )

    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Say 'Groq is working!' in exactly 3 words"}],
            max_tokens=20,
        )
        result = response.choices[0].message.content
        print(f"   [OK] Groq Response: {result}")
        return True
    except Exception as e:
        print(f"   [X] Groq Error: {e}")
        return False


async def test_cerebras_connection():
    """Test direct Cerebras API connection"""
    print("\n" + "-" * 40)
    print("[TEST 2] Cerebras API Connection")
    print("-" * 40)

    cerebras_key = os.getenv("CEREBRAS_API_KEY")
    if not cerebras_key or len(cerebras_key) < 10:
        print("   [SKIP] CEREBRAS_API_KEY not set")
        return None

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=cerebras_key,
        base_url="https://api.cerebras.ai/v1"
    )

    try:
        response = await client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "user", "content": "Say 'Cerebras is working!' in exactly 3 words"}],
            max_tokens=20,
        )
        result = response.choices[0].message.content
        print(f"   [OK] Cerebras Response: {result}")
        return True
    except Exception as e:
        print(f"   [X] Cerebras Error: {e}")
        return False


async def test_matchmaker_agent():
    """Test Matchmaker Agent"""
    print("\n" + "-" * 40)
    print("[TEST 3] Matchmaker Agent")
    print("-" * 40)

    from app.agents.matchmaker import analyze_compatibility

    profile_a = {
        "full_name": "Ahmed Khan",
        "gender": "male",
        "date_of_birth": "1995-05-15",
        "city": "Lahore",
        "country": "Pakistan",
        "sect": "sunni",
        "religiosity": "practicing",
        "prayer_frequency": "five_daily",
        "education_level": "Masters",
        "profession": "Software Engineer",
        "marital_status": "never_married",
        "has_children": False,
        "wants_children": "yes",
        "bio": "Looking for a pious wife who values family and deen.",
    }

    profile_b = {
        "full_name": "Fatima Ali",
        "gender": "female",
        "date_of_birth": "1998-08-20",
        "city": "Karachi",
        "country": "Pakistan",
        "sect": "sunni",
        "religiosity": "practicing",
        "prayer_frequency": "five_daily",
        "hijab_preference": "wears",
        "education_level": "Bachelors",
        "profession": "Doctor",
        "marital_status": "never_married",
        "has_children": False,
        "wants_children": "yes",
        "bio": "Seeking a kind, practicing Muslim husband.",
    }

    try:
        print("   Analyzing compatibility...")
        result = await analyze_compatibility(profile_a, profile_b)
        print(f"   [OK] Compatibility Score: {result.get('compatibility_score', 'N/A')}")
        print(f"   [OK] Zone: {result.get('zone', 'N/A')}")
        strengths = result.get('strengths', [])
        if strengths:
            print(f"   [OK] Strengths: {strengths[:2]}")
        return True
    except Exception as e:
        print(f"   [X] Matchmaker Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_coach_agent():
    """Test Coach Agent"""
    print("\n" + "-" * 40)
    print("[TEST 4] Relationship Coach Agent")
    print("-" * 40)

    from app.agents.coach import get_coach_response

    conversation = [
        {"sender_id": "user_a", "text": "Assalam o Alaikum! How are you?"},
        {"sender_id": "user_b", "text": "Wa Alaikum Assalam! I'm good, Alhamdulillah. How about you?"},
        {"sender_id": "user_a", "text": "I'm well too. I noticed you're a doctor. That's impressive!"},
        {"sender_id": "user_b", "text": "JazakAllah! Yes, I work at a hospital. What do you do?"},
    ]

    try:
        print("   Getting coaching response...")
        result = await get_coach_response(
            user_id="user_a",
            user_name="Ahmed",
            match_name="Fatima",
            conversation=conversation,
            question="Is she interested in me? What should I talk about next?",
        )
        print(f"   [OK] Coach Response (truncated):")
        # Truncate long response
        truncated = result[:300] if len(result) > 300 else result
        print(f"   {truncated}...")
        return True
    except Exception as e:
        print(f"   [X] Coach Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_safety_agent():
    """Test Safety Agent"""
    print("\n" + "-" * 40)
    print("[TEST 5] Safety Agent")
    print("-" * 40)

    from app.agents.safety import check_safety

    # Test with some slightly suspicious messages
    messages = [
        {"sender_id": "other", "text": "You're so beautiful, I've never felt this way before!"},
        {"sender_id": "me", "text": "Thank you, but we just started talking."},
        {"sender_id": "other", "text": "I know but I feel like we're soulmates. Can I have your phone number?"},
        {"sender_id": "other", "text": "Also, I'm having some financial troubles. Could you help me out?"},
    ]

    try:
        print("   Checking safety...")
        result = await check_safety(
            messages=messages,
            user_id="me",
            user_name="Ahmed",
            other_user_name="Suspicious User",
        )
        print(f"   [OK] Safety Score: {result.get('safety_score', 'N/A')}")
        print(f"   [OK] Alert Level: {result.get('alert_level', 'N/A')}")
        concerns = result.get('concerns', [])
        print(f"   [OK] Concerns Found: {len(concerns)}")
        if concerns:
            first_concern = concerns[0]
            if isinstance(first_concern, dict):
                print(f"   [!] First concern: {first_concern.get('type', 'unknown')}")
            else:
                print(f"   [!] First concern: {first_concern}")
        return True
    except Exception as e:
        print(f"   [X] Safety Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    results = {}

    # Test 1: Groq Connection
    results['groq'] = await test_groq_connection()

    # Test 2: Cerebras Connection
    results['cerebras'] = await test_cerebras_connection()

    # Only test agents if at least one API is working
    if results['groq'] or results['cerebras']:
        # Test 3: Matchmaker
        results['matchmaker'] = await test_matchmaker_agent()

        # Test 4: Coach
        results['coach'] = await test_coach_agent()

        # Test 5: Safety
        results['safety'] = await test_safety_agent()
    else:
        print("\n[X] Cannot test agents - no AI provider available")

    # Summary
    print("\n" + "=" * 60)
    print("[SUMMARY] TEST RESULTS")
    print("=" * 60)

    for test, passed in results.items():
        if passed is True:
            status = "[PASS]"
        elif passed is None:
            status = "[SKIP]"
        else:
            status = "[FAIL]"
        print(f"   {test.capitalize():20} {status}")

    passed_count = sum(1 for v in results.values() if v is True)
    total_count = sum(1 for v in results.values() if v is not None)

    print(f"\n   Total: {passed_count}/{total_count} tests passed")
    print("=" * 60)

    if passed_count == total_count and total_count > 0:
        print("\n[SUCCESS] All AI agents are working correctly!")
    elif passed_count > 0:
        print("\n[PARTIAL] Some tests passed. Check failed tests above.")
    else:
        print("\n[FAILED] No tests passed. Check your API keys and connection.")


if __name__ == "__main__":
    asyncio.run(main())
