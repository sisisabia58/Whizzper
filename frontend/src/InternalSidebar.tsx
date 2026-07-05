import React from 'react';
import {
  AudioLines,
  LayoutDashboard,
  FileAudio,
  Clock,
  ServerCog } from
'lucide-react';
const nav = [
{
  label: 'Overview',
  icon: LayoutDashboard,
  active: true
},
{
  label: 'Transcripts',
  icon: FileAudio,
  active: false
},
{
  label: 'History',
  icon: Clock,
  active: false
}];

export function InternalSidebar() {
  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-zinc-200 bg-paper h-screen sticky top-0 px-4 py-6">
      <div className="flex items-center gap-2 px-2 mb-2">
        <AudioLines className="w-7 h-7 text-ink" strokeWidth={2.2} />
        <span className="text-xl font-display font-extrabold text-ink tracking-tight">
          Whizzper
        </span>
      </div>
      <span className="ml-9 mb-8 inline-flex w-fit items-center gap-1.5 px-2 py-0.5 rounded-full border border-zinc-300 bg-paper-off text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
        <ServerCog className="w-3 h-3" />
        Internal
      </span>

      <nav className="flex flex-col gap-1" aria-label="Internal tools">
        {nav.map((item) =>
        <button
          key={item.label}
          aria-current={item.active ? 'page' : undefined}
          className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${item.active ? 'bg-ink text-paper' : 'text-zinc-600 hover:bg-paper-off hover:text-ink'}`}>
          
            <item.icon className="w-4.5 h-4.5" strokeWidth={2} />
            {item.label}
          </button>
        )}
      </nav>

      <div className="mt-auto pt-6 border-t border-zinc-200">
        <p className="px-2 text-xs text-zinc-400 leading-relaxed">
          Internal transcription console. Unlimited usage — no account or
          billing required.
        </p>
      </div>
    </aside>);

}
