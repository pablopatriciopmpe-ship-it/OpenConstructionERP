// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
/**
 * Lean & functional product profile flags (Brazil profile).
 * User decision:
 * 1. No videos anywhere (watch video buttons, step play icons, embeds, "Learn this step", learning tips).
 * 2. No guided cases (ModuleCasesButton "Casos N", graduation cap badges, "Browse cases").
 * 3. No project journey modal & header button (11-step modal, "Etapa N" / "Project journey" button).
 * 4. Keep "Como funciona" (6-concept module guide) on each screen.
 * 5. Clean top bar (Header): hide ask AI, background processes, news, module builder, subscribe, help menu.
 */
export const SHOW_GUIDED_CASES = false;
export const SHOW_VIDEOS = false;
export const SHOW_PROJECT_JOURNEY = false;
export const SHOW_HEADER_EXTRAS = false;
