import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import ComplianceScoreDisplay from "../components/ComplianceScore";

export default function Compliance() {
  const { data: leaderboardData } = useQuery({
    queryKey: ["leaderboard"],
    queryFn: api.compliance.leaderboard,
  });

  const entries = leaderboardData?.items ?? [];

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Compliance Leaderboard</h1>

      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <p className="text-sm text-gray-500 mb-4">
          Score = (passed runs / total runs) &times; 100 over the last 30 days
        </p>

        {entries.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            No compliance data available. Teams will appear here once runs are recorded.
          </p>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Rank
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Team
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Score
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Contracts
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Violations (30d)
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {entries.map((entry) => (
                <tr key={entry.team_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    #{entry.rank}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">{entry.team_name}</td>
                  <td className="px-4 py-3">
                    <ComplianceScoreDisplay score={entry.score} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {entry.contracts_owned}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {entry.violations_30d}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
