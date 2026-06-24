"use client";

import Editor, { OnMount } from "@monaco-editor/react";
import { useRef } from "react";
import { SpectralIssue, RedoclyIssue } from "./types";

type Props = {
  content: string;
  onChange: (value: string) => void;
  spectralIssues: SpectralIssue[];
  redoclyIssues: RedoclyIssue[];
};

type MonacoInstance = Parameters<OnMount>[1];

export default function BundleEditor({
  content,
  onChange,
  spectralIssues,
  redoclyIssues,
}: Props) {
  const monacoRef = useRef<MonacoInstance | null>(null);

  const handleMount: OnMount = (editor, monaco) => {
    monacoRef.current = monaco;

    const applyMarkers = () => {
      const model = editor.getModel();
      if (!model) return;

      const markers = [
        ...spectralIssues.map((issue) => ({
          severity:
            issue.severity === 0
              ? monaco.MarkerSeverity.Error
              : issue.severity === 1
                ? monaco.MarkerSeverity.Warning
                : monaco.MarkerSeverity.Info,
          message: `[Spectral] [${issue.code}] ${issue.message}`,
          startLineNumber: (issue.range?.start.line ?? 0) + 1,
          startColumn: (issue.range?.start.character ?? 0) + 1,
          endLineNumber:
            (issue.range?.end.line ?? issue.range?.start.line ?? 0) + 1,
          endColumn:
            (issue.range?.end.character ??
              (issue.range?.start.character ?? 0) + 10) + 1,
        })),
        ...redoclyIssues.map((issue) => {
          const line = (issue.line ?? 0) + 1;
          const col = (issue.column ?? 0) + 1;
          return {
            severity:
              issue.severity === "error"
                ? monaco.MarkerSeverity.Error
                : monaco.MarkerSeverity.Warning,
            message: `[Redocly] [${issue.ruleId}] ${issue.message}`,
            startLineNumber: line,
            startColumn: col,
            endLineNumber: line,
            endColumn: col + 20,
          };
        }),
      ];

      monaco.editor.setModelMarkers(model, "linter", markers);
    };

    // Đợi model sẵn sàng rồi mới apply markers
    if (editor.getModel()) {
      applyMarkers();
    } else {
      const disposable = editor.onDidChangeModel(() => {
        applyMarkers();
        disposable.dispose();
      });
    }
  };

  return (
    <Editor
      height="100%"
      defaultLanguage="yaml"
      value={content}
      onChange={(val) => onChange(val ?? "")}
      onMount={handleMount}
      loading={
        <div className="flex items-center justify-center h-full text-gray-400 text-sm">
          Đang tải editor...
        </div>
      }
      options={{
        fontSize: 13,
        minimap: { enabled: false },
        lineNumbers: "on",
        scrollBeyondLastLine: false,
        wordWrap: "on",
        automaticLayout: true,
      }}
    />
  );
}
