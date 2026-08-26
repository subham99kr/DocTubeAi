"""
Voice status narration.

Converts meaningful internal LangGraph execution phases into
short natural-language messages suitable for TTS.

This module sits between:

    LangGraph
        ↓
    VoiceGraphRunner
        ↓
    VoiceStatusManager
        ↓
    VoiceGraphEvent
        ↓
    TTS

The manager intentionally hides LangGraph implementation
details from the voice pipeline.

Responsibilities
----------------
    - Translate meaningful graph phases into voice-friendly text.
    - Deduplicate repeated phases during retrieval/tool loops.
    - Keep status narration independent from TTS.
    - Prevent internal graph implementation details from
      leaking into the user experience.

This module does NOT
--------------------
    - execute LangGraph
    - perform retrieval
    - perform web search
    - perform reranking
    - evaluate retrieved evidence
    - perform TTS
    - stream assistant answer text


Current DocTubeAI graph phases
------------------------------

    router
        ↓
    tool_call
        ↓
    vector_search / internet_search / web_scraper
        ↓
    reranker
        ↓
    retrieval_evaluator
        ↓
    rag_chatbot

or:

    router
        ↓
    simple_chat

Only the retrieval-related phases need explicit narration.

The following remain silent:

    router
    tool_call
    simple_chat
    rag_chatbot
    prune

The final assistant answer is streamed separately by
VoiceGraphRunner and should never be treated as a status.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ============================================================
# VOICE STATUS MANAGER
# ============================================================

@dataclass(slots=True)
class VoiceStatusManager:
    """
    Converts meaningful LangGraph node activity into short,
    natural-language voice status messages.

    A conceptual status is announced at most once per
    assistant turn.

    Example:

        vector_search
            ↓
        "I'm checking your documents."

        reranker
            ↓
        "I'm narrowing down the most relevant information."

        retrieval_evaluator
            ↓
        "I'm rechecking the information I found."

    If the graph enters vector_search multiple times because
    of a retrieval loop, the user still hears the document
    search status only once.
    """

    # --------------------------------------------------------
    # Tracks statuses already announced during the current
    # assistant turn.
    # --------------------------------------------------------

    announced: set[str] = field(
        default_factory=set
    )

    # ========================================================
    # RESET
    # ========================================================

    def reset(self) -> None:
        """
        Reset status announcements for a new assistant turn.

        VoiceGraphRunner calls this before every new graph
        execution.

        Example:

            Turn 1:
                vector_search
                → status announced

            Turn 2:
                vector_search
                → status announced again

        Without reset(), Turn 2 would incorrectly remain silent.
        """

        self.announced.clear()

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(
        self,
        node_name: str | None,
    ) -> str | None:
        """
        Convert a LangGraph node name into a user-facing
        voice status.

        Parameters
        ----------
        node_name:
            Internal LangGraph node name obtained from:

                event["metadata"]["langgraph_node"]

        Returns
        -------
        str | None

            A short natural-language status when the graph
            reaches a meaningful user-facing phase.

            None when:

                - the node is unknown
                - the node is intentionally silent
                - the same conceptual phase was already announced
                  during this assistant turn
        """

        if not node_name:
            return None

        # ====================================================
        # DOCUMENT RETRIEVAL
        # ====================================================

        if node_name == "vector_search":

            return self._once(
                key="documents",
                message=(
                    "I'm checking your documents."
                ),
            )

        # ====================================================
        # INTERNET SEARCH
        # ====================================================

        if node_name == "internet_search":

            return self._once(
                key="web_search",
                message=(
                    "I'm checking the web for more information."
                ),
            )

        # ====================================================
        # WEBPAGE RETRIEVAL
        # ====================================================

        if node_name == "web_scraper":

            return self._once(
                key="web_pages",
                message=(
                    "I'm looking through the relevant information."
                ),
            )

        # ====================================================
        # RERANKING
        # ====================================================

        if node_name == "reranker":

            return self._once(
                key="reranking",
                message=(
                    "I'm narrowing down the most relevant information."
                ),
            )

        # ====================================================
        # RETRIEVAL EVALUATION
        # ====================================================

        if node_name == "retrieval_evaluator":

            return self._once(
                key="verification",
                message=(
                    "I'm rechecking the information I found."
                ),
            )

        # ====================================================
        # SILENT INTERNAL NODES
        # ====================================================

        # These nodes intentionally produce no narration:
        #
        #     router
        #     tool_call
        #     simple_chat
        #     rag_chatbot
        #     prune
        #
        # Why?
        #
        # router:
        #     "I'm routing your request" adds no useful value.
        #
        # tool_call:
        #     Internal planning detail.
        #
        # simple_chat:
        #     The response starts streaming immediately.
        #
        # rag_chatbot:
        #     The final answer starts streaming immediately.
        #
        # prune:
        #     Internal state cleanup.
        #
        # The voice layer should expose user-relevant progress,
        # not graph implementation details.
        # ====================================================

        return None

    # ========================================================
    # DEDUPLICATION
    # ========================================================

    def _once(
        self,
        key: str,
        message: str,
    ) -> str | None:
        """
        Return a status only the first time that conceptual
        phase is encountered during the current assistant turn.

        This is intentionally based on a logical key rather
        than the raw LangGraph node name.

        Example:

            vector_search
            vector_search
            vector_search

        becomes:

            "I'm checking your documents."

        only once.

        This is especially important because the graph may
        perform multiple retrieval/tool iterations.
        """

        if key in self.announced:
            return None

        self.announced.add(key)

        return message