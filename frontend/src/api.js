import { getToken, signOut } from "./auth";

/** POST /chat with the current access token. Same origin, so no CORS. */
export async function ask(question, conversationId) {
  const token = await getToken();
  if (!token) throw new Error("Your session expired. Please sign in again.");

  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ question, conversation_id: conversationId }),
  });

  if (res.status === 401) {
    signOut();
    throw new Error("Your session expired. Please sign in again.");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail?.[0]?.msg || `Request failed (${res.status})`);
  }
  return res.json();
}
