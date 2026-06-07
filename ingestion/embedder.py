import os
from typing import List, Union
import logging

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """
    Wraps OpenAI and sentence-transformers embedding providers.
    Falls back to sentence-transformers if OPENAI_API_KEY is not set.
    """

    def __init__(self, provider: str = "sentence-transformers", model: str = None):
        self.provider = provider
        self.model = model
        self._client = None
        self._st_model = None
        self._setup()

    def _setup(self):
        if self.provider == "openai":
            try:
                import httpx
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=os.environ["OPENAI_API_KEY"],
                    base_url=os.environ.get("OPENAI_BASE_URL"),
                    http_client=httpx.Client(verify=False),
                )
                self.model = self.model or "text-embedding-3-small"
                logger.info(f"Using OpenAI embeddings: {self.model}")
            except (ImportError, KeyError) as e:
                logger.warning(f"OpenAI not available ({e}), falling back to sentence-transformers")
                self.provider = "sentence-transformers"
                self._setup_st()
        else:
            self._setup_st()

    def _setup_st(self):
        from sentence_transformers import SentenceTransformer
        self.model = self.model or "all-MiniLM-L6-v2"
        self._st_model = SentenceTransformer(self.model)
        logger.info(f"Using sentence-transformers: {self.model}")

    def embed(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """Embed one or more texts and return a list of embedding vectors."""
        if isinstance(texts, str):
            texts = [texts]

        if self.provider == "openai":
            response = self._client.embeddings.create(input=texts, model=self.model)
            return [item.embedding for item in response.data]
        else:
            return self._st_model.encode(texts, convert_to_numpy=True).tolist()

    def embed_single(self, text: str) -> List[float]:
        return self.embed([text])[0]
