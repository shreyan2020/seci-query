import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Biotech Program Workspace",
  description: "Project-first biotech workflow planning with project-scoped personas",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
