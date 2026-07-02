type Tone = "default" | "warning" | "success" | "danger";

export type Stat = {
  label: string;
  value: number | string;
  tone?: Tone;
  loading?: boolean;
};

type Props = { stats: Stat[] };

const toneClasses: Record<Tone, string> = {
  default: "text-gray-800",
  success: "text-emerald-600",
  warning: "text-amber-600",
  danger: "text-red-600",
};

export default function StatTiles({ stats }: Props) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((s) => (
        <div
          key={s.label}
          className="bg-white border border-gray-200 rounded-2xl shadow-sm p-4"
        >
          <p className="text-sm text-gray-500">{s.label}</p>
          {s.loading ? (
            <div className="h-8 w-12 bg-gray-100 rounded animate-pulse mt-1" />
          ) : (
            <p
              className={`text-2xl font-semibold mt-1 ${toneClasses[s.tone ?? "default"]}`}
            >
              {s.value}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
