// Keep persisted backend step IDs compatible with existing unfinished setups.
export function visibleStep(storedStep = 1) {
  return Math.max(1, Math.min(4, storedStep <= 2 ? storedStep : storedStep - 1));
}

export function budgetComparison(accounts, budgets) {
  const cents = value => Math.round((Number(value) || 0) * 100);
  const opening = accounts.reduce((total, row) => total + cents(row.opening_balance), 0);
  const allocated = budgets.reduce((total, row) => total + cents(row.monthly_limit), 0);
  return { opening: opening / 100, allocated: allocated / 100, difference: (opening - allocated) / 100 };
}
