import { X } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";

interface CreateAuthorModalProps {
  isOpen: boolean;
  submitting?: boolean;
  onClose: () => void;
  onCreate: (payload: {
    authorName: string;
    school?: string;
    avatarUrl?: string;
  }) => Promise<void> | void;
}

export default function CreateAuthorModal({
  isOpen,
  submitting = false,
  onClose,
  onCreate,
}: CreateAuthorModalProps) {
  const [authorName, setAuthorName] = useState("");
  const [school, setSchool] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-on-background/20 backdrop-blur-md"
      />

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="relative w-full max-w-lg bg-surface p-8 rounded-sm editorial-shadow border border-outline-variant/10"
      >
        <div className="flex justify-between items-center mb-8">
          <h2 className="font-headline text-3xl font-medium tracking-tight">
            Create New Author
          </h2>
          <button
            onClick={onClose}
            className="text-secondary hover:text-on-background transition-colors p-1"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <form
          className="space-y-6"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!authorName.trim() || submitting) return;
            await onCreate({
              authorName: authorName.trim(),
              school: school.trim() || undefined,
              avatarUrl: avatarUrl.trim() || undefined,
            });
            setAuthorName("");
            setSchool("");
            setAvatarUrl("");
          }}
        >
          <div className="space-y-2">
            <label className="font-label text-[10px] uppercase tracking-widest text-secondary block">
              Author Name
            </label>
            <input
              type="text"
              value={authorName}
              onChange={(event) => setAuthorName(event.target.value)}
              placeholder="e.g. Friedrich Hayek"
              className="w-full bg-surface-container-low border-none font-body text-sm py-3 px-4 outline-none focus:ring-1 focus:ring-primary rounded-sm transition-all"
            />
          </div>

          <div className="space-y-2">
            <label className="font-label text-[10px] uppercase tracking-widest text-secondary block">
              School of Thought
            </label>
            <input
              type="text"
              value={school}
              onChange={(event) => setSchool(event.target.value)}
              placeholder="e.g. Keynesian"
              className="w-full bg-surface-container-low border-none font-body text-sm py-3 px-4 outline-none focus:ring-1 focus:ring-primary rounded-sm transition-all"
            />
          </div>

          <div className="space-y-2">
            <label className="font-label text-[10px] uppercase tracking-widest text-secondary block">
              Avatar URL
            </label>
            <input
              type="text"
              value={avatarUrl}
              onChange={(event) => setAvatarUrl(event.target.value)}
              placeholder="https://example.com/avatar.png"
              className="w-full bg-surface-container-low border-none font-body text-sm py-3 px-4 outline-none focus:ring-1 focus:ring-primary rounded-sm transition-all"
            />
          </div>

          <div className="pt-4 flex gap-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-6 py-3 border border-outline-variant/30 rounded-sm font-label text-sm font-semibold tracking-wide hover:bg-surface-container-low transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !authorName.trim()}
              className="flex-1 bg-primary text-on-primary px-6 py-3 rounded-sm font-label text-sm font-semibold tracking-wide hover:bg-primary-dim transition-all shadow-md active:translate-y-px disabled:opacity-60"
            >
              {submitting ? "Creating..." : "Create Author"}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
