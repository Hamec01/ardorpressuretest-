const NATURAL_IDENTIFIER_OPTIONS: Intl.CollatorOptions = {
  numeric: true,
  sensitivity: 'base',
};

export function comparePipeIdentifiers(left: string, right: string): number {
  return left.trim().localeCompare(right.trim(), undefined, NATURAL_IDENTIFIER_OPTIONS);
}

export function sortPipeIdentifiers(values: readonly string[]): string[] {
  return values.map((value) => String(value).trim()).filter(Boolean).sort(comparePipeIdentifiers);
}

export function sortPipeInput(raw: string): string[] {
  return sortPipeIdentifiers(raw.split(/[\n,;]+/));
}
