import Link from "next/link";

export function LogoMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="9" fill="#d4f25e" />
      <path d="M9 21c0-6.5 5-11 14-11-0.5 8-5 12.5-11.5 12.5" fill="none" stroke="#0e2a1f" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M9 23.5c2.5-3.5 5.5-6 9-7.5" fill="none" stroke="#0e2a1f" strokeWidth="2" strokeLinecap="round" />
      <circle cx="23.5" cy="8.5" r="1.8" fill="#0e2a1f" />
    </svg>
  );
}

export function Logo({ light = false, href = "/" }: { light?: boolean; href?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2.5" aria-label="Agri Nova home">
      <LogoMark />
      <span className={`text-[17px] font-extrabold tracking-tight ${light ? "text-white" : "text-forest"}`}>Agri Nova</span>
    </Link>
  );
}
