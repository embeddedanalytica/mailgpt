const API_BASE_URL = "https://pzv9s7kmjd.execute-api.us-west-2.amazonaws.com";

export async function registerUser(email) {
  try {
    const response = await fetch(`${API_BASE_URL}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });
    return response.message || "Successfully registered!";
  } catch (error) {
    alert("Error submitting email:", error);
    console.error("Error submitting email:", error);
    return "Something went wrong. Please try again.";
  }
}