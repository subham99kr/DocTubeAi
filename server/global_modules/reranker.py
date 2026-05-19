from sentence_transformers import CrossEncoder

_reranker = None


def get_reranker():

    global _reranker

    if _reranker is None:

        _reranker = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )

    return _reranker