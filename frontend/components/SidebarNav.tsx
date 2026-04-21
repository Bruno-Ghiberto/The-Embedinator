"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams, useRouter } from "next/navigation";
import {
  MessageSquare,
  FolderOpen,
  Settings,
  Activity,
  Plus,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import ThemeToggle from "@/components/ThemeToggle";
import ChatHistory from "@/components/ChatHistory";
import { useChatHistory } from "@/hooks/useChatHistory";

const NAV_LINKS = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/collections", label: "Collections", icon: FolderOpen },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/observability", label: "Observability", icon: Activity },
] as const;

export default function SidebarNav() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem className="group-data-[collapsible=icon]:hidden">
            <SidebarMenuButton size="lg" render={<Link href="/" />}>
              <span className="truncate text-base font-bold">
                The Embedinator
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem className="group-data-[collapsible=icon]:hidden">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => router.push("/chat?new=1")}
            >
              <Plus className="h-4 w-4 mr-2" />
              New Chat
            </Button>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <Suspense>
          <ChatHistorySection />
        </Suspense>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarMenu>
            {NAV_LINKS.map(({ href, label, icon: Icon }) => {
              const isActive =
                pathname === href || pathname.startsWith(`${href}/`);
              return (
                <SidebarMenuItem key={href}>
                  <SidebarMenuButton
                    render={<Link href={href} />}
                    isActive={isActive}
                    tooltip={label}
                  >
                    <Icon />
                    <span>{label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <ThemeToggle />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

// ─── ChatHistory Section (uses useSearchParams → needs Suspense) ─────────────

function ChatHistorySection() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const {
    sessions,
    searchSessions,
    renameSession,
    deleteSession,
    isLoading,
  } = useChatHistory();
  const [searchQuery, setSearchQuery] = useState("");

  const activeSessionId =
    pathname === "/chat" ? searchParams.get("session") : null;

  const displaySessions = searchQuery
    ? searchSessions(searchQuery)
    : sessions;

  if (isLoading) return null;

  return (
    <ChatHistory
      sessions={displaySessions}
      activeSessionId={activeSessionId}
      onSessionClick={(id) => router.push(`/chat?session=${id}`)}
      onSessionRename={renameSession}
      onSessionDelete={deleteSession}
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
    />
  );
}
