import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";
import "./globals.css";
import MonacoErrorSuppressor from "./MonacoErrorSuppressor";

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "API Converter",
  description: "Chuyển đổi tài liệu .docx thành OpenAPI 3.1 YAML",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="vi"
      className={`${geistMono.variable} h-full antialiased`}
      style={{ colorScheme: "light" }}
    >
      <body className="min-h-full flex flex-col">
        <MonacoErrorSuppressor />
        {children}
      </body>
    </html>
  );
}
