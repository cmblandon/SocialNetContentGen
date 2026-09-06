"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    if (!response.ok) {
      setError("Invalid token.");
      return;
    }
    router.push("/");
  }

  return (
    <main>
      <h1>Archivo Desclasificado — Admin Panel</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="token">Access token</label>
        <input
          id="token"
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        <button type="submit">Log in</button>
      </form>
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
