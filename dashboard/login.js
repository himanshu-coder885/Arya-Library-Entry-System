const loginForm = document.getElementById("loginForm");
const loginFeedback = document.getElementById("loginFeedback");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const togglePasswordBtn = document.getElementById("togglePasswordBtn");
const forgotPasswordBtn = document.getElementById("forgotPasswordBtn");
const resetForm = document.getElementById("resetForm");
const otpCodeInput = document.getElementById("otpCode");
const newPasswordInput = document.getElementById("newPassword");
const toggleNewPasswordBtn = document.getElementById("toggleNewPasswordBtn");

function setFeedback(message, type = "") {
  loginFeedback.textContent = message;
  loginFeedback.className = `feedback ${type}`.trim();
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = usernameInput.value.trim();
  const password = passwordInput.value;

  if (!username || !password) {
    setFeedback("Enter both username and password.", "error");
    return;
  }

  setFeedback("Signing in...");

  const response = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  const data = await response.json();
  if (!response.ok || !data.ok) {
    setFeedback(data.message || "Login failed.", "error");
    return;
  }

  setFeedback("Login successful. Opening admin panel...", "ok");
  window.location.href = "/admin";
});

if (togglePasswordBtn) {
  togglePasswordBtn.addEventListener("click", () => {
    const showing = passwordInput.type === "text";
    passwordInput.type = showing ? "password" : "text";
    togglePasswordBtn.textContent = showing ? "Show" : "Hide";
    togglePasswordBtn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    passwordInput.focus();
  });
}

if (toggleNewPasswordBtn) {
  toggleNewPasswordBtn.addEventListener("click", () => {
    const showing = newPasswordInput.type === "text";
    newPasswordInput.type = showing ? "password" : "text";
    toggleNewPasswordBtn.textContent = showing ? "Show" : "Hide";
    toggleNewPasswordBtn.setAttribute("aria-label", showing ? "Show new password" : "Hide new password");
    newPasswordInput.focus();
  });
}

if (forgotPasswordBtn) {
  forgotPasswordBtn.addEventListener("click", async () => {
    setFeedback("Sending recovery request...");
    try {
      const response = await fetch("/api/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: usernameInput.value.trim(),
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        setFeedback(data.message || "Recovery email could not be sent.", "error");
        return;
      }
      if (resetForm) {
        resetForm.classList.remove("hidden");
      }
      setFeedback(data.message || "OTP sent.", "ok");
      if (otpCodeInput) {
        otpCodeInput.focus();
      }
    } catch (error) {
      setFeedback("Recovery email could not be sent. Please check email settings.", "error");
    }
  });
}

if (resetForm) {
  resetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = usernameInput.value.trim();
    const otp = otpCodeInput.value.trim();
    const newPassword = newPasswordInput.value;

    if (!username || !otp || !newPassword) {
      setFeedback("Enter username, OTP, and new password.", "error");
      return;
    }

    setFeedback("Resetting password...");
    try {
      const response = await fetch("/api/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          otp,
          new_password: newPassword,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        setFeedback(data.message || "Password reset failed.", "error");
        return;
      }

      setFeedback(data.message || "Password reset successful.", "ok");
      resetForm.classList.add("hidden");
      otpCodeInput.value = "";
      newPasswordInput.value = "";
      passwordInput.value = "";
      passwordInput.focus();
    } catch (error) {
      setFeedback("Password reset failed. Please try again.", "error");
    }
  });
}
