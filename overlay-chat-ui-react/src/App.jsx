import React, { useMemo, useState } from "react";
import {
  Send, Upload, Users, Shield, Link as LinkIcon, WifiOff,
  Plus, File, Lock, MessageSquare, Search, X
} from "lucide-react";

// ----- mock data -----
const MOCK_PEERS = [
  { id: "a1b2c3", nick: "alpha", status: "online" },
  { id: "d4e5f6", nick: "bravo", status: "online" },
  { id: "0f1e2d", nick: "charlie", status: "offline" },
];

const MOCK_GROUPS = [{ id: "g-demo", name: "Demo Group", members: ["alpha", "bravo"] }];

const MOCK_MESSAGES = [
  { id: 1, from: "alpha", to: "me", text: "Hey there!", ts: Date.now() - 560000 },
  { id: 2, from: "me", to: "alpha", text: "Hi! Secure channel up.", ts: Date.now() - 555000 },
  { id: 3, from: "bravo", to: "g-demo", text: "Group chat also works.", ts: Date.now() - 450000 },
  { id: 4, from: "me", to: "g-demo", text: "Nice! sending file soon…", ts: Date.now() - 445000 },
];

// ----- utils -----
const cx = (...xs) => xs.filter(Boolean).join(" ");
const timeAgo = (ts) => {
  const d = Math.floor((Date.now() - ts) / 1000);
  if (d < 60) return `${d}s`;
  const m = Math.floor(d / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h`;
};

// ----- small components -----
function TopBar({ connected, onToggle }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-950/60">
      <div className="flex items-center gap-2 text-zinc-200">
        <Shield className="w-5 h-5" />
        <span className="font-semibold">Overlay Chat</span>
        <span className="ml-3 text-xs text-zinc-400 hidden md:inline">Prototype UI • Mock data</span>
      </div>
      <div className="flex items-center gap-3">
        <div className={cx("text-xs px-2 py-1 rounded-full border",
          connected ? "border-emerald-500 text-emerald-400" : "border-zinc-600 text-zinc-400")}>
          {connected ? "Secure session active" : "Not connected"}
        </div>
        <button onClick={onToggle}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700">
          {connected ? <WifiOff className="w-4 h-4" /> : <LinkIcon className="w-4 h-4" />}
          {connected ? "Disconnect" : "Connect"}
        </button>
      </div>
    </div>
  );
}

function Sidebar({ peers, groups, onNewGroup }) {
  return (
    <div className="w-full md:w-72 border-r border-zinc-800 bg-zinc-950/70 p-3 flex flex-col gap-4">
      <div>
        <div className="flex items-center justify-between text-zinc-400 text-xs mb-2">
          <div className="flex items-center gap-2"><Users className="w-4 h-4" /><span>Peers</span></div>
          <Search className="w-4 h-4" />
        </div>
        <div className="space-y-1">
          {peers.map(p => (
            <div key={p.id} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-zinc-800/60 cursor-pointer">
              <div className={cx("w-2 h-2 rounded-full", p.status === "online" ? "bg-emerald-500" : "bg-zinc-600")} />
              <div>
                <div className="text-zinc-200 text-sm">{p.nick}</div>
                <div className="text-[10px] text-zinc-500">{p.id}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="flex items-center justify-between text-zinc-400 text-xs mb-2">
          <div className="flex items-center gap-2"><MessageSquare className="w-4 h-4" /><span>Groups</span></div>
          <button onClick={onNewGroup} className="text-zinc-400 hover:text-zinc-200"><Plus className="w-4 h-4" /></button>
        </div>
        <div className="space-y-1">
          {groups.map(g => (
            <div key={g.id} className="px-2 py-1.5 rounded-lg hover:bg-zinc-800/60 cursor-pointer">
              <div className="text-zinc-200 text-sm">{g.name}</div>
              <div className="text-[10px] text-zinc-500">{g.id} • {g.members.length} members</div>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-auto text-[11px] text-zinc-500 pt-2 border-t border-zinc-800">UI mock • Tailwind • Lucide</div>
    </div>
  );
}

function ChatBubble({ m }) {
  const mine = m.from === "me";
  return (
    <div className={cx("flex", mine ? "justify-end" : "justify-start")}>
      <div className={cx(
        "max-w-[75%] rounded-2xl px-3 py-2 mb-2 shadow border",
        mine ? "bg-emerald-600/20 text-emerald-100 border-emerald-700" :
               "bg-zinc-800/70 text-zinc-100 border-zinc-700"
      )}>
        <div className="text-xs text-zinc-400 mb-0.5">{mine ? "you" : m.from} • {timeAgo(m.ts)}</div>
        <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
      </div>
    </div>
  );
}

function ChatPane({ messages, onSend, onSendFile }) {
  const [text, setText] = useState("");
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto p-4 space-y-1 bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-950">
        {messages.map(m => <ChatBubble key={m.id} m={m} />)}
      </div>
      <div className="border-t border-zinc-800 p-3">
        <div className="flex items-center gap-2">
          <button onClick={onSendFile}
                  className="p-2 rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-200" title="Send file">
            <Upload className="w-5 h-5" />
          </button>
          <input
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Type a secure message…"
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-3 py-2 text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-emerald-600"
          />
          <button
            onClick={() => { if (text.trim()) { onSend(text); setText(""); } }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white">
            <Send className="w-4 h-4" /> Send
          </button>
        </div>
      </div>
    </div>
  );
}

function FileModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur flex items-center justify-center p-4 z-50">
      <div className="w-full max-w-lg rounded-2xl border border-zinc-700 bg-zinc-900 text-zinc-100 shadow-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <div className="flex items-center gap-2 text-zinc-300"><File className="w-4 h-4" /><span>Send a file</span></div>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-4 space-y-3">
          <div className="text-sm text-zinc-400">This is a mock modal. In the real app, we’ll show chunking progress and ACKs.</div>
          <div className="rounded-xl border border-zinc-700 bg-zinc-800 p-4">
            <div className="text-xs text-zinc-400 mb-2">Choose file</div>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-zinc-300"><File className="w-4 h-4" /><span>report.pdf</span></div>
              <div className="text-xs text-zinc-400">1.2 MB</div>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2">
            <button onClick={onClose} className="px-3 py-2 rounded-xl border border-zinc-700 text-zinc-300 hover:bg-zinc-800">Cancel</button>
            <button className="px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white inline-flex items-center gap-2"><Lock className="w-4 h-4" /> Send securely</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [connected, setConnected] = useState(false);
  const [showFile, setShowFile] = useState(false);
  const [msgs, setMsgs] = useState(MOCK_MESSAGES);
  const peers = useMemo(() => MOCK_PEERS, []);
  const groups = useMemo(() => MOCK_GROUPS, []);

  const handleSend = (text) => {
    const m = { id: Date.now(), from: "me", to: "alpha", text, ts: Date.now() };
    setMsgs(prev => [...prev, m]);
  };

  return (
    <div className="h-screen w-full bg-zinc-950 text-zinc-100 flex flex-col">
      <TopBar connected={connected} onToggle={() => setConnected(v => !v)} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar peers={peers} groups={groups} onNewGroup={() => {}} />
        <div className="flex-1 min-w-0">
          <div className="h-full grid grid-rows-[auto_1fr]">
            <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-900/60 flex items-center justify-between">
              <div className="text-sm text-zinc-300 inline-flex items-center gap-2">
                <MessageSquare className="w-4 h-4" /> Channel: <span className="font-medium text-zinc-100">alpha</span>
              </div>
              <div className="text-xs text-zinc-400">AEAD: ChaCha20-Poly1305 • Handshake: Noise XX</div>
            </div>
            <ChatPane messages={msgs} onSend={handleSend} onSendFile={() => setShowFile(true)} />
          </div>
        </div>
      </div>
      <FileModal open={showFile} onClose={() => setShowFile(false)} />
    </div>
  );
}
