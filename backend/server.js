import fs from "fs";
import { createApp } from "./src/app.js";
import { env } from "./config/env.js";
import { paths } from "./config/paths.js";

// Ensure storage directories exist
const ensureDirectories = () => {
  const dirs = [paths.collections, paths.reports, paths.summaries];
  dirs.forEach(dir => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
      console.log("Created directory:", dir);
    }
  });
};

ensureDirectories();

const app = createApp();

app.listen(env.PORT, () => {
  console.log("Backend running on port", env.PORT);
  console.log("FastAPI URL:", env.FASTAPI_URL);
});