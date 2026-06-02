"use client";

import { useEffect } from "react";

export default function MonacoErrorSuppressor() {
  useEffect(() => {
    const handler = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      // Bỏ qua lỗi cancelation nội bộ của Monaco
      if (reason && typeof reason === "object" && reason.type === "cancelation") {
        event.preventDefault();
      }
    };
    window.addEventListener("unhandledrejection", handler);
    return () => window.removeEventListener("unhandledrejection", handler);
  }, []);

  return null;
}
