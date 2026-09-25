import React, { useMemo, useState } from 'react';
import { Activity, BarChart3, Boxes, FileText, Gauge, Trophy } from 'lucide-react';
import { PressureTest } from '../types';
import { calculateStatistics, StatisticsPeriod } from '../statistics';
import { useI18n } from '../context/LanguageContext';

interface StatisticsTabProps {
  tests: PressureTest[];
}

const DONUT_COLORS = ['#38BDF8', '#10B981', '#F59E0B', '#8B5CF6', '#F43F5E', '#64748B'];
const PERIOD_LABEL_KEYS: Record<StatisticsPeriod, 'stats_period_all' | 'stats_period_year' | 'stats_period_month' | 'stats_period_week'> = {
  all: 'stats_period_all',
  year: 'stats_period_year',
  month: 'stats_period_month',
  week: 'stats_period_week',
};
const ONE_DECIMAL_FORMATTER = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

function formatNumber(value: number): string {
  return ONE_DECIMAL_FORMATTER.format(value);
}

export const StatisticsTab: React.FC<StatisticsTabProps> = ({ tests }) => {
  const { t } = useI18n();
  const [period, setPeriod] = useState<StatisticsPeriod>('all');
  const statistics = useMemo(() => calculateStatistics(tests, period), [tests, period]);
  const donutItems = useMemo(() => {
    const leaders = statistics.bundleDistribution.slice(0, 5);
    const otherPipeCount = statistics.bundleDistribution.slice(5).reduce((sum, item) => sum + item.pipeCount, 0);
    return otherPipeCount ? [...leaders, { bundle: t('stats_other'), pipeCount: otherPipeCount, maxPressure: null }] : leaders;
  }, [statistics.bundleDistribution, t]);
  const donutTotal = donutItems.reduce((sum, item) => sum + item.pipeCount, 0);
  let donutOffset = 0;
  const donutSegments = donutItems.map((item, index) => {
    const start = donutOffset;
    donutOffset += donutTotal ? (item.pipeCount / donutTotal) * 100 : 0;
    return `${DONUT_COLORS[index % DONUT_COLORS.length]} ${start}% ${donutOffset}%`;
  });
  const maxDailyPipes = Math.max(1, ...statistics.daily.map((item) => item.pipes));

  return (
    <section className="statistics-tab">
      <div className="statistics-hero">
        <div>
          <div className="statistics-eyebrow"><BarChart3 size={16} /> ARDOR Analytics</div>
          <h1>{t('stats_title')}</h1>
          <p>{t('stats_subtitle')}</p>
        </div>
        <div className="statistics-period" role="group" aria-label={t('stats_period')}>
          {(['all', 'year', 'month', 'week'] as StatisticsPeriod[]).map((value) => (
            <button key={value} type="button" className={period === value ? 'active' : ''} onClick={() => setPeriod(value)}>{t(PERIOD_LABEL_KEYS[value])}</button>
          ))}
        </div>
      </div>

      <div className="statistics-kpis">
        <article className="statistics-kpi cyan"><span><Boxes size={20} /></span><div><small>{t('stats_tested_pipes')}</small><strong>{statistics.pipeCount}</strong><em>{t('stats_unique_pipes')}</em></div></article>
        <article className="statistics-kpi emerald"><span><FileText size={20} /></span><div><small>{t('stats_created_logs')}</small><strong>{statistics.logCount}</strong><em>{t('stats_logs')}</em></div></article>
        <article className="statistics-kpi amber"><span><Activity size={20} /></span><div><small>{t('stats_daily_average')}</small><strong>{formatNumber(statistics.averagePipesPerActiveDay)}</strong><em>{t('stats_pipes_per_active_day')}</em></div></article>
        <article className="statistics-kpi violet"><span><Gauge size={20} /></span><div><small>{t('stats_average_pressure')}</small><strong>{statistics.averagePressure === null ? '—' : formatNumber(statistics.averagePressure)}</strong><em>bar</em></div></article>
      </div>

      <div className="statistics-feature-grid">
        <article className="statistics-panel statistics-donut-panel">
          <header><div><small>{t('stats_distribution')}</small><h2>{t('stats_pipes_by_bundle')}</h2></div><Boxes size={20} /></header>
          <div className="statistics-donut-layout">
            <div className="statistics-donut" style={{ background: donutSegments.length ? `conic-gradient(${donutSegments.join(',')})` : 'var(--bg-inset-60)' }}>
              <div><strong>{statistics.pipeCount}</strong><span>{t('stats_pipes')}</span></div>
            </div>
            <div className="statistics-legend">
              {donutItems.length ? donutItems.map((item, index) => <div key={item.bundle}><span style={{ background: DONUT_COLORS[index % DONUT_COLORS.length] }} /><b>{item.bundle}</b><em>{item.pipeCount}</em></div>) : <p>{t('stats_no_data')}</p>}
            </div>
          </div>
        </article>

        <div className="statistics-leaders">
          <article className="statistics-leader"><span className="leader-icon"><Trophy size={22} /></span><div><small>{t('stats_top_bundle_pipes')}</small><strong>{statistics.topBundleByPipes?.bundle || '—'}</strong><p>{statistics.topBundleByPipes ? `${statistics.topBundleByPipes.pipeCount} ${t('stats_pipes')}` : t('stats_no_data')}</p></div></article>
          <article className="statistics-leader pressure"><span className="leader-icon"><Gauge size={22} /></span><div><small>{t('stats_top_bundle_pressure')}</small><strong>{statistics.topBundleByPressure?.bundle || '—'}</strong><p>{statistics.topBundleByPressure?.maxPressure == null ? t('stats_no_data') : `${formatNumber(statistics.topBundleByPressure.maxPressure)} bar`}</p></div></article>
        </div>
      </div>

      <article className="statistics-panel statistics-daily-panel">
        <header><div><small>{t('stats_productivity')}</small><h2>{t('stats_daily_chart')}</h2></div><div className="statistics-average-badge">Ø {formatNumber(statistics.averagePipesPerActiveDay)} / {t('stats_day')}</div></header>
        {statistics.daily.length ? (
          <div className="statistics-bars" aria-label={t('stats_daily_chart')}>
            {statistics.daily.map((item) => <div key={item.date} className="statistics-bar-column" title={`${item.date}: ${item.pipes} ${t('stats_pipes')}, ${item.logs} ${t('stats_logs')}`}><div className="statistics-bar-value">{item.pipes}</div><div className="statistics-bar-track"><span style={{ height: `${Math.max(5, (item.pipes / maxDailyPipes) * 100)}%` }} /></div><time>{item.date.slice(5)}</time></div>)}
          </div>
        ) : <div className="statistics-empty">{t('stats_no_data')}</div>}
      </article>
    </section>
  );
};
