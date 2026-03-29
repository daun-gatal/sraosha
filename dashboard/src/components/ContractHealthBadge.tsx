interface Props {
  status: "passing" | "warning" | "failing" | "unknown";
}

const styles: Record<string, string> = {
  passing: "bg-green-100 text-green-800",
  warning: "bg-amber-100 text-amber-800",
  failing: "bg-red-100 text-red-800",
  unknown: "bg-gray-100 text-gray-600",
};

export default function ContractHealthBadge({ status }: Props) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] ?? styles.unknown}`}
    >
      {status}
    </span>
  );
}
