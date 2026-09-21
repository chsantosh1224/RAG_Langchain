import { useEffect, useRef, useState } from "react";
import { ask } from "../api";
import Message from "./Message";
import Composer from "./Composer";

export default function Chat({ onSessionExpired }) {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = async (question) => {
    setError("");
    setMessages((m) => [...m, { role: "user", text: question }]);
    setBusy(true);
    try {
      const data = await ask(question, conversationId);
      setConversationId(data.conversation_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: data.answer,
          sources: data.sources,
          rewritten:
            data.standalone_question !== question ? data.standalone_question : null,
        },
      ]);
    } catch (err) {
      setError(err.message);
      if (err.message.includes("session expired")) onSessionExpired();
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="chat">
      {messages.length === 0 && (
        <p className="muted">
          Try: “How many days of parental leave do I get?”
        </p>
      )}

      {messages.map((m, i) => (
        <Message key={i} {...m} />
      ))}

      {busy && <div className="msg assistant thinking">Thinking…</div>}
      <div ref={endRef} />

      <Composer disabled={busy} onSend={send} />
      {error && <p className="error">{error}</p>}
    </section>
  );
}
