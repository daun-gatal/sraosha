interface Props {
  score: number | null;
  size?: "sm" | "lg";
}

export default function ComplianceScore({ score, size = "sm" }: Props) {
  if (score === null) {
    return <span className="text-gray-400">N/A</span>;
  }

  const color =
    score >= 90 ? "text-green-600" : score >= 70 ? "text-amber-600" : "text-red-600";

  const textSize = size === "lg" ? "text-4xl" : "text-lg";

  return (
    <span className={`${textSize} font-bold ${color}`}>
      {score.toFixed(1)}%
    </span>
  );
}
