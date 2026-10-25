import type { Metadata } from "next";
import { Suspense } from "react";
import { FileBrowser } from "@/components/files/file-browser";
import { TableSkeleton } from "@/components/files/file-table";

export const metadata: Metadata = { title: "Files" };

export default function FilesPage() {
  // useSearchParams() needs a Suspense boundary in a static export.
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:py-10">
          <div className="overflow-hidden rounded-xl border border-border bg-surface">
            <TableSkeleton />
          </div>
        </div>
      }
    >
      <FileBrowser />
    </Suspense>
  );
}
