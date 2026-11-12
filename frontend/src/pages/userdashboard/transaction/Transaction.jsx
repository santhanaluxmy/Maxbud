
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowDownLeft,
  ArrowUpRight,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CreditCard,
  FilterX,
  Pencil,
  Plus,
  ReceiptText,
  Search,
  Trash2,
  Wallet,
  X,
} from "lucide-react";

import { api } from "../../../api/client";
import "./Transaction.css";

const PAGE_SIZE = 10;

const expenseCategories = [
  "Food",
  "Transport",
  "Rent",
  "Bills",
  "Shopping",
  "Health",
  "Education",
  "Entertainment",
  "Loan",
  "Other",
];

const incomeCategories = [
  "Salary",
  "Business",
  "Freelance",
  "Gift",
  "Other",
];

function localDate() {
  const date = new Date();
  const part = (value) => String(value).padStart(2, "0");

  return `${date.getFullYear()}-${part(
    date.getMonth() + 1
  )}-${part(date.getDate())}`;
}

function newForm(kind = "expense", accountId = "") {
  return {
    kind,
    amount: "",
    account_id: String(accountId),
    category: kind === "income" ? "Salary" : "Food",
    txn_date: localDate(),
    description: "",
  };
}

const valueOf = (value) => Number(value ?? 0) || 0;

