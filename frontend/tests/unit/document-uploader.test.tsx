/**
 * BUG-040 — the client-side upload cap. The UI advertised and enforced 50 MB
 * while the backend accepts 100 MiB (backend/config.py max_upload_size_mb), so
 * a legitimate 60 MiB PDF was rejected before any request left the browser.
 *
 * Files go in through react-dropzone's hidden <input type="file">; sizes are
 * faked with a property override, nothing is allocated.
 */
import { describe, test, expect, vi, afterEach } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import DocumentUploader from "@/components/DocumentUploader";
import { ingestFile } from "@/lib/api";

// The queue effect calls ingestFile as soon as a file is accepted; keep it
// pending so the accepted row stays in its "Uploading…" state.
vi.mock("@/lib/api", () => ({
  ingestFile: vi.fn(() => new Promise(() => {})),
  // Imported by IngestionProgress, which mounts once an upload resolves.
  getIngestionJob: vi.fn(),
}));

const MIB = 1024 * 1024;

function fakePdf(name: string, size: number): File {
  const file = new File(["x"], name, { type: "application/pdf" });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

function renderUploader(): HTMLInputElement {
  const { container } = render(
    <DocumentUploader collectionId="c1" onUploadComplete={vi.fn()} />,
  );
  return container.querySelector('input[type="file"]') as HTMLInputElement;
}

describe("DocumentUploader — upload size cap (BUG-040)", () => {
  afterEach(() => {
    vi.mocked(ingestFile).mockClear();
  });

  test("a 60 MiB PDF is accepted client-side and handed to ingestFile (BUG-040 symptom)", async () => {
    const input = renderUploader();
    const file = fakePdf("big.pdf", 60 * MIB);

    fireEvent.change(input, { target: { files: [file] } });

    await screen.findByText("big.pdf");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(ingestFile).toHaveBeenCalledWith("c1", file);
  });

  test("a file above 100 MiB is rejected with a message naming the 100 MB limit", async () => {
    const input = renderUploader();
    const file = fakePdf("huge.pdf", 100 * MIB + 1);

    fireEvent.change(input, { target: { files: [file] } });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("100 MB");
    expect(ingestFile).not.toHaveBeenCalled();
  });

  test("the drop zone advertises the 100 MB cap", () => {
    renderUploader();
    expect(screen.getByText(/max 100 MB/)).toBeInTheDocument();
  });
});
