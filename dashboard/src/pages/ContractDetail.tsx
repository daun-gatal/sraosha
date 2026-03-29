import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import DriftChart from "../components/DriftChart";
import RunHistoryTable from "../components/RunHistoryTable";

export default function ContractDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: contract, isLoading } = useQuery({
    queryKey: ["contract", id],
    queryFn: () => api.contracts.get(id!),
    enabled: !!id,
  });

  const { data: runsData } = useQuery({
    queryKey: ["runs", id],
    queryFn: () => api.runs.list({ contract_id: id!, limit: 20 }),
    enabled: !!id,
  });

  const { data: driftData } = useQuery({
    queryKey: ["drift-history", id],
    queryFn: () => api.drift.history(id!),
    enabled: !!id,
  });

  if (isLoading) {
    return <p className="text-gray-500">Loading...</p>;
  }

  if (!contract) {
    return <p className="text-red-500">Contract not found.</p>;
  }

  const runs = runsData?.items ?? [];
  const driftMetrics = driftData?.items ?? [];

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-4">
        <Link to="/" className="text-indigo-600 hover:underline text-sm">&larr; Back</Link>
        <h1 className="text-2xl font-bold text-gray-900">{contract.title}</h1>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Contract Metadata</h2>
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">ID</dt>
            <dd className="font-mono text-gray-900">{contract.contract_id}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Owner</dt>
            <dd className="text-gray-900">{contract.owner_team ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Mode</dt>
            <dd className="text-gray-900">{contract.enforcement_mode}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Active</dt>
            <dd className="text-gray-900">{contract.is_active ? "Yes" : "No"}</dd>
          </div>
        </dl>
        {contract.description && (
          <p className="mt-4 text-sm text-gray-600">{contract.description}</p>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Run History</h2>
        <RunHistoryTable runs={runs} />
      </div>

      {driftMetrics.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4">Drift Metrics</h2>
          <DriftChart
            metrics={driftMetrics}
            warningThreshold={driftMetrics[0]?.warning_threshold}
            breachThreshold={driftMetrics[0]?.breach_threshold}
          />
        </div>
      )}

      <div className="text-sm">
        <Link to="/impact" className="text-indigo-600 hover:underline">
          View in Impact Map &rarr;
        </Link>
      </div>
    </div>
  );
}
