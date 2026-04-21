"use client";

import React, { useState, useCallback, useMemo } from "react";
import type { ChatSessionSummary } from "@/hooks/useChatHistory";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarMenuAction,
  SidebarMenuBadge,
} from "@/components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ChatHistoryProps {
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  onSessionClick: (id: string) => void;
  onSessionRename: (id: string, title: string) => void;
  onSessionDelete: (id: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

interface DateGroup {
  label: string;
  sessions: ChatSessionSummary[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function groupByDate(sessions: ChatSessionSummary[]): DateGroup[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86_400_000);
  const sevenDaysAgo = new Date(today.getTime() - 7 * 86_400_000);

  const todaySessions: ChatSessionSummary[] = [];
  const yesterdaySessions: ChatSessionSummary[] = [];
  const lastWeekSessions: ChatSessionSummary[] = [];
  const olderSessions: ChatSessionSummary[] = [];

  for (const session of sessions) {
    const d = new Date(session.updatedAt);
    if (d >= today) {
      todaySessions.push(session);
    } else if (d >= yesterday) {
      yesterdaySessions.push(session);
    } else if (d >= sevenDaysAgo) {
      lastWeekSessions.push(session);
    } else {
      olderSessions.push(session);
    }
  }

  const groups: DateGroup[] = [];
  if (todaySessions.length > 0)
    groups.push({ label: "Today", sessions: todaySessions });
  if (yesterdaySessions.length > 0)
    groups.push({ label: "Yesterday", sessions: yesterdaySessions });
  if (lastWeekSessions.length > 0)
    groups.push({ label: "Previous 7 Days", sessions: lastWeekSessions });
  if (olderSessions.length > 0)
    groups.push({ label: "Older", sessions: olderSessions });

  return groups;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function ChatHistory({
  sessions,
  activeSessionId,
  onSessionClick,
  onSessionRename,
  onSessionDelete,
  searchQuery,
  onSearchChange,
}: ChatHistoryProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ChatSessionSummary | null>(
    null,
  );

  const groups = useMemo(() => groupByDate(sessions), [sessions]);

  const handleStartRename = useCallback((session: ChatSessionSummary) => {
    setEditingId(session.id);
    setEditValue(session.title);
  }, []);

  const handleFinishRename = useCallback(() => {
    if (editingId && editValue.trim()) {
      onSessionRename(editingId, editValue.trim());
    }
    setEditingId(null);
  }, [editingId, editValue, onSessionRename]);

  const handleConfirmDelete = useCallback(() => {
    if (deleteTarget) {
      onSessionDelete(deleteTarget.id);
      setDeleteTarget(null);
    }
  }, [deleteTarget, onSessionDelete]);

  return (
    <>
      <SidebarGroup className="group-data-[collapsible=icon]:hidden">
        <SidebarGroupLabel>Conversations</SidebarGroupLabel>
        <SidebarGroupContent>
          <div className="px-2 py-1.5">
            <Input
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="h-7 text-xs"
            />
          </div>

          {groups.length === 0 ? (
            <p className="px-2 py-3 text-xs text-muted-foreground">
              {searchQuery
                ? "No matching conversations."
                : "No conversations yet."}
            </p>
          ) : (
            groups.map((group) => (
              <div key={group.label}>
                <p className="px-2 pt-2 pb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  {group.label}
                </p>
                <SidebarMenu>
                  {group.sessions.map((session) => (
                    <SidebarMenuItem key={session.id}>
                      {editingId === session.id ? (
                        <div className="px-2 py-1">
                          <Input
                            autoFocus
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onBlur={handleFinishRename}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleFinishRename();
                              if (e.key === "Escape") setEditingId(null);
                            }}
                            className="h-7 text-xs"
                          />
                        </div>
                      ) : (
                        <>
                          <SidebarMenuButton
                            size="sm"
                            isActive={session.id === activeSessionId}
                            onClick={() => onSessionClick(session.id)}
                            tooltip={`${session.title} · ${relativeTime(session.updatedAt)} · ${session.messageCount} messages`}
                          >
                            <span className="truncate max-w-[160px]">
                              {session.title}
                            </span>
                          </SidebarMenuButton>

                          <SidebarMenuBadge>
                            {session.messageCount}
                          </SidebarMenuBadge>

                          <DropdownMenu>
                            <DropdownMenuTrigger
                              render={<SidebarMenuAction showOnHover />}
                            >
                              <MoreHorizontal />
                              <span className="sr-only">Actions</span>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent side="right" align="start">
                              <DropdownMenuItem
                                onClick={() => handleStartRename(session)}
                              >
                                <Pencil className="size-4" />
                                Rename
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                variant="destructive"
                                onClick={() => setDeleteTarget(session)}
                              >
                                <Trash2 className="size-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </>
                      )}
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </div>
            ))
          )}
        </SidebarGroupContent>
      </SidebarGroup>

      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete conversation?</DialogTitle>
            <DialogDescription>
              This will permanently remove &ldquo;{deleteTarget?.title}&rdquo;.
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>
              Cancel
            </DialogClose>
            <Button variant="destructive" onClick={handleConfirmDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
