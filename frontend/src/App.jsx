import { useEffect, useState } from "react";
import Login from "./components/Login";
import Chat from "./components/Chat";
import { getToken, hasSession, signOut } from "./auth";

export default function App() {
  const [signedIn, setSignedIn] = useState(false);
  const [checking, setChecking] = useState(true);

  // A stored refresh token means we can restore the session without a sign-in.
  useEffect(() => {
    if (!hasSession()) {
      setChecking(false);
      return;
    }
    getToken()
      .then((token) => setSignedIn(Boolean(token)))
      .finally(() => setChecking(false));
  }, []);

  const handleSignOut = () => {
    signOut();
    setSignedIn(false);
  };

  return (
    <main>
      <header>
        <h1>Policy Assistant</h1>
        {signedIn && (
          <button className="link" onClick={handleSignOut}>
            Sign out
          </button>
        )}
      </header>
      <p className="sub">Answers come only from the uploaded policy documents.</p>

      {checking ? (
        <p className="muted">Restoring session…</p>
      ) : signedIn ? (
        <Chat onSessionExpired={handleSignOut} />
      ) : (
        <Login onSignedIn={() => setSignedIn(true)} />
      )}
    </main>
  );
}
