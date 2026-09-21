export default function Message({ role, text, sources, rewritten }) {
  return (
    <div className={`msg ${role}`}>
      <div className="text">{text}</div>

      {rewritten && <div className="meta">searched for: {rewritten}</div>}

      {sources?.length > 0 && (
        <div className="meta">
          Sources:{" "}
          {sources.map((s, i) => (
            <span key={i} className="source">
              {s.source} p.{s.page}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
