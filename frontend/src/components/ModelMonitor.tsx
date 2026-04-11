import { useEffect, useState } from "react";
import { getUserDebugState } from "@/lib/api";
import { Zap, RotateCw } from "lucide-react";

interface ModelMonitorProps {
  userId: string | null;
  refreshInterval?: number; // milliseconds
}

export const ModelMonitor = ({ userId, refreshInterval = 10000 }: ModelMonitorProps) => {
  const [state, setState] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const refresh = async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const data = await getUserDebugState(userId);
      setState(data);
      setLastUpdate(new Date());
    } catch (err) {
      console.error("Failed to refresh model state:", err);
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh on interval
  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, refreshInterval);
    return () => clearInterval(interval);
  }, [userId, refreshInterval]);

  if (!state) return null;

  const getReadyStatus = () => {
    if (state.model_ready) return { text: "✓ Learning Active", color: "text-green-600" };
    if (state.interactions > 0) return { text: "⏳ Gathering Data", color: "text-yellow-600" };
    return { text: "○ No Data Yet", color: "text-gray-600" };
  };

  const status = getReadyStatus();

  return (
    <div className="fixed bottom-4 right-4 z-40 w-72 rounded-lg border border-blue-200 bg-white p-4 shadow-lg">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`h-2 w-2 rounded-full ${state.model_ready ? "bg-green-500" : "bg-yellow-500"} animate-pulse`} />
          <h3 className="font-semibold text-sm text-gray-900">Model Learning</h3>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="p-1 hover:bg-gray-100 rounded transition-colors"
          title="Refresh model state"
        >
          <RotateCw className={`h-4 w-4 text-gray-600 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Status */}
      <div className={`mb-3 text-sm font-medium ${status.color}`}>{status.text}</div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="bg-blue-50 rounded p-2">
          <div className="text-xs text-blue-600 font-medium">Interactions</div>
          <div className="text-xl font-bold text-blue-900">{state.interactions}</div>
        </div>
        <div className="bg-green-50 rounded p-2">
          <div className="text-xs text-green-600 font-medium">Liked</div>
          <div className="text-xl font-bold text-green-900">{state.liked_count}</div>
        </div>
        <div className="bg-red-50 rounded p-2">
          <div className="text-xs text-red-600 font-medium">Disliked</div>
          <div className="text-xl font-bold text-red-900">{state.disliked_count}</div>
        </div>
        <div className="bg-purple-50 rounded p-2">
          <div className="text-xs text-purple-600 font-medium">Irritation</div>
          <div className="text-xl font-bold text-purple-900">{state.irritation_count}</div>
        </div>
      </div>

      {/* Message */}
      <div className="text-xs text-gray-600 bg-gray-50 rounded p-2">
        {state.model_ready
          ? "🎉 Model is personalizing! Scores below are live."
          : state.interactions > 0
            ? `📊 Need ${Math.max(0, 1 - state.liked_count)} more like and ${Math.max(0, 1 - state.disliked_count)} more dislike.`
            : "👉 Start swiping to train the model!"}
      </div>

      {/* Last Update */}
      {lastUpdate && (
        <div className="mt-2 text-xs text-gray-500 text-center">
          Updated {Math.round((Date.now() - lastUpdate.getTime()) / 1000)}s ago
        </div>
      )}
    </div>
  );
};
