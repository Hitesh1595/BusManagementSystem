import { Link } from "react-router-dom";
import {
  Bus,
  Check,
  Globe,
  IndianRupee,
  ListChecks,
  Mail,
  MapPin,
  ShieldCheck,
  Smartphone,
  SquareArrowOutUpRight,
  Users,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import { homeForRole } from "@/components/layout/navConfig";

const WA = "https://wa.me/91XXXXXXXXXX?text=Hi%2C%20I'm%20interested%20in%20YatraTrack%20for%20my%20school";
const WA_PRICING = "https://wa.me/91XXXXXXXXXX?text=Hi%2C%20I'd%20like%20pricing%20for%20YatraTrack";

function WaIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M.057 24l1.687-6.163a11.867 11.867 0 01-1.587-5.946C.16 5.335 5.495 0 12.05 0a11.82 11.82 0 018.413 3.488 11.82 11.82 0 013.48 8.414c-.003 6.557-5.338 11.892-11.893 11.892a11.9 11.9 0 01-5.688-1.448L.057 24zm6.597-3.807c1.676.995 3.276 1.591 5.392 1.592 5.448 0 9.886-4.434 9.889-9.885.002-5.462-4.415-9.89-9.881-9.892-5.452 0-9.887 4.434-9.889 9.884a9.86 9.86 0 001.516 5.26l-.999 3.648 3.972-.607zm11.387-5.464c-.074-.124-.272-.198-.57-.347-.297-.149-1.758-.868-2.031-.967-.272-.099-.47-.149-.669.149-.198.297-.768.967-.941 1.165-.173.198-.347.223-.644.074-.297-.149-1.255-.462-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.521.151-.172.2-.296.3-.495.099-.198.05-.372-.025-.521-.075-.148-.669-1.611-.916-2.206-.242-.579-.487-.501-.669-.51l-.57-.01c-.198 0-.52.074-.792.372s-1.04 1.016-1.04 2.479 1.065 2.876 1.213 3.074c.149.198 2.095 3.2 5.076 4.487.71.306 1.263.489 1.694.626.712.226 1.36.194 1.872.118.571-.085 1.758-.719 2.006-1.413.248-.695.248-1.29.173-1.414z" />
    </svg>
  );
}

const FEATURES = [
  { icon: MapPin, title: "Live GPS tracking", body: "Bus ki real-time location map par dekho — ETA ke saath. Parents ko har second pata rahega bus kahan hai." },
  { icon: ListChecks, title: "Attendance", body: "Driver har stop par ek tap mein attendance mark karta hai. Boarded ya absent — record automatic save ho jaata hai." },
  { icon: ShieldCheck, title: "Child-safety alerts", body: "Agar koi bachcha board nahi hua ya drop nahi hua, school aur parents ko turant alert milta hai." },
  { icon: SquareArrowOutUpRight, title: "No app install needed", body: "App store ke chakkar nahi. Bas link kholo aur track karo. Parents ka phone storage free, no updates." },
  { icon: Smartphone, title: "Works on any phone browser", body: "Android ho ya iPhone, naya ho ya purana — koi bhi browser mein chalta hai. Low data, fast loading." },
  { icon: IndianRupee, title: "Affordable for Indian schools", body: "Mehngi hardware ya costly GPS device ki zaroorat nahi. Budget-friendly pricing jo har school afford kar sake." },
];

const STEPS = [
  { n: 1, title: "School sets up routes", body: "Admin routes aur stops banata hai, drivers aur buses assign karta hai. Sab kuch ek dashboard se." },
  { n: 2, title: "Parents join with a code", body: "School ka join code share karo. Parents khud register karte hain — bachche ko link karo, ho gaya." },
  { n: 3, title: "Track the bus live", body: "Bus chalti hai, parents live location dekhte hain aur safety alerts paate hain. Tension free." },
];

const ROLES = [
  { icon: Users, title: "Parents", body: "Bus live track karo, board/drop notifications pao, aur mann ki shanti. Bachcha safe pahuncha — confirm." },
  { icon: Bus, title: "Drivers", body: "Bade buttons, simple screen. Trip start karo, attendance lo, drop karo — sab kuch ek tap mein." },
  { icon: ShieldCheck, title: "Schools", body: "Poori fleet ek dashboard se manage karo — routes, drivers, students, aur safety records." },
];

