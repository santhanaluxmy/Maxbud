import { LayoutDashboard, Wallet, ArrowLeftRight, PieChart, Target, LineChart, ScanLine, Sparkles, Users, Settings, Bell } from "lucide-react";

export const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "accounts", label: "My Accounts", icon: Wallet },
  { id: "transactions", label: "Transactions", icon: ArrowLeftRight },
  { id: "budgets", label: "Budgets", icon: PieChart },
  { id: "goals", label: "Savings Goals", icon: Target },
  { id: "reminders", label: "Reminders", icon: Bell, planned: true },
  { id: "reports", label: "Reports", icon: LineChart },
  { id: "scan", label: "AI Bill Scan", icon: ScanLine, planned: true },
  { id: "advisor", label: "AI Advisor", icon: Sparkles, planned: true },
  { id: "family", label: "Family", icon: Users, premium: true },
  { id: "settings", label: "Settings", icon: Settings },
];

export const dashboardPath = (id) => id === "overview" ? "/dashboard" : `/dashboard/${({ scan: "ai-scan", advisor: "ai-advisor" })[id] || id}`;
