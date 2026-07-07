"use client";

export type Step = {
  id: string;
  label: string;
};

export function toSteps(defs: { id: string; label: string }[]): Step[] {
  return defs.map((d) => ({
    id: d.id,
    label: d.label,
  }));
}

// activeIndex đến từ useActiveStep ở page.tsx — dùng chung với StepSection
// (timeline dọc giữa trang) để cả 2 nơi luôn đồng bộ, không mỗi nơi tự chạy
// 1 IntersectionObserver riêng trên cùng tập section.
type Props = { steps: Step[]; activeIndex: number };

export default function WorkflowStepper({ steps, activeIndex }: Props) {
  return (
    <ol className="flex items-center justify-center">
      {steps.map((step, i) => {
        const isDone = i < activeIndex;
        const isCurrent = i === activeIndex;
        return (
          <li key={step.id} className="flex items-center">
            <button
              type="button"
              aria-current={isCurrent ? "step" : undefined}
              onClick={() =>
                document
                  .getElementById(step.id)
                  ?.scrollIntoView({ behavior: "smooth", block: "start" })
              }
              className="flex items-center gap-2 group rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2"
            >
              <span
                className={`relative flex items-center justify-center w-7 h-7 shrink-0 rounded-full text-xs font-semibold transition-all duration-300 motion-reduce:transition-none ${
                  isDone
                    ? "bg-indigo-600 text-white"
                    : isCurrent
                      ? "bg-indigo-600 text-white ring-4 ring-indigo-100"
                      : "bg-white border-2 border-gray-300 text-gray-400 group-hover:border-indigo-400 group-hover:text-indigo-500"
                }`}
              >
                {isDone ? (
                  <svg
                    className="w-3.5 h-3.5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                ) : (
                  i + 1
                )}
              </span>
              <span
                className={`text-sm hidden lg:inline transition-colors duration-300 motion-reduce:transition-none ${
                  isCurrent
                    ? "text-gray-900 font-medium"
                    : isDone
                      ? "text-gray-600"
                      : "text-gray-400 group-hover:text-indigo-500"
                }`}
              >
                {step.label}
              </span>
            </button>
            {i < steps.length - 1 && (
              <span
                aria-hidden="true"
                className={`h-0.5 w-8 lg:w-16 mx-2 lg:mx-3 rounded-full transition-colors duration-500 motion-reduce:transition-none ${
                  i < activeIndex ? "bg-indigo-600" : "bg-gray-200"
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
