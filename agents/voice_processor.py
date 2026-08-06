"""
agents/voice_processor.py
--------------------------
Receives a raw text transcript from Deepgram STT and routes it to the
correct procurement intent, which the LangGraph supervisor then dispatches.
"""

import re


class VoiceProcessor:
    """
    Intent parser for voice transcripts.
    Receives plain-text output from Deepgram and maps it to a structured 
    intent + parameters dict consumed by the LangGraph supervisor node.
    """

    def parse_intent(self, text: str) -> dict:
        """
        Parse a Deepgram transcript into a procurement intent.

        Args:
            text: Raw transcript string from Deepgram STT.

        Returns:
            {"intent": str, "params": dict}
        """
        text = text.lower().strip()

        # ── Shortage / Low-Stock Check ────────────────────────────────────
        if any(kw in text for kw in ["shortage", "out of stock", "running low", "low stock"]):
            return {
                "intent": "CHECK_SHORTAGE",
                "params": {
                    "timeframe": "next month" if "next month" in text else "now",
                    "sku": self._extract_sku(text),
                }
            }

        # ── Demand Forecast ───────────────────────────────────────────────
        if any(kw in text for kw in ["forecast", "predict", "demand", "how much do we need"]):
            return {
                "intent": "FORECAST_DEMAND",
                "params": {"sku": self._extract_sku(text)}
            }

        # ── Inventory / Stock Status ──────────────────────────────────────
        if any(kw in text for kw in ["inventory", "stock", "status", "how many", "current level"]):
            return {
                "intent": "STOCK_STATUS",
                "params": {"sku": self._extract_sku(text)}
            }

        # ── Risk Assessment ───────────────────────────────────────────────
        if any(kw in text for kw in ["risk", "reliable", "reliability", "assess", "delay", "penalty"]):
            return {
                "intent": "ASSESS_RISK",
                "params": {"sku": self._extract_sku(text)}
            }

        # ── Best Supplier / Quote ─────────────────────────────────────────
        if any(kw in text for kw in ["supplier", "vendor", "cheapest", "best quote", "best price"]):
            return {
                "intent": "FIND_SUPPLIER",
                "params": {"sku": self._extract_sku(text)}
            }

        # ── Purchase Order Approval ───────────────────────────────────────
        if any(kw in text for kw in ["approve", "place order", "go ahead", "confirm purchase", "yes"]):
            return {
                "intent": "APPROVE_ORDER",
                "params": {}
            }

        # ── RAG / Contract / Policy Query ─────────────────────────────────
        if any(kw in text for kw in ["contract", "policy", "sop", "terms", "penalty clause", "escalation"]):
            return {
                "intent": "POLICY_QUERY",
                "params": {"query": text}
            }

        # ── Fallback ──────────────────────────────────────────────────────
        return {"intent": "GENERAL_QUERY", "params": {"query": text}}

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_sku(text: str) -> str | None:
        """
        Extract a SKU code referenced in the transcript.
        Patterns: SCR-M8-001, PLT-A36-6, ALU-ING-01, etc.
        """
        match = re.search(r"\b([A-Z]{2,4}-[A-Z0-9]+-[A-Z0-9]+)\b", text.upper())
        return match.group(1) if match else None
