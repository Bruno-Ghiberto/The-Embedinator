import { describe, test, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { getConfidenceTier } from "@/lib/types";

// ─── Mocks ────────────────────────────────────────────────────────────────────
// All vi.mock calls are hoisted before imports by vitest.
// Use require("react") inside factories to avoid hoisting issues.

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

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

// Mock base-ui Popover so Portal renders inline and content is always visible
vi.mock("@base-ui/react/popover", () => {
  const React = require("react") as typeof import("react");
  const Popover = {
    Root: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { "data-slot": "popover" }, children),
    Trigger: ({
      children,
      className,
      ...props
    }: {
      children: React.ReactNode;
      className?: string;
      "aria-label"?: string;
    }) =>
      React.createElement(
        "button",
        { type: "button", className, ...props },
        children,
      ),
    Portal: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Positioner: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Popup: ({
      children,
      className,
    }: {
      children: React.ReactNode;
      className?: string;
    }) =>
      React.createElement("div", { "data-slot": "popover-content", className }, children),
    Title: ({ children, ...props }: { children: React.ReactNode }) =>
      React.createElement("h3", props, children),
    Description: ({ children, ...props }: { children: React.ReactNode }) =>
      React.createElement("p", props, children),
  };
  return { Popover };
});

// Mock base-ui Dialog so Portal renders inline and content shows when open
vi.mock("@base-ui/react/dialog", () => {
  const React = require("react") as typeof import("react");
  const DialogCtx = React.createContext<{
    open: boolean;
    onOpenChange: (v: boolean) => void;
  }>({ open: false, onOpenChange: () => {} });

  const Dialog = {
    Root: ({
      children,
      open,
      onOpenChange,
    }: {
      children: React.ReactNode;
      open?: boolean;
      onOpenChange?: (v: boolean) => void;
    }) =>
      React.createElement(
        DialogCtx.Provider,
        { value: { open: open ?? false, onOpenChange: onOpenChange ?? (() => {}) } },
        children,
      ),
    Trigger: ({
      children,
      render,
      ...props
    }: {
      children?: React.ReactNode;
      render?: React.ReactElement;
    }) => {
      const ctx = React.useContext(DialogCtx);
      if (render && React.isValidElement(render)) {
        return React.cloneElement(
          render as React.ReactElement<Record<string, unknown>>,
          { onClick: () => ctx.onOpenChange(true), ...props },
          children,
        );
      }
      return React.createElement(
        "button",
        { type: "button", onClick: () => ctx.onOpenChange(true), ...props },
        children,
      );
    },
    Portal: ({ children }: { children: React.ReactNode }) => {
      const { open } = React.useContext(DialogCtx);
      return open ? React.createElement(React.Fragment, null, children) : null;
    },
    Backdrop: () => null,
    Popup: ({
      children,
      className,
    }: {
      children: React.ReactNode;
      className?: string;
      showCloseButton?: boolean;
    }) =>
      React.createElement("div", { role: "dialog", className }, children),
    Title: ({ children }: { children: React.ReactNode }) =>
      React.createElement("h2", null, children),
    Description: ({ children }: { children: React.ReactNode }) =>
      React.createElement("p", null, children),
    Close: ({
      children,
      render,
      disabled,
    }: {
      children?: React.ReactNode;
      render?: React.ReactElement;
      disabled?: boolean;
    }) => {
      const ctx = React.useContext(DialogCtx);
      if (render && React.isValidElement(render)) {
        return React.cloneElement(
          render as React.ReactElement<Record<string, unknown>>,
          { onClick: () => ctx.onOpenChange(false), disabled },
          children,
        );
      }
      return React.createElement(
        "button",
        { type: "button", onClick: () => ctx.onOpenChange(false), disabled },
        children,
      );
    },
  };
  return { Dialog };
});

// Mock base-ui Menu so DropdownMenu items are always visible
vi.mock("@base-ui/react/menu", () => {
  const React = require("react") as typeof import("react");
  const Menu = {
    Root: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { "data-slot": "dropdown-menu" }, children),
    Trigger: ({
      children,
      render,
      ...props
    }: {
      children?: React.ReactNode;
      render?: React.ReactElement;
    }) => {
      if (render && React.isValidElement(render)) {
        return React.cloneElement(
          render as React.ReactElement<Record<string, unknown>>,
          { "aria-haspopup": "menu", ...props },
          children,
        );
      }
      return React.createElement(
        "button",
        { type: "button", "aria-haspopup": "menu", ...props },
        children,
      );
    },
    Portal: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Positioner: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Popup: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { role: "menu" }, children),
    Item: ({
      children,
      render,
      onClick,
      ...props
    }: {
      children?: React.ReactNode;
      render?: React.ReactElement;
      onClick?: () => void;
      variant?: string;
    }) => {
      if (render && React.isValidElement(render)) {
        return React.cloneElement(
          render as React.ReactElement<Record<string, unknown>>,
          { role: "menuitem", onClick, ...props },
          children,
        );
      }
      return React.createElement(
        "div",
        { role: "menuitem", onClick, ...props },
        children,
      );
    },
    Separator: () => React.createElement("hr"),
    Group: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { role: "group" }, children),
    GroupLabel: ({ children }: { children: React.ReactNode }) =>
      React.createElement("span", null, children),
    CheckboxItem: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { role: "menuitemcheckbox" }, children),
    RadioGroup: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { role: "radiogroup" }, children),
    RadioItem: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { role: "menuitemradio" }, children),
    ItemIndicator: () => null,
    Arrow: () => null,
  };
  return { Menu };
});

