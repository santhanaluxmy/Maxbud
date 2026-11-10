import { useEffect, useRef, useState } from "react";

export default function GoogleAuthButton({ onSuccess }) {
  const buttonRef = useRef(null);
  const onSuccessRef = useRef(onSuccess);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    onSuccessRef.current = onSuccess;
  }, [onSuccess]);

  useEffect(() => {
    let cancelled = false;
    let timer;
    const startedAt = Date.now();

    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
    const backendUrl = import.meta.env.VITE_BACKEND_URL;

    if (!clientId || !backendUrl) {
      setError("Google sign-in is not configured");
      return;
    }

    function initializeGoogle() {
      if (cancelled) return;

      if (!window.google?.accounts?.id) {
        if (Date.now() - startedAt >= 15000) {
          setError("Google could not load. Please refresh and try again");
          return;
        }

        timer = window.setTimeout(initializeGoogle, 200);
        return;
      }

      window.google.accounts.id.initialize({
        client_id: clientId,

        callback: async ({ credential }) => {
          if (cancelled) return;

          if (!credential) {
            setError("Google sign-in failed. Please try again");
            return;
          }

          setBusy(true);
          setError("");

          try {
            const response = await fetch(
              `${backendUrl.replace(/\/$/, "")}/auth/google`,
              {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                },
                body: JSON.stringify({ credential }),
              }
            );

            const data = await response.json();

            if (!response.ok) {
              throw new Error(
                typeof data.detail === "string"
                  ? data.detail
                  : "Google sign-in failed"
              );
            }

            if (!cancelled) {
              onSuccessRef.current(data);
            }
          } catch (err) {
            if (!cancelled) {
              setError(err.message || "Unable to sign in");
            }
          } finally {
            if (!cancelled) setBusy(false);
          }
        },
      });

      if (buttonRef.current) {
        buttonRef.current.replaceChildren();

        window.google.accounts.id.renderButton(buttonRef.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
        });
      }
    }

    initializeGoogle();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  return (
    <div>
      <div
        ref={buttonRef}
        style={{
          pointerEvents: busy ? "none" : "auto",
          opacity: busy ? 0.6 : 1,
        }}
      />

      {busy && <p role="status">Signing in...</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}