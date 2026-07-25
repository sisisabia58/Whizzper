import React, { useState } from 'react';
import { ShieldAlert, ExternalLink, X } from 'lucide-react';

interface TranslateConsentModalProps {
  isOpen: boolean;
  onConfirm: (sourceLang: string, targetLang: string) => void;
  onClose: () => void;
}

const SUPPORTED_TARGET_LANGUAGES = [
  { code: 'id', name: 'Indonesian (Bahasa Indonesia)' },
  { code: 'es', name: 'Spanish (Español)' },
  { code: 'fr', name: 'French (Français)' },
  { code: 'de', name: 'German (Deutsch)' },
  { code: 'ja', name: 'Japanese (日本語)' },
  { code: 'zh-CN', name: 'Chinese Simplified (简体中文)' },
  { code: 'en', name: 'English' },
];

export const TranslateConsentModal: React.FC<TranslateConsentModalProps> = ({
  isOpen,
  onConfirm,
  onClose,
}) => {
  const [sourceLang, setSourceLang] = useState('auto');
  const [targetLang, setTargetLang] = useState('id');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-xl bg-slate-900 border border-slate-800 p-6 shadow-2xl text-slate-100 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-200"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4 text-sky-400">
          <ShieldAlert className="w-6 h-6" />
          <h3 className="text-xl font-bold">Google Translate External Proxy</h3>
        </div>

        <p className="text-sm text-slate-300 mb-4 leading-relaxed">
          You are about to view this transcript through Google Translate’s free web proxy (<code>.translate.goog</code>).
          Your transcript content will be sent to and processed by Google Translate in your browser.
        </p>

        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1">
              Target Language
            </label>
            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              {SUPPORTED_TARGET_LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-slate-200 rounded-lg"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(sourceLang, targetLang)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-sky-600 hover:bg-sky-500 rounded-lg shadow-lg shadow-sky-900/30"
          >
            <span>Proceed to Translate</span>
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
