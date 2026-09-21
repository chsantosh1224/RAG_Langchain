/** Cognito sign-in straight from the browser.
 *
 * The app client is public (no secret), so USER_PASSWORD_AUTH is safe to call here.
 * The access token is kept in memory only; the refresh token is stored so a page
 * reload doesn't force a new sign-in.
 */
const REFRESH_KEY = "rag.refreshToken";

let config = null;
let accessToken = null;
let expiresAt = 0;

export async function loadConfig() {
  if (!config) config = await (await fetch("/ui/config")).json();
  return config;
}

async function cognito(target, body) {
  const { region } = await loadConfig();
  const res = await fetch(`https://cognito-idp.${region}.amazonaws.com/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": `AWSCognitoIdentityProviderService.${target}`,
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || `${target} failed`);
  return data;
}

function store(result) {
  accessToken = result.AccessToken;
  expiresAt = Date.now() + (result.ExpiresIn - 60) * 1000; // refresh a minute early
  if (result.RefreshToken) {
    try {
      localStorage.setItem(REFRESH_KEY, result.RefreshToken);
    } catch {
      /* private mode: stay signed in for this tab only */
    }
  }
  return accessToken;
}

export async function signIn(username, password) {
  const { clientId } = await loadConfig();
  const data = await cognito("InitiateAuth", {
    AuthFlow: "USER_PASSWORD_AUTH",
    ClientId: clientId,
    AuthParameters: { USERNAME: username, PASSWORD: password },
  });
  if (!data.AuthenticationResult) {
    throw new Error(
      data.ChallengeName === "NEW_PASSWORD_REQUIRED"
        ? "This account needs a permanent password. Set one with the AWS CLI first."
        : `Unsupported sign-in challenge: ${data.ChallengeName}`
    );
  }
  return store(data.AuthenticationResult);
}

async function refresh() {
  const refreshToken = safeGet(REFRESH_KEY);
  if (!refreshToken) return null;
  const { clientId } = await loadConfig();
  try {
    const data = await cognito("InitiateAuth", {
      AuthFlow: "REFRESH_TOKEN_AUTH",
      ClientId: clientId,
      AuthParameters: { REFRESH_TOKEN: refreshToken },
    });
    return store(data.AuthenticationResult);
  } catch {
    signOut();
    return null;
  }
}

/** Returns a valid access token, refreshing it if needed, or null when signed out. */
export async function getToken() {
  if (accessToken && Date.now() < expiresAt) return accessToken;
  return refresh();
}

export function signOut() {
  accessToken = null;
  expiresAt = 0;
  try {
    localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* ignore */
  }
}

export function hasSession() {
  return Boolean(accessToken || safeGet(REFRESH_KEY));
}

function safeGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
