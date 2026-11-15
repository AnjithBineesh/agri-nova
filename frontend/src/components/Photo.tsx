"use client";

import { useState } from "react";
import { IMAGES, type ImageKey } from "@/lib/images";

/** Photo with a calm colour fallback (sky-to-field gradient) if the image cannot load. */
export function Photo({ name, className = "", priority = false, decorative = false }: {
  name: ImageKey; className?: string; priority?: boolean; decorative?: boolean;
}) {
  const img = IMAGES[name];
  const [failed, setFailed] = useState(false);
  return (
    <div className={`${/\b(absolute|fixed)\b/.test(className) ? "" : "relative"} overflow-hidden bg-gradient-to-b from-[#7fa9c9] via-[#9fbf8a] to-[#3f6b3a] ${className}`}>
      {!failed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={img.src} alt={decorative ? "" : img.alt} loading={priority ? "eager" : "lazy"}
             onError={() => setFailed(true)} className="absolute inset-0 h-full w-full object-cover" />
      )}
    </div>
  );
}
