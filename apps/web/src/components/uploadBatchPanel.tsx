"use client";

import { useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

type UploadSourceKind = "pdf_batch" | "zip_import";

type UploadBatchPanelProps = {
  workspaceId: string;
};

type UploadResponse = {
  batch: {
    batch_id: string;
    status: string;
    progress: {
      accepted_items: number;
      rejected_items: number;
      total_items: number;
    };
  };
  job: {
    job_id: string;
    status: string;
  } | null;
};

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

export function UploadBatchPanel({ workspaceId }: UploadBatchPanelProps) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [sourceKind, setSourceKind] = useState<UploadSourceKind>("pdf_batch");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFeedback("");
    setError("");

    const form = event.currentTarget;
    const input = form.elements.namedItem("files") as HTMLInputElement | null;
    if (!input?.files?.length) {
      setError("Choose at least one file to create a batch.");
      return;
    }

    const formData = new FormData();
    formData.append("workspace_id", workspaceId);
    formData.append("source_kind", sourceKind);
    Array.from(input.files).forEach((file) => {
      formData.append("files", file);
    });

    startTransition(async () => {
      const response = await fetch("/api/uploads/batch", {
        method: "POST",
        body: formData,
      });
      const payload = (await response.json()) as UploadResponse | { detail?: string };

      if (!response.ok) {
        setError(
          "detail" in payload && payload.detail
            ? payload.detail
            : "The upload batch could not be created.",
        );
        return;
      }

      if (!("batch" in payload)) {
        setError("The upload response was not recognized.");
        return;
      }

      setFeedback(
        `Created ${payload.batch.batch_id}. ${payload.batch.progress.accepted_items} accepted, ${payload.batch.progress.rejected_items} rejected. ${
          payload.job ? `${formatStatus(payload.job.status)} job ${payload.job.job_id} queued.` : ""
        }`.trim(),
      );
      formRef.current?.reset();
      setSourceKind("pdf_batch");
      router.refresh();
    });
  }

  return (
    <div className="detail-card upload-panel">
      <div className="detail-heading">Create a new ingestion batch</div>
      <p>
        Upload a set of academic PDFs or a single ZIP archive. Accepted files
        are stored immediately and turned into one durable batch ingestion job.
      </p>
      <form ref={formRef} className="upload-form" onSubmit={handleSubmit}>
        <div className="upload-mode-row">
          <button
            type="button"
            className={`mode-chip${sourceKind === "pdf_batch" ? " mode-chip--active" : ""}`}
            onClick={() => setSourceKind("pdf_batch")}
          >
            Batch PDFs
          </button>
          <button
            type="button"
            className={`mode-chip${sourceKind === "zip_import" ? " mode-chip--active" : ""}`}
            onClick={() => setSourceKind("zip_import")}
          >
            ZIP import
          </button>
        </div>
        <input
          key={sourceKind}
          className="upload-input"
          name="files"
          type="file"
          accept={sourceKind === "pdf_batch" ? ".pdf,application/pdf" : ".zip,application/zip"}
          multiple={sourceKind === "pdf_batch"}
        />
        <button type="submit" className="upload-submit" disabled={isPending}>
          {isPending ? "Creating batch..." : "Create ingestion batch"}
        </button>
      </form>
      {feedback ? <div className="upload-feedback">{feedback}</div> : null}
      {error ? <div className="upload-error">{error}</div> : null}
    </div>
  );
}
