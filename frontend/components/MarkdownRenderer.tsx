"use client";

import React from "react";
import dynamic from "next/dynamic";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { markdownComponents } from "@/lib/markdown-components";
import { Skeleton } from "@/components/ui/skeleton";

const ReactMarkdown = dynamic(() => import("react-markdown"), {
  ssr: false,
  loading: () => <Skeleton className="h-4 w-full" />,
});

interface MarkdownRendererProps {
  content: string;
  className?: string;
  isStreaming?: boolean;
}

function hasIncompleteFence(content: string): boolean {
  const fenceCount = (content.match(/```/g) || []).length;
  return fenceCount % 2 !== 0;
}

// Memoized remark/rehype plugin arrays to avoid re-creating on every render
const remarkPlugins = [remarkGfm];
const rehypePlugins = [rehypeHighlight];

function MarkdownRendererInner({
  content,
  className,
  isStreaming,
}: MarkdownRendererProps) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={rehypePlugins}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && hasIncompleteFence(content) && (
        <Skeleton className="h-24 w-full rounded mt-2" />
      )}
    </div>
  );
}

export const MarkdownRenderer = React.memo(MarkdownRendererInner);
