import { Router } from "express";
import { runsController } from "../controllers/runs.controller.js";

export const runsRouter = Router();

runsRouter.post("/generate", runsController.generate);
runsRouter.post("/generate-from-spec", runsController.generateFromSpec);
runsRouter.post("/update", runsController.updateTestcases);
runsRouter.get("/:runId", runsController.getCollection);
runsRouter.get("/:runId/count", runsController.getTestCount);
runsRouter.post("/:runId/execute", runsController.execute);
runsRouter.post("/:runId/execute-batch", runsController.executeBatch);