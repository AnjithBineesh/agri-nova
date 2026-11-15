import Link from "next/link";
import { ArrowDown, ArrowUpRight, BrainCircuit, Layers, LineChart, Repeat, Sprout } from "lucide-react";
import { Accordion } from "@/components/Accordion";
import FieldMosaic from "@/components/FieldMosaic";
import { Logo } from "@/components/Logo";
import { Photo } from "@/components/Photo";
import { IMAGES } from "@/lib/images";

const STATS = [
  ["22", "crops the AI model can recommend"],
  ["2,820", "field records used for training"],
  ["99.6%", "accuracy on records it never saw"],
  ["3+", "rotation strategies compared for every farm"],
];

const FEATURES = [
  { icon: <BrainCircuit className="h-4 w-4" />, title: "AI crop prediction",
    body: "A machine-learning model trained on thousands of recorded crop, soil and climate conditions ranks the crops that best match your nitrogen, phosphorus, potassium, pH, temperature, humidity and rainfall, and shows you why." },
  { icon: <Layers className="h-4 w-4" />, title: "Soil analysis you can trust",
    body: "Type in your soil test or upload the lab report. You confirm every value we read, and each result is explained against its reference method. There's no made-up score." },
  { icon: <Sprout className="h-4 w-4" />, title: "Crops that fit your land",
    body: "Every crop is scored against your temperatures, rainfall, season length, soil pH and texture. If a crop hits a hard limit, it's marked unsuitable and we tell you why." },
  { icon: <Repeat className="h-4 w-4" />, title: "Rotation strategies, not a single crop",
    body: "Compare your current practice with soil-building, water-saving and climate-resilient rotations. You decide how much soil, water, climate, income and diversity matter." },
  { icon: <LineChart className="h-4 w-4" />, title: "Five years, simulated side by side",
    body: "See how soil carbon, nitrogen balance, water demand and climate risk could change season by season under today's climate or a warmer, drier one." },
];

const STEPS = [
  ["Pin your farm", "Drop a pin, share your location, or draw your field boundary."],
  ["Add your soil test", "Type it in or upload the report. You review every value."],
  ["Get a crop prediction", "The AI ranks crops for each of your growing seasons."],
  ["Choose your strategy", "Compare rotations, set your priorities and download a report."],
];

const MODEL_ROWS = [
  { name: "Soil nutrients", what: "Nitrogen, phosphorus and potassium from your soil test", res: "N · P · K" },
  { name: "Soil reaction", what: "How acidic or alkaline the soil is", res: "pH" },
  { name: "Temperature", what: "Average temperature during the growing season", res: "°C" },
  { name: "Humidity", what: "Average relative humidity during the season", res: "%" },
  { name: "Rainfall", what: "Average monthly rainfall during the season", res: "mm" },
  { name: "Micronutrients", what: "Advanced soil model: EC, sulphur, zinc, iron, copper, manganese, boron", res: "optional" },
];

