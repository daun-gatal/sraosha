import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";
import ImpactGraph from "../components/ImpactGraph";

export default function ImpactMap() {
  const { data: graphData } = useQuery({
    queryKey: ["impact-graph"],
    queryFn: api.impact.graph,
  });

  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [fields, setFields] = useState("");

  const analyzeMutation = useMutation({
    mutationFn: ({ id, changedFields }: { id: string; changedFields: string[] }) =>
      api.impact.analyze(id, changedFields),
  });

  const nodes = graphData?.nodes ?? [];
  const edges = graphData?.edges ?? [];

  const handleAnalyze = () => {
    if (!selectedNode || !fields.trim()) return;
    const changedFields = fields.split(",").map((f) => f.trim()).filter(Boolean);
    analyzeMutation.mutate({ id: selectedNode, changedFields });
  };

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Impact Map</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ImpactGraph
            nodes={nodes}
            edges={edges}
            onNodeClick={(id) => setSelectedNode(id)}
          />
        </div>

        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold mb-4">Analyze Change Impact</h2>

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contract
                </label>
                <select
                  value={selectedNode ?? ""}
                  onChange={(e) => setSelectedNode(e.target.value || null)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                >
                  <option value="">Select a contract...</option>
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Changed Fields (comma-separated)
                </label>
                <input
                  type="text"
                  value={fields}
                  onChange={(e) => setFields(e.target.value)}
                  placeholder="field_a, field_b"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                />
              </div>

              <button
                onClick={handleAnalyze}
                disabled={!selectedNode || !fields.trim()}
                className="w-full bg-indigo-600 text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Analyze Impact
              </button>
            </div>

            {analyzeMutation.data && (
              <div className="mt-4 space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">Severity:</span>
                  <span
                    className={`font-medium ${
                      analyzeMutation.data.severity === "high"
                        ? "text-red-600"
                        : analyzeMutation.data.severity === "medium"
                          ? "text-amber-600"
                          : "text-green-600"
                    }`}
                  >
                    {analyzeMutation.data.severity}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">Directly affected:</span>
                  <span className="ml-2 text-gray-900">
                    {analyzeMutation.data.directly_affected.length > 0
                      ? analyzeMutation.data.directly_affected.join(", ")
                      : "None"}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">Transitively affected:</span>
                  <span className="ml-2 text-gray-900">
                    {analyzeMutation.data.transitively_affected.length > 0
                      ? analyzeMutation.data.transitively_affected.join(", ")
                      : "None"}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