const ROUTE_PATH = "M 40 210 C 110 190, 90 120, 170 120 S 260 70, 320 50";

export function LandingPage() {
  const user = useAuthStore((s) => s.user);
  const appCta = user
    ? { label: "Open dashboard", to: homeForRole(user.role) }
    : { label: "Log in", to: "/login" };

  return (
    <div className="min-h-screen bg-white font-sans text-gray-500 antialiased">
      <LandingStyles />
      <div className="h-[3px] bg-indigo-600" />

      {/* Nav */}
      <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/85 backdrop-blur-md">
        <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <a href="#main" className="flex items-center gap-2.5">
            <span className="grid size-9 place-items-center rounded-xl bg-indigo-600 text-base font-bold text-white shadow-sm">Y</span>
            <span className="text-lg font-bold tracking-tight text-indigo-950">Yatra<span className="text-indigo-600">Track</span></span>
          </a>
          <div className="hidden items-center gap-8 md:flex">
            <a href="#features" className="text-sm font-medium text-indigo-950/70 transition hover:text-indigo-600">Features</a>
            <a href="#how" className="text-sm font-medium text-indigo-950/70 transition hover:text-indigo-600">How it works</a>
            <a href="#pricing" className="text-sm font-medium text-indigo-950/70 transition hover:text-indigo-600">Pricing</a>
            <a href="#contact" className="text-sm font-medium text-indigo-950/70 transition hover:text-indigo-600">Contact</a>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <Link to={appCta.to} className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-semibold text-indigo-950 transition hover:border-indigo-300 hover:bg-indigo-50">
              {appCta.label}
            </Link>
            <a href={WA} className="inline-flex items-center gap-2 rounded-lg bg-[#25d366] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:brightness-95">
              <WaIcon className="size-4" /> WhatsApp
            </a>
          </div>
        </nav>
      </header>

      <main id="main">
        {/* Hero */}
        <section className="lp-hero-glow relative overflow-hidden">
          <div className="mx-auto max-w-6xl px-4 pb-12 pt-14 sm:px-6 sm:pt-20 lg:pb-20">
            <div className="grid items-center gap-12 lg:grid-cols-2">
              <div className="text-center lg:text-left">
                <span className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-indigo-50 px-3.5 py-1.5 text-sm font-semibold text-indigo-700">
                  Made for Indian Schools <span aria-hidden>🇮🇳</span>
                </span>
                <h1 className="mt-6 text-4xl font-extrabold leading-[1.1] tracking-tight text-indigo-950 sm:text-5xl lg:text-6xl">
                  बच्चों का सफर,<br className="hidden sm:block" />
                  <span className="text-indigo-600">Safe &amp; Tracked.</span>
                </h1>
                <p className="mt-3 text-lg font-medium text-indigo-950/70">Children's journey, Safe &amp; Tracked.</p>
                <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-gray-500 sm:text-lg lg:mx-0">
                  Live bus location, attendance, aur child-safety alerts — sab kuch ek jagah.
                  Parents ko pata rehta hai bus kahan hai aur bachcha safely board hua ya nahi.{" "}
                  <span className="font-semibold text-indigo-950">No app install needed</span> — koi bhi phone browser mein chalta hai.
                </p>
                <div className="mt-8 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-center lg:justify-start">
                  <Link to={appCta.to} className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-3.5 text-base font-semibold text-white shadow-lg transition hover:bg-indigo-700">
                    {appCta.label} <span aria-hidden>→</span>
                  </Link>
                  <a href={WA} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#25d366] px-6 py-3.5 text-base font-semibold text-white shadow-lg transition hover:brightness-95">
                    <WaIcon className="size-5" /> WhatsApp Us
                  </a>
                </div>
                <ul className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm font-medium text-indigo-950/70 lg:justify-start">
                  {["Live GPS", "Safety alerts", "No app needed", "Any phone browser"].map((t) => (
                    <li key={t} className="inline-flex items-center gap-1.5">
                      <Check className="size-4 text-indigo-600" /> {t}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Dashboard preview mockup */}
              <div className="relative">
                <div className="mx-auto max-w-md rounded-2xl border border-gray-200 bg-white p-3 shadow-xl">
                  <div className="flex items-center justify-between px-2 py-1.5">
                    <div className="flex items-center gap-1.5" aria-hidden>
                      <span className="size-2.5 rounded-full bg-gray-200" />
                      <span className="size-2.5 rounded-full bg-gray-200" />
                      <span className="size-2.5 rounded-full bg-gray-200" />
                    </div>
                    <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">Morning route · Bus 04</span>
                  </div>
                  <div className="lp-dot-grid relative mt-2 h-64 overflow-hidden rounded-xl border border-gray-200 bg-[#fafafa]" role="img" aria-label="Live map preview: a school bus moving along its route toward the school">
                    <div className="absolute left-3 top-3 z-20 inline-flex items-center gap-1.5 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-bold text-red-600 shadow-sm ring-1 ring-red-100 backdrop-blur">
                      <span className="lp-live-dot inline-block size-2 rounded-full bg-red-600" /> LIVE
                    </div>
                    <div className="absolute right-3 top-3 z-20 rounded-full bg-indigo-600 px-2.5 py-1 text-[11px] font-semibold text-white shadow-sm">ETA next stop · 4 min</div>
                    <svg className="absolute inset-0 size-full" viewBox="0 0 360 260" fill="none" preserveAspectRatio="none" aria-hidden>
                      <path d={ROUTE_PATH} stroke="#4f46e5" strokeWidth="4" strokeLinecap="round" strokeDasharray="2 11" opacity="0.5" />
                      <circle cx="40" cy="210" r="7" fill="#ffffff" stroke="#4f46e5" strokeWidth="3" />
                      <circle cx="170" cy="120" r="7" fill="#ffffff" stroke="#4f46e5" strokeWidth="3" />
                      <rect x="312" y="42" width="16" height="16" rx="3" fill="#4f46e5" />
                    </svg>
                    <div className="lp-bus-travel absolute left-0 top-0 z-10" style={{ offsetPath: `path('${ROUTE_PATH}')`, offsetRotate: "0deg" } as React.CSSProperties}>
                      <div className="lp-bus-dot grid size-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-indigo-600 text-white shadow-lg ring-2 ring-white">
                        <Bus className="relative z-10 size-4" />
                      </div>
                    </div>
                    <span className="absolute bottom-3 left-3 z-10 rounded-md bg-white/85 px-2 py-0.5 text-[10px] font-medium text-indigo-950/70 backdrop-blur">Stop 1 · Picked up</span>
                    <span className="absolute right-3 top-12 z-10 rounded-md bg-white/85 px-2 py-0.5 text-[10px] font-medium text-indigo-950/70 backdrop-blur">🏫 School</span>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <div className="rounded-lg bg-indigo-50 p-2.5 text-center">
                      <div className="text-lg font-bold text-indigo-700">28</div>
                      <div className="text-[10px] font-medium text-indigo-950/60">Boarded</div>
                    </div>
                    <div className="rounded-lg bg-gray-50 p-2.5 text-center ring-1 ring-gray-200">
                      <div className="text-lg font-bold text-indigo-950">32 km/h</div>
                      <div className="text-[10px] font-medium text-indigo-950/60">Speed</div>
                    </div>
                    <div className="rounded-lg bg-green-50 p-2.5 text-center">
                      <div className="text-lg font-bold text-green-700">On time</div>
                      <div className="text-[10px] font-medium text-indigo-950/60">Status</div>
                    </div>
                  </div>
                </div>
                <div className="absolute -bottom-4 left-1/2 z-20 w-[88%] max-w-xs -translate-x-1/2 rounded-xl border border-gray-200 bg-white p-3 shadow-xl sm:-left-6 sm:translate-x-0">
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-green-50 text-green-600">
                      <Check className="size-5" />
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-indigo-950">Aarav boarded the bus ✅</p>
                      <p className="text-xs text-gray-500">Stop 1 · 7:42 AM · Parent notified</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features */}
        <section id="features" className="border-t border-gray-200 bg-[#fafafa] py-16 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-indigo-600">Features</p>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-indigo-950 sm:text-4xl">Sab kuch jo school ko chahiye</h2>
              <p className="mt-4 text-base text-gray-500">Ek simple platform — tracking se lekar safety tak. School, drivers aur parents, sab ek page par.</p>
            </div>
            <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ icon: Icon, title, body }) => (
                <article key={title} className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg">
                  <span className="grid size-11 place-items-center rounded-xl bg-indigo-50 text-indigo-600"><Icon className="size-6" /></span>
                  <h3 className="mt-4 text-lg font-bold text-indigo-950">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-gray-500">{body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="py-16 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-indigo-600">How it works</p>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-indigo-950 sm:text-4xl">Teen simple steps</h2>
              <p className="mt-4 text-base text-gray-500">Setup mein minutes lagte hain. Na hardware, na training — bas shuru karo.</p>
            </div>
            <ol className="mt-12 grid gap-6 md:grid-cols-3">
              {STEPS.map((s) => (
                <li key={s.n} className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                  <span className="grid size-10 place-items-center rounded-full bg-indigo-600 text-base font-bold text-white">{s.n}</span>
                  <h3 className="mt-4 text-lg font-bold text-indigo-950">{s.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-gray-500">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Built for */}
        <section className="border-t border-gray-200 bg-[#fafafa] py-16 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-semibold uppercase tracking-wider text-indigo-600">Built for everyone</p>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-indigo-950 sm:text-4xl">Har role ke liye banaya gaya</h2>
            </div>
            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {ROLES.map(({ icon: Icon, title, body }) => (
                <article key={title} className="rounded-2xl border border-gray-200 bg-white p-7 shadow-sm">
                  <span className="grid size-12 place-items-center rounded-xl bg-indigo-50 text-indigo-600"><Icon className="size-6" /></span>
                  <h3 className="mt-4 text-xl font-bold text-indigo-950">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-gray-500">{body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Pricing */}
        <section id="pricing" className="py-16 sm:py-20">
          <div className="mx-auto max-w-3xl px-4 sm:px-6">
            <div className="overflow-hidden rounded-3xl border border-indigo-100 bg-gradient-to-b from-indigo-50 to-white p-8 text-center shadow-sm sm:p-12">
              <p className="text-sm font-semibold uppercase tracking-wider text-indigo-600">Pricing</p>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-indigo-950 sm:text-4xl">Simple, school-friendly pricing</h2>
              <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-gray-500">
                Aapke school ke size ke hisaab se plan. Koi hidden charges nahi, koi mehengi device nahi. WhatsApp par baat karein — hum aapke liye sahi plan suggest karenge.
              </p>
              <div className="mt-7 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
                <a href={WA_PRICING} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#25d366] px-6 py-3.5 text-base font-semibold text-white shadow-lg transition hover:brightness-95">
                  <WaIcon className="size-5" /> WhatsApp for pricing
                </a>
                <a href="mailto:hello@yatratrack.in?subject=YatraTrack%20pricing" className="inline-flex items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white px-6 py-3.5 text-base font-semibold text-indigo-950 transition hover:border-indigo-300 hover:bg-indigo-50">
                  <Mail className="size-5" /> Email us
                </a>
              </div>
              <p className="mt-5 text-sm font-medium text-indigo-950/60">No spam · No sales pressure · No commitment</p>
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="bg-indigo-600">
          <div className="mx-auto max-w-4xl px-4 py-14 text-center sm:px-6 sm:py-16">
            <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">Apne school ki buses ko safe banaiye</h2>
            <p className="mx-auto mt-4 max-w-xl text-base text-indigo-100">Ek WhatsApp message bhejiye — hum aapke school ke liye sab set up kar denge.</p>
            <div className="mt-7 flex justify-center">
              <a href={WA} className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-7 py-3.5 text-base font-semibold text-indigo-700 shadow-lg transition hover:bg-indigo-50">
                <WaIcon className="size-5 text-[#25d366]" /> Chat on WhatsApp
              </a>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer id="contact" className="border-t border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
          <div className="grid gap-10 md:grid-cols-3">
            <div>
              <span className="flex items-center gap-2.5">
                <span className="grid size-9 place-items-center rounded-xl bg-indigo-600 text-base font-bold text-white">Y</span>
                <span className="text-lg font-bold tracking-tight text-indigo-950">Yatra<span className="text-indigo-600">Track</span></span>
              </span>
              <p className="mt-4 max-w-xs text-sm leading-relaxed text-gray-500">
                School-bus tracking, attendance aur child-safety alerts — banaya gaya Indian schools ke liye. बच्चों का सफर, Safe &amp; Tracked.
              </p>
            </div>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wider text-indigo-950">Contact</h3>
              <ul className="mt-4 space-y-3 text-sm">
                <li><a href={WA} className="inline-flex items-center gap-2 font-medium text-indigo-950 transition hover:text-[#25d366]"><WaIcon className="size-4 text-[#25d366]" /> WhatsApp: +91XXXXXXXXXX</a></li>
                <li><a href="mailto:hello@yatratrack.in" className="inline-flex items-center gap-2 font-medium text-indigo-950 transition hover:text-indigo-600"><Mail className="size-4" /> hello@yatratrack.in</a></li>
                <li><a href="https://yatratrack.in" className="inline-flex items-center gap-2 font-medium text-indigo-950 transition hover:text-indigo-600"><Globe className="size-4" /> yatratrack.in</a></li>
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wider text-indigo-950">Explore</h3>
              <ul className="mt-4 space-y-3 text-sm">
                <li><a href="#features" className="font-medium text-gray-500 transition hover:text-indigo-600">Features</a></li>
                <li><a href="#how" className="font-medium text-gray-500 transition hover:text-indigo-600">How it works</a></li>
                <li><a href="#pricing" className="font-medium text-gray-500 transition hover:text-indigo-600">Pricing</a></li>
              </ul>
            </div>
          </div>
          <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-gray-200 pt-6 text-sm text-gray-500 sm:flex-row">
            <p>© 2026 YatraTrack. All rights reserved.</p>
            <p className="inline-flex items-center gap-1.5">Made with <span className="text-red-500" aria-label="love">❤️</span> in India <span aria-hidden>🇮🇳</span></p>
          </div>
        </div>
      </footer>
    </div>
  );
}

/** Landing-only animations + decorative backgrounds (scoped, prefixed lp-). */
function LandingStyles() {
  return (
    <style>{`
      .lp-hero-glow{background:radial-gradient(60% 50% at 50% 0%,rgba(99,102,241,.10) 0%,rgba(99,102,241,.04) 38%,rgba(255,255,255,0) 72%),radial-gradient(40% 38% at 82% 22%,rgba(99,102,241,.07) 0%,rgba(255,255,255,0) 70%);}
      .lp-dot-grid{background-image:radial-gradient(rgba(79,70,229,.10) 1px,transparent 1px);background-size:22px 22px;}
      .lp-bus-dot::before{content:'';position:absolute;inset:-10px;border-radius:9999px;background:rgba(79,70,229,.35);animation:lp-pulse 1.8s ease-out infinite;}
      @keyframes lp-pulse{0%{transform:scale(.6);opacity:.8}70%{transform:scale(2.4);opacity:0}100%{transform:scale(2.4);opacity:0}}
      .lp-live-dot{animation:lp-blink 1.2s steps(2,start) infinite;}
      @keyframes lp-blink{0%,100%{opacity:1}50%{opacity:.25}}
      .lp-bus-travel{animation:lp-travel 9s ease-in-out infinite alternate;}
      @keyframes lp-travel{0%{offset-distance:6%}100%{offset-distance:92%}}
      @media (prefers-reduced-motion: reduce){.lp-bus-dot::before,.lp-live-dot,.lp-bus-travel{animation:none}}
    `}</style>
  );
}
