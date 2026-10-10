import type { Metadata, Viewport } from "next";
import Providers from "./providers";
import { Toaster } from "@/components/ui/sonner";
import "../styles.css";


export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: "DocContextly — AI Knowledge Workspace for Research & Learning",
  description:
    "DocContextly is an AI-powered knowledge workspace for research, learning, and content creation. Chat with documents, websites, YouTube videos, and notes, then generate presentations, podcasts, study guides, quizzes, mind maps, and more.",
  keywords: [
    "AI Knowledge Workspace",
    "NotebookLM Alternative",
    "AI Research Assistant",
    "RAG",
    "Chat with PDF",
    "Document AI",
    "AI Presentation Generator",
    "AI Podcast Generator",
    "Study Guide Generator",
    "Mind Map Generator",
    "Quiz Generator",
    "Knowledge Management",
  ],
  openGraph: {
    title: "DocContextly — AI Knowledge Workspace for Research & Learning",
    description:
      "An AI-powered knowledge workspace that helps you research, learn, and create from documents, websites, YouTube videos, and notes.",
    type: "website",
    siteName: "DocContextly",
  },
  twitter: {
    card: "summary_large_image",
    title: "DocContextly — AI Knowledge Workspace",
    description:
      "Research, learn, and create with AI using your documents, websites, YouTube videos, and notes.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
        <Toaster position="top-right" />
      </body>
    </html>
  );
}
