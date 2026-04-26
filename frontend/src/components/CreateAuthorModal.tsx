import { ImagePlus, Loader2, X } from "lucide-react";
import { motion } from "motion/react";
import { ChangeEvent, useRef, useState } from "react";

interface CreateAuthorModalProps {
  isOpen: boolean;
  submitting?: boolean;
  onClose: () => void;
  onCreate: (payload: {
    authorName: string;
    language: "english" | "chinese";
    avatarFile?: File;
  }) => Promise<void> | void;
}

export default function CreateAuthorModal({
  isOpen,
  submitting = false,
  onClose,
  onCreate,
}: CreateAuthorModalProps) {
  const [authorName, setAuthorName] = useState("");
  const [language, setLanguage] = useState<"english" | "chinese">("english");
  const [avatarPreview, setAvatarPreview] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAvatarFile(file);
    const reader = new FileReader();
    reader.onloadend = () => {
      setAvatarPreview(typeof reader.result === "string" ? reader.result : "");
    };
    reader.readAsDataURL(file);
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

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
              language,
              avatarFile: avatarFile || undefined,
            });
            setAuthorName("");
            setLanguage("english");
            setAvatarPreview("");
            setAvatarFile(null);
            if (fileInputRef.current) fileInputRef.current.value = "";
          }}
        >
          <div className="space-y-2">
            <label className="font-label text-[10px] uppercase tracking-widest text-secondary block">
              Author Name
            </label>
            <input
              type="text"
              required
              value={authorName}
              onChange={(event) => setAuthorName(event.target.value)}
              placeholder="e.g. Friedrich Hayek"
              className="w-full bg-surface-container-low border-none font-body text-sm py-3 px-4 outline-none focus:ring-1 focus:ring-primary rounded-sm transition-all"
            />
          </div>

          <div className="space-y-2">
            <label className="font-label text-[10px] uppercase tracking-widest text-secondary block">
              Author Language
            </label>
            <select
              value={language}
              onChange={(event) =>
                setLanguage(event.target.value === "chinese" ? "chinese" : "english")
              }
              className="w-full bg-surface-container-low border-none font-body text-sm py-3 px-4 outline-none focus:ring-1 focus:ring-primary rounded-sm transition-all"
            >
              <option value="english">English</option>
              <option value="chinese">Chinese</option>
            </select>
          </div>

          <div className="space-y-2">
            <label className="font-label text-[10px] uppercase tracking-widest text-secondary block">
              Author Portrait
            </label>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="image/*"
              className="hidden"
            />
            <div
              onClick={handleUploadClick}
              className="relative w-full aspect-video bg-surface-container-low border-2 border-dashed border-outline-variant/30 rounded-sm flex flex-col items-center justify-center cursor-pointer group hover:border-primary/50 transition-all overflow-hidden"
            >
              {avatarPreview ? (
                <img
                  src={avatarPreview}
                  alt="Avatar Preview"
                  className="w-full h-full object-cover filter grayscale group-hover:grayscale-0 transition-all duration-500"
                />
              ) : (
                <div className="text-center">
                  <ImagePlus className="w-8 h-8 text-outline-variant mx-auto mb-2 group-hover:scale-110 transition-transform" />
                  <span className="font-label text-[10px] uppercase tracking-widest text-outline-variant">
                    Upload Portrait
                  </span>
                </div>
              )}
            </div>
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
              className="flex-1 bg-primary text-on-primary px-6 py-3 rounded-sm font-label text-sm font-semibold tracking-wide hover:bg-primary-dim transition-all shadow-md active:translate-y-px disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              {submitting ? "Creating..." : "Create Author"}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
