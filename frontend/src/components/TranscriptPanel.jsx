import React from "react";
import { MessageSquare, Bot, User, Cpu } from "lucide-react";

export default function TranscriptPanel({ transcripts = [], agentThought = "" }) {
  return (
    <div className="glass-panel p-5 h-[380px] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-200">Live Agent Execution & Speech Stream</h3>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-mono">
          REAL-TIME WEBRTC
        </span>
      </div>

      {/* Transcript Feed */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {transcripts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6">
            <Bot className="w-8 h-8 text-slate-600 mb-2 animate-bounce" />
            <p className="text-xs text-slate-500 font-medium">
              Click the glowing Voice AI orb to initiate a voice conversation.
            </p>
            <p className="text-[11px] text-slate-600 mt-1">
              Example: "Check inventory for PLT-A36-6 and draft a PO if low"
            </p>
          </div>
        ) : (
          transcripts.map((msg, idx) => (
            <div
              key={idx}
              className={`flex items-start gap-2.5 ${
                msg.sender === "user" ? "flex-row-reverse" : "flex-row"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0 ${
                  msg.sender === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gradient-to-r from-purple-600 to-cyan-500 text-white"
                }`}
              >
                {msg.sender === "user" ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
              </div>

              <div
                className={`max-w-[82%] rounded-2xl px-3.5 py-2 text-xs leading-relaxed ${
                  msg.sender === "user"
                    ? "bg-blue-600/20 text-blue-100 border border-blue-500/30 rounded-tr-none"
                    : "bg-slate-800/80 text-slate-200 border border-slate-700/80 rounded-tl-none"
                }`}
              >
                {msg.agent && (
                  <div className="flex items-center gap-1.5 mb-1 text-[10px] text-purple-400 font-mono font-medium">
                    <Cpu className="w-3 h-3" />
                    <span>{msg.agent}</span>
                  </div>
                )}
                <p>{msg.text}</p>
                <span className="text-[9px] text-slate-500 mt-1 block text-right">
                  {msg.time || "Just now"}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Active Multi-Agent Thought Indicator */}
      {agentThought && (
        <div className="mt-3 p-2 rounded-lg bg-purple-950/40 border border-purple-500/30 flex items-center gap-2 text-xs text-purple-300">
          <Cpu className="w-3.5 h-3.5 animate-spin text-purple-400" />
          <span className="font-mono text-[11px] truncate">{agentThought}</span>
        </div>
      )}
    </div>
  );
}
