import { Loader2, RefreshCw, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { ChangeEvent, useRef, useState } from "react";
import { resolvePublicAssetUrl } from "../api";
import type { Author, Document } from "../types";
import ConfirmDialog from "./ConfirmDialog";

interface AuthorSectionProps {
  author: Author;
  documents: Document[];
  reloadingDocumentId?: string | null;
  deletingAuthor?: boolean;
  avatarUploading?: boolean;
  onReloadDocument: (documentId: string) => Promise<void> | void;
  onDeleteAuthor: () => Promise<void> | void;
  onUploadAvatar: (file: File) => Promise<void> | void;
}

export default function AuthorSection({
  author,
  documents,
  reloadingDocumentId = null,
  deletingAuthor = false,
  avatarUploading = false,
  onReloadDocument,
  onDeleteAuthor,
  onUploadAvatar,
}: AuthorSectionProps) {
  const [confirmAuthorDelete, setConfirmAuthorDelete] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const avatarSrc = resolvePublicAssetUrl(author.avatarUrl);

  const handleAvatarClick = () => {
    if (avatarUploading) return;
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await onUploadAvatar(file);
    } finally {
      e.target.value = "";
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="group"
    >
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-outline-variant/10">
        <div className="flex items-center gap-6">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="image/*"
            className="hidden"
            disabled={avatarUploading}
          />

          <motion.button
            type="button"
            whileHover={avatarUploading ? {} : { scale: 1.1 }}
            whileTap={avatarUploading ? {} : { scale: 0.95 }}
            onClick={handleAvatarClick}
            disabled={avatarUploading}
            className="cursor-pointer relative group/avatar rounded-full disabled:cursor-not-allowed"
            title={avatarUploading ? "Uploading avatar..." : "Upload avatar"}
          >
            {avatarSrc ? (
              <img
                className="w-16 h-16 object-cover rounded-full filter grayscale hover:grayscale-0 transition-all duration-500 editorial-shadow"
                src={avatarSrc}
                alt={author.authorName}
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="w-16 h-16 bg-surface-container-highest rounded-full flex items-center justify-center editorial-shadow transition-colors">
                <span className="font-headline text-2xl italic text-outline-variant group-hover/avatar:text-primary transition-colors">
                  {author.authorName.slice(0, 1).toUpperCase()}
                </span>
              </div>
            )}
            {avatarUploading && (
              <span className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center">
                <Loader2 className="w-4 h-4 text-white animate-spin" />
              </span>
            )}
          </motion.button>

          <div>
            <h3 className="font-headline text-3xl font-medium tracking-tight">
              {author.authorName}
            </h3>
            <p className="font-label text-[10px] text-outline-variant uppercase tracking-widest mt-1">
              {author.school || "Unknown school"} - {documents.length} Documents
            </p>
          </div>
        </div>

        <button
          onClick={() => setConfirmAuthorDelete(true)}
          className="text-error/40 hover:text-error transition-colors p-2 rounded-sm hover:bg-error/5"
          title="Delete Author"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {documents.length > 0 ? (
        <div className="bg-surface-container-low rounded-sm overflow-hidden">
          <table className="w-full text-left font-body text-sm border-collapse">
            <thead className="bg-surface-container-high/50 font-label text-[10px] uppercase tracking-widest text-secondary">
              <tr>
                <th className="px-6 py-4 font-semibold">Book Title</th>
                <th className="px-6 py-4 font-semibold">PDF URI</th>
                <th className="px-6 py-4 font-semibold">Status</th>
                <th className="px-6 py-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/10">
              {documents.map((document) => (
                <tr key={document.documentId} className="hover:bg-white transition-colors">
                  <td className="px-6 py-5 font-medium text-on-background">{document.bookTitle}</td>
                  <td className="px-6 py-5 text-secondary max-w-xs truncate" title={document.pdfUri}>
                    {document.pdfUri}
                  </td>
                  <td className="px-6 py-5">
                    <span
                      className={`px-2 py-1 rounded-sm text-[10px] font-bold uppercase tracking-tighter ${
                        document.status === "active"
                          ? "bg-tertiary-container text-on-tertiary-container"
                          : document.status === "failed"
                            ? "bg-error/10 text-error"
                            : "bg-surface-container-highest text-secondary"
                      }`}
                    >
                      {document.status}
                    </span>
                  </td>
                  <td className="px-6 py-5 text-right">
                    <button
                      className="text-primary hover:underline underline-offset-4 inline-flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
                      disabled={reloadingDocumentId === document.documentId}
                      onClick={() => onReloadDocument(document.documentId)}
                    >
                      <RefreshCw
                        className={`w-3 h-3 ${
                          reloadingDocumentId === document.documentId ? "animate-spin" : ""
                        }`}
                      />
                      {reloadingDocumentId === document.documentId ? "Reloading..." : "Reload"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-surface-container-low/40 rounded-sm p-12 text-center border-2 border-dashed border-outline-variant/10">
          <p className="font-body text-secondary italic">No documents indexed for this author yet.</p>
        </div>
      )}

      <ConfirmDialog
        isOpen={confirmAuthorDelete}
        title="Delete Author"
        message={`Delete ${author.authorName} and all related documents/snapshots? This cannot be undone.`}
        confirmLabel={deletingAuthor ? "Deleting..." : "Delete Author"}
        onConfirm={async () => {
          await onDeleteAuthor();
          setConfirmAuthorDelete(false);
        }}
        onCancel={() => setConfirmAuthorDelete(false)}
      />
    </motion.div>
  );
}
