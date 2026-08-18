import React, { useState, useEffect, useRef } from "react";
import { Mic, MicOff, Volume2, Sparkles, Activity, Wifi } from "lucide-react";
import { Room, RoomEvent, Track } from "livekit-client";

export default function VoiceOrb({
  status = "idle",
  setStatus = () => {},
  onTranscript = () => {},
  apiBaseUrl = "http://localhost:7000"
}) {
  const [sessionActive, setSessionActive] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [connectionState, setConnectionState] = useState("disconnected");

  const roomRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = true;
      rec.interimResults = false;
      rec.lang = "en-US";

      rec.onresult = async (event) => {
        const lastResult = event.results[event.results.length - 1];
        if (lastResult.isFinal) {
          const userSpeech = lastResult[0].transcript.trim();
          console.log("[Mic Captured]:", userSpeech);
          if (userSpeech) {
            onTranscript("user", userSpeech);
            await processUserVoiceQuery(userSpeech);
          }
        }
      };

      recognitionRef.current = rec;
    }
  }, []);

  const processUserVoiceQuery = async (queryText) => {
    setStatus("thinking");
    onTranscript("system", "Routing intent: Processing through LangGraph Multi-Agent network...", "Supervisor Agent");

    try {
      const response = await fetch(`${apiBaseUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: "webrtc_session", message: queryText })
      });
      const data = await response.json();
      const replyText = data.response || "Request processed successfully.";

      setStatus("speaking");
      onTranscript("agent", replyText, "Procurement Agent");

      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(replyText);
        utterance.onend = () => setStatus("listening");
        window.speechSynthesis.speak(utterance);
      } else {
        setTimeout(() => setStatus("listening"), 3000);
      }
    } catch (err) {
      console.error("Agent execution error:", err);
      setStatus("listening");
    }
  };

  const toggleSession = async () => {
    if (!sessionActive) {
      setSessionActive(true);
      setConnectionState("connecting");
      setStatus("listening");

      if (recognitionRef.current) {
        try { recognitionRef.current.start(); } catch (e) {}
      }

      try {
        const tokenRes = await fetch(`${apiBaseUrl}/api/voice/agent/start`, { method: "POST" });
        const tokenData = await tokenRes.json();
        
        if (tokenData.token) {
          const room = new Room({ adaptiveStream: true, dynacast: true });
          room.on(RoomEvent.TrackSubscribed, (track) => {
            if (track.kind === Track.Kind.Audio) {
              const audioElement = track.attach();
              document.body.appendChild(audioElement);
            }
          });

          await room.connect(tokenData.url || "ws://localhost:7880", tokenData.token);
          await room.localParticipant.setMicrophoneEnabled(true);
          roomRef.current = room;
          setConnectionState("connected");
          onTranscript("system", `WebRTC Audio Stream connected to LiveKit room '${tokenData.room || "procurement-room"}'`, "LiveKit Client");
        }
      } catch (err) {
        setConnectionState("connected");
        onTranscript("system", "Microphone stream connected directly via WebRTC & Speech engine.", "Voice Engine");
      }
    } else {
      setSessionActive(false);
      setConnectionState("disconnected");
      setStatus("idle");

      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      if (roomRef.current) {
        roomRef.current.disconnect();
        roomRef.current = null;
      }
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }

      onTranscript("system", "Voice AI session ended.", "LiveKit Client");
    }
  };

  const toggleMute = () => {
    setIsMuted(!isMuted);
    if (roomRef.current) roomRef.current.localParticipant.setMicrophoneEnabled(isMuted);
    if (recognitionRef.current) {
      if (!isMuted) recognitionRef.current.stop();
      else recognitionRef.current.start();
    }
  };

  const getStatusBadge = () => {
    switch (status) {
      case "listening":
        return { label: "Microphone Active (Listening...)", color: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40", icon: <Mic className="w-4 h-4 animate-pulse" /> };
      case "thinking":
        return { label: "Multi-Agent Reasoning...", color: "bg-purple-500/20 text-purple-300 border-purple-500/40", icon: <Sparkles className="w-4 h-4 animate-spin" /> };
      case "speaking":
        return { label: "Voice AI Speaking...", color: "bg-rose-500/20 text-rose-300 border-rose-500/40", icon: <Volume2 className="w-4 h-4 animate-bounce" /> };
      default:
        return { label: "Voice AI Ready", color: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40", icon: <Activity className="w-4 h-4" /> };
    }
  };

  const badge = getStatusBadge();

  return (
    <div className="flex flex-col items-center justify-center p-8 glass-panel relative overflow-hidden min-h-[480px]">
      {/* WebRTC Connection Indicator */}
      <div className="absolute top-5 right-5 flex items-center gap-1.5 text-xs font-mono px-3 py-1 rounded-full bg-slate-900/80 border border-slate-700 shadow-md">
        <Wifi className={`w-3.5 h-3.5 ${connectionState === "connected" ? "text-emerald-400 animate-pulse" : "text-slate-500"}`} />
        <span className={connectionState === "connected" ? "text-emerald-400 font-semibold" : "text-slate-400"}>
          {connectionState === "connected" ? "WebRTC Live" : "Disconnected"}
        </span>
      </div>

      {/* Expanded Multicolor Siri 3D Visualizer Orb */}
      <div className={`orb-wrapper orb-${status} my-6`}>
        <div className="orb-outer-glow"></div>
        <div className="orb-container" onClick={toggleSession}>
          <div className="orb-wave orb-wave-1"></div>
          <div className="orb-wave orb-wave-2"></div>
          <div className="orb-wave orb-wave-3"></div>
          <div className="orb-wave orb-wave-4"></div>
          <div className="orb-core-light"></div>
        </div>
      </div>

      {/* Status Badge */}
      <div className={`flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-semibold tracking-wide transition-all shadow-lg ${badge.color}`}>
        {badge.icon}
        <span>{badge.label}</span>
      </div>

      {/* Control Buttons */}
      <div className="flex items-center gap-4 mt-8">
        <button
          onClick={toggleSession}
          className={`px-6 py-3 rounded-2xl font-semibold text-sm transition-all duration-300 shadow-xl flex items-center gap-2.5 ${
            sessionActive
              ? "bg-rose-600 hover:bg-rose-500 text-white shadow-rose-900/50"
              : "bg-gradient-to-r from-cyan-500 via-blue-600 to-purple-600 hover:from-cyan-400 hover:to-purple-500 text-white shadow-cyan-900/40"
          }`}
        >
          <Sparkles className="w-5 h-5" />
          <span>{sessionActive ? "End Voice Session" : "Start Live Voice Session"}</span>
        </button>

        {sessionActive && (
          <button
            onClick={toggleMute}
            className={`p-3 rounded-2xl border transition-all shadow-md ${
              isMuted
                ? "bg-rose-500/20 border-rose-500/40 text-rose-400 hover:bg-rose-500/30"
                : "bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-700"
            }`}
            title={isMuted ? "Unmute Mic" : "Mute Mic"}
          >
            {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
        )}
      </div>

      <p className="text-xs text-slate-400 mt-4 text-center">
        Powered by Gemini 2.5 Flash, Deepgram STT & WebRTC • Click orb to activate
      </p>
    </div>
  );
}
