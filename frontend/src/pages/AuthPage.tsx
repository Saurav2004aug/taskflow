import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { useAuth } from "../hooks/useAuth";

type Mode = "login" | "register";

export default function AuthPage() {
  const { login, register, notice } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(notice);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setFields({});
    try {
      if (mode === "login") await login(email, password);
      else await register(name, email, password);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        setFields(err.fields);
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setFields({});
  }

  return (
    <main className="auth">
      <section className="auth-hero" aria-hidden="true">
        <div className="brand brand-lg">
          <span className="brand-mark">✓</span> TaskFlow
        </div>
        <p className="auth-tagline">Plan your work. Drag it to done.</p>
        <div className="hero-board">
          {["To do", "In progress", "Done"].map((col, i) => (
            <div className="hero-col" key={col}>
              <span>{col}</span>
              {Array.from({ length: 3 - i }).map((_, j) => (
                <div className="hero-card" key={j} style={{ width: `${90 - j * 18}%` }} />
              ))}
            </div>
          ))}
        </div>
      </section>

      <section className="auth-panel">
        <form className="auth-form" onSubmit={onSubmit} noValidate>
          <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p className="muted">
            {mode === "login" ? "Log in to see your board." : "It takes ten seconds. No credit card."}
          </p>

          {error && (
            <div className="alert" role="alert">
              {error}
            </div>
          )}

          {mode === "register" && (
            <label className="field">
              <span>Name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required />
              {fields.name && <small className="field-error">{fields.name}</small>}
            </label>
          )}
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
            {fields.email && <small className="field-error">{fields.email}</small>}
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={8}
              required
            />
            {fields.password && <small className="field-error">{fields.password}</small>}
          </label>

          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </button>

          <p className="muted center">
            {mode === "login" ? "New here? " : "Already have an account? "}
            <button type="button" className="link" onClick={() => switchMode(mode === "login" ? "register" : "login")}>
              {mode === "login" ? "Create an account" : "Log in"}
            </button>
          </p>
        </form>
      </section>
    </main>
  );
}
