import { PlannedTestList } from './types';

export type PlannedTestListSortMode =
  | 'created_desc'
  | 'created_asc'
  | 'name_asc'
  | 'name_desc'
  | 'pipes_desc'
  | 'pipes_asc';

const compareNatural = (left: string, right: string) => left.localeCompare(
  right,
  undefined,
  { numeric: true, sensitivity: 'base' },
);

export const isPlannedTestListComplete = (plan: PlannedTestList): boolean => (
  plan.pipe_count > 0 && plan.completed_count >= plan.pipe_count
);

export const activePlannedTestPriority = (plan: PlannedTestList): number => (
  isPlannedTestListComplete(plan) ? 0 : plan.priority
);

export const sortPlannedTestLists = (
  plans: PlannedTestList[],
  mode: PlannedTestListSortMode,
): PlannedTestList[] => [...plans].sort((left, right) => {
  const priorityDifference = activePlannedTestPriority(right) - activePlannedTestPriority(left);
  if (priorityDifference !== 0) return priorityDifference;

  if (mode === 'created_desc') return Date.parse(right.created_at) - Date.parse(left.created_at);
  if (mode === 'created_asc') return Date.parse(left.created_at) - Date.parse(right.created_at);
  if (mode === 'name_desc') return compareNatural(right.name, left.name);
  if (mode === 'pipes_desc') return right.pipe_count - left.pipe_count || compareNatural(left.name, right.name);
  if (mode === 'pipes_asc') return left.pipe_count - right.pipe_count || compareNatural(left.name, right.name);
  return compareNatural(left.name, right.name);
});
