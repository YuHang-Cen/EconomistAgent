import { PlusCircle } from 'lucide-react';
import { Author } from '../types';
import { motion, AnimatePresence } from 'motion/react';
import React, { useState, useRef } from 'react';
import ConfirmDialog from './ConfirmDialog';

interface AuthorSectionProps {
  author: Author;
  onRemoveManuscript: (manuscriptId: string) => void;
  key?: string;
}

export default function AuthorSection({ author, onRemoveManuscript }: AuthorSectionProps) {
  const [avatarUrl, setAvatarUrl] = useState(author.avatarUrl);
  const [confirmDelete, setConfirmDelete] = useState<{ isOpen: boolean; manuscriptId: string | null; title: string }>({
    isOpen: false,
    manuscriptId: null,
    title: ''
  });
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleAvatarClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarUrl(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const openDeleteConfirm = (id: string, title: string) => {
    setConfirmDelete({ isOpen: true, manuscriptId: id, title });
  };

  const handleConfirmDelete = () => {
    if (confirmDelete.manuscriptId) {
      onRemoveManuscript(confirmDelete.manuscriptId);
    }
    setConfirmDelete({ isOpen: false, manuscriptId: null, title: '' });
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
          />
          <motion.div
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleAvatarClick}
            className="cursor-pointer relative"
          >
            {avatarUrl ? (
              <img
                className="w-16 h-16 object-cover rounded-full filter grayscale hover:grayscale-0 transition-all duration-500 editorial-shadow"
                src={avatarUrl}
                alt={author.name}
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="w-16 h-16 bg-surface-container-highest rounded-full flex items-center justify-center editorial-shadow">
                <span className="font-headline text-2xl italic text-outline-variant">{author.initials}</span>
              </div>
            )}
          </motion.div>
          <div>
            <h3 className="font-headline text-3xl font-medium tracking-tight">{author.name}</h3>
            <p className="font-label text-[10px] text-outline-variant uppercase tracking-widest mt-1">
              {author.school} • {author.manuscriptsCount} Manuscripts Imported
            </p>
          </div>
        </div>
        <button className="text-primary hover:text-primary-dim font-label text-xs font-bold transition-colors flex items-center gap-2">
          <PlusCircle className="w-4 h-4" />
          ADD BOOK
        </button>
      </div>

      {author.manuscripts.length > 0 ? (
        <div className="bg-surface-container-low rounded-sm overflow-hidden">
          <table className="w-full text-left font-body text-sm border-collapse">
            <thead className="bg-surface-container-high/50 font-label text-[10px] uppercase tracking-widest text-secondary">
              <tr>
                <th className="px-6 py-4 font-semibold">Manuscript Title</th>
                <th className="px-6 py-4 font-semibold">Upload Date</th>
                <th className="px-6 py-4 font-semibold">Status</th>
                <th className="px-6 py-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/10">
              <AnimatePresence mode="popLayout">
                {author.manuscripts.map((manuscript) => (
                  <motion.tr 
                    key={manuscript.id} 
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="hover:bg-white transition-colors"
                  >
                    <td className="px-6 py-5 font-medium text-on-background">{manuscript.title}</td>
                    <td className="px-6 py-5 text-secondary">{manuscript.uploadDate}</td>
                    <td className="px-6 py-5">
                      <span
                        className={`px-2 py-1 rounded-sm text-[10px] font-bold uppercase tracking-tighter ${
                          manuscript.status === 'indexed'
                            ? 'bg-tertiary-container text-on-tertiary-container'
                            : 'bg-surface-container-highest text-secondary'
                        }`}
                      >
                        {manuscript.status}
                      </span>
                    </td>
                    <td className="px-6 py-5 text-right space-x-3">
                      <button
                        className={`underline-offset-4 ${
                          manuscript.status === 'indexed' ? 'text-primary hover:underline' : 'text-outline-variant cursor-not-allowed'
                        }`}
                        disabled={manuscript.status !== 'indexed'}
                      >
                        Reload
                      </button>
                      <button 
                        onClick={() => openDeleteConfirm(manuscript.id, manuscript.title)}
                        className="text-error/70 hover:text-error"
                      >
                        Remove
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-surface-container-low/40 rounded-sm p-12 text-center border-2 border-dashed border-outline-variant/10">
          <p className="font-body text-secondary italic">No documents indexed for this author yet.</p>
          <button className="mt-4 font-label text-[10px] uppercase tracking-widest text-primary hover:underline">
            Start initial import
          </button>
        </div>
      )}

      <ConfirmDialog
        isOpen={confirmDelete.isOpen}
        title="Remove Manuscript"
        message={`Are you sure you want to remove "${confirmDelete.title}"? This action cannot be undone and all associated indexing data will be lost.`}
        confirmLabel="Remove"
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDelete({ isOpen: false, manuscriptId: null, title: '' })}
      />
    </motion.div>
  );
}
