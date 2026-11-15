import { Logo } from "./Logo";
import { Photo } from "./Photo";

export function AuthShell({ title, intro, children, aside }: {
  title: string; intro?: string; children: React.ReactNode; aside: string;
}) {
  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-[1.05fr_1fr]">
      <div className="hidden p-3 lg:block">
        <div className="relative isolate flex h-full flex-col justify-between overflow-hidden rounded-hero p-10">
          <Photo name="youngWheat" priority className="absolute inset-0 -z-10" />
          <div className="absolute inset-0 -z-10 bg-gradient-to-t from-black/60 via-black/10 to-black/30" />
          <Logo light />
          <div>
            <p className="max-w-md text-[34px] font-bold leading-tight text-white">{aside}</p>
            <p className="mt-4 text-sm text-white/75">Earth intelligence. Smarter farming. A sustainable future.</p>
          </div>
        </div>
      </div>
      <main className="flex items-center justify-center px-5 py-12">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden"><Logo /></div>
          <h1 className="page-title">{title}</h1>
          {intro && <p className="mt-2 text-ink-soft">{intro}</p>}
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}
