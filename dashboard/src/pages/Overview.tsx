import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import ContractHealthBadge from "../components/ContractHealthBadge";

export default function Overview() {
  const { data: contractsData } = useQuery({
    queryKey: ["contracts"],
    queryFn: api.contracts.list,
  });
  const { data: summaryData } = useQuery({
    queryKey: ["runs-summary"],
    queryFn: api.runs.summary,
  });
  const { data: driftAlerts } = useQuery({
    queryKey: ["drift-alerts"],
    queryFn: api.drift.alerts,
  });

  const contracts = contractsData?.items ?? [];
  const summary = summaryData?.items ?? [];
  const alerts = driftAlerts ?? [];

  const summaryMap = new Map(summary.map((s) => [s.contract_id, s]));

  const totalContracts = contracts.length;
  const passing = contracts.filter((c) => {
    const s = summaryMap.get(c.contract_id);
    return s && s.failed === 0 && s.error === 0 && s.total_runs > 0;
  }).length;
  const passingPct = totalContracts > 0 ? ((passing / totalContracts) * 100).toFixed(0) : "—";

  const stats = [
    { label: "Total Contracts", value: totalContracts },
    { label: "Passing", value: `${passingPct}%` },
    { label: "Drift Alerts", value: alerts.length },
    { label: "Recent Violations", value: summary.reduce((a, s) => a + s.failed, 0) },
  ];

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard Overview</h1>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-white rounded-lg border border-gray-200 p-6">
            <p className="text-sm text-gray-500">{s.label}</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Contract Health</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contract</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Owner</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mode</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Runs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {contracts.map((c) => {
                const s = summaryMap.get(c.contract_id);
                const hasAlert = alerts.some((a) => a.contract_id === c.contract_id);
                let status: "passing" | "warning" | "failing" | "unknown" = "unknown";
                if (s && s.total_runs > 0) {
                  if (s.failed > 0) status = "failing";
                  else if (hasAlert) status = "warning";
                  else status = "passing";
                }
                return (
                  <tr key={c.contract_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <Link to={`/contracts/${c.contract_id}`} className="text-indigo-600 hover:underline font-medium">
                        {c.title}
                      </Link>
                      <p className="text-xs text-gray-400">{c.contract_id}</p>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{c.owner_team ?? "—"}</td>
                    <td className="px-6 py-4"><ContractHealthBadge status={status} /></td>
                    <td className="px-6 py-4 text-sm text-gray-600">{c.enforcement_mode}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{s?.total_runs ?? 0}</td>
                  </tr>
                );
              })}
              {contracts.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500">No contracts registered yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
