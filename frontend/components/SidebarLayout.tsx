"use client";

import { useState, useCallback, useEffect } from "react";
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import SidebarNav from "@/components/SidebarNav";
import PageBreadcrumb from "@/components/PageBreadcrumb";
import { Separator } from "@/components/ui/separator";
import { StatusBanner } from "@/components/StatusBanner";

export function SidebarLayout({ children }: { children: React.ReactNode }) {
  // Start with `true` on both server and client to avoid hydration mismatch.
  // After mount, read the persisted value from localStorage.
  const [open, setOpen] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("sidebar-open");
    if (stored === "false") {
      setOpen(false);
    }
  }, []);

  const handleOpenChange = useCallback((value: boolean) => {
    setOpen(value);
    localStorage.setItem("sidebar-open", String(value));
  }, []);

  return (
    <SidebarProvider open={open} onOpenChange={handleOpenChange}>
      <SidebarNav />
      <SidebarInset>
        <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <PageBreadcrumb />
        </header>
        <StatusBanner />
        <main className="flex flex-1 flex-col min-h-0">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
