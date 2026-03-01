export const EMAIL_COPY = {
  verify: {
    subject: "Verify your GeniML email",
    text: ({ verificationLink, tokenTtlMinutes }) =>
      `It looks like you've registered with GeniML.\n\nPlease verify your email before we can proceed.\n\nVerification link: ${verificationLink}\nThis link expires in ${tokenTtlMinutes} minutes.\n\nIf you never triggered this registration, please ignore this email.`,
    source: "no-reply@geniml.com",
  },
};
