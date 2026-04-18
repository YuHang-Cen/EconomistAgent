import { Eye, EyeOff, Settings as SettingsIcon, X } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";

export interface RuntimeModelSettings {
  provider: string;
  modelName: string;
  apiBase: string;
  apiKey: string;
}

export interface RuntimeSettingsState {
  skillsModel: RuntimeModelSettings;
  answerModel: RuntimeModelSettings;
}

interface SettingsModalProps {
  isOpen: boolean;
  value: RuntimeSettingsState;
  onClose: () => void;
  onSave: (next: RuntimeSettingsState) => void;
}

export default function SettingsModal({ isOpen, value, onClose, onSave }: SettingsModalProps) {
  const [showSkillApiKey, setShowSkillApiKey] = useState(false);
  const [showAnswerApiKey, setShowAnswerApiKey] = useState(false);
  const [draft, setDraft] = useState<RuntimeSettingsState>(value);

  if (!isOpen) return null;

  const providers = ["deepseek", "openai", "anthropic", "google"];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-on-background/40 backdrop-blur-sm"
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="relative bg-background w-full max-w-2xl rounded-sm shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
      >
        <div className="px-8 py-6 border-b border-outline-variant/10 flex justify-between items-center bg-surface-container-low">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-sm">
              <SettingsIcon className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-headline font-bold text-on-background">Runtime Model Settings</h2>
              <p className="text-[10px] font-label text-secondary uppercase tracking-widest">
                In-memory only
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-surface-container-high rounded-sm transition-colors text-secondary hover:text-on-background"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-8 space-y-10 custom-scrollbar">
          <section className="space-y-4">
            <h3 className="text-xs font-label font-bold uppercase tracking-[0.2em] text-primary">
              Skills Model
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <select
                value={draft.skillsModel.provider}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    skillsModel: { ...draft.skillsModel, provider: event.target.value },
                  })
                }
                className="bg-surface-container-low border border-outline-variant/20 rounded-sm px-3 py-2"
              >
                {providers.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <input
                value={draft.skillsModel.modelName}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    skillsModel: { ...draft.skillsModel, modelName: event.target.value },
                  })
                }
                placeholder="model name"
                className="bg-surface-container-low border border-outline-variant/20 rounded-sm px-3 py-2"
              />
              <input
                value={draft.skillsModel.apiBase}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    skillsModel: { ...draft.skillsModel, apiBase: event.target.value },
                  })
                }
                placeholder="api base"
                className="md:col-span-2 bg-surface-container-low border border-outline-variant/20 rounded-sm px-3 py-2"
              />
              <div className="md:col-span-2 relative">
                <input
                  type={showSkillApiKey ? "text" : "password"}
                  value={draft.skillsModel.apiKey}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      skillsModel: { ...draft.skillsModel, apiKey: event.target.value },
                    })
                  }
                  placeholder="api key"
                  className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-3 py-2 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowSkillApiKey(!showSkillApiKey)}
                  className="absolute right-3 top-2.5 text-outline-variant hover:text-primary"
                >
                  {showSkillApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <h3 className="text-xs font-label font-bold uppercase tracking-[0.2em] text-primary">
              Answer Model
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <select
                value={draft.answerModel.provider}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    answerModel: { ...draft.answerModel, provider: event.target.value },
                  })
                }
                className="bg-surface-container-low border border-outline-variant/20 rounded-sm px-3 py-2"
              >
                {providers.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <input
                value={draft.answerModel.modelName}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    answerModel: { ...draft.answerModel, modelName: event.target.value },
                  })
                }
                placeholder="model name"
                className="bg-surface-container-low border border-outline-variant/20 rounded-sm px-3 py-2"
              />
              <input
                value={draft.answerModel.apiBase}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    answerModel: { ...draft.answerModel, apiBase: event.target.value },
                  })
                }
                placeholder="api base"
                className="md:col-span-2 bg-surface-container-low border border-outline-variant/20 rounded-sm px-3 py-2"
              />
              <div className="md:col-span-2 relative">
                <input
                  type={showAnswerApiKey ? "text" : "password"}
                  value={draft.answerModel.apiKey}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      answerModel: { ...draft.answerModel, apiKey: event.target.value },
                    })
                  }
                  placeholder="api key"
                  className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-3 py-2 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowAnswerApiKey(!showAnswerApiKey)}
                  className="absolute right-3 top-2.5 text-outline-variant hover:text-primary"
                >
                  {showAnswerApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </section>
        </div>

        <div className="px-8 py-6 border-t border-outline-variant/10 bg-surface-container-low flex justify-end gap-4">
          <button
            onClick={onClose}
            className="px-6 py-2 rounded-sm font-label text-xs font-bold uppercase tracking-widest text-secondary hover:text-on-background transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onSave(draft);
              onClose();
            }}
            className="bg-primary text-on-primary px-8 py-2 rounded-sm font-label text-xs font-bold uppercase tracking-widest hover:bg-primary-dim transition-all shadow-md"
          >
            Save Changes
          </button>
        </div>
      </motion.div>
    </div>
  );
}
