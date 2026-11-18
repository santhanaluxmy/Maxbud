import { createContext, useContext } from "react";

export const SubscriptionContext = createContext(null);
export function useSubscription() {
  const context = useContext(SubscriptionContext);
  if (!context) throw new Error("SubscriptionProvider is required");
  return context;
}

export const planLabels = { trial: "Free Trial", premium_individual: "Premium Individual", family_pack: "Family Pack", free: "Legacy Free", premium: "Legacy Premium", read_only: "Read-only history" };
