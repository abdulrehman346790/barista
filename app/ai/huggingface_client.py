from huggingface_hub import InferenceClient
from typing import List, Dict, Optional
import numpy as np

from app.config import settings


# Initialize Huggingface client
client = InferenceClient(token=settings.HF_TOKEN)

# Free Huggingface models
HF_MODELS = {
    "sentiment": "cardiffnlp/twitter-roberta-base-sentiment-latest",
    "toxicity": "unitary/toxic-bert",
    "embeddings": "sentence-transformers/all-MiniLM-L6-v2",
    "chat": "mistralai/Mistral-7B-Instruct-v0.2",
}


class SentimentAnalyzer:
    """Analyze sentiment of text using Huggingface."""

    def analyze(self, text: str) -> float:
        """
        Analyze sentiment of text.
        Returns score from -1.0 (negative) to 1.0 (positive).
        """
        try:
            result = client.text_classification(
                text[:512],  # Limit text length
                model=HF_MODELS["sentiment"],
            )
            # Result format: [{"label": "positive", "score": 0.92}]
            if result:
                label = result[0]["label"].lower()
                score = result[0]["score"]

                if "positive" in label:
                    return score
                elif "negative" in label:
                    return -score
                else:  # neutral
                    return 0.0
            return 0.0
        except Exception as e:
            print(f"Sentiment analysis error: {e}")
            return 0.0

    def analyze_batch(self, texts: List[str]) -> List[float]:
        """Analyze sentiment of multiple texts."""
        return [self.analyze(text) for text in texts]


class ToxicityDetector:
    """Detect toxic content using Huggingface."""

    def detect(self, text: str) -> Dict:
        """
        Detect toxicity in text.
        Returns dict with is_toxic, score, and detected categories.
        """
        try:
            result = client.text_classification(
                text[:512],
                model=HF_MODELS["toxicity"],
            )
            if result:
                # Check if toxic
                is_toxic = result[0]["label"].lower() == "toxic"
                score = result[0]["score"] if is_toxic else 1 - result[0]["score"]

                return {
                    "is_toxic": is_toxic and score > 0.7,
                    "toxicity_score": score if is_toxic else 0.0,
                    "confidence": result[0]["score"],
                    "flags": ["toxic_content"] if is_toxic and score > 0.7 else [],
                }
            return {"is_toxic": False, "toxicity_score": 0.0, "flags": []}
        except Exception as e:
            print(f"Toxicity detection error: {e}")
            return {"is_toxic": False, "toxicity_score": 0.0, "flags": []}


class LanguageStyleMatcher:
    """Calculate language style similarity between users."""

    def get_embedding(self, text: str) -> List[float]:
        """Get text embedding."""
        try:
            result = client.feature_extraction(
                text[:1000],
                model=HF_MODELS["embeddings"],
            )
            # Result is a list of embeddings, take mean
            if isinstance(result, list):
                if isinstance(result[0], list):
                    return np.mean(result, axis=0).tolist()
                return result
            return []
        except Exception as e:
            print(f"Embedding error: {e}")
            return []

    def calculate_similarity(
        self, user1_texts: List[str], user2_texts: List[str]
    ) -> float:
        """
        Calculate Language Style Matching score between two users.
        Returns score from 0.0 (no match) to 1.0 (perfect match).
        """
        if not user1_texts or not user2_texts:
            return 0.5  # Neutral if no data

        try:
            # Combine texts for each user
            user1_combined = " ".join(user1_texts[:10])  # Limit to 10 messages
            user2_combined = " ".join(user2_texts[:10])

            # Get embeddings
            emb1 = self.get_embedding(user1_combined)
            emb2 = self.get_embedding(user2_combined)

            if not emb1 or not emb2:
                return 0.5

            # Calculate cosine similarity
            emb1 = np.array(emb1)
            emb2 = np.array(emb2)

            similarity = np.dot(emb1, emb2) / (
                np.linalg.norm(emb1) * np.linalg.norm(emb2)
            )

            # Normalize to 0-1 range (cosine similarity is -1 to 1)
            return float((similarity + 1) / 2)
        except Exception as e:
            print(f"LSM calculation error: {e}")
            return 0.5


class ConversationCoach:
    """Generate reply suggestions using LLM."""

    def suggest_replies(
        self,
        last_messages: List[str],
        user_name: str = "User",
        context: Optional[str] = None,
    ) -> List[Dict]:
        """
        Generate contextual reply suggestions.
        Returns list of suggested replies with tone and explanation.
        """
        try:
            # Build prompt
            conversation = "\n".join(
                [f"{'Them' if i % 2 == 0 else 'You'}: {msg}" for i, msg in enumerate(last_messages)]
            )

            prompt = f"""You are a helpful dating coach for a Muslim matrimonial app.
Based on this conversation, suggest 3 appropriate, respectful replies.

Conversation:
{conversation}

{f"Additional context: {context}" if context else ""}

Provide 3 reply suggestions in this format:
1. [friendly] Reply text here | Explanation of why this works
2. [curious] Reply text here | Explanation of why this works
3. [thoughtful] Reply text here | Explanation of why this works

Keep replies respectful, halal, and engaging. Focus on building genuine connection."""

            response = client.text_generation(
                prompt,
                model=HF_MODELS["chat"],
                max_new_tokens=300,
                temperature=0.7,
            )

            # Parse response
            suggestions = []
            lines = response.strip().split("\n")

            for line in lines:
                if line.strip() and line[0].isdigit():
                    # Parse format: "1. [tone] Reply | Explanation"
                    try:
                        parts = line.split("]", 1)
                        if len(parts) == 2:
                            tone = parts[0].split("[")[-1].strip()
                            rest = parts[1].strip()

                            if "|" in rest:
                                reply, explanation = rest.split("|", 1)
                            else:
                                reply = rest
                                explanation = "A thoughtful response"

                            suggestions.append({
                                "text": reply.strip(),
                                "tone": tone,
                                "explanation": explanation.strip(),
                            })
                    except:
                        continue

            # Fallback suggestions if parsing failed
            if not suggestions:
                suggestions = [
                    {
                        "text": "That's really interesting! Tell me more about that.",
                        "tone": "curious",
                        "explanation": "Shows genuine interest in their story",
                    },
                    {
                        "text": "I can relate to that. For me, it's been...",
                        "tone": "friendly",
                        "explanation": "Builds connection through shared experience",
                    },
                    {
                        "text": "What made you interested in that?",
                        "tone": "thoughtful",
                        "explanation": "Encourages deeper conversation",
                    },
                ]

            return suggestions[:3]

        except Exception as e:
            print(f"Coaching error: {e}")
            # Return fallback suggestions
            return [
                {
                    "text": "That's really interesting! Tell me more.",
                    "tone": "curious",
                    "explanation": "Shows genuine interest",
                },
                {
                    "text": "I appreciate you sharing that with me.",
                    "tone": "friendly",
                    "explanation": "Validates their openness",
                },
                {
                    "text": "What are your thoughts on...",
                    "tone": "thoughtful",
                    "explanation": "Keeps conversation flowing",
                },
            ]


# Singleton instances
sentiment_analyzer = SentimentAnalyzer()
toxicity_detector = ToxicityDetector()
lsm_calculator = LanguageStyleMatcher()
conversation_coach = ConversationCoach()
