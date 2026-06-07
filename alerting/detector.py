import json
import os
from datetime import datetime
from typing import List, Dict
from scraper.models import RegulatoryDocument

SEEN_HASHES_FILE = "./data/seen_content_hashes.json"


class ChangeDetector:
    """
    Detects new and amended regulatory documents by comparing content hashes
    against previously seen state.
    """

    def __init__(self, state_file: str = SEEN_HASHES_FILE):
        self.state_file = state_file
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                self.seen = json.load(f)
        else:
            self.seen = {}

    def _save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.seen, f, indent=2)

    def detect_changes(
        self, documents: List[RegulatoryDocument]
    ) -> Dict[str, List[RegulatoryDocument]]:
        """Returns dict with 'new' and 'amended' document lists."""
        new_docs = []
        amended_docs = []

        for doc in documents:
            prev_hash = self.seen.get(doc.id)
            if prev_hash is None:
                new_docs.append(doc)
            elif prev_hash != doc.content_hash:
                doc.is_amended = True
                amended_docs.append(doc)
            self.seen[doc.id] = doc.content_hash

        self._save_state()
        return {"new": new_docs, "amended": amended_docs}

    def get_stats(self) -> Dict:
        return {
            "total_tracked": len(self.seen),
            "state_file": self.state_file,
        }
