import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DriftMetric } from "../api/client";

interface Props {
  metrics: DriftMetric[];
  warningThreshold?: number | null;
  breachThreshold?: number | null;
}

export default function DriftChart({ metrics, warningThreshold, breachThreshold }: Props) {
  const data = [...metrics]
    .sort((a, b) => new Date(a.measured_at).getTime() - new Date(b.measured_at).getTime())
    .map((m) => ({
      date: new Date(m.measured_at).toLocaleDateString(),
      value: m.value,
    }));

  if (data.length === 0) {
    return <p className="text-gray-500 text-sm">No drift data available.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} dot={false} />
        {warningThreshold != null && (
          <ReferenceLine y={warningThreshold} stroke="#f59e0b" strokeDasharray="5 5" label="Warning" />
        )}
        {breachThreshold != null && (
          <ReferenceLine y={breachThreshold} stroke="#ef4444" strokeDasharray="5 5" label="Breach" />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
