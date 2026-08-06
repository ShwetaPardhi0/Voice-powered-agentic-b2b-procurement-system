import re

class VoiceProcessor:
    """Simple NLP engine to parse voice transcripts into intents."""
    
    def parse_intent(self, text: str):
        text = text.lower()
        
        if any(word in text for word in ["shortage", "out of stock", "running low"]):
            return {
                "intent": "CHECK_SHORTAGE",
                "params": {
                    "timeframe": "next month" if "next month" in text else "now"
                }
            }
            
        if any(word in text for word in ["status", "inventory", "stock"]):
            return {
                "intent": "STOCK_STATUS",
                "params": {}
            }
            
        if "approve" in text or "yes" in text or "go ahead" in text:
            return {
                "intent": "APPROVE_ORDER",
                "params": {}
            }

        return {"intent": "UNKNOWN", "params": {}}
