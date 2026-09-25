import { PressureTest, TestRevision } from './types';

export type StatisticsPeriod = 'all' | 'year' | 'month' | 'week';

export interface BundleStatistic {
  bundle: string;
  pipeCount: number;
  maxPressure: number | null;
}

export interface DailyStatistic {
  date: string;
  pipes: number;
  logs: number;
}

export interface PressureTestStatistics {
  pipeCount: number;
  logCount: number;
  activeDayCount: number;
  averagePipesPerActiveDay: number;
  averagePressure: number | null;
  topBundleByPipes: BundleStatistic | null;
  topBundleByPressure: BundleStatistic | null;
  bundleDistribution: BundleStatistic[];
  daily: DailyStatistic[];
}

function primaryRevision(test: PressureTest): TestRevision | undefined {
  return test.revisions.find((revision) => revision.is_primary) || test.revisions[0];
}

export function parsePressureBar(value?: string): number | null {
  if (!value) return null;
  const match = value.replace(',', '.').match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function startOfPeriod(period: StatisticsPeriod, now: Date): Date | null {
  if (period === 'all') return null;
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  if (period === 'week') {
    const mondayOffset = (start.getDay() + 6) % 7;
    start.setDate(start.getDate() - mondayOffset);
  } else if (period === 'month') {
    start.setDate(1);
  } else {
    start.setMonth(0, 1);
  }
  return start;
}

function dateKey(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function testDate(test: PressureTest, revision?: TestRevision): Date | null {
  const value = revision?.created_at || test.created_at;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function bundleForPipe(pipe: string): string | null {
  const [bundle] = pipe.split('/', 1);
  const normalized = bundle?.trim();
  return normalized || null;
}

export function calculateStatistics(tests: PressureTest[], period: StatisticsPeriod, now = new Date()): PressureTestStatistics {
  const start = startOfPeriod(period, now);
  const uniquePipes = new Set<string>();
  const pressures: number[] = [];
  const bundlePipes = new Map<string, Set<string>>();
  const bundleMaxPressure = new Map<string, number>();
  const dailyPipes = new Map<string, Set<string>>();
  const dailyLogs = new Map<string, number>();
  let logCount = 0;

  for (const test of tests) {
    const revision = primaryRevision(test);
    const createdAt = testDate(test, revision);
    if (!revision || !createdAt || (start && createdAt < start) || createdAt > now) continue;

    logCount += 1;
    const day = dateKey(createdAt);
    dailyLogs.set(day, (dailyLogs.get(day) || 0) + 1);
    const dayPipes = dailyPipes.get(day) || new Set<string>();
    dailyPipes.set(day, dayPipes);

    const metadata = revision.metadata_json || {};
    const pressure = parsePressureBar(metadata.test_pressure);
    if (pressure !== null) pressures.push(pressure);

    const pipes = metadata.pipe_numbers || [];
    const explicitBundles = new Set((metadata.bundle_numbers || []).map((bundle) => String(bundle).trim()).filter(Boolean));
    for (const pipeValue of pipes) {
      const pipe = String(pipeValue).trim();
      if (!pipe) continue;
      uniquePipes.add(pipe);
      dayPipes.add(pipe);
      const pipeBundle = bundleForPipe(pipe);
      if (pipeBundle) explicitBundles.add(pipeBundle);
      if (pipeBundle) {
        const set = bundlePipes.get(pipeBundle) || new Set<string>();
        set.add(pipe);
        bundlePipes.set(pipeBundle, set);
      }
    }

    for (const bundle of explicitBundles) {
      if (!bundlePipes.has(bundle)) bundlePipes.set(bundle, new Set<string>());
      if (pressure !== null) bundleMaxPressure.set(bundle, Math.max(bundleMaxPressure.get(bundle) ?? pressure, pressure));
    }
  }

  const bundles: BundleStatistic[] = Array.from(bundlePipes, ([bundle, pipes]) => ({
    bundle,
    pipeCount: pipes.size,
    maxPressure: bundleMaxPressure.get(bundle) ?? null,
  }));

  const topBundleByPipes = bundles.reduce<BundleStatistic | null>((best, item) => !best || item.pipeCount > best.pipeCount ? item : best, null);
  const topBundleByPressure = bundles.reduce<BundleStatistic | null>((best, item) => {
    if (item.maxPressure === null) return best;
    return !best || best.maxPressure === null || item.maxPressure > best.maxPressure ? item : best;
  }, null);

  const daily = Array.from(dailyLogs, ([date, logs]) => ({ date, logs, pipes: dailyPipes.get(date)?.size || 0 }))
    .sort((left, right) => left.date.localeCompare(right.date))
    .slice(-31);
  const activeDayCount = dailyLogs.size;

  return {
    pipeCount: uniquePipes.size,
    logCount,
    activeDayCount,
    averagePipesPerActiveDay: activeDayCount ? uniquePipes.size / activeDayCount : 0,
    averagePressure: pressures.length ? pressures.reduce((sum, value) => sum + value, 0) / pressures.length : null,
    topBundleByPipes,
    topBundleByPressure,
    bundleDistribution: bundles.sort((left, right) => right.pipeCount - left.pipeCount),
    daily,
  };
}
