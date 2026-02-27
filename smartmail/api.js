const API_BASE_URL = "https://pzv9s7kmjd.execute-api.us-west-2.amazonaws.com";

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

/**
 * Registers a waitlist email.
 * @param {string} email
 * @returns {Promise<{ok: boolean, message: string}>}
 */
export async function registerUser(email) {
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
        message: apiMessage || "We could not complete your request right now. Please try again shortly."
      };
    }

    return {
      ok: true,
      message: apiMessage || "You are on the waitlist. We will reach out when your invite is ready."
    };
  } catch (error) {
    console.error("Error submitting waitlist email:", error);
    return {
      ok: false,
      message: "Network error. Please check your connection and try again."
    };
  }
}
