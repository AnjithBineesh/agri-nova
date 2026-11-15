"use client";

import { useId, useState } from "react";
import { Minus, Plus } from "lucide-react";

export interface AccordionItem {
  title: string;
  body: React.ReactNode;
  icon?: React.ReactNode;
}

export function Accordion({ items, initial = 0 }: { items: AccordionItem[]; initial?: number }) {
  const [open, setOpen] = useState<number | null>(initial);
  const base = useId();
  return (
    <div className="space-y-3">
      {items.map((it, i) => {
        const isOpen = open === i;
        return (
          <div key={it.title} className={`rounded-2xl border transition-colors ${isOpen ? "border-line bg-white shadow-soft" : "border-line/70 bg-paper"}`}>
            <button className="flex w-full items-center gap-3 px-5 py-4 text-left" aria-expanded={isOpen}
                    aria-controls={`${base}-${i}`} onClick={() => setOpen(isOpen ? null : i)}>
              {it.icon && <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white text-forest">{it.icon}</span>}
              <span className="flex-1 font-semibold">{it.title}</span>
              {isOpen ? <Minus className="h-4 w-4 text-ink-soft" /> : <Plus className="h-4 w-4 text-ink-soft" />}
            </button>
            {isOpen && <div id={`${base}-${i}`} className="px-5 pb-5 text-sm leading-relaxed text-ink-soft">{it.body}</div>}
          </div>
        );
      })}
    </div>
  );
}
