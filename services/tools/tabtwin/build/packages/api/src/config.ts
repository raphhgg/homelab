export type AppConfig = {
  port: number;
  bind: string;
  databaseUrl: string;
  bootstrapToken: string;
  devDeviceToken: string | undefined;
  allowedHosts: string[];
};

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required env ${name}`);
  }
  return value;
}

function csv(name: string, fallback: string[]): string[] {
  const raw = process.env[name];
  if (!raw) return fallback;
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export function loadConfig(): AppConfig {
  return {
    port: Number(process.env.PORT ?? "47821"),
    bind: process.env.BIND ?? "127.0.0.1",
    databaseUrl: required("DATABASE_URL"),
    bootstrapToken: required("BOOTSTRAP_TOKEN"),
    devDeviceToken: process.env.DEV_DEVICE_TOKEN || undefined,
    allowedHosts: csv("ALLOWED_HOSTS", ["127.0.0.1", "localhost", "api"]),
  };
}
