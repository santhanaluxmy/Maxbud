import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api/client";
import { SubscriptionContext } from "./SubscriptionContext";

export default function SubscriptionProvider({ children }) {
  const [subscription, setSubscription] = useState(null);
  const [usage, setUsage] = useState(null);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const invalidate = useCallback(() => { ++generation.current; }, []);
  const { pathname } = useLocation();
  const refresh = useCallback(async () => {
    const request = ++generation.current;
    try {
      const [state, meter] = await Promise.all([api("/subscriptions"), api("/ai/usage")]);
      if (request === generation.current) { setSubscription(state); setUsage(meter); setError(""); }
      return state;
    } catch (e) { if (request === generation.current) setError(e.message); throw e; }
  }, []);
  useEffect(() => {
    const reload = () => { if (document.visibilityState === "visible") refresh().catch(() => {}); };
    reload();
    window.addEventListener("focus", reload);
    document.addEventListener("visibilitychange", reload);
    return () => { invalidate(); window.removeEventListener("focus", reload); document.removeEventListener("visibilitychange", reload); };
  }, [pathname, refresh, invalidate]);
  const value = useMemo(() => ({ subscription, usage, error, refresh }), [subscription, usage, error, refresh]);
  return <SubscriptionContext.Provider value={value}>{children}</SubscriptionContext.Provider>;
}
