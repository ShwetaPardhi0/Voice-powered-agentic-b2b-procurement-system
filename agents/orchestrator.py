from agents.inventory_agent import InventoryAgent
from agents.forecast_agent import ForecastAgent
from agents.supplier_agent import SupplierAgent
from agents.procurement_agent import ProcurementAgent
from agents.risk_agent import RiskAgent
from agents.voice_processor import VoiceProcessor

class B2BOrchestrator:
    def __init__(self):
        self.inventory = InventoryAgent()
        self.forecast = ForecastAgent()
        self.supplier = SupplierAgent()
        self.procurement = ProcurementAgent()
        self.risk = RiskAgent()
        self.voice = VoiceProcessor()
        self.pending_approval = None

    def handle_voice_command(self, transcript: str):
        intent_data = self.voice.parse_intent(transcript)
        intent = intent_data["intent"]
        params = intent_data["params"]

        if intent == "CHECK_SHORTAGE":
            return self._handle_shortage_check(params)
        elif intent == "APPROVE_ORDER":
            return self._handle_approval()
        elif intent == "STOCK_STATUS":
            return self._handle_stock_status()
        else:
            return "I'm sorry, I didn't quite catch that. Could you repeat?"

    def _handle_shortage_check(self, params):
        inventory = self.inventory.get_stock_level()
        results = []
        
        for item in inventory:
            sku = item["sku"]
            shortage, amount = self.forecast.will_face_shortage(sku, item["stock_level"])
            
            if shortage:
                # Find best supplier
                best_quote = self.supplier.get_best_quote(sku, amount)
                if best_quote:
                    # Check risk before proceeding
                    risk_assessment = self.risk.get_risk_assessment(best_quote["vendor_id"])
                    risk_warning = ""
                    if risk_assessment["status"] != "SAFE":
                        risk_warning = f" [RISK ALERT: {risk_assessment['warning']}]"

                    # Try to process order
                    outcome = self.procurement.process_order_request(sku, amount, best_quote)
                    
                    response_msg = outcome["message"]
                    if risk_warning:
                        response_msg += risk_warning
                        
                    if outcome["action"] == "APPROVAL_REQUIRED":
                        self.pending_approval = outcome["details"]
                    results.append(response_msg)
                else:
                    results.append(f"We will face a shortage of {amount} {item['unit']} of {item['name']}, but no suppliers were found.")
        
        if not results:
            return "Current stock levels and forecasts look healthy for next month. No shortages expected."
        
        return " ".join(results)

    def _handle_approval(self):
        if not self.pending_approval:
            return "There are no orders pending approval."
        
        # Manually finalize order
        self.procurement._log_order(self.pending_approval)
        msg = f"Order for {self.pending_approval['sku']} has been approved and placed with {self.pending_approval['vendor_name']}."
        self.pending_approval = None
        return msg

    def _handle_stock_status(self):
        inventory = self.inventory.get_stock_level()
        status_lines = [f"{item['name']}: {item['stock_level']} {item['unit']}" for item in inventory]
        return "Current stock levels: " + ", ".join(status_lines)
