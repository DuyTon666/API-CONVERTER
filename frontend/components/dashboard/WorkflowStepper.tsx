"use client";

export type Step = {
  id: string;
  label: string;
};

export function toSteps(defs: { id: string; label: string }[]): Step[] {
  return defs.map((d, i) => ({
    id: d.id,
    label: d.label,
  }));
}

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
              className={`w-7 h-7 rounded-full border-2 flex items-center justify-center text-xs font-semibold transition-colors group-hover:border-indigo-500`}
            >
              {i + 1}
            </span>
            <span
              className={`text-sm hidden lg:inline transition-colors group-hover:text-indigo-600 `}
            >
              {step.label}
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}
