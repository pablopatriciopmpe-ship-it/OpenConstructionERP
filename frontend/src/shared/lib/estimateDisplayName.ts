/** Only presentation: never use this value as a mutation payload. */
export function estimateDisplayName(name: string): string {
  return name.replace(/ - Budget$/, ' - Orçamento-base');
}
