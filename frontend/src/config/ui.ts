function parseBooleanEnv(value: string | undefined): boolean {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "yes" || normalized === "on";
}

export const UI_ANALYSIS_ONLY = parseBooleanEnv(import.meta.env.VITE_UI_ANALYSIS_ONLY as string | undefined);
