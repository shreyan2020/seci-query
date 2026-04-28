import { classNames } from '@/features/biotech-workspace/lib/utils';

interface ModeBackdropProps {
  modeKey: string;
}

const MODE_BACKDROPS: Record<
  string,
  {
    base: string;
    leftPanel: string;
    rightPanel: string;
    divider: string;
    glow: string;
  }
> = {
  general: {
    base: 'bg-[radial-gradient(circle_at_10%_8%,rgba(16,185,129,0.26),transparent_28%),radial-gradient(circle_at_86%_14%,rgba(59,130,246,0.22),transparent_30%),linear-gradient(180deg,#effaf4_0%,#e8f3f6_44%,#f8fafc_100%)]',
    leftPanel: 'border-emerald-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.76),rgba(236,253,245,0.56))]',
    rightPanel: 'border-sky-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.78),rgba(239,246,255,0.56))]',
    divider: 'bg-slate-200/80',
    glow: 'bg-emerald-300/20',
  },
  evidence: {
    base: 'bg-[radial-gradient(circle_at_12%_10%,rgba(59,130,246,0.36),transparent_28%),radial-gradient(circle_at_84%_14%,rgba(45,212,191,0.3),transparent_30%),linear-gradient(180deg,#dfefff_0%,#ecfbff_44%,#f8fbff_100%)]',
    leftPanel: 'border-sky-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.78),rgba(239,246,255,0.6))]',
    rightPanel: 'border-cyan-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(236,254,255,0.58))]',
    divider: 'bg-sky-200/90',
    glow: 'bg-sky-300/20',
  },
  data: {
    base: 'bg-[radial-gradient(circle_at_10%_10%,rgba(14,165,233,0.34),transparent_28%),radial-gradient(circle_at_84%_12%,rgba(99,102,241,0.32),transparent_30%),repeating-linear-gradient(90deg,rgba(15,23,42,0.05)_0px,rgba(15,23,42,0.05)_1px,transparent_1px,transparent_28px),linear-gradient(180deg,#e0ecff_0%,#edf1ff_46%,#fbfcff_100%)]',
    leftPanel: 'border-sky-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(239,246,255,0.58))]',
    rightPanel: 'border-indigo-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(238,242,255,0.6))]',
    divider: 'bg-indigo-200/90',
    glow: 'bg-indigo-300/20',
  },
  experiment: {
    base: 'bg-[radial-gradient(circle_at_10%_10%,rgba(16,185,129,0.34),transparent_30%),radial-gradient(circle_at_84%_12%,rgba(251,191,36,0.3),transparent_30%),linear-gradient(180deg,#e5f9ee_0%,#f3f8df_48%,#fffdf2_100%)]',
    leftPanel: 'border-emerald-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(236,253,245,0.6))]',
    rightPanel: 'border-amber-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(255,251,235,0.62))]',
    divider: 'bg-emerald-200/90',
    glow: 'bg-emerald-300/20',
  },
  process: {
    base: 'bg-[radial-gradient(circle_at_10%_10%,rgba(6,182,212,0.32),transparent_30%),radial-gradient(circle_at_84%_12%,rgba(14,165,233,0.28),transparent_30%),linear-gradient(180deg,#e1f9fc_0%,#e7f4fb_48%,#f8fcff_100%)]',
    leftPanel: 'border-cyan-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(236,254,255,0.58))]',
    rightPanel: 'border-sky-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(239,246,255,0.56))]',
    divider: 'bg-cyan-200/90',
    glow: 'bg-cyan-300/20',
  },
  economics: {
    base: 'bg-[radial-gradient(circle_at_10%_10%,rgba(148,163,184,0.34),transparent_30%),radial-gradient(circle_at_84%_12%,rgba(245,158,11,0.28),transparent_30%),linear-gradient(180deg,#f0f2ee_0%,#f5ead6_46%,#fffaf0_100%)]',
    leftPanel: 'border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(248,250,252,0.58))]',
    rightPanel: 'border-amber-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(255,251,235,0.6))]',
    divider: 'bg-amber-200/90',
    glow: 'bg-amber-300/20',
  },
  sourcing: {
    base: 'bg-[radial-gradient(circle_at_10%_10%,rgba(245,158,11,0.32),transparent_30%),radial-gradient(circle_at_84%_12%,rgba(132,204,22,0.28),transparent_30%),linear-gradient(180deg,#fff1dd_0%,#f3f5da_48%,#fffff4_100%)]',
    leftPanel: 'border-amber-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(255,251,235,0.6))]',
    rightPanel: 'border-lime-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(247,254,231,0.58))]',
    divider: 'bg-lime-200/90',
    glow: 'bg-lime-300/20',
  },
  recovery: {
    base: 'bg-[radial-gradient(circle_at_10%_10%,rgba(217,70,239,0.3),transparent_30%),radial-gradient(circle_at_84%_12%,rgba(14,165,233,0.26),transparent_30%),linear-gradient(180deg,#faeaff_0%,#f0eeff_48%,#fafcff_100%)]',
    leftPanel: 'border-fuchsia-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(250,245,255,0.6))]',
    rightPanel: 'border-sky-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.8),rgba(239,246,255,0.58))]',
    divider: 'bg-fuchsia-200/90',
    glow: 'bg-fuchsia-300/20',
  },
};

export function ModeBackdrop({ modeKey }: ModeBackdropProps) {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {Object.entries(MODE_BACKDROPS).map(([key, palette]) => (
        <div
          key={key}
          className={classNames(
            'absolute inset-0 transition-[opacity,transform,filter] duration-[1100ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none',
            key === modeKey ? 'opacity-100 blur-0 scale-100' : 'opacity-0 blur-sm scale-[1.03]'
          )}
        >
          <div className={classNames('absolute inset-0', palette.base)} />
          <div
            className={classNames(
              'absolute left-[-8vw] top-[9vh] hidden h-[54vh] w-[44vw] rounded-[3rem] border shadow-[0_40px_120px_-80px_rgba(15,23,42,0.45)] md:block',
              palette.leftPanel
            )}
          />
          <div
            className={classNames(
              'absolute right-[-5vw] top-[15vh] hidden h-[56vh] w-[40vw] rounded-[3rem] border shadow-[0_40px_120px_-80px_rgba(15,23,42,0.45)] md:block',
              palette.rightPanel
            )}
          />
          <div className={classNames('absolute left-1/2 top-[7vh] hidden h-[70vh] w-px -translate-x-1/2 md:block', palette.divider)} />
          <div className={classNames('absolute inset-x-[14vw] bottom-[-18vh] h-[34vh] rounded-full blur-3xl', palette.glow)} />
        </div>
      ))}
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.04),rgba(248,250,252,0.22)_38%,rgba(248,250,252,0.48)_100%)]" />
    </div>
  );
}
