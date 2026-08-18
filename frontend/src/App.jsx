import React, { useState, useEffect } from "react";
import VoiceOrb from "./components/VoiceOrb";
import DashboardStats from "./components/DashboardStats";
import TranscriptPanel from "./components/TranscriptPanel";
import InventoryTable from "./components/InventoryTable";
import PurchaseOrders from "./components/PurchaseOrders";
import { getInventory, getOrders, getAnalytics, approvePO, rejectPO, startVoiceSession } from "./services/api";
import { Bot, RefreshCw, Cpu, Wifi } from "lucide-react";

export default function App() {
  const [inventory, setInventory] = useState([]);
  const [orders, setOrders] = useState([]);
  const [analytics, setAnalytics] = useState({});
  const [transcripts, setTranscripts] = useState([]);
  const [orbStatus, setOrbStatus] = useState("idle"); // 'idle' | 'listening' | 'thinking' | 'speaking'
  const [sessionActive, setSessionActive] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [loading, setLoading] = useState(false);

  // Fetch initial PostgreSQL database state
  const loadData = async () => {
    setLoading(true);
    try {
      const [invData, ordData, anaData] = await Promise.all([
        getInventory(),
        getOrders(),
        getAnalytics()
      ]);
      if (Array.isArray(invData)) setInventory(invData);
      if (Array.isArray(ordData)) setOrders(ordData);
      if (anaData) setAnalytics(anaData);
    } catch (err) {
      console.error("Error loading dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  // Handle PO Approvals from Dashboard
  const handleApprovePO = async (poId) => {
    try {
      await approvePO(poId);
      addTranscript("system", `🟢 Approved PO #${poId} in PostgreSQL. Inventory updated!`, "Procurement Agent");
      loadData();
    } catch (err) {
      alert("Failed to approve PO: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleRejectPO = async (poId) => {
    try {
      await rejectPO(poId);
      addTranscript("system", `🔴 Rejected PO #${poId} in PostgreSQL. Workflow stopped.`, "Procurement Agent");
      loadData();
    } catch (err) {
      alert("Failed to reject PO: " + (err.response?.data?.detail || err.message));
    }
  };

  const addTranscript = (sender, text, agent = null) => {
    setTranscripts((prev) => [
      ...prev,
      { sender, text, agent, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
    ]);
  };

  // Toggle Live Voice Session
  const handleToggleVoiceSession = async () => {
    if (!sessionActive) {
      setSessionActive(true);
      setOrbStatus("listening");
      addTranscript("user", "Hello Voice AI! Check inventory levels for PLT-A36-6.");
      
      // Simulate multi-agent voice execution pipeline
      setTimeout(() => {
        setOrbStatus("thinking");
        addTranscript("system", "Routing intent: Checking stock levels & reorder thresholds...", "Supervisor Agent");
      }, 1500);

      setTimeout(() => {
        setOrbStatus("speaking");
        addTranscript(
          "agent",
          "PLT-A36-6 stock is currently at 75 units (below reorder threshold 100). Recommended draft: 5 units @ ₹8,200.00 (Total ₹41,000.00). Requesting approval via Slack.",
          "Procurement Agent"
        );
      }, 3500);

      setTimeout(() => {
        setOrbStatus("idle");
      }, 7000);

      try {
        await startVoiceSession();
      } catch (err) {
        console.log("LiveKit connection simulated locally.");
      }
    } else {
      setSessionActive(false);
      setOrbStatus("idle");
      addTranscript("system", "Voice AI session ended.", "LiveKit Client");
    }
  };

  return (
    <div className="min-h-screen p-4 md:p-8 space-y-6">
      {/* Top Navigation Bar */}
      <header className="glass-panel px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-tr from-cyan-500 to-purple-600 text-white shadow-lg">
            <Bot className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-slate-100 via-cyan-200 to-purple-300 bg-clip-text text-transparent">
              Agentic Inventory Control Tower
            </h1>
            <p className="text-[11px] text-slate-400">Voice-Powered B2B Autonomous Procurement Engine</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            <Wifi className="w-3.5 h-3.5 animate-pulse" />
            <span>FastAPI & PostgreSQL Live</span>
          </div>

          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-slate-700"
            title="Refresh Data"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-cyan-400" : ""}`} />
          </button>
        </div>
      </header>

      {/* Main Analytics Row */}
      <DashboardStats analytics={analytics} />

      {/* Centerpiece Voice AI Row — Expanded Orb Panel (7 cols) & Transcript (5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Expanded Siri Glowing Voice AI Orb Panel */}
        <div className="lg:col-span-7">
          <VoiceOrb
            status={orbStatus}
            setStatus={setOrbStatus}
            onTranscript={addTranscript}
            apiBaseUrl="http://localhost:7000"
          />
        </div>

        {/* Live Speech & Agent Transcript Stream */}
        <div className="lg:col-span-5">
          <TranscriptPanel
            transcripts={transcripts}
            agentThought={orbStatus === "thinking" ? "LangGraph: Evaluating supplier quotes & PO thresholds..." : ""}
          />
        </div>
      </div>

      {/* Data Monitoring Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <InventoryTable items={inventory} />
        <PurchaseOrders orders={orders} onApprove={handleApprovePO} onReject={handleRejectPO} />
      </div>

      {/* Footer */}
      <footer className="text-center text-xs text-slate-600 pt-4 border-t border-slate-800/40">
        Voice-Powered B2B Autonomous Procurement System • Powered by LiveKit, Deepgram, Gemini 2.5 Flash & pgvector
      </footer>
    </div>
  );
}
