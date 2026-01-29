"""
RAG (Retrieval Augmented Generation) Service
Per-chat vector storage for contextual AI responses
"""

import os
import json
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
import hashlib

# Lazy loading for heavy imports
_model = None
_faiss = None

def get_embedding_model():
    """Lazy load sentence-transformers model"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        # Use a lightweight model for speed
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model

def get_faiss():
    """Lazy load FAISS"""
    global _faiss
    if _faiss is None:
        import faiss
        _faiss = faiss
    return _faiss


class ChatRAGStore:
    """
    Per-match RAG storage using FAISS for vector search.
    Each match has its own vector index for conversation context.
    """

    def __init__(self, storage_dir: str = "rag_data"):
        self.storage_dir = storage_dir
        self.embedding_dim = 384  # Dimension for all-MiniLM-L6-v2
        self._indexes: Dict[str, any] = {}  # Cache loaded indexes
        self._metadata: Dict[str, List[Dict]] = {}  # Cache metadata

        # Create storage directory
        os.makedirs(storage_dir, exist_ok=True)

    def _get_match_dir(self, match_id: str) -> str:
        """Get storage directory for a specific match"""
        match_dir = os.path.join(self.storage_dir, match_id)
        os.makedirs(match_dir, exist_ok=True)
        return match_dir

    def _get_index_path(self, match_id: str) -> str:
        return os.path.join(self._get_match_dir(match_id), "index.faiss")

    def _get_metadata_path(self, match_id: str) -> str:
        return os.path.join(self._get_match_dir(match_id), "metadata.json")

    def _load_or_create_index(self, match_id: str):
        """Load existing index or create new one"""
        faiss = get_faiss()

        if match_id in self._indexes:
            return self._indexes[match_id]

        index_path = self._get_index_path(match_id)

        if os.path.exists(index_path):
            # Load existing index
            index = faiss.read_index(index_path)
        else:
            # Create new index with L2 distance
            index = faiss.IndexFlatL2(self.embedding_dim)

        self._indexes[match_id] = index
        return index

    def _load_metadata(self, match_id: str) -> List[Dict]:
        """Load metadata for match"""
        if match_id in self._metadata:
            return self._metadata[match_id]

        metadata_path = self._get_metadata_path(match_id)

        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            metadata = []

        self._metadata[match_id] = metadata
        return metadata

    def _save_index(self, match_id: str):
        """Save index to disk"""
        faiss = get_faiss()

        if match_id in self._indexes:
            index_path = self._get_index_path(match_id)
            faiss.write_index(self._indexes[match_id], index_path)

    def _save_metadata(self, match_id: str):
        """Save metadata to disk"""
        if match_id in self._metadata:
            metadata_path = self._get_metadata_path(match_id)
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self._metadata[match_id], f, ensure_ascii=False, indent=2)

    def _generate_message_id(self, sender_id: str, content: str, timestamp: str) -> str:
        """Generate unique ID for a message"""
        data = f"{sender_id}:{content}:{timestamp}"
        return hashlib.md5(data.encode()).hexdigest()

    def add_message(
        self,
        match_id: str,
        sender_id: str,
        sender_name: str,
        content: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """
        Add a chat message to the RAG store.

        Args:
            match_id: ID of the match/conversation
            sender_id: ID of the message sender
            sender_name: Name of the sender
            content: Message content
            timestamp: Optional timestamp (defaults to now)

        Returns:
            True if added, False if duplicate
        """
        if not content or not content.strip():
            return False

        timestamp = timestamp or datetime.utcnow().isoformat()
        message_id = self._generate_message_id(sender_id, content, timestamp)

        # Load existing data
        metadata = self._load_metadata(match_id)

        # Check for duplicate
        existing_ids = {m.get('message_id') for m in metadata}
        if message_id in existing_ids:
            return False

        # Generate embedding
        model = get_embedding_model()
        embedding = model.encode([content])[0]

        # Add to index
        index = self._load_or_create_index(match_id)
        embedding_np = np.array([embedding], dtype=np.float32)
        index.add(embedding_np)

        # Add metadata
        metadata.append({
            'message_id': message_id,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'content': content,
            'timestamp': timestamp,
            'index_position': len(metadata)
        })

        # Save to disk
        self._save_index(match_id)
        self._save_metadata(match_id)

        return True

    def add_messages_batch(
        self,
        match_id: str,
        messages: List[Dict]
    ) -> int:
        """
        Add multiple messages at once (more efficient).

        Args:
            match_id: ID of the match
            messages: List of dicts with sender_id, sender_name, content, timestamp

        Returns:
            Number of messages added
        """
        if not messages:
            return 0

        metadata = self._load_metadata(match_id)
        existing_ids = {m.get('message_id') for m in metadata}

        new_messages = []
        new_contents = []

        for msg in messages:
            content = msg.get('content', '').strip()
            if not content:
                continue

            timestamp = msg.get('timestamp', datetime.utcnow().isoformat())
            message_id = self._generate_message_id(
                msg['sender_id'],
                content,
                timestamp
            )

            if message_id not in existing_ids:
                new_messages.append({
                    'message_id': message_id,
                    'sender_id': msg['sender_id'],
                    'sender_name': msg.get('sender_name', 'Unknown'),
                    'content': content,
                    'timestamp': timestamp
                })
                new_contents.append(content)
                existing_ids.add(message_id)

        if not new_messages:
            return 0

        # Generate embeddings in batch
        model = get_embedding_model()
        embeddings = model.encode(new_contents)

        # Add to index
        index = self._load_or_create_index(match_id)
        embeddings_np = np.array(embeddings, dtype=np.float32)
        index.add(embeddings_np)

        # Add metadata with positions
        start_pos = len(metadata)
        for i, msg in enumerate(new_messages):
            msg['index_position'] = start_pos + i
            metadata.append(msg)

        # Save
        self._save_index(match_id)
        self._save_metadata(match_id)

        return len(new_messages)

    def search(
        self,
        match_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Search for relevant messages in the conversation.

        Args:
            match_id: ID of the match
            query: Search query
            top_k: Number of results to return

        Returns:
            List of relevant messages with scores
        """
        metadata = self._load_metadata(match_id)

        if not metadata:
            return []

        index = self._load_or_create_index(match_id)

        if index.ntotal == 0:
            return []

        # Generate query embedding
        model = get_embedding_model()
        query_embedding = model.encode([query])[0]
        query_np = np.array([query_embedding], dtype=np.float32)

        # Search
        k = min(top_k, index.ntotal)
        distances, indices = index.search(query_np, k)

        # Get results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= 0 and idx < len(metadata):
                result = metadata[idx].copy()
                result['relevance_score'] = float(1.0 / (1.0 + distances[0][i]))
                results.append(result)

        return results

    def get_recent_context(
        self,
        match_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get most recent messages for context.

        Args:
            match_id: ID of the match
            limit: Maximum number of messages

        Returns:
            List of recent messages sorted by timestamp
        """
        metadata = self._load_metadata(match_id)

        if not metadata:
            return []

        # Sort by timestamp and get recent
        sorted_msgs = sorted(
            metadata,
            key=lambda x: x.get('timestamp', ''),
            reverse=True
        )[:limit]

        # Return in chronological order
        return list(reversed(sorted_msgs))

    def get_conversation_summary(
        self,
        match_id: str
    ) -> Dict:
        """
        Get summary statistics for the conversation.
        """
        metadata = self._load_metadata(match_id)

        if not metadata:
            return {
                'total_messages': 0,
                'participants': [],
                'first_message': None,
                'last_message': None
            }

        participants = {}
        for msg in metadata:
            sender = msg.get('sender_name', 'Unknown')
            participants[sender] = participants.get(sender, 0) + 1

        sorted_msgs = sorted(metadata, key=lambda x: x.get('timestamp', ''))

        return {
            'total_messages': len(metadata),
            'participants': participants,
            'first_message': sorted_msgs[0].get('timestamp') if sorted_msgs else None,
            'last_message': sorted_msgs[-1].get('timestamp') if sorted_msgs else None
        }

    def clear_match_data(self, match_id: str):
        """Clear all RAG data for a match"""
        import shutil

        match_dir = self._get_match_dir(match_id)
        if os.path.exists(match_dir):
            shutil.rmtree(match_dir)

        # Clear cache
        self._indexes.pop(match_id, None)
        self._metadata.pop(match_id, None)


# Global instance
_rag_store: Optional[ChatRAGStore] = None

def get_rag_store() -> ChatRAGStore:
    """Get or create the global RAG store instance"""
    global _rag_store
    if _rag_store is None:
        # Use environment variable for storage path, default to rag_data
        storage_dir = os.getenv('RAG_STORAGE_DIR', 'rag_data')
        _rag_store = ChatRAGStore(storage_dir=storage_dir)
    return _rag_store


# Convenience functions
def index_chat_message(
    match_id: str,
    sender_id: str,
    sender_name: str,
    content: str,
    timestamp: Optional[str] = None
) -> bool:
    """Index a single chat message"""
    store = get_rag_store()
    return store.add_message(match_id, sender_id, sender_name, content, timestamp)


def index_chat_history(match_id: str, messages: List[Dict]) -> int:
    """Index multiple messages from chat history"""
    store = get_rag_store()
    return store.add_messages_batch(match_id, messages)


def get_relevant_context(
    match_id: str,
    query: str,
    top_k: int = 5,
    include_recent: int = 10
) -> Dict:
    """
    Get relevant context for AI response.
    Combines semantic search with recent messages.

    Returns:
        {
            'relevant_messages': [...],  # Semantically similar
            'recent_messages': [...],    # Most recent
            'summary': {...}             # Conversation stats
        }
    """
    store = get_rag_store()

    relevant = store.search(match_id, query, top_k=top_k)
    recent = store.get_recent_context(match_id, limit=include_recent)
    summary = store.get_conversation_summary(match_id)

    return {
        'relevant_messages': relevant,
        'recent_messages': recent,
        'summary': summary
    }


def format_context_for_ai(context: Dict) -> str:
    """
    Format RAG context into a string for AI prompt.
    """
    lines = []

    # Add summary
    summary = context.get('summary', {})
    if summary.get('total_messages', 0) > 0:
        lines.append(f"[Conversation has {summary['total_messages']} messages]")
        lines.append("")

    # Add recent messages
    recent = context.get('recent_messages', [])
    if recent:
        lines.append("=== Recent Conversation ===")
        for msg in recent[-10:]:  # Last 10
            sender = msg.get('sender_name', 'Unknown')
            content = msg.get('content', '')
            lines.append(f"{sender}: {content}")
        lines.append("")

    # Add relevant context
    relevant = context.get('relevant_messages', [])
    if relevant:
        lines.append("=== Relevant Past Messages ===")
        for msg in relevant[:5]:  # Top 5
            sender = msg.get('sender_name', 'Unknown')
            content = msg.get('content', '')
            score = msg.get('relevance_score', 0)
            if score > 0.3:  # Only include if relevant enough
                lines.append(f"{sender}: {content}")
        lines.append("")

    return "\n".join(lines)
