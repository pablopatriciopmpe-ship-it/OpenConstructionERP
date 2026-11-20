// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP​‌‍⁠​‌‍⁠​‌‍⁠​‌‍⁠
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import clsx from 'clsx';
import { publicAsset } from '../lib/publicAsset';
import { BRAND } from '@/brand';

type LogoSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface LogoProps {
  size?: LogoSize;
  /** Fade the mark in once; the brand kit forbids glow, float or other effects. */
  animate?: boolean;
  /**
   * Which kit variant to show. `auto` follows the app theme; use `light` or
   * `dark` when the mark sits on a fixed background colour.
   */
  tone?: 'auto' | 'light' | 'dark';
  className?: string;
}

// Kit rule: sizes in multiples of 16 px so the 16-unit grid stays pixel-sharp.
const sizeMap: Record<LogoSize, string> = {
  xs: 'h-4 w-4',
  sm: 'h-8 w-8',
  md: 'h-8 w-8',
  lg: 'h-12 w-12',
  xl: 'h-16 w-16',
};


/** Evolux Obras mark from the single product brand file. */
export function Logo({ size = 'md', animate = false, tone: _tone = 'auto', className }: LogoProps) {
  const img = 'block h-full w-full select-none';
  return (
    <span
      className={clsx(sizeMap[size], 'relative inline-block shrink-0', animate && 'animate-fade-in', className)}
      data-testid="oe-logo-mark"
    >
      <img src={publicAsset(BRAND.symbol)} alt="" aria-hidden draggable={false} className={img} />
    </span>
  );
}

/* ── Wordmark ──────────────────────────────────────────────────────────── */

const textSizeMap: Record<LogoSize, string> = {
  xs: 'text-sm',
  sm: 'text-base',
  md: 'text-base',
  lg: 'text-xl',
  xl: 'text-2xl',
};

// Kit: Onest, fallback Inter. Onest is not bundled (no external requests), so it
// only applies where installed locally; otherwise the app's Inter stack is used.
const WORDMARK_FONT = "Onest, var(--oe-font-sans)";

/** Product wordmark, kept in sync with the brand module. */
export function Wordmark({ size = 'md', className }: { size?: LogoSize; className?: string }) {
  return (
    <span
      className={clsx(textSizeMap[size], 'whitespace-nowrap leading-none text-content-primary', className)}
      style={{ fontFamily: WORDMARK_FONT }}
    >
      <span className="font-semibold">{BRAND.name}</span>
    </span>
  );
}

interface LogoWithTextProps extends LogoProps {
  /** Kept for callers; the product name is always part of the wordmark. */
  showVersion?: boolean;
}

/**
 * Mark + wordmark lockup. The gap is a quarter of the mark width (kit clear space).
 */
export function LogoWithText({ size = 'md', animate, tone, className }: LogoWithTextProps) {
  const gap = size === 'xs' ? 'gap-1' : size === 'lg' ? 'gap-3' : size === 'xl' ? 'gap-4' : 'gap-2';
  return (
    <span
      className={clsx('inline-flex items-center', gap, className)}
      role="img"
      aria-label={BRAND.name}
    >
      <Logo size={size} animate={animate} tone={tone} />
      <Wordmark size={size} />
    </span>
  );
}

/* ── Academy mark ──────────────────────────────────────────────────────── */

/** OpenConstruction Academy mark from the unmodified brand-kit SVGs. */
export function AcademyMark({ className }: { className?: string }) {
  const img = 'block h-full w-full select-none';
  return (
    <span className={clsx('relative inline-block shrink-0', className ?? 'h-4 w-4')} data-testid="oe-academy-mark" aria-hidden>
      <img src={publicAsset('/brand/academy/academy-mark-light.svg')} alt="" draggable={false} className={clsx(img, 'dark:hidden')} />
      <img src={publicAsset('/brand/academy/academy-mark-dark.svg')} alt="" draggable={false} className={clsx(img, 'hidden dark:block')} />
    </span>
  );
}

/* ── App lockup ────────────────────────────────────────────────────────── */

const LOCKUP = {
  nav: { mark: '16px', text: '13px', gap: 'gap-1' },
  lg: { mark: '32px', text: '20px', gap: 'gap-2.5' },
} as const;

/**
 * Product lockup for app chrome, sourced from the provisional brand module.
 * Sizes are absolute so the root font scale never inflates the brand.
 */
export function BrandLockup({ size = 'nav', animate, className }: { size?: keyof typeof LOCKUP; animate?: boolean; className?: string }) {
  const s = LOCKUP[size];
  return (
    <span className={clsx('inline-flex items-center', s.gap, className)} role="img" aria-label={BRAND.name} style={{ ['--oe-lockup-mark' as string]: s.mark }}>
      <Logo animate={animate} className="!h-[var(--oe-lockup-mark)] !w-[var(--oe-lockup-mark)]" />
      <span
        aria-hidden
        className="whitespace-nowrap font-medium leading-none tracking-tight text-content-primary"
        style={{ fontFamily: WORDMARK_FONT, fontSize: s.text }}
      >
        {BRAND.name}
      </span>
    </span>
  );
}
