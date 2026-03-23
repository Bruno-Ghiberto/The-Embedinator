"use client";

import React, { useState, useCallback } from "react";
import type { Components } from "react-markdown";
import "highlight.js/styles/github-dark.css";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";

function CopyButton({ getText }: { getText: () => string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    const text = getText();
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [getText]);

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={handleCopy}
      className="absolute right-2 top-2 h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100"
      aria-label="Copy code"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-green-500" />
      ) : (
        <Copy className="h-3.5 w-3.5 text-muted-foreground" />
      )}
    </Button>
  );
}

// MUST be defined at module level — NOT inside any component.
// Vercel rule: rerender-no-inline-components
export const markdownComponents: Components = {
  h1: ({ node, children, ...props }) => (
    <h1
      className="text-2xl font-bold text-foreground mt-6 mb-3"
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ node, children, ...props }) => (
    <h2
      className="text-xl font-semibold text-foreground mt-5 mb-2"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ node, children, ...props }) => (
    <h3
      className="text-lg font-medium text-foreground mt-4 mb-2"
      {...props}
    >
      {children}
    </h3>
  ),
  h4: ({ node, children, ...props }) => (
    <h4
      className="text-base font-medium text-foreground mt-3 mb-1"
      {...props}
    >
      {children}
    </h4>
  ),
  code: ({ node, className, children, ...props }) => {
    const isInline = !className;
    if (isInline) {
      return (
        <code
          className="bg-muted rounded px-1.5 py-0.5 text-sm font-mono"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  pre: ({ node, children, ...props }) => {
    const getTextContent = () => {
      const el = document.createElement("div");
      // Extract text from the pre element's children by rendering to string
      const text =
        typeof children === "string"
          ? children
          : (props as Record<string, unknown>)["data-text"]?.toString() ?? "";
      el.remove();
      return text;
    };

    return (
      <div className="relative group my-3">
        <pre
          className="bg-zinc-900 rounded-lg p-4 overflow-x-auto text-sm"
          {...props}
        >
          {children}
        </pre>
        <CopyButton
          getText={() => {
            // Get text from the rendered pre element
            const pre = document.querySelector(
              "div.group:hover > pre",
            );
            return pre?.textContent ?? "";
          }}
        />
      </div>
    );
  },
  a: ({ node, children, ...props }) => (
    <a
      className="text-primary underline hover:text-primary/80"
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    >
      {children}
    </a>
  ),
  ul: ({ node, children, ...props }) => (
    <ul className="list-disc pl-6 space-y-1 my-2" {...props}>
      {children}
    </ul>
  ),
  ol: ({ node, children, ...props }) => (
    <ol className="list-decimal pl-6 space-y-1 my-2" {...props}>
      {children}
    </ol>
  ),
  blockquote: ({ node, children, ...props }) => (
    <blockquote
      className="border-l-4 border-primary/30 pl-4 italic text-muted-foreground my-2"
      {...props}
    >
      {children}
    </blockquote>
  ),
  table: ({ node, children, ...props }) => (
    <div className="overflow-x-auto my-3">
      <table className="border-collapse w-full text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  img: ({ node, ...props }) => (
    <img className="max-w-full rounded my-2" {...props} />
  ),
};
