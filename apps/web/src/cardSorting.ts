import { PressureTest, TestRevision } from './types';

export type CardSortKey = 'log_no' | 'date' | 'operator' | 'pressure' | 'bundle' | 'pipe';
export type SortDirection = 'asc' | 'desc';

function primaryRevision(test: PressureTest): TestRevision | undefined {
  return test.revisions.find((revision) => revision.is_primary) || test.revisions[0];
}

function firstNaturalValue(values: string[] | undefined): string | null {
  if (!values?.length) return null;
  return values.slice().sort((left, right) => left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' }))[0];
}

function pressureBar(value: string | undefined): number | null {
  if (!value) return null;
  const match = value.replace(',', '.').match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function sortValue(test: PressureTest, key: CardSortKey): string | number | null {
  const revision = primaryRevision(test);
  const metadata = revision?.metadata_json || {};
  switch (key) {
    case 'log_no': return test.log_no || null;
    case 'date': {
      const timestamp = Date.parse(revision?.created_at || test.created_at);
      return Number.isNaN(timestamp) ? null : timestamp;
    }
    case 'operator': return revision?.operator || null;
    case 'pressure': return pressureBar(metadata.test_pressure);
    case 'bundle': return firstNaturalValue(metadata.bundle_numbers);
    case 'pipe': return firstNaturalValue(metadata.pipe_numbers);
  }
}

function compareValues(left: string | number | null, right: string | number | null, direction: SortDirection): number {
  if (left === null && right === null) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  const multiplier = direction === 'asc' ? 1 : -1;
  if (typeof left === 'number' && typeof right === 'number') return multiplier * (left - right);
  return multiplier * String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: 'base' });
}

export function sortCards(tests: PressureTest[], key: CardSortKey, direction: SortDirection): PressureTest[] {
  return tests
    .map((test, originalIndex) => ({ test, originalIndex }))
    .sort((left, right) => {
      const compared = compareValues(sortValue(left.test, key), sortValue(right.test, key), direction);
      return compared || left.originalIndex - right.originalIndex;
    })
    .map(({ test }) => test);
}
