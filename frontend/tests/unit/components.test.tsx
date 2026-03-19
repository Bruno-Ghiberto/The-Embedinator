import { describe, test, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { getConfidenceTier } from "@/lib/types";

// ─── Mocks ────────────────────────────────────────────────────────────────────
// All vi.mock calls are hoisted before imports by vitest.
// Use require("react") inside factories to avoid hoisting issues.

vi.mock("next/link", () => {
  const React = require("react") as typeof import("react");
  return {
    default: ({
      children,
      href,
    }: {
      children: React.ReactNode;
      href: string;
    }) => React.createElement("a", { href }, children),
  };
});

vi.mock("@radix-ui/react-tooltip", () => {
  const React = require("react") as typeof import("react");
  return {
    Provider: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Root: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Trigger: ({
      children,
      asChild,
    }: {
      children: React.ReactElement;
      asChild?: boolean;
    }) => {
      if (asChild && React.isValidElement(children)) return children;
      return React.createElement("span", null, children);
    },
    // Portal renders inline so tooltip content is visible in DOM
    Portal: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Content: ({ children }: { children: React.ReactNode }) =>
      React.createElement(
        "div",
        { "data-testid": "tooltip-content" },
        children,
      ),
    Arrow: () => null,
  };
});

vi.mock("@radix-ui/react-dialog", () => {
  const React = require("react") as typeof import("react");

  // Context shares open/onOpenChange between Root, Trigger, Portal, Close
  const DialogCtx = React.createContext<{
    open: boolean;
    onOpenChange: (v: boolean) => void;
  }>({ open: false, onOpenChange: () => {} });

  return {
    Root: ({
      children,
      open,
      onOpenChange,
    }: {
      children: React.ReactNode;
      open: boolean;
      onOpenChange: (v: boolean) => void;
    }) =>
      React.createElement(
        DialogCtx.Provider,
        { value: { open, onOpenChange } },
        children,
      ),

    Trigger: ({
      children,
      asChild,
    }: {
      children: React.ReactElement;
      asChild?: boolean;
    }) => {
      const ctx = React.useContext(DialogCtx);
      if (asChild && React.isValidElement(children)) {
        return React.cloneElement(
          children as React.ReactElement<Record<string, unknown>>,
          { onClick: () => ctx.onOpenChange(true) },
        );
      }
      return React.createElement(
        "button",
        { onClick: () => ctx.onOpenChange(true) },
        children,
      );
    },

    // Portal renders children only when open; null otherwise
    Portal: ({ children }: { children: React.ReactNode }) => {
      const { open } = React.useContext(DialogCtx);
      return open
        ? React.createElement(React.Fragment, null, children)
        : null;
    },

    Overlay: () => null,

    Content: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { role: "dialog" }, children),

    Title: ({ children }: { children: React.ReactNode }) =>
      React.createElement("h2", null, children),

    Close: ({
      children,
      asChild,
    }: {
      children: React.ReactElement;
      asChild?: boolean;
    }) => {
      const ctx = React.useContext(DialogCtx);
      if (asChild && React.isValidElement(children)) {
        return React.cloneElement(
          children as React.ReactElement<Record<string, unknown>>,
          { onClick: () => ctx.onOpenChange(false) },
        );
      }
      return React.createElement(
        "button",
        { onClick: () => ctx.onOpenChange(false) },
        children,
      );
    },

    Description: ({ children }: { children: React.ReactNode }) =>
      React.createElement("p", null, children),
  };
});

vi.mock("@radix-ui/react-select", () => {
  const React = require("react") as typeof import("react");
  return {
    Root: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Trigger: ({
      children,
      id,
      "aria-label": ariaLabel,
    }: {
      children: React.ReactNode;
      id?: string;
      "aria-label"?: string;
    }) =>
      React.createElement("button", { id, "aria-label": ariaLabel }, children),
    Value: ({ placeholder }: { placeholder?: string }) =>
      React.createElement("span", null, placeholder ?? ""),
    Icon: () => null,
    Portal: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Content: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", null, children),
    Viewport: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", null, children),
    Item: ({
      children,
      value,
    }: {
      children: React.ReactNode;
      value: string;
    }) =>
      React.createElement("div", { "data-value": value }, children),
    ItemText: ({ children }: { children: React.ReactNode }) =>
      React.createElement("span", null, children),
    ItemIndicator: () => null,
  };
});

vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    code: string;
    traceId?: string;
    constructor(
      status: number,
      code: string,
      message: string,
      traceId?: string,
    ) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.code = code;
      this.traceId = traceId;
    }
  }

  return {
    deleteCollection: vi.fn().mockResolvedValue(undefined),
    createCollection: vi
      .fn()
      .mockResolvedValue({ id: "new-col", name: "test" }),
    ApiError,
  };
});

vi.mock("@/hooks/useModels", () => ({
  useModels: () => ({ embedModels: [], llmModels: [] }),
}));

// ─── Component + lib imports ──────────────────────────────────────────────────

import ConfidenceIndicator from "@/components/ConfidenceIndicator";
import CitationTooltip from "@/components/CitationTooltip";
import CollectionCard from "@/components/CollectionCard";
import CreateCollectionDialog from "@/components/CreateCollectionDialog";
import { deleteCollection } from "@/lib/api";
import type { Citation, Collection } from "@/lib/types";

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const MOCK_COLLECTION: Collection = {
  id: "col-1",
  name: "My Collection",
  description: null,
  embedding_model: "nomic-embed-text",
  chunk_profile: "default",
  document_count: 5,
  created_at: "2024-01-01T00:00:00Z",
};

const MOCK_CITATION_REMOVED: Citation = {
  passage_id: "p1",
  document_id: "d1",
  document_name: "report.pdf",
  start_offset: 0,
  end_offset: 50,
  text: "Some passage text here.",
  relevance_score: 0.9,
  source_removed: true,
};

const MOCK_CITATION_PRESENT: Citation = {
  ...MOCK_CITATION_REMOVED,
  source_removed: false,
};

// ─── getConfidenceTier — boundary values (pure function) ──────────────────────

describe("getConfidenceTier — boundary values", () => {
  test("score 0 → red", () => expect(getConfidenceTier(0)).toBe("red"));

  test("score 39 → red (boundary below yellow)", () =>
    expect(getConfidenceTier(39)).toBe("red"));

  test("score 40 → yellow (lower yellow boundary)", () =>
    expect(getConfidenceTier(40)).toBe("yellow"));

  test("score 69 → yellow (upper yellow boundary)", () =>
    expect(getConfidenceTier(69)).toBe("yellow"));

  test("score 70 → green (lower green boundary)", () =>
    expect(getConfidenceTier(70)).toBe("green"));

  test("score 100 → green", () =>
    expect(getConfidenceTier(100)).toBe("green"));
});

// ─── ConfidenceIndicator — aria-label ────────────────────────────────────────

describe("ConfidenceIndicator — aria-label reflects tier and score", () => {
  test.each<[number, string]>([
    [0, "Low confidence: 0%"],
    [39, "Low confidence: 39%"],
    [40, "Medium confidence: 40%"],
    [69, "Medium confidence: 69%"],
    [70, "High confidence: 70%"],
    [100, "High confidence: 100%"],
  ])("score %i → aria-label '%s'", (score, expected) => {
    const { container } = render(<ConfidenceIndicator score={score} />);
    expect(
      container.querySelector(`[aria-label="${expected}"]`),
    ).toBeInTheDocument();
  });
});

// ─── CitationTooltip — source_removed badge ───────────────────────────────────

