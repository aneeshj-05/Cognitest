import fs from "fs/promises";

export async function writeJson(path, data) {
  await fs.writeFile(path, JSON.stringify(data, null, 2));
}

export async function readJson(path) {
  const raw = await fs.readFile(path, "utf-8");
  return JSON.parse(raw);
}