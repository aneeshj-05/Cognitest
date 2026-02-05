import { runsService } from "../modules/runs/runs.service.js";

export const runsController = {
  async generate(req, res, next) {
    try {
      const result = await runsService.generate(req.body);
      res.json(result);
    } catch (err) {
      next(err);
    }
  },

  async generateFromSpec(req, res, next) {
    try {
      const result = await runsService.generateFromSpec(req.body);
      res.json(result);
    } catch (err) {
      next(err);
    }
  },

  async updateTestcases(req, res, next) {
    try {
      const result = await runsService.updateTestcases(req.body);
      res.json(result);
    } catch (err) {
      next(err);
    }
  },

  async getCollection(req, res, next) {
    try {
      const result = await runsService.getCollection(req.params.runId);
      res.json(result);
    } catch (err) {
      next(err);
    }
  },

  async execute(req, res, next) {
    try {
      const result = await runsService.execute(req.params.runId);
      res.json(result);
    } catch (err) {
      next(err);
    }
  },

  async executeBatch(req, res, next) {
    try {
      const { runId } = req.params;
      const { batchIndex = 0, batchSize = 10 } = req.body;
      const result = await runsService.executeBatch(runId, batchIndex, batchSize);
      res.json(result);
    } catch (err) {
      next(err);
    }
  },

  async getTestCount(req, res, next) {
    try {
      const result = await runsService.getTestCount(req.params.runId);
      res.json(result);
    } catch (err) {
      next(err);
    }
  }
};