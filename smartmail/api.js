const API_BASE_URL =
  (typeof window !== "undefined" && window.SMARTMAIL_API_BASE) || "https://geniml.com";

async function parseJsonSafe(response) {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * Registers a waitlist email.
 * @param {string} email
 * @returns {Promise<{ok: boolean, message: string}>}
 */
export async function registerUser(email) {
  if (!isValidEmail(email)) {
    return {
      ok: false,
      message: "Invalid email address"
    };
  }

  try {
    const response = await fetch(`${API_BASE_URL}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });

    const payload = await parseJsonSafe(response);
    const apiMessage = typeof payload?.message === "string" ? payload.message.trim() : "";

    if (!response.ok) {
      return {
        ok: false,
        message: apiMessage || `HTTP_${response.status}`
      };
    }

    return {
      ok: true,
      message: apiMessage || "Waitlist submission successful"
    };
  } catch (error) {
    const detail = error?.message ?? String(error);
    console.error("Error submitting waitlist email:", detail, error);
    return {
      ok: false,
      message: "Network request failed"
    };
  }
}
