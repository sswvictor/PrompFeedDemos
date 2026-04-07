import { SegmentedControl } from '../../../../components/ui';
import { FINANCE_PERIODS } from '../financeConfig';

export default function FinancePeriodPicker({ selected, onSelect }) {
  const activeIndex = FINANCE_PERIODS.findIndex((period) => period.id === selected);

  return (
    <SegmentedControl
      options={FINANCE_PERIODS.map((period) => ({ id: period.id, label: period.label }))}
      activeIndex={activeIndex < 0 ? 0 : activeIndex}
      onChange={(index) => onSelect(FINANCE_PERIODS[index].id)}
    />
  );
}
