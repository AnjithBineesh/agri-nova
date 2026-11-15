export const FAMILY_COLOR: Record<string, string> = {
  Poaceae: "#c9b458",
  Fabaceae: "#4f9150",
  Brassicaceae: "#d9c23a",
  Solanaceae: "#c0574a",
  Asteraceae: "#e09a3a",
  Pedaliaceae: "#a58fc4",
  Malvaceae: "#d7cfc0",
  Amaryllidaceae: "#9c7bb0",
  fallow: "#a8906c",
};

export function RotationRibbon({ items, families }: {
  items: { crop: string; crop_name: string; span: number; season?: string }[];
  families: Record<string, string>;
}) {
  return (
    <ol className="flex w-full overflow-hidden rounded-xl border border-line" aria-label="Crop sequence">
      {items.map((it, i) => {
        const fam = it.crop === "fallow" ? "fallow" : families[it.crop];
        const color = FAMILY_COLOR[fam] ?? "#bfc8bf";
        return (
          <li key={i} className="min-w-0 border-l border-white/70 px-2.5 py-2 first:border-l-0" style={{ flex: it.span, background: color + "33" }}>
            <div className="h-1 rounded" style={{ background: color }} />
            <div className="mt-1.5 truncate text-sm font-semibold text-ink" title={it.crop_name}>{it.crop_name}</div>
            {it.season && <div className="truncate text-xs text-ink-soft">{it.season}</div>}
          </li>
        );
      })}
    </ol>
  );
}
