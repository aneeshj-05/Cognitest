import path from "path";
import { env } from "./env.js";

const root = process.cwd();

export const paths = {
  collections: path.join(root, env.STORAGE_DIR, "collections"),
  reports: path.join(root, env.STORAGE_DIR, "reports"),
  summaries: path.join(root, env.STORAGE_DIR, "summaries")
};