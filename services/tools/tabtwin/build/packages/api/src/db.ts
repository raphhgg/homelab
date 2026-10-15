import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import postgres from "postgres";

export type Sql = postgres.Sql;
export type Db = postgres.Sql | postgres.TransactionSql;

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

export function toJson(value: unknown): Json {
  const raw: unknown = JSON.parse(JSON.stringify(value ?? {}));
  if (raw === null || typeof raw === "object" || typeof raw === "string" || typeof raw === "number" || typeof raw === "boolean") {
    return raw as Json;
  }
  return {};
}

const schemaPath = join(dirname(fileURLToPath(import.meta.url)), "schema.sql");
const schemaSql = readFileSync(schemaPath, "utf8");

export function createSql(databaseUrl: string): Sql {
  return postgres(databaseUrl, {
    max: 10,
    idle_timeout: 20,
    connect_timeout: 10,
    onnotice: () => undefined,
  });
}

export async function migrate(sql: Sql): Promise<void> {
  await sql.unsafe(schemaSql);
}

export async function ping(sql: Sql): Promise<boolean> {
  try {
    await sql`SELECT 1`;
    return true;
  } catch {
    return false;
  }
}
