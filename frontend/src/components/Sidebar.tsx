import { FileUp, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import type { Author } from "../types";

interface SidebarProps {
  authors: Author[];
  selectedAuthorId: string | null;
  uploading?: boolean;
  onAuthorChange: (authorId: string) => void;
  onUpload: (payload: { authorId: string; bookTitle: string; file: File }) => Promise<void> | void;
}

export default function Sidebar({
  authors,
  selectedAuthorId,
  uploading = false,
  onAuthorChange,
  onUpload,
}: SidebarProps) {
  const [bookTitle, setBookTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const selectedAuthor = useMemo(
    () => authors.find((item) => item.authorId === selectedAuthorId),
    [authors, selectedAuthorId]
  );

  return (
    <section className="col-span-12 lg:col-span-4 space-y-8">
      <div className="bg-surface-container-low p-8 rounded-sm editorial-shadow sticky top-32">
        <h2 className="font-headline text-2xl mb-6 italic">Quick Import</h2>

        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!selectedAuthorId || !bookTitle.trim() || !file || uploading) return;
            await onUpload({
              authorId: selectedAuthorId,
              bookTitle: bookTitle.trim(),
              file,
            });
            setBookTitle("");
            setFile(null);
          }}
        >
          <label className="block">
            <span className="font-label text-[10px] uppercase tracking-widest text-secondary block mb-2">
              Select Author
            </span>
            <select
              value={selectedAuthorId || ""}
              onChange={(event) => onAuthorChange(event.target.value)}
              className="w-full bg-white border-none font-body text-sm py-3 px-4 outline-none focus:ring-1 focus:ring-primary rounded-sm transition-all"
            >
              <option value="" disabled>
                Select an author
              </option>
              {authors.map((author) => (
                <option key={author.authorId} value={author.authorId}>
                  {author.authorName}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="font-label text-[10px] uppercase tracking-widest text-secondary block mb-2">
              Book Title
            </span>
            <input
              type="text"
              value={bookTitle}
              onChange={(event) => setBookTitle(event.target.value)}
              placeholder="e.g. General Theory"
              className="w-full bg-white border-none font-body text-sm py-3 px-4 outline-none focus:ring-1 focus:ring-primary rounded-sm transition-all"
            />
          </label>

          <label className="block">
            <span className="font-label text-[10px] uppercase tracking-widest text-secondary block mb-2">
              PDF File
            </span>
            <div className="border-2 border-dashed border-outline-variant/30 rounded-sm p-4 bg-white/50">
              <label className="flex items-center gap-3 cursor-pointer text-sm text-secondary">
                <FileUp className="w-4 h-4" />
                <span>{file ? file.name : "Choose a PDF file"}</span>
                <input
                  type="file"
                  accept=".pdf,application/pdf"
                  className="hidden"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                />
              </label>
            </div>
          </label>

          <button
            type="submit"
            disabled={!selectedAuthorId || !bookTitle.trim() || !file || uploading}
            className="w-full bg-primary text-on-primary px-6 py-3 rounded-sm font-label text-sm font-semibold tracking-wide hover:bg-primary-dim transition-all shadow-md active:translate-y-px disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <span className="inline-flex items-center gap-2">
              <Upload className="w-4 h-4" />
              {uploading ? "Uploading..." : "Upload & Reload"}
            </span>
          </button>
        </form>

        {selectedAuthor && (
          <p className="mt-4 text-xs text-secondary">
            Current author: <span className="font-semibold">{selectedAuthor.authorName}</span>
          </p>
        )}
      </div>
    </section>
  );
}
