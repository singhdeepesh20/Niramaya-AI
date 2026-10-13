export function GoogleButton() {
  return (
    <div>
      <button className="google-button" type="button" disabled aria-describedby="google-note">
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5Z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.24 5.47-4.72 7.16l7.62 5.91c4.45-4.1 7.14-10.14 7.14-17.54Z"/><path fill="#FBBC05" d="M10.54 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.27-3.13.75-4.59l-7.98-6.2A23.9 23.9 0 0 0 0 24c0 3.9.94 7.6 2.56 10.78l7.98-6.19Z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.9-5.91l-7.62-5.91c-2.12 1.42-4.83 2.27-8.28 2.27-6.26 0-11.57-4.22-13.46-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48Z"/></svg>
        Continue with Google
      </button>
      <span className="integration-note" id="google-note">Google sign-in isn’t configured yet.</span>
    </div>
  );
}
