"use client";

import { useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

type UploadSourceKind = "pdf_batch" | "zip_import";

type UploadBatchPanelProps = {
  workspaceId: string;
  activeStorageBackend: string;
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

type DirectUploadReservationResponse = {
  workspace_id: string;
  source_kind: UploadSourceKind;
  upload_strategy: string;
  items: Array<{
    filename: string;
    media_type: string | null;
    size_bytes: number | null;
    sha256: string | null;
    status: "accepted" | "rejected";
    message: string;
    storage_backend: string | null;
    storage_key: string | null;
    upload_url: string | null;
    upload_method: string | null;
    upload_headers: Record<string, string>;
  }>;
};

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function shouldUseDirectUpload(activeStorageBackend: string) {
  return activeStorageBackend.toLowerCase().includes("+s3");
}

async function sha256Hex(file: File) {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

export function UploadBatchPanel({
  workspaceId,
  activeStorageBackend,
}: UploadBatchPanelProps) {
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
      let response: Response;
      let payload: UploadResponse | { detail?: string };

      if (shouldUseDirectUpload(activeStorageBackend)) {
        const files = Array.from(input.files ?? []);
        const fileDigests = await Promise.all(
          files.map(async (file) => ({
            file,
            sha256: await sha256Hex(file),
          })),
        );
        const reservationResponse = await fetch("/api/uploads/direct-batch", {
          method: "POST",
          headers: {
            "content-type": "application/json",
          },
          body: JSON.stringify({
            workspace_id: workspaceId,
            source_kind: sourceKind,
            items: fileDigests.map(({ file, sha256 }) => ({
              filename: file.name,
              media_type: file.type || null,
              size_bytes: file.size,
              sha256,
            })),
          }),
        });
        const reservationPayload = (await reservationResponse.json()) as
          | DirectUploadReservationResponse
          | { detail?: string };

        if (!reservationResponse.ok) {
          setError(
            "detail" in reservationPayload && reservationPayload.detail
              ? reservationPayload.detail
              : "The direct upload reservation could not be created.",
          );
          return;
        }

        if (!("items" in reservationPayload)) {
          setError("The direct upload response was not recognized.");
          return;
        }

        for (const instruction of reservationPayload.items) {
          if (
            instruction.status !== "accepted" ||
            !instruction.upload_url ||
            !instruction.storage_backend ||
            !instruction.storage_key
          ) {
            continue;
          }
          const matched = fileDigests.find(
            ({ file, sha256 }) =>
              file.name === instruction.filename &&
              file.size === (instruction.size_bytes ?? file.size) &&
              sha256 === instruction.sha256,
          );
          if (!matched) {
            setError(`Could not match ${instruction.filename} to a reserved upload.`);
            return;
          }
          const uploadResponse = await fetch(instruction.upload_url, {
            method: instruction.upload_method || "PUT",
            headers: instruction.upload_headers,
            body: matched.file,
          });
          if (!uploadResponse.ok) {
            setError(
              `Direct upload failed for ${instruction.filename}: ${uploadResponse.status} ${uploadResponse.statusText}`,
            );
            return;
          }
        }

        response = await fetch("/api/uploads/batch", {
          method: "POST",
          headers: {
            "content-type": "application/json",
          },
          body: JSON.stringify({
            workspace_id: workspaceId,
            source_kind: sourceKind,
            items: reservationPayload.items.map((item) =>
              item.status === "accepted" && item.storage_backend && item.storage_key
                ? {
                    filename: item.filename,
                    media_type: item.media_type,
                    size_bytes: item.size_bytes,
                    storage_backend: item.storage_backend,
                    storage_key: item.storage_key,
                    sha256: item.sha256,
                  }
                : {
                    filename: item.filename,
                    media_type: item.media_type,
                    size_bytes: item.size_bytes,
                    validation_error: item.message,
                  },
            ),
          }),
        });
      } else {
        response = await fetch("/api/uploads/batch", {
          method: "POST",
          body: formData,
        });
      }

      payload = (await response.json()) as UploadResponse | { detail?: string };

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

      const modeSummary =
        sourceKind === "zip_import"
          ? "Archive accepted. Hypatia will expand it into per-paper PDF items during ingestion."
          : `${payload.batch.progress.accepted_items} accepted, ${payload.batch.progress.rejected_items} rejected.`;
      setFeedback(
        `Created ${payload.batch.batch_id}. ${modeSummary} ${
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
        {shouldUseDirectUpload(activeStorageBackend)
          ? " This workspace uploads directly to object storage before the batch is finalized."
          : ""}
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