describe("CitationTooltip — source_removed rendering", () => {
  test("source_removed: true renders 'Source removed' badge text", () => {
    render(<CitationTooltip citation={MOCK_CITATION_REMOVED} index={1} />);
    expect(screen.getByText("Source removed")).toBeInTheDocument();
  });

  test("source_removed: false does NOT render 'Source removed' text", () => {
    render(<CitationTooltip citation={MOCK_CITATION_PRESENT} index={1} />);
    expect(screen.queryByText("Source removed")).not.toBeInTheDocument();
  });

  test("source_removed: false renders document_name in tooltip", () => {
    render(<CitationTooltip citation={MOCK_CITATION_PRESENT} index={1} />);
    // document_name appears in the tooltip content
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
  });

  test("citation trigger button shows [N] index", () => {
    render(<CitationTooltip citation={MOCK_CITATION_PRESENT} index={3} />);
    expect(screen.getByRole("button", { name: /Citation 3/i })).toBeInTheDocument();
  });
});

// ─── CollectionCard — delete confirmation dialog ──────────────────────────────

describe("CollectionCard — delete confirmation dialog", () => {
  beforeEach(() => {
    vi.mocked(deleteCollection).mockClear();
  });

  test("Delete button opens dialog showing 'Delete collection?' before deleteCollection is called", () => {
    const onDelete = vi.fn();
    render(<CollectionCard collection={MOCK_COLLECTION} onDelete={onDelete} />);

    // Dialog content not shown initially
    expect(screen.queryByText("Delete collection?")).not.toBeInTheDocument();

    // Click the Delete trigger (aria-label set by CollectionCard)
    fireEvent.click(
      screen.getByRole("button", {
        name: /Delete collection My Collection/i,
      }),
    );

    // Dialog title must appear in DOM
    expect(screen.getByText("Delete collection?")).toBeInTheDocument();

    // deleteCollection must NOT have been called — dialog is just confirmation UI
    expect(vi.mocked(deleteCollection)).not.toHaveBeenCalled();
  });

  test("deleteCollection is called with collection.id when confirm button is clicked", async () => {
    const onDelete = vi.fn();
    render(<CollectionCard collection={MOCK_COLLECTION} onDelete={onDelete} />);

    // Open dialog
    fireEvent.click(
      screen.getByRole("button", {
        name: /Delete collection My Collection/i,
      }),
    );

    // Wrap in act to flush async state updates from handleConfirmDelete
    const { act } = await import("@testing-library/react");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    });

    expect(vi.mocked(deleteCollection)).toHaveBeenCalledWith("col-1");
  });
});

// ─── CreateCollectionDialog — slug validation ─────────────────────────────────

describe("CreateCollectionDialog — slug validation", () => {
  function openDialog() {
    // "New Collection" button is the Dialog.Trigger
    fireEvent.click(screen.getByRole("button", { name: /New Collection/i }));
  }

  test("invalid slug '-foo' (starts with hyphen) shows role=alert error", () => {
    render(<CreateCollectionDialog onCreated={vi.fn()} />);
    openDialog();

    fireEvent.change(screen.getByPlaceholderText("my-collection"), {
      target: { value: "-foo" },
    });

    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  test("valid slug 'valid-name' does NOT show role=alert error", () => {
    render(<CreateCollectionDialog onCreated={vi.fn()} />);
    openDialog();

    fireEvent.change(screen.getByPlaceholderText("my-collection"), {
      target: { value: "valid-name" },
    });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  test("slug starting with uppercase shows role=alert error", () => {
    render(<CreateCollectionDialog onCreated={vi.fn()} />);
    openDialog();

    fireEvent.change(screen.getByPlaceholderText("my-collection"), {
      target: { value: "Invalid" },
    });

    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  test("empty name shows role=alert error", () => {
    render(<CreateCollectionDialog onCreated={vi.fn()} />);
    openDialog();

    // Type something first so the input is "dirty", then clear
    const input = screen.getByPlaceholderText("my-collection");
    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.change(input, { target: { value: "" } });

    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  test("invalid slug disables submit button", () => {
    render(<CreateCollectionDialog onCreated={vi.fn()} />);
    openDialog();

    fireEvent.change(screen.getByPlaceholderText("my-collection"), {
      target: { value: "-invalid" },
    });

    expect(
      screen.getByRole("button", { name: /Create/i }),
    ).toBeDisabled();
  });
});
