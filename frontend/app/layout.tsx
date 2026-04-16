import type { Metadata } from "next";
import { Inter, Geist } from "next/font/google";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { cn } from "@/lib/utils";
import { SidebarLayout } from "@/components/SidebarLayout";
import { BackendStatusProvider } from "@/components/BackendStatusProvider";
import { Toaster } from "@/components/ui/sonner";
import CommandPalette from "@/components/CommandPalette";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "The Embedinator",
  description: "RAG-powered document intelligence platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={cn("font-sans", geist.variable, "dark")}>
      <body suppressHydrationWarning className={`${inter.variable} antialiased`}>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem enableColorScheme={false}>
          <BackendStatusProvider>
            <SidebarLayout>
              {children}
            </SidebarLayout>
          </BackendStatusProvider>
          <Toaster />
          <CommandPalette />
        </ThemeProvider>
      </body>
    </html>
  );
}
