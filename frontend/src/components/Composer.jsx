import { useState } from "react";

export default function Composer({ disabled, onSend }) {
  const [value, setValue] = useState("");

  const submit = (e) => {
    e.preventDefault();
    const question = value.trim();
    if (!question || disabled) return;
    setValue("");
    onSend(question);
  };

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        rows={2}
        value={value}
        placeholder="Ask about leave policy…"
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) submit(e);
        }}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        Ask
      </button>
    </form>
  );
}
