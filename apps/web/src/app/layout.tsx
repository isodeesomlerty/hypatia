import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hypatia V2",
  description: "Production architecture workspace for Hypatia.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
