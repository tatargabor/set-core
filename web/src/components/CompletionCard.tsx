import { useState } from "react";

interface CompletionCardProps {
  project: string;
  timeout?: number;
  onAction?: (action: string) => void;
}

export function CompletionCard({ project, timeout = 300, onAction }: CompletionCardProps) {
  const [specPath, setSpecPath] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<string | null>(null);

  const sendAction = async (action: string, spec?: string) => {
    setSending(true);
    try {
      const res = await fetch(`/api/${project}/completion`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, spec: spec || "" }),
      });
      if (res.ok) {
        setSent(action);
        onAction?.(action);
      }
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <div className="border border-green-500/30 bg-green-500/10 rounded-lg p-4 mb-4">
        <div className="text-green-400 font-mono text-sm">
          Action sent: <span className="font-bold">{sent}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-amber-500/30 bg-amber-500/10 rounded-lg p-4 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-amber-400 text-lg">🏁</span>
        <h3 className="text-amber-200 font-mono font-bold text-sm">Orchestration Complete</h3>
      </div>
      <p className="text-zinc-400 text-xs font-mono mb-3">
        All changes resolved. Auto-stop in {timeout}s if no action taken.
      </p>
      <div className="flex flex-wrap gap-2 mb-3">
        <button
          onClick={() => sendAction("accept")}
          disabled={sending}
          className="px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white text-xs font-mono rounded disabled:opacity-50"
        >
          ✅ Accept & Stop
        </button>
        <button
          onClick={() => sendAction("rerun")}
          disabled={sending}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono rounded disabled:opacity-50"
        >
          🔄 Re-run
        </button>
      </div>
      <div className="flex gap-2 items-center">
        <input
          type="text"
          value={specPath}
          onChange={(e) => setSpecPath(e.target.value)}
          placeholder="docs/v2.md"
          className="flex-1 px-2 py-1 bg-zinc-800 border border-zinc-600 rounded text-xs font-mono text-zinc-300 placeholder:text-zinc-600"
        />
        <button
          onClick={() => specPath && sendAction("newspec", specPath)}
          disabled={sending || !specPath}
          className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-mono rounded disabled:opacity-50"
        >
          📋 New Spec
        </button>
      </div>
    </div>
  );
}
