import { v4 as uuid } from "uuid";
import path from "path";
import { fastapi } from "../../clients/fastapi.client.js";
import { writeJson, readJson } from "../../utils/fileStore.js";
import { runNewman } from "./newman.service.js";
import { paths } from "../../../config/paths.js";

export const runsService = {

  async generate({ swaggerUrl }) {
    const runId = uuid();

    // 1. Parse Swagger
    const { data: parsed } = await fastapi.post("/parse-swagger", {
      swaggerUrl
    });

    // 2. Generate tests via Gemini (FastAPI)
    const { data: generated } = await fastapi.post("/generate-tests", {
      parsed
    });

    const filePath = path.join(paths.collections, `${runId}.json`);
    await writeJson(filePath, generated.collection);

    return {
      runId,
      testcases: generated.testcases,
      message: "Testcases generated and stored"
    };
  },

  async generateFromSpec({ spec }) {
    const runId = uuid();

    // 1. Parse Swagger spec directly
    const { data: parsed } = await fastapi.post("/parse-swagger-spec", {
      spec
    });

    // 2. Generate tests via Gemini (FastAPI)
    const { data: generated } = await fastapi.post("/generate-tests", {
      parsed
    });

    const filePath = path.join(paths.collections, `${runId}.json`);
    await writeJson(filePath, generated.collection);

    return {
      runId,
      testcases: generated.testcases,
      message: "Testcases generated and stored"
    };
  },

  async updateTestcases({ runId, collection }) {
    const filePath = path.join(paths.collections, `${runId}.json`);
    await writeJson(filePath, collection);
    return { message: "Testcases updated" };
  },

  async getCollection(runId) {
    const filePath = path.join(paths.collections, `${runId}.json`);
    const collection = await readJson(filePath);
    return { runId, collection };
  },

  async execute(runId) {
    const filePath = path.join(paths.collections, `${runId}.json`);
    const collection = await readJson(filePath);

    // Run Newman automatically
    const { reportJson } = await runNewman(runId, collection);
    const report = await readJson(reportJson);

    // Analyze report via FastAPI
    const { data: summary } = await fastapi.post("/analyze-report", {
      report
    });

    const summaryPath = path.join(paths.summaries, `${runId}.json`);
    await writeJson(summaryPath, summary);

    return { runId, summary };
  },

  /**
   * Execute a batch of tests from the collection
   * @param {string} runId - The run ID
   * @param {number} batchIndex - The batch number (0-indexed)
   * @param {number} batchSize - Number of tests per batch
   */
  async executeBatch(runId, batchIndex, batchSize = 10) {
    const filePath = path.join(paths.collections, `${runId}.json`);
    const fullCollection = await readJson(filePath);
    
    const items = fullCollection.item || [];
    const totalItems = items.length;
    const startIndex = batchIndex * batchSize;
    const endIndex = Math.min(startIndex + batchSize, totalItems);
    
    // Check if batch is within range
    if (startIndex >= totalItems) {
      return {
        runId,
        batchIndex,
        isComplete: true,
        summary: {
          total: 0,
          passed: 0,
          failed: 0,
          successEndpoints: [],
          failedEndpoints: []
        },
        progress: {
          currentBatch: batchIndex,
          totalBatches: Math.ceil(totalItems / batchSize),
          testedSoFar: totalItems,
          totalTests: totalItems
        }
      };
    }
    
    // Create a batch collection with only the items for this batch
    const batchItems = items.slice(startIndex, endIndex);
    const batchCollection = {
      ...fullCollection,
      item: batchItems,
      info: {
        ...fullCollection.info,
        name: `${fullCollection.info?.name || 'API Tests'} - Batch ${batchIndex + 1}`
      }
    };
    
    const batchRunId = `${runId}-batch-${batchIndex}`;
    
    console.log(`[Batch] Running batch ${batchIndex + 1}: items ${startIndex + 1} to ${endIndex} of ${totalItems}`);
    
    // Run Newman on the batch
    const { reportJson } = await runNewman(batchRunId, batchCollection);
    const report = await readJson(reportJson);

    // Analyze report via FastAPI
    const { data: summary } = await fastapi.post("/analyze-report", {
      report
    });

    const isComplete = endIndex >= totalItems;
    const totalBatches = Math.ceil(totalItems / batchSize);

    return {
      runId,
      batchIndex,
      isComplete,
      summary,
      progress: {
        currentBatch: batchIndex + 1,
        totalBatches,
        testedSoFar: endIndex,
        totalTests: totalItems
      }
    };
  },

  /**
   * Get the total number of tests in a collection
   */
  async getTestCount(runId) {
    const filePath = path.join(paths.collections, `${runId}.json`);
    const collection = await readJson(filePath);
    const totalTests = collection.item?.length || 0;
    return { runId, totalTests };
  }
};