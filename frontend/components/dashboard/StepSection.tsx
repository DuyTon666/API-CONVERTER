"use client";

import { ReactNode } from "react";

export type StepStatus = "done" | "current" | "upcoming";

type Props = {
  id: string;
  number: number;
  label: string;
  status: StepStatus;
  isLast?: boolean;
  children: ReactNode;
};

// 1 khối trong timeline dọc: cột mốc số/tick bên trái, nối bằng đường kẻ dọc
// xuống bước kế tiếp — dùng chung ngôn ngữ hình ảnh (tick/glow/màu) với
// WorkflowStepper (thanh bước sticky ở trên) để 2 nơi luôn khớp trạng thái.
export default function StepSection({
  id,
  number,
  label,
  status,
  isLast = false,
  children,
}: Props) {
  const isUpcoming = status === "upcoming";
  const isDone = status === "done";

  return (
    <section id={id} className="flex gap-4 lg:gap-6 scroll-mt-32">
      <div className="flex flex-col items-center shrink-0">
        <span
          className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold transition-colors duration-300 motion-reduce:transition-none ${
            isUpcoming
              ? "bg-white border-2 border-gray-300 text-gray-400"
              : "bg-indigo-600 text-white"
          } ${status === "current" ? "ring-4 ring-indigo-100" : ""}`}
        >
          {isDone ? (
            <svg
              className="w-4 h-4"
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
            number
          )}
        </span>
        {!isLast && (
          <span
            aria-hidden="true"
            className={`w-0.5 flex-1 my-2 rounded-full transition-colors duration-500 motion-reduce:transition-none ${
              isDone ? "bg-indigo-600" : "bg-gray-200"
            }`}
          />
        )}
      </div>
      <div className="flex-1 min-w-0 pb-10 space-y-6">
        <h2
          className={`text-sm font-semibold uppercase tracking-wide ${
            isUpcoming ? "text-gray-400" : "text-gray-900"
          }`}
        >
          {label}
        </h2>
        {children}
      </div>
    </section>
  );
}
