import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "ContextTrace - RAG Reliability SDK",
  description:
    "Trace retrieval, verify citations, classify RAG failures, and generate reliability reports for RAG and agent applications."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