export default function Landing() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <div className="p-2 sm:p-3">
        <header className="relative isolate overflow-hidden rounded-hero bg-forest">
          <Photo name="heroWheat" priority className="absolute inset-0 -z-10" />
          <div className="absolute inset-0 -z-10 bg-gradient-to-r from-black/55 via-black/25 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 -z-10 h-40 bg-gradient-to-t from-black/45 to-transparent" />

          <nav className="flex items-center justify-between gap-4 px-5 py-5 sm:px-8" aria-label="Main">
            <Logo light />
            <div className="hidden items-center gap-1 rounded-full bg-white/15 p-1 text-sm backdrop-blur md:flex">
              <a href="#top" className="rounded-full bg-white px-4 py-1.5 font-semibold text-forest">Home</a>
              <a href="#solutions" className="rounded-full px-4 py-1.5 text-white/90 hover:bg-white/15">Solutions</a>
              <a href="#how" className="rounded-full px-4 py-1.5 text-white/90 hover:bg-white/15">How it works</a>
              <a href="#model" className="rounded-full px-4 py-1.5 text-white/90 hover:bg-white/15">The AI model</a>
            </div>
            <div className="flex items-center gap-2">
              <Link href="/login" className="hidden rounded-full px-4 py-2 text-sm font-semibold text-white hover:bg-white/15 sm:inline-flex">Sign in</Link>
              <Link href="/register" className="btn bg-white text-forest hover:bg-lime">Get started</Link>
            </div>
          </nav>

          <section id="top" className="px-5 pb-10 pt-20 sm:px-10 sm:pt-28 lg:pb-14 lg:pt-36">
            <h1 className="max-w-3xl text-[44px] font-bold leading-[1.02] text-white sm:text-[64px] lg:text-[76px]">
              Know what to grow <span className="accent">before you sow.</span>
            </h1>
            <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-white/85">
              Agri Nova predicts the crops that suit your soil and season, then plans the rotation strategy
              that keeps your land healthy and productive for years.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/register" className="btn-lime px-6 py-3 text-[15px]">
                Analyse your farm <ArrowUpRight className="h-4 w-4" />
              </Link>
              <Link href="/login?next=/app/predict" className="btn-glass px-6 py-3 text-[15px]">Try crop prediction</Link>
            </div>
            <div className="mt-16 flex flex-wrap items-end justify-between gap-6 sm:mt-24">
              <a href="#solutions" className="inline-flex items-center gap-2 text-sm font-semibold text-white/80 hover:text-white">
                Scroll <ArrowDown className="h-4 w-4" />
              </a>
              <div className="flex items-center gap-3 rounded-full bg-white/15 py-1.5 pl-1.5 pr-4 text-sm text-white backdrop-blur">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-lime text-forest"><BrainCircuit className="h-4 w-4" /></span>
                Machine learning for every season, explained in plain words
              </div>
            </div>
          </section>
        </header>
      </div>

      {/* Key numbers */}
      <section className="mx-auto max-w-6xl px-5 py-10" aria-label="Key numbers">
        <dl className="grid grid-cols-2 gap-6 md:grid-cols-4">
          {STATS.map(([n, l]) => (
            <div key={l} className="border-l-2 border-lime pl-4">
              <dt className="sr-only">{l}</dt>
              <dd className="text-[34px] font-bold leading-none tracking-tight text-forest">{n}</dd>
              <dd className="mt-2 text-sm leading-snug text-ink-soft">{l}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* Mission statement */}
      <section className="bg-paper">
        <div className="mx-auto max-w-6xl px-5 py-20">
          <span className="tag">Our mission</span>
          <p className="mt-6 max-w-4xl text-[28px] font-semibold leading-snug text-ink sm:text-[38px]">
            Agri Nova supports farmers, researchers and agricultural organisations{" "}
            <span className="text-ink-faint">with practical tools that respect the land, protect the soil, save water and help every
            season adapt to a changing climate.</span>
          </p>
        </div>
      </section>

      {/* Solutions */}
      <section id="solutions" className="mx-auto max-w-6xl px-5 py-24">
        <span className="tag">What Agri Nova does</span>
        <div className="mt-5 grid gap-6 lg:grid-cols-2 lg:items-end">
          <h2 className="text-[36px] font-bold leading-[1.08] sm:text-[48px]">
            Smart farming decisions <span className="accent block">that start from your soil</span>
          </h2>
          <p className="max-w-md text-ink-soft lg:justify-self-end">
            Your soil test and your farm's weather say a lot about what will thrive. Agri Nova combines them
            with crop science and machine learning to answer the question every farmer faces: what should I grow next?
          </p>
        </div>
        <div className="mt-12 grid gap-8 lg:grid-cols-2">
          <Accordion items={FEATURES} initial={0} />
          <div className="relative min-h-[420px] overflow-hidden rounded-[24px]">
            <Photo name="irrigation" className="absolute inset-0" />
            <div className="absolute inset-x-4 bottom-4 rounded-2xl bg-white/90 p-4 text-sm backdrop-blur">
              <p className="font-semibold text-ink">Water planning from real rainfall</p>
              <p className="mt-1 text-ink-soft">Crop water use is calculated from your farm's weather record, so you can see how much each rotation needs from irrigation.</p>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="bg-paper">
        <div className="mx-auto max-w-6xl px-5 py-24">
          <span className="tag">How it works</span>
          <h2 className="mt-5 text-[36px] font-bold leading-tight sm:text-[44px]">Four steps from pin <span className="accent">to plan</span></h2>
          <ol className="mt-12 grid gap-4 md:grid-cols-4">
            {STEPS.map(([t, b], i) => (
              <li key={t} className="rounded-panel bg-white p-6 shadow-soft">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-lime font-bold text-forest">{i + 1}</span>
                <h3 className="mt-5 text-lg font-bold">{t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">{b}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Rotation illustration */}
      <section className="mx-auto max-w-6xl px-5 py-24">
        <div className="grid gap-10 rounded-[28px] bg-forest p-6 sm:p-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <span className="inline-flex rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white/80">Rotation, visualised</span>
            <h2 className="mt-5 text-[34px] font-bold leading-tight text-white sm:text-[42px]">
              Every season changes <span className="accent text-lime">what the soil gets back</span>
            </h2>
            <p className="mt-4 text-white/75">
              Alternating cereals with legumes and other crop families breaks pest cycles, uses water from different
              depths and returns nutrients and organic matter. Step through the seasons to see a rotation at work.
            </p>
            <Link href="/register" className="btn-lime mt-8">Plan my rotation <ArrowUpRight className="h-4 w-4" /></Link>
          </div>
          <FieldMosaic />
        </div>
      </section>

      {/* Model */}
      <section id="model" className="bg-paper">
        <div className="mx-auto max-w-6xl px-5 py-24">
          <div className="grid gap-10 lg:grid-cols-[1fr_1.2fr]">
            <div>
              <span className="tag">The AI model</span>
              <h2 className="mt-5 text-[36px] font-bold leading-tight sm:text-[44px]">Predictions you can <span className="accent">check</span></h2>
              <p className="mt-4 text-ink-soft">
                Six machine-learning algorithms were trained and compared; the most accurate one is used. Every
                prediction shows its probability, the typical conditions for that crop, and which of your values
                fall outside them. If your conditions are unlike anything the model has seen, it says so.
              </p>
              <div className="relative mt-8 h-56 overflow-hidden rounded-[24px]">
                <Photo name="soilHands" className="absolute inset-0" />
              </div>
            </div>
            <div className="overflow-hidden rounded-panel border border-line bg-white shadow-soft">
              <table className="table-base">
                <thead><tr><th className="pl-5">What the model reads</th><th>Meaning</th><th className="pr-5">Unit</th></tr></thead>
                <tbody>
                  {MODEL_ROWS.map((d) => (
                    <tr key={d.name}>
                      <td className="pl-5 font-bold text-forest">{d.name}</td>
                      <td className="text-ink-soft">{d.what}</td>
                      <td className="whitespace-nowrap pr-5 font-semibold text-orbit">{d.res}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="border-t border-line px-5 py-4 text-xs leading-relaxed text-ink-faint">
                Fill these in yourself, or let Agri Nova take them from your saved soil test and your farm&apos;s weather record.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="p-2 sm:p-3">
        <div className="relative isolate overflow-hidden rounded-hero">
          <Photo name="aerial" className="absolute inset-0 -z-10" />
          <div className="absolute inset-0 -z-10 bg-forest/70" />
          <div className="mx-auto max-w-4xl px-5 py-24 text-center">
            <h2 className="text-[36px] font-bold leading-tight text-white sm:text-[52px]">
              The model suggests. <span className="accent">You decide what grows next.</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-white/80">Free to use. Set up your first farm in about two minutes.</p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link href="/register" className="btn-lime px-6 py-3">Create a free account <ArrowUpRight className="h-4 w-4" /></Link>
              <Link href="/login" className="btn-glass px-6 py-3">Sign in</Link>
            </div>
          </div>
        </div>
      </section>

      <footer className="mx-auto max-w-6xl px-5 py-10">
        <div className="flex flex-col gap-6 border-t border-line pt-8 text-sm text-ink-soft md:flex-row md:items-start md:justify-between">
          <div className="max-w-sm">
            <Logo />
            <p className="mt-3">AI crop prediction, rotation strategy and soil health planning for farmers, researchers and organisations.</p>
          </div>
          <div className="max-w-md text-xs leading-relaxed text-ink-faint">
            <p>Decision support only. For high-impact decisions, consult your local agricultural extension officer or an agronomist.</p>
            <p className="mt-2">
              Photos via Unsplash: {Object.values(IMAGES).map((i, k) => (
                <span key={i.page}>{k ? ", " : ""}<a href={i.page} className="underline underline-offset-2" target="_blank" rel="noreferrer">{i.credit}</a></span>
              ))}.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