const formatMoney = (value, unit = "LKR") =>
  `${unit} ${valueOf(value).toLocaleString("en-LK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

function formatDate(value) {
  if (!value) return "—";

  const [year, month, day] = value.split("-").map(Number);

  if (!year || !month || !day) return value;

  return new Intl.DateTimeFormat("en-LK", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(year, month - 1, day));
}

function SummaryCard({
  label,
  value,
  icon: Icon,
  tone,
  note,
}) {
  return (
    <div className={`txd-summary-card txd-${tone}`}>
      <div className="txd-summary-top">
        <span>{label}</span>

        <span className="txd-summary-icon">
          <Icon size={19} />
        </span>
      </div>

      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}

export default function Transaction() {
  const [searchParams] = useSearchParams();

  const [accounts, setAccounts] = useState([]);
  const [overview, setOverview] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hasNext, setHasNext] = useState(false);
  const [page, setPage] = useState(0);
  const [revision, setRevision] = useState(0);

  const [error, setError] = useState("");
  const [accountsError, setAccountsError] = useState("");
  const [notice, setNotice] = useState("");

  const [kind, setKind] = useState("all");
  const [accountFilter, setAccountFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [search, setSearch] = useState("");

  const [modalOpen, setModalOpen] = useState(
    () => searchParams.get("add") === "1"
  );

  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(() => newForm());
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const activeAccounts = accounts.filter(
    (account) =>
      !account.is_archived &&
      account.status !== "archived"
  );

  const unit =
    overview?.currency ||
    accounts[0]?.currency ||
    "LKR";

  const monthlyIncome = valueOf(
    overview?.monthly_income
  );

  const monthlyExpenses = valueOf(
    overview?.monthly_expenses
  );

  // Load accounts and dashboard summary.

  useEffect(() => {
    const controller = new AbortController();

    async function loadReferenceData() {
      const [accountResult, dashboardResult] =
        await Promise.allSettled([
          api("/accounts", {
            signal: controller.signal,
          }),
          api("/dashboard", {
            signal: controller.signal,
          }),
        ]);

      if (controller.signal.aborted) return;

      if (accountResult.status === "fulfilled") {
        const payload = accountResult.value;

        setAccounts(
          Array.isArray(payload)
            ? payload
            : payload?.items || []
        );

        setAccountsError("");
      } else {
        setAccountsError(
          accountResult.reason?.message ||
            "Accounts could not load."
        );
      }

      if (dashboardResult.status === "fulfilled") {
        setOverview(dashboardResult.value);
      }
    }

    loadReferenceData();

    return () => controller.abort();
  }, [revision]);

  // Load transactions with filters and pagination.

  useEffect(() => {
    const controller = new AbortController();

    async function loadTransactions() {
      if (
        startDate &&
        endDate &&
        startDate > endDate
      ) {
        setError(
          "Start date cannot be after end date."
        );

        setRows([]);
        setHasNext(false);
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");

      const params = new URLSearchParams({
        limit: String(PAGE_SIZE + 1),
        offset: String(page * PAGE_SIZE),
      });

      if (kind !== "all") {
        params.set("kind", kind);
      }

      if (accountFilter) {
        params.set("account_id", accountFilter);
      }

      if (startDate) {
        params.set("start_date", startDate);
      }

      if (endDate) {
        params.set("end_date", endDate);
      }

      try {
        const result = await api(
          `/transactions?${params.toString()}`,
          {
            signal: controller.signal,
          }
        );

        if (controller.signal.aborted) return;

        const items = Array.isArray(result)
          ? result
          : [];

        setRows(items.slice(0, PAGE_SIZE));
        setHasNext(items.length > PAGE_SIZE);
      } catch (err) {
        if (!controller.signal.aborted) {
          setRows([]);
          setHasNext(false);

          setError(
            err.message ||
              "Could not load transactions."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadTransactions();

    return () => controller.abort();
  }, [
    accountFilter,
    endDate,
    kind,
    page,
    revision,
    startDate,
  ]);

  const visibleRows = rows.filter((transaction) => {
    const account = accounts.find(
      (item) => item.id === transaction.account_id
    );

    const text = `${
      transaction.description || ""
    } ${transaction.category || ""} ${
      account?.name || ""
    }`;

    return text
      .toLowerCase()
      .includes(search.trim().toLowerCase());
  });

  function openForm(
    transaction = null,
    entryKind = "expense"
  ) {
    if (
      transaction?.transfer_id ||
      transaction?.kind?.startsWith("transfer_")
    ) {
      return;
    }

    setEditing(transaction);

    setForm(
      transaction
        ? {
            account_id: String(
              transaction.account_id
            ),
            kind: transaction.kind,
            category: transaction.category,
            amount: String(transaction.amount),
            txn_date: transaction.txn_date,
            description:
              transaction.description || "",
          }
        : newForm(
            entryKind,
            activeAccounts[0]?.id
          )
    );

    setFormError("");
    setModalOpen(true);
  }

  // Create or edit a transaction.

  async function saveTransaction(event) {
    event.preventDefault();

    const amount = form.amount.trim();

    if (
      !/^\d{1,12}(\.\d{1,2})?$/.test(amount) ||
      Number(amount) <= 0
    ) {
      setFormError(
        "Enter a valid positive amount with up to 2 decimal places."
      );
      return;
    }

    if (
      !activeAccounts.some(
        (account) =>
          String(account.id) === form.account_id
      )
    ) {
      setFormError(
        "Please select an active account."
      );
      return;
    }

    if (!form.category.trim() || !form.txn_date) {
      setFormError(
        "Category and date are required."
      );
      return;
    }

    const payload = {
      account_id: Number(form.account_id),
      kind: form.kind,
      amount,
      category: form.category.trim(),
      description: form.description.trim(),
      txn_date: form.txn_date,
    };

    setSaving(true);
    setFormError("");

    try {
      await api(
        editing
          ? `/transactions/${editing.id}`
          : "/transactions",
        {
          method: editing ? "PUT" : "POST",
          data: payload,
        }
      );

      setModalOpen(false);
      setEditing(null);
      setPage(0);

      setRevision((count) => count + 1);

      setNotice(
        editing
          ? "Transaction updated successfully."
          : "Transaction saved successfully."
      );
    } catch (err) {
      setFormError(
        err.message ||
          "Could not save transaction."
      );
    } finally {
      setSaving(false);
    }
  }

  // Delete a transaction.

  async function deleteTransaction() {
    if (!deleteTarget) return;

    setSaving(true);
    setError("");

    try {
      await api(
        `/transactions/${deleteTarget.id}`,
        {
          method: "DELETE",
        }
      );

      setDeleteTarget(null);

      if (rows.length === 1 && page > 0) {
        setPage((old) => old - 1);
      }

      setRevision((count) => count + 1);

      setNotice(
        "Transaction deleted successfully."
      );
    } catch (err) {
      setError(
        err.message ||
          "Unable to delete transaction."
      );

      setDeleteTarget(null);
    } finally {
      setSaving(false);
    }
  }

  function resetFilters() {
    setKind("all");
    setAccountFilter("");
    setStartDate("");
    setEndDate("");
    setSearch("");
    setPage(0);
  }

  function setKindFilter(value) {
    setKind(value);
    setPage(0);
  }

  const hasFilters =
    kind !== "all" ||
    accountFilter ||
    startDate ||
    endDate ||
    search;

  const noAccount =
    activeAccounts.length === 0 &&
    !accountsError;

  return (
    <section className="txd-page">
      {/* PAGE HEADER */}

      <header className="txd-header">
        <div>
          <span className="txd-eyebrow">
            MAXBUD / MONEY MANAGEMENT
          </span>

          <h1>Transactions</h1>

          <p>
            Every income and expense, organised
            in one place.
          </p>
        </div>

        {/* THE ONLY ADD TRANSACTION BUTTON */}

        <button
          type="button"
          className="txd-primary"
          onClick={() => openForm()}
        >
          <Plus size={18} />
          Add transaction
        </button>
      </header>

      {/* FINANCIAL SUMMARY */}

      <div className="txd-summary-grid">
        <SummaryCard
          label="Income this month"
          value={
            overview
              ? formatMoney(
                  monthlyIncome,
                  unit
                )
              : "—"
          }
          icon={ArrowDownLeft}
          tone="income"
          note="Recorded transactions"
        />

        <SummaryCard
          label="Expenses this month"
          value={
            overview
              ? formatMoney(
                  monthlyExpenses,
                  unit
                )
              : "—"
          }
          icon={ArrowUpRight}
          tone="expense"
          note="Recorded transactions"
        />

        <SummaryCard
          label="Net cash flow"
          value={
            overview
              ? formatMoney(
                  monthlyIncome -
                    monthlyExpenses,
                  unit
                )
              : "—"
          }
          icon={Wallet}
          tone="balance"
          note="Income minus expenses"
        />
      </div>

      {/* SUCCESS MESSAGE */}

      {notice && (
        <div
          className="txd-notice"
          role="status"
        >
          <Check size={17} />

          {notice}

          <button
            type="button"
            onClick={() => setNotice("")}
            aria-label="Dismiss message"
          >
            <X size={15} />
          </button>
        </div>
      )}

      {/* ACCOUNTS ERROR */}

      {accountsError && (
        <div
          className="txd-alert"
          role="alert"
        >
          <CircleAlert size={17} />
          {accountsError}
        </div>
      )}

      {/* ACCOUNT REQUIRED */}

      {noAccount && (
        <div className="txd-account-alert">
          <CreditCard size={20} />

          <div>
            <strong>
              Create an account first
            </strong>

            <p>
              Transactions need a Cash, Bank
              or Wallet account so MaxBud
              can track your balance.
            </p>
          </div>

          <Link to="/dashboard/accounts">
            Go to Accounts
          </Link>
        </div>
      )}

      {/* TRANSACTION HISTORY */}

      <div className="txd-panel">
        <div className="txd-panel-head">
          <div>
            <h2>Transaction history</h2>

            <p>
              Review, filter and manage
              your financial entries.
            </p>
          </div>
        </div>

        {/* NO REFRESH OR NEW TRANSACTION BUTTON */}

        {/* SEARCH AND FILTERS */}

        <div className="txd-toolbar">
          <label className="txd-search">
            <Search size={17} />

            <input
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Search this page..."
              aria-label="Search displayed transactions"
            />
          </label>

          <select
            value={accountFilter}
            aria-label="Filter by account"
            onChange={(event) => {
              setAccountFilter(
                event.target.value
              );
              setPage(0);
            }}
          >
            <option value="">
              All accounts
            </option>

            {accounts.map((account) => (
              <option
                key={account.id}
                value={account.id}
              >
                {account.name}
              </option>
            ))}
          </select>

          <label className="txd-date">
            <CalendarDays size={15} />

            <span>From</span>

            <input
              type="date"
              value={startDate}
              onChange={(event) => {
                setStartDate(
                  event.target.value
                );
                setPage(0);
              }}
            />
          </label>

          <label className="txd-date">
            <span>To</span>

            <input
              type="date"
              value={endDate}
              onChange={(event) => {
                setEndDate(
                  event.target.value
                );
                setPage(0);
              }}
            />
          </label>
        </div>

        {/* ALL / INCOME / EXPENSE FILTERS */}

        <div className="txd-filterline">
          <div
            className="txd-kind-filter"
            role="group"
            aria-label="Transaction type"
          >
            {[
              ["all", "All"],
              ["income", "Income"],
              ["expense", "Expenses"],
            ].map(([value, label]) => (
              <button
                type="button"
                key={value}
                className={
                  kind === value
                    ? "selected"
                    : ""
                }
                onClick={() =>
                  setKindFilter(value)
                }
              >
                {label}
              </button>
            ))}
          </div>

          {hasFilters && (
            <button
              type="button"
              className="txd-clear"
              onClick={resetFilters}
            >
              <FilterX size={15} />
              Clear filters
            </button>
          )}
        </div>

        {/* ERROR */}

        {error && (
          <div
            className="txd-alert"
            role="alert"
          >
            <CircleAlert size={17} />
            {error}
          </div>
        )}

        {/* TRANSACTIONS TABLE */}

        {loading ? (
          <div
            className="txd-loading"
            role="status"
          >
            Loading transactions...
          </div>
        ) : visibleRows.length ? (
          <div className="txd-table-wrap">
            <table className="txd-table">
              <thead>
                <tr>
                  <th>Transaction</th>
                  <th>Category</th>
                  <th>Account</th>
                  <th>Date</th>
                  <th>Amount</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {visibleRows.map(
                  (transaction) => {
                    const account =
                      accounts.find(
                        (item) =>
                          item.id ===
                          transaction.account_id
                      );

                    const isIncome =
                      transaction.kind ===
                        "income" ||
                      transaction.kind ===
                        "transfer_in";

                    const isTransfer =
                      Boolean(
                        transaction.transfer_id
                      ) ||
                      transaction.kind?.startsWith(
                        "transfer_"
                      );

                    return (
                      <tr
                        key={transaction.id}
                      >
                        <td>
                          <span className="txd-identity">
                            <span
                              className={`txd-row-icon ${
                                isIncome
                                  ? "income"
                                  : "expense"
                              }`}
                            >
                              {isIncome ? (
                                <ArrowDownLeft
                                  size={18}
                                />
                              ) : (
                                <ArrowUpRight
                                  size={18}
                                />
                              )}
                            </span>

                            <span>
                              <strong>
                                {transaction.description ||
                                  (isTransfer
                                    ? "Account transfer"
                                    : isIncome
                                    ? "Income"
                                    : "Expense")}
                              </strong>

                              <small>
                                {isTransfer
                                  ? "Transfer entry"
                                  : isIncome
                                  ? "Money in"
                                  : "Money out"}
                              </small>
                            </span>
                          </span>
                        </td>

                        <td>
                          <span className="txd-category">
                            {transaction.category}
                          </span>
                        </td>

                        <td>
                          {account?.name ||
                            `Account #${transaction.account_id}`}
                        </td>

                        <td>
                          {formatDate(
                            transaction.txn_date
                          )}
                        </td>

                        <td
                          className={`txd-amount ${
                            isIncome
                              ? "income"
                              : "expense"
                          }`}
                        >
                          {isIncome
                            ? "+"
                            : "−"}

                          {formatMoney(
                            transaction.amount,
                            unit
                          )}
                        </td>

                        <td>
                          <div className="txd-row-actions">
                            {!isTransfer ? (
                              <>
                                <button
                                  type="button"
                                  title="Edit"
                                  aria-label={`Edit transaction ${transaction.id}`}
                                  onClick={() =>
                                    openForm(
                                      transaction
                                    )
                                  }
                                >
                                  <Pencil
                                    size={16}
                                  />
                                </button>

                                <button
                                  type="button"
                                  title="Delete"
                                  aria-label={`Delete transaction ${transaction.id}`}
                                  onClick={() =>
                                    setDeleteTarget(
                                      transaction
                                    )
                                  }
                                >
                                  <Trash2
                                    size={16}
                                  />
                                </button>
                              </>
                            ) : (
                              <small>
                                Linked
                              </small>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  }
                )}
              </tbody>
            </table>
          </div>
        ) : (
          /* EMPTY STATE */

          <div className="txd-empty">
            <span className="txd-empty-icon">
              <ReceiptText size={27} />
            </span>

            <h3>
              {hasFilters
                ? "No matching transactions"
                : "No transactions yet"}
            </h3>

            <p>
              {hasFilters
                ? "Try different filters or check another page."
                : "Add your first income or expense to start tracking your money."}
            </p>

            {noAccount && (
              <Link
                className="txd-primary"
                to="/dashboard/accounts"
              >
                Create an account
              </Link>
            )}
          </div>
        )}

        {/* PAGINATION */}

        <div className="txd-pagination">
          <span>
            {loading
              ? "Loading..."
              : `Page ${page + 1} · ${rows.length} loaded`}
          </span>

          <div>
            <button
              type="button"
              disabled={
                page === 0 || loading
              }
              onClick={() =>
                setPage((old) => old - 1)
              }
            >
              <ChevronLeft size={16} />
              Previous
            </button>

            <button
              type="button"
              disabled={
                !hasNext || loading
              }
              onClick={() =>
                setPage((old) => old + 1)
              }
            >
              Next
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* ADD / EDIT TRANSACTION MODAL */}

      {modalOpen && (
        <div
          className="txd-overlay"
          onMouseDown={(event) => {
            if (
              event.target ===
                event.currentTarget &&
              !saving
            ) {
              setModalOpen(false);
            }
          }}
        >
          <section
            className="txd-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="txd-form-title"
          >
            <div className="txd-modal-head">
              <div>
                <span className="txd-eyebrow">
                  MONEY ENTRY
                </span>

                <h2 id="txd-form-title">
                  {editing
                    ? "Edit transaction"
                    : "Add a transaction"}
                </h2>
              </div>

              <button
                type="button"
                aria-label="Close dialog"
                onClick={() =>
                  setModalOpen(false)
                }
                disabled={saving}
              >
                <X size={21} />
              </button>
            </div>

            <form
              onSubmit={saveTransaction}
            >
              {/* INCOME / EXPENSE */}

              <div
                className="txd-kind-picker"
                role="group"
                aria-label="Transaction type"
              >
                {[
                  "expense",
                  "income",
                ].map((option) => (
                  <button
                    type="button"
                    key={option}
                    className={
                      form.kind === option
                        ? "selected"
                        : ""
                    }
                    onClick={() =>
                      setForm((old) => ({
                        ...old,
                        kind: option,
                        category:
                          option === "income"
                            ? "Salary"
                            : "Food",
                      }))
                    }
                  >
                    {option ===
                    "income" ? (
                      <ArrowDownLeft
                        size={18}
                      />
                    ) : (
                      <ArrowUpRight
                        size={18}
                      />
                    )}

                    {option ===
                    "income"
                      ? "Income"
                      : "Expense"}
                  </button>
                ))}
              </div>

              {/* AMOUNT */}

              <label className="txd-form-field">
                <span>
                  Amount ({unit}) *
                </span>

                <input
                  autoFocus
                  required
                  inputMode="decimal"
                  placeholder="e.g. 2500.00"
                  value={form.amount}
                  onChange={(event) =>
                    setForm((old) => ({
                      ...old,
                      amount:
                        event.target.value,
                    }))
                  }
                />
              </label>

              <div className="txd-form-grid">
                {/* ACCOUNT */}

                <label className="txd-form-field">
                  <span>
                    Account *
                  </span>

                  <select
                    required
                    value={
                      form.account_id
                    }
                    onChange={(event) =>
                      setForm((old) => ({
                        ...old,
                        account_id:
                          event.target.value,
                      }))
                    }
                  >
                    <option value="">
                      Select account
                    </option>

                    {activeAccounts.map(
                      (account) => (
                        <option
                          key={
                            account.id
                          }
                          value={
                            account.id
                          }
                        >
                          {account.name}
                          {" ("}
                          {formatMoney(
                            account.current_balance,
                            account.currency ||
                              unit
                          )}
                          {")"}
                        </option>
                      )
                    )}
                  </select>
                </label>

                {/* DATE */}

                <label className="txd-form-field">
                  <span>Date *</span>

                  <input
                    required
                    type="date"
                    value={
                      form.txn_date
                    }
                    onChange={(event) =>
                      setForm((old) => ({
                        ...old,
                        txn_date:
                          event.target.value,
                      }))
                    }
                  />
                </label>
              </div>

              {/* CATEGORY */}

              <label className="txd-form-field">
                <span>
                  Category *
                </span>

                <input
                  required
                  maxLength={60}
                  list="txd-categories"
                  value={
                    form.category
                  }
                  onChange={(event) =>
                    setForm((old) => ({
                      ...old,
                      category:
                        event.target.value,
                    }))
                  }
                />

                <datalist id="txd-categories">
                  {(
                    form.kind ===
                    "income"
                      ? incomeCategories
                      : expenseCategories
                  ).map((category) => (
                    <option
                      key={
                        category
                      }
                      value={
                        category
                      }
                    />
                  ))}
                </datalist>
              </label>

              {/* OPTIONAL NOTE */}

              <label className="txd-form-field">
                <span>
                  Note (optional)
                </span>

                <input
                  maxLength={255}
                  placeholder="What was this for?"
                  value={
                    form.description
                  }
                  onChange={(event) =>
                    setForm((old) => ({
                      ...old,
                      description:
                        event.target.value,
                    }))
                  }
                />
              </label>

              {/* NO ACCOUNT MESSAGE */}

              {noAccount && (
                <p className="txd-form-hint">
                  You need an active account
                  before saving.{" "}

                  <Link to="/dashboard/accounts">
                    Create one here.
                  </Link>
                </p>
              )}

              {/* FORM ERROR */}

              {formError && (
                <p
                  role="alert"
                  className="txd-form-error"
                >
                  {formError}
                </p>
              )}

              {/* MODAL ACTIONS */}

              <div className="txd-modal-actions">
                <button
                  type="button"
                  onClick={() =>
                    setModalOpen(false)
                  }
                  disabled={saving}
                >
                  Cancel
                </button>

                <button
                  className="txd-primary"
                  type="submit"
                  disabled={
                    saving ||
                    activeAccounts.length === 0
                  }
                >
                  <Check size={17} />

                  {saving
                    ? "Saving..."
                    : editing
                    ? "Save changes"
                    : "Save transaction"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}

      {/* DELETE CONFIRMATION */}

      {deleteTarget && (
        <div className="txd-overlay">
          <section
            className="txd-confirm"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="txd-delete-title"
          >
            <span className="txd-delete-icon">
              <Trash2 size={25} />
            </span>

            <h2 id="txd-delete-title">
              Delete this transaction?
            </h2>

            <p>
              This removes the entry
              from your history and
              updates the tracked
              account balance.
            </p>

            <div className="txd-modal-actions">
              <button
                type="button"
                onClick={() =>
                  setDeleteTarget(null)
                }
                disabled={saving}
              >
                Cancel
              </button>

              <button
                className="txd-danger"
                type="button"
                disabled={saving}
                onClick={
                  deleteTransaction
                }
              >
                {saving
                  ? "Deleting..."
                  : "Delete transaction"}
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
