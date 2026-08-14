import os
import sys
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_connection
from agents.graph import build_graph
from voice.livekit_client import LiveKitClient
from voice.pipeline import VoicePipeline

app = FastAPI(title="Agentic B2B Control Tower Backend")

# Enable CORS for React frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compile LangGraph Multi-Agent network once on startup
agent_app = build_graph()

# In-memory session message history
sessions: dict[str, list] = {}

# ── POST /api/chat ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.post("/api/chat")
async def handle_chat(request: ChatRequest):
    """
    Standard LangGraph runner endpoint.
    Retrieves message history for the given session_id,
    appends the new HumanMessage, executes the graph,
    stores updated history, and returns the worker response.
    """
    try:
        session_id = request.session_id
        if session_id not in sessions:
            sessions[session_id] = []
            
        # Append incoming message
        sessions[session_id].append(HumanMessage(content=request.message))
        
        # Prepare state
        initial_state = {
            "messages": sessions[session_id],
            "next": "",
            "context": {}
        }
        
        # Run graph
        final_state = agent_app.invoke(initial_state)
        
        # Cache updated messages list back to session
        sessions[session_id] = list(final_state["messages"])
        
        # Pull latest AI response
        response_msg = "No reply generated."
        for msg in reversed(final_state["messages"]):
            if hasattr(msg, "content") and msg.content and isinstance(msg, AIMessage):
                response_msg = msg.content
                break
                
        return {
            "response": response_msg,
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/status ────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """Health check endpoint validating PostgreSQL database connectivity."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


# ── GET /api/inventory ─────────────────────────────────────────────────────────

@app.get("/api/inventory")
async def get_inventory():
    """Fetches details on stock levels, checking which SKUs are below reorder limits."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = """
            SELECT i.id, i.sku, p.name, i.warehouse_id, i.stock_level, i.reorder_threshold, p.unit
            FROM inventory i
            JOIN products p ON i.sku = p.sku
            ORDER BY i.sku ASC
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        inventory = []
        for r in rows:
            low_stock = r[4] <= r[5]
            inventory.append({
                "id": str(r[0]),
                "sku": r[1],
                "name": r[2],
                "warehouse_id": r[3],
                "stock_level": r[4],
                "reorder_threshold": r[5],
                "unit": r[6],
                "low_stock_warning": low_stock
            })
        return {"inventory": inventory}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/orders ────────────────────────────────────────────────────────────

@app.get("/api/orders")
async def get_orders():
    """Returns the full purchase orders history combined with line items detail."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = """
            SELECT po.id, po.supplier_id, s.name, po.status, po.created_at
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            ORDER BY po.created_at DESC
        """
        cursor.execute(sql)
        po_rows = cursor.fetchall()
        
        orders = []
        for r in po_rows:
            po_id, supplier_id, name, status, created_at = r
            
            cursor.execute(
                """
                SELECT pli.sku, p.name, pli.quantity, pli.price
                FROM po_line_items pli
                JOIN products p ON pli.sku = p.sku
                WHERE pli.po_id = %s
                """,
                (po_id,)
            )
            li_rows = cursor.fetchall()
            
            line_items = [
                {
                    "sku": li[0],
                    "name": li[1],
                    "quantity": li[2],
                    "price": float(li[3]),
                    "subtotal": li[2] * float(li[3])
                }
                for li in li_rows
            ]
            
            orders.append({
                "po_id": str(po_id),
                "supplier_id": supplier_id,
                "supplier_name": name,
                "status": status,
                "created_at": str(created_at),
                "items": line_items,
                "total_cost": sum(item["subtotal"] for item in line_items)
            })
            
        cursor.close()
        conn.close()
        return {"orders": orders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/db-analytics ──────────────────────────────────────────────────────

@app.get("/api/db-analytics")
async def get_db_analytics():
    """Aggregates transactional statistics for dashboard rendering."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM warehouses")
        total_warehouses = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM suppliers")
        total_suppliers = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM inventory WHERE stock_level <= reorder_threshold")
        low_stock_warnings = cursor.fetchone()[0]
        
        # Financial sum breakdown per PO status
        cursor.execute(
            """
            SELECT po.status, COUNT(DISTINCT po.id), COALESCE(SUM(pli.quantity * pli.price), 0)
            FROM purchase_orders po
            LEFT JOIN po_line_items pli ON po.id = pli.po_id
            GROUP BY po.status
            """
        )
        stats_rows = cursor.fetchall()
        
        breakdown = {}
        for row in stats_rows:
            status, cnt, val = row
            breakdown[status] = {
                "count": cnt,
                "estimated_value": float(val)
            }
            
        cursor.close()
        conn.close()
        
        return {
            "summary": {
                "total_products": total_products,
                "total_warehouses": total_warehouses,
                "total_suppliers": total_suppliers,
                "low_stock_warnings": low_stock_warnings
            },
            "financial_breakdown": breakdown
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ── Lazy-loaded voice pipeline (initialised on first use) ──────────────────────
_voice_pipeline: VoicePipeline | None = None
_livekit_client: LiveKitClient | None = None

def _get_voice_pipeline() -> VoicePipeline:
    global _voice_pipeline
    if _voice_pipeline is None:
        _voice_pipeline = VoicePipeline()
    return _voice_pipeline

def _get_livekit_client() -> LiveKitClient:
    global _livekit_client
    if _livekit_client is None:
        _livekit_client = LiveKitClient()
    return _livekit_client


# ── POST /api/voice/token ─────────────────────────────────────────────────────

class VoiceTokenRequest(BaseModel):
    session_id: str
    room_name: str = "procurement-room"

@app.post("/api/voice/token")
async def get_voice_token(request: VoiceTokenRequest):
    """
    Issue a signed LiveKit JWT token for the frontend WebRTC client.
    LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_URL must be set in .env.
    """
    try:
        lk = _get_livekit_client()
        token = lk.generate_token(
            room_name=request.room_name,
            participant_name=request.session_id,
        )
        return {
            "token": token,
            "livekit_url": lk.livekit_url,
            "room": request.room_name,
        }
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /api/voice/upload ────────────────────────────────────────────────────

@app.post("/api/voice/upload")
async def handle_voice_upload(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    tts_enabled: bool = Form(True),
):
    """
    Accepts an audio file upload, transcribes it via Deepgram STT, runs
    the transcript through the LangGraph agent network, and returns both
    the text reply and synthesised speech (ElevenLabs) as audio/mpeg.

    Form fields:
      - session_id   : unique conversation identifier
      - audio        : audio file (wav / mp3 / webm / ogg etc.)
      - tts_enabled  : whether to return TTS audio (default True)
    """
    try:
        audio_bytes = await audio.read()
        mime_type = audio.content_type or "audio/wav"

        pipeline = _get_voice_pipeline()
        result = pipeline.run(
            audio_bytes=audio_bytes,
            session_id=session_id,
            mime_type=mime_type,
        )

        if tts_enabled and result.get("audio"):
            # Return synthesised speech directly as audio stream
            return Response(
                content=result["audio"],
                media_type="audio/mpeg",
                headers={
                    "X-Transcript": result["transcript"][:500],
                    "X-Intent": str(result["intent"].get("intent", "")),
                    "X-Agent-Response": result["response"][:500],
                },
            )

        return {
            "transcript": result["transcript"],
            "intent": result["intent"],
            "response": result["response"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /voice-ui ─────────────────────────────────────────────────────────────

@app.get("/voice-ui", response_class=HTMLResponse)
@app.get("/demo", response_class=HTMLResponse)
async def serve_voice_ui():
    """
    Renders the interactive Voice-to-Voice AI Procurement dashboard.
    """
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "voice_ui.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="voice_ui.html template not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn
    # Pre-configure UTF-8 encoding support
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    uvicorn.run(app, host="0.0.0.0", port=7000)
