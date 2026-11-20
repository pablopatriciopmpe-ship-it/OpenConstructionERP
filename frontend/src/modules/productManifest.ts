// Product allowlist for the Evolux SaaS edition.
//
// This is deliberately separate from the module manifests so pruning is
// reversible: restoring an id here restores the existing module without
// deleting or moving its source files.

/** Modules that may be loaded by this product build. */
export const PRODUCT_MODULE_IDS = new Set([
  'assemblies',
  'validation',
  'schedule',
  '5d',
  'tendering', // infrastructure: required by quote capture, not a menu item
  'reports',
  'pdf-takeoff',
  'estimate-checks',
  'gaeb-exchange',
  'ddc-ifc-converter',
  'ddc-rvt-converter',
  'quote_capture',
]);

/** Modules loaded for infrastructure but intentionally hidden from product navigation. */
export const PRODUCT_INFRA_MODULE_IDS = new Set(['tendering']);

/** The SaaS product does not mount the removed anonymous client-error sink. */
export const PRODUCT_DISABLE_ERROR_REPORTING = true;

/** Module ids exposed in the product module menu and sidebar. */
export const PRODUCT_NAV_MODULE_IDS = new Set(
  [...PRODUCT_MODULE_IDS].filter((id) => !PRODUCT_INFRA_MODULE_IDS.has(id)),
);

/** Static sidebar routes shipped by the approved SaaS feature set. */
export const PRODUCT_NAV_ROUTES = new Set([
  '/', '/projects', '/files', '/boq', '/templates', '/costs', '/catalog',
  '/assemblies', '/takeoff?tab=measurements', '/dwg-takeoff', '/bim',
  '/bim/rules', '/quantities', '/match-elements', '/schedule', '/tasks',
  '/cost-control', '/5d', '/progress', '/measurement-book', '/full-evm',
  '/cvr', '/postcalc', '/daily-diary', '/photos', '/field-reports',
  '/changeorders', '/variations', '/punchlist', '/inspections', '/rfi',
  '/meetings', '/offers', '/preliminaries', '/allowances', '/price-index',
  '/waste-factors', '/estimate-checks', '/reports', '/reporting',
  '/drawing-compare', '/markups', '/quantities', '/resources', '/labor-rates',
  '/validation', '/notifications', '/teams', '/users', '/settings', '/eac', '/price-breakdown',
]);

/** Static nav keys used by catalogue rows whose manifest id differs from its feature id. */
const PRODUCT_NAV_ALIASES: Record<string, string> = {
  cost_control: '5d',
  '5d_cost_model': '5d',
  quote_capture: 'quote_capture',
};

export function isProductModule(id: string): boolean {
  return PRODUCT_MODULE_IDS.has(id);
}

export function isProductNavModule(id: string): boolean {
  const resolved = PRODUCT_NAV_ALIASES[id] ?? id;
  return PRODUCT_NAV_MODULE_IDS.has(resolved);
}

export function isProductNavRoute(route: string): boolean {
  return PRODUCT_NAV_ROUTES.has(route);
}
