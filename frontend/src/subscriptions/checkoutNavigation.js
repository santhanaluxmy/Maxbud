// Only the authenticated reconciliation response can choose a paid destination.
export function verifiedCheckoutDestination(result) {
  const subscription = result?.subscription;
  if (result?.activation !== "active" || subscription?.source !== "stripe_test" || subscription?.status !== "active") return null;
  if (subscription.plan === "premium_individual") return "/dashboard";
  if (subscription.plan === "family_pack") return "/dashboard/family";
  return null;
}
