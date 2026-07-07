"use client";

import { useEffect, useState } from "react";

// Scrollspy dùng chung cho WorkflowStepper (thanh bước sticky) và StepSection
// (timeline dọc giữa trang) — 1 IntersectionObserver duy nhất theo dõi section
// nào đang ở đầu viewport, tránh 2 nơi tự chạy observer trùng nhau trên cùng
// 1 tập phần tử. Dùng `key` (chuỗi nối các id) thay vì mảng `stepIds` làm dep
// vì mảng truyền vào luôn là literal mới mỗi lần render — nếu để thẳng mảng
// vào dependency, effect sẽ tháo/gắn lại observer ở mọi lần render cha re-render.
export function useActiveStep(stepIds: string[]): number {
  const [activeIndex, setActiveIndex] = useState(0);
  const key = stepIds.join(",");

  useEffect(() => {
    const sections = stepIds
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const index = sections.indexOf(entry.target as HTMLElement);
          if (index !== -1) setActiveIndex(index);
        });
      },
      { rootMargin: "-30% 0px -60% 0px" },
    );
    sections.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return activeIndex;
}
