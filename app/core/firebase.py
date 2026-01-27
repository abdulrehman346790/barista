import firebase_admin
from firebase_admin import credentials, db, auth
from typing import Optional

from app.config import settings


# Global Firebase app instance
firebase_app: Optional[firebase_admin.App] = None


def init_firebase():
    """Initialize Firebase Admin SDK."""
    global firebase_app

    if firebase_app is not None:
        return firebase_app

    # Check if Firebase credentials are configured
    if not settings.FIREBASE_PROJECT_ID or not settings.FIREBASE_CLIENT_EMAIL:
        print("Firebase credentials not configured - skipping initialization")
        return None

    # Create credentials from environment variables
    cred_dict = {
        "type": "service_account",
        "project_id": settings.FIREBASE_PROJECT_ID,
        "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
        "client_email": settings.FIREBASE_CLIENT_EMAIL,
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    try:
        cred = credentials.Certificate(cred_dict)
        firebase_app = firebase_admin.initialize_app(
            cred,
            {
                "databaseURL": f"https://{settings.FIREBASE_PROJECT_ID}-default-rtdb.firebaseio.com"
            },
        )
        print("Firebase initialized")
        return firebase_app
    except Exception as e:
        print(f"Firebase initialization failed: {e}")
        return None


class FirebaseService:
    """
    Service for Firebase Realtime Database and Authentication.
    Handles chat rooms and custom tokens.
    """

    def create_chat_room(self, match_id: str, user1_id: str, user2_id: str) -> str:
        """
        Create a new chat room in Firebase Realtime DB.
        Returns the chat room ID.
        """
        ref = db.reference(f"chats/{match_id}")
        ref.set(
            {
                "metadata": {
                    "created_at": {".sv": "timestamp"},
                    "user1_id": user1_id,
                    "user2_id": user2_id,
                    f"unread_count_{user1_id}": 0,
                    f"unread_count_{user2_id}": 0,
                },
                "messages": {},
                "typing": {user1_id: False, user2_id: False},
            }
        )
        return match_id

    def get_custom_token(self, user_id: str) -> str:
        """
        Generate a custom Firebase auth token for the user.
        Client uses this to authenticate with Firebase.
        """
        return auth.create_custom_token(user_id).decode("utf-8")

    def delete_chat_room(self, match_id: str) -> None:
        """Delete a chat room (when unmatched)."""
        ref = db.reference(f"chats/{match_id}")
        ref.delete()

    def get_chat_metadata(self, match_id: str) -> Optional[dict]:
        """Get chat room metadata."""
        ref = db.reference(f"chats/{match_id}/metadata")
        return ref.get()

    def update_unread_count(self, match_id: str, user_id: str, count: int) -> None:
        """Update unread message count for a user."""
        ref = db.reference(f"chats/{match_id}/metadata/unread_count_{user_id}")
        ref.set(count)

    def send_message(
        self, match_id: str, sender_id: str, text: str, encrypted: bool = True
    ) -> str:
        """
        Send a message to a chat room.
        Returns the message ID.
        Note: In production, messages should be encrypted client-side.
        """
        ref = db.reference(f"chats/{match_id}/messages")
        message_ref = ref.push(
            {
                "sender_id": sender_id,
                "text": text,
                "timestamp": {".sv": "timestamp"},
                "read": False,
                "encrypted": encrypted,
            }
        )
        return message_ref.key

    def mark_messages_read(self, match_id: str, reader_id: str) -> None:
        """Mark all messages as read for a user."""
        # Reset unread count
        self.update_unread_count(match_id, reader_id, 0)


# Singleton instance
firebase_service = FirebaseService()
