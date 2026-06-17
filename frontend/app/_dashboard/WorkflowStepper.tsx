"use client";

export type StepStatus = "done" | "current" | "upcoming";

export type Step = {
  id: string;
  label: string;
  status: StepStatus;
};

export function toSteps(
  defs: { id: string; label: string; done: boolean }[],
): Step[] {
  const firstNotDone = defs.findIndex((d) => !d.done);
  return defs.map((d, i) => ({
    id: d.id,
    label: d.label,
    status: d.done ? "done" : i === firstNotDone ? "current" : "upcoming",
  }));
}

const circleClasses: Record<StepStatus, string> = {
  done: "bg-indigo-600 border-indigo-600 text-white",
  current: "bg-white border-indigo-600 text-indigo-600",
  upcoming: "bg-gray-200 border-gray-200 text-gray-400",
};

const labelClasses: Record<StepStatus, string> = {
  done: "text-gray-700",
  current: "text-indigo-600 font-semibold",
  upcoming: "text-gray-400",
};

type Props = { steps: Step[] };

export default function WorkflowStepper({ steps }: Props) {
  return (
    <ol className="flex items-center justify-center gap-4 lg:gap-8">
      {steps.map((step, i) => (
        <li key={step.id} className="flex items-center gap-4 lg:gap-8">
          <button
            type="button"
            onClick={() =>
              document
                .getElementById(step.id)
                ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
            className="flex items-center gap-2 group"
          >
            <span
              className={`w-7 h-7 rounded-full border-2 flex items-center justify-center text-xs font-semibold transition-colors group-hover:border-indigo-500 ${circleClasses[step.status]}`}
            >
              {step.status === "done" ? "✓" : i + 1}
            </span>
            <span
              className={`text-sm hidden lg:inline transition-colors group-hover:text-indigo-600 ${labelClasses[step.status]}`}
            >
              {step.label}
            </span>
          </button>
          {i < steps.length - 1 && (
            <div
              className={`w-6 lg:w-12 h-px ${
                step.status === "done" ? "bg-indigo-400" : "bg-gray-300"
              }`}
            />
          )}
        </li>
      ))}
    </ol>
  );
}