// Mock base-ui Select
vi.mock("@base-ui/react/select", () => {
  const React = require("react") as typeof import("react");
  const Select = {
    Root: ({
      children,
    }: {
      children: React.ReactNode;
      value?: string;
      onValueChange?: (v: string) => void;
    }) => React.createElement(React.Fragment, null, children),
    Trigger: ({
      children,
      id,
      "aria-label": ariaLabel,
    }: {
      children: React.ReactNode;
      id?: string;
      className?: string;
      "aria-label"?: string;
    }) =>
      React.createElement("button", { id, "aria-label": ariaLabel, type: "button" }, children),
    Value: ({ placeholder }: { placeholder?: string }) =>
      React.createElement("span", null, placeholder ?? ""),
    Icon: ({ render }: { render?: React.ReactElement }) =>
      render ? render : null,
    Portal: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Positioner: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    ScrollUpArrow: () => null,
    ScrollDownArrow: () => null,
    Popup: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", null, children),
    List: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", null, children),
    Group: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", null, children),
    GroupLabel: ({ children }: { children: React.ReactNode }) =>
      React.createElement("span", null, children),
    Separator: () => React.createElement("hr"),
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
    ItemIndicator: ({ render, children }: { render?: React.ReactElement; children?: React.ReactNode }) =>
      render ? React.cloneElement(render as React.ReactElement<Record<string, unknown>>, {}, children) : null,
  };
  return { Select };
});

// Mock base-ui Tooltip to render inline
vi.mock("@base-ui/react/tooltip", () => {
  const React = require("react") as typeof import("react");
  const Tooltip = {
    Provider: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Root: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Trigger: ({
      children,
      render,
      ...props
    }: {
      children?: React.ReactNode;
      render?: React.ReactElement;
    }) => {
      if (render && React.isValidElement(render)) {
        return React.cloneElement(
          render as React.ReactElement<Record<string, unknown>>,
          props,
          children,
        );
      }
      return React.createElement("span", props, children);
    },
    Portal: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Positioner: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    Popup: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { "data-testid": "tooltip-content" }, children),
    Arrow: () => null,
  };
  return { Tooltip };
});

// Mock base-ui useRender and mergeProps for breadcrumb components
vi.mock("@base-ui/react/use-render", () => {
  const React = require("react") as typeof import("react");
  return {
    useRender: ({ defaultTagName, props, render }: { defaultTagName: string; props: Record<string, unknown>; render?: React.ReactElement; state?: Record<string, unknown> }) => {
      if (render && React.isValidElement(render)) {
        return React.cloneElement(render as React.ReactElement<Record<string, unknown>>, props);
      }
      return React.createElement(defaultTagName, props);
    },
  };
});

vi.mock("@base-ui/react/merge-props", () => ({
  mergeProps: (...args: Record<string, unknown>[]) => Object.assign({}, ...args),
}));

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
import { CitationHoverCard } from "@/components/CitationHoverCard";
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

// ─── CitationHoverCard — source_removed rendering ─────────────────────────────

describe("CitationHoverCard — source_removed rendering", () => {
  test("source_removed: true renders line-through pill", () => {
    render(<CitationHoverCard citation={MOCK_CITATION_REMOVED} citationNumber={1} />);
    const pill = screen.getByText("[1]");
    expect(pill).toBeInTheDocument();
    expect(pill.className).toContain("line-through");
  });

  test("source_removed: false renders clickable citation pill", () => {
    render(<CitationHoverCard citation={MOCK_CITATION_PRESENT} citationNumber={1} />);
    const pill = screen.getByText("[1]");
    expect(pill).toBeInTheDocument();
    expect(pill.className).not.toContain("line-through");
  });

  test("source_removed: false includes document_name in aria-label", () => {
    render(<CitationHoverCard citation={MOCK_CITATION_PRESENT} citationNumber={1} />);
    expect(screen.getByLabelText(/report\.pdf/)).toBeInTheDocument();
  });

  test("citation trigger shows [N] number with aria-label", () => {
    render(<CitationHoverCard citation={MOCK_CITATION_PRESENT} citationNumber={3} />);
    expect(screen.getByLabelText(/Citation 3/i)).toBeInTheDocument();
  });
});

// ─── CollectionCard — delete confirmation dialog ──────────────────────────────

describe("CollectionCard — delete confirmation dialog", () => {
  beforeEach(() => {
    vi.mocked(deleteCollection).mockClear();
  });

  test("Delete menu item opens dialog showing 'Delete collection?' before deleteCollection is called", () => {
    const onDelete = vi.fn();
    render(<CollectionCard collection={MOCK_COLLECTION} onDelete={onDelete} />);

    // Dialog content not shown initially
    expect(screen.queryByText("Delete collection?")).not.toBeInTheDocument();

    // Click the Delete menu item (rendered inline by menu mock)
    const deleteItem = screen.getByText("Delete");
    fireEvent.click(deleteItem);

    // Dialog title must appear in DOM
    expect(screen.getByText("Delete collection?")).toBeInTheDocument();

    // deleteCollection must NOT have been called — dialog is just confirmation UI
    expect(vi.mocked(deleteCollection)).not.toHaveBeenCalled();
  });

  test("deleteCollection is called with collection.id when confirm button is clicked", async () => {
    const onDelete = vi.fn();
    render(<CollectionCard collection={MOCK_COLLECTION} onDelete={onDelete} />);

    // Open dialog by clicking Delete menu item
    fireEvent.click(screen.getByText("Delete"));

    // Wrap in act to flush async state updates from handleConfirmDelete
    const { act } = await import("@testing-library/react");
    await act(async () => {
      // Click the "Delete" button inside the dialog (not the menu item)
      const deleteButtons = screen.getAllByText("Delete");
      // The last one is the confirm button in the dialog
      const confirmButton = deleteButtons.find(
        (el) => el.closest("[role='dialog']") !== null,
      );
      if (confirmButton) {
        fireEvent.click(confirmButton);
      }
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
