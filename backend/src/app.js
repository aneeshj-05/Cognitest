import express from "express";
import cors from "cors";
import { runsRouter } from "./routes/runs.routes.js";
import { errorMiddleware } from "./middlewares/error.middleware.js";

export function createApp() {
  const app = express();
  app.use(cors());
  app.use(express.json({ limit: "10mb" }));

  // Health check endpoint
  app.get("/health", (req, res) => {
    res.json({ status: "ok", service: "backend" });
  });

  app.use("/api/runs", runsRouter);
  app.use(errorMiddleware);

  return app;
}