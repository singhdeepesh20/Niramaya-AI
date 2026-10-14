import type { Metadata } from "next";
import "./styles.css";
import "./reports.css";
import "./workspace.css";
import "./document-overrides.css";

export const metadata: Metadata = {
  title: "Niramaya-AI | Your Health Records. Smarter.",
  description: "A more thoughtful way to understand and organize your health records.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
