import type { ValidationRun } from "../api/client";

interface Props {
  runs: ValidationRun[];
}

export default function RunHistoryTable({ runs }: Props) {
  if (runs.length === 0) {
    return <p className="text-gray-500 text-sm">No runs recorded yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Timestamp
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Status
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Checks
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Duration
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
              Triggered By
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {runs.map((run) => (
            <tr key={run.id} className="hover:bg-gray-50">
              <td className="px-4 py-3 text-sm text-gray-700">
                {new Date(run.run_at).toLocaleString()}
              </td>
              <td className="px-4 py-3">
                <span
                  className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                    run.status === "passed"
                      ? "bg-green-100 text-green-800"
                      : run.status === "failed"
                        ? "bg-red-100 text-red-800"
                        : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {run.status}
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-gray-700">
                {run.checks_passed}/{run.checks_total}
              </td>
              <td className="px-4 py-3 text-sm text-gray-700">
                {run.duration_ms ? `${run.duration_ms}ms` : "—"}
              </td>
              <td className="px-4 py-3 text-sm text-gray-500">{run.triggered_by ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
