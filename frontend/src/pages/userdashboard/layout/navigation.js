import { LayoutDashboard, Wallet, ArrowLeftRight, PieChart, Target, LineChart, ScanLine, Sparkles, Users, Settings, Bell, CreditCard } from "lucide-react";

export const navigationGroups = [
  { label: "", items: [{ id: "overview", label: "Overview", icon: LayoutDashboard }] },
  { label: "Money Management", items: [
    { id: "accounts", label: "Accounts", icon: Wallet },
    { id: "transactions", label: "Transactions", icon: ArrowLeftRight },
    { id: "budgets", label: "Budgets", icon: PieChart },
    { id: "goals", label: "Savings Goals", icon: Target },
    { id: "reminders", label: "Reminders", icon: Bell },
    { id: "reports", label: "Reports", icon: LineChart },
  ] },
  { label: "Smart Tools", items: [
    { id: "scan", label: "AI Receipt Scanner", icon: ScanLine },
    { id: "advisor", label: "AI Advisor", icon: Sparkles },
  ] },
  { label: "Household", items: [{ id: "family", label: "Family Management", icon: Users }] },
  { label: "Account", items: [
    { id: "upgrade", label: "Subscription", icon: CreditCard },
    { id: "settings", label: "Settings", icon: Settings },
  ] },
];
export const navigation = navigationGroups.flatMap(group => group.items);
export const dashboardPath = (id) => id === "overview" ? "/dashboard" : `/dashboard/${({ scan: "ai-scan", advisor: "ai-advisor" })[id] || id}`;
