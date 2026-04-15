import { X, Eye, EyeOff, Globe, Cpu, Zap, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { motion } from 'motion/react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [showSkillApiKey, setShowSkillApiKey] = useState(false);
  const [showAnswerApiKey, setShowAnswerApiKey] = useState(false);
  const [settings, setSettings] = useState({
    language: 'zh-CN',
    skillModel: {
      provider: 'OpenAI',
      apiKey: '',
      modelName: 'gpt-4o',
      apiBase: 'https://api.openai.com/v1'
    },
    answerModel: {
      provider: 'OpenAI',
      apiKey: '',
      modelName: 'gpt-4o',
      apiBase: 'https://api.openai.com/v1'
    }
  });

  if (!isOpen) return null;

  const providers = ['OpenAI', 'Google', 'Anthropic', 'DeepSeek'];

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
        {/* Header */}
        <div className="px-8 py-6 border-b border-outline-variant/10 flex justify-between items-center bg-surface-container-low">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-sm">
              <Zap className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-headline font-bold text-on-background">System Settings</h2>
              <p className="text-[10px] font-label text-secondary uppercase tracking-widest">Configure your AI environment</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-surface-container-high rounded-sm transition-colors text-secondary hover:text-on-background"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-8 space-y-12 custom-scrollbar">
          {/* General Settings */}
          <section className="space-y-6">
            <div className="flex items-center gap-2 mb-4">
              <Globe className="w-4 h-4 text-primary" />
              <h3 className="text-xs font-label font-bold uppercase tracking-[0.2em] text-primary">General</h3>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-label font-bold text-secondary uppercase tracking-wider">Language</label>
                <select 
                  value={settings.language}
                  onChange={(e) => setSettings({...settings, language: e.target.value})}
                  className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-4 py-2.5 text-sm focus:ring-1 focus:ring-primary outline-none transition-all"
                >
                  <option value="zh-CN">简体中文 (Chinese Simplified)</option>
                  <option value="en-US">English (United States)</option>
                </select>
              </div>
            </div>
          </section>

          {/* Skills Generation Model */}
          <section className="space-y-6">
            <div className="flex items-center gap-2 mb-4">
              <Cpu className="w-4 h-4 text-primary" />
              <h3 className="text-xs font-label font-bold uppercase tracking-[0.2em] text-primary">Skills Generation</h3>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-label font-bold text-secondary uppercase tracking-wider">Provider</label>
                <select 
                  value={settings.skillModel.provider}
                  onChange={(e) => setSettings({
                    ...settings, 
                    skillModel: { ...settings.skillModel, provider: e.target.value }
                  })}
                  className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-4 py-2.5 text-sm focus:ring-1 focus:ring-primary outline-none transition-all"
                >
                  {providers.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-label font-bold text-secondary uppercase tracking-wider">Model Name</label>
                <input 
                  type="text"
                  value={settings.skillModel.modelName}
                  onChange={(e) => setSettings({
                    ...settings, 
                    skillModel: { ...settings.skillModel, modelName: e.target.value }
                  })}
                  placeholder="e.g. gpt-4o"
                  className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-4 py-2.5 text-sm focus:ring-1 focus:ring-primary outline-none transition-all"
                />
              </div>

              <div className="space-y-2 md:col-span-2">
                <label className="text-xs font-label font-bold text-secondary uppercase tracking-wider">API Key</label>
                <div className="relative">
                  <input 
                    type={showSkillApiKey ? "text" : "password"}
                    value={settings.skillModel.apiKey}
                    onChange={(e) => setSettings({
                      ...settings, 
                      skillModel: { ...settings.skillModel, apiKey: e.target.value }
                    })}
                    placeholder="sk-..."
                    className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-4 py-2.5 text-sm focus:ring-1 focus:ring-primary outline-none transition-all pr-12"
                  />
                  <button 
                    onClick={() => setShowSkillApiKey(!showSkillApiKey)}
                    className="absolute right-3 top-2.5 text-outline-variant hover:text-primary transition-colors"
                  >
                    {showSkillApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2 md:col-span-2">
                <label className="text-xs font-label font-bold text-secondary uppercase tracking-wider">API Base URL</label>
                <input 
                  type="text"
                  value={settings.skillModel.apiBase}
                  onChange={(e) => setSettings({
                    ...settings, 
                    skillModel: { ...settings.skillModel, apiBase: e.target.value }
                  })}
                  placeholder="https://api.openai.com/v1"
                  className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-4 py-2.5 text-sm focus:ring-1 focus:ring-primary outline-none transition-all"
                />
              </div>
            </div>
          </section>

          {/* Final Answer Model */}
          <section className="space-y-6">
            <div className="flex items-center gap-2 mb-4">
              <ShieldCheck className="w-4 h-4 text-primary" />
              <h3 className="text-xs font-label font-bold uppercase tracking-[0.2em] text-primary">Analysis Engine</h3>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-label font-bold text-secondary uppercase tracking-wider">Provider</label>
                <select 
                  value={settings.answerModel.provider}
                  onChange={(e) => setSettings({
                    ...settings, 
                    answerModel: { ...settings.answerModel, provider: e.target.value }
                  })}
                  className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-4 py-2.5 text-sm focus:ring-1 focus:ring-primary outline-none transition-all"
                >
                  {providers.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-label font-bold text-secondary uppercase tracking-wider">Model Name</label>
                <input 
                  type="text"
                  value={settings.answerModel.modelName}
                  onChange={(e) => setSettings({
                    ...settings, 
                    answerModel: { ...settings.answerModel, modelName: e.target.value }
                  })}
                  placeholder="e.g. gpt-4o"
                  className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-4 py-2.5 text-sm focus:ring-1 focus:ring-primary outline-none transition-all"
                />
              </div>

              <div className="space-y-2 md:col-span-2">
                <label className="text-xs font-label font-bold text-secondary uppercase tracking-wider">API Key</label>
                <div className="relative">
                  <input 
                    type={showAnswerApiKey ? "text" : "password"}
                    value={settings.answerModel.apiKey}
                    onChange={(e) => setSettings({
                      ...settings, 
                      answerModel: { ...settings.answerModel, apiKey: e.target.value }
                    })}
                    placeholder="sk-..."
                    className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-4 py-2.5 text-sm focus:ring-1 focus:ring-primary outline-none transition-all pr-12"
                  />
                  <button 
                    onClick={() => setShowAnswerApiKey(!showAnswerApiKey)}
                    className="absolute right-3 top-2.5 text-outline-variant hover:text-primary transition-colors"
                  >
                    {showAnswerApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2 md:col-span-2">
                <label className="text-xs font-label font-bold text-secondary uppercase tracking-wider">API Base URL</label>
                <input 
                  type="text"
                  value={settings.answerModel.apiBase}
                  onChange={(e) => setSettings({
                    ...settings, 
                    answerModel: { ...settings.answerModel, apiBase: e.target.value }
                  })}
                  placeholder="https://api.openai.com/v1"
                  className="w-full bg-surface-container-low border border-outline-variant/20 rounded-sm px-4 py-2.5 text-sm focus:ring-1 focus:ring-primary outline-none transition-all"
                />
              </div>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="px-8 py-6 border-t border-outline-variant/10 bg-surface-container-low flex justify-end gap-4">
          <button 
            onClick={onClose}
            className="px-6 py-2 rounded-sm font-label text-xs font-bold uppercase tracking-widest text-secondary hover:text-on-background transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={onClose}
            className="bg-primary text-on-primary px-8 py-2 rounded-sm font-label text-xs font-bold uppercase tracking-widest hover:bg-primary-dim transition-all shadow-md"
          >
            Save Changes
          </button>
        </div>
      </motion.div>
    </div>
  );
}
