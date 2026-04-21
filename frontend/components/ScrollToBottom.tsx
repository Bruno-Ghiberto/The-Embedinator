"use client";

import React, { useState, useEffect, useCallback } from "react";
import { ArrowDown } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ScrollToBottomProps {
  scrollContainerRef: React.RefObject<HTMLElement | null>;
  isStreaming: boolean;
}

function ScrollToBottomInner({
  scrollContainerRef,
  isStreaming,
}: ScrollToBottomProps) {
  const [showButton, setShowButton] = useState(false);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, clientHeight, scrollHeight } = container;
      setShowButton(scrollTop + clientHeight < scrollHeight - 100);
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, [scrollContainerRef]);

  const scrollToBottom = useCallback(() => {
    scrollContainerRef.current?.scrollTo({
      top: scrollContainerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [scrollContainerRef]);

  // Auto-scroll during streaming
  useEffect(() => {
    if (isStreaming && !showButton) {
      scrollContainerRef.current?.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [isStreaming, showButton, scrollContainerRef]);

  if (!showButton) return null;

  return (
    <div className="absolute bottom-24 right-6 z-10">
      <Button
        variant="secondary"
        size="icon"
        className="rounded-full shadow-md"
        onClick={scrollToBottom}
        aria-label="Scroll to bottom"
      >
        <ArrowDown className="h-4 w-4" />
      </Button>
    </div>
  );
}

export const ScrollToBottom = React.memo(ScrollToBottomInner);
