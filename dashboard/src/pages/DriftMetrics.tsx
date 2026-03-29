import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

export default function DriftMetrics() {
  const { data: alerts } = useQuery({
    queryKey: ["drift-alerts"],
    queryFn: api.drift.alerts,
  });

  const items = alerts ?? [];

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Drift Metrics</h1>

      {items.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center text-gray-500">
          No active drift warnings. All metrics are within thresholds.
        </div>
      ) : (
        <div className="grid gap-4">
          {items.map((alert, i) => (
            <div
              key={i}
              className={`bg-white rounded-lg border p-6 ${
                alert.breach_threshold && alert.current_value >= alert.breach_threshold
                  ? "border-red-300 bg-red-50"
                  : "border-amber-300 bg-amber-50"
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">
                    {alert.contract_id} — {alert.metric_type}
                  </h3>
                  <p className="text-sm text-gray-600">
                    {alert.table_name}
                    {alert.column_name ? `.${alert.column_name}` : ""}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-gray-900">
                    {(alert.current_value * 100).toFixed(1)}%
                  </p>
                  {alert.estimated_breach_in_runs != null && alert.estimated_breach_in_runs > 0 && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                      Breach in ~{alert.estimated_breach_in_runs} runs
                    </span>
                  )}
                </div>
              </div>
              <div className="mt-3 flex gap-6 text-sm text-gray-500">
                {alert.warning_threshold != null && (
                  <span>Warning: {(alert.warning_threshold * 100).toFixed(1)}%</span>
                )}
                {alert.breach_threshold != null && (
                  <span>Breach: {(alert.breach_threshold * 100).toFixed(1)}%</span>
                )}
                {alert.trend_slope != null && (
                  <span>Slope: {alert.trend_slope.toFixed(4)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
