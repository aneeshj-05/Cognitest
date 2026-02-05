import newman from "newman";
import path from "path";
import { paths } from "../../../config/paths.js";

export async function runNewman(runId, collection) {
  const reportJson = path.join(paths.reports, `${runId}.json`);
  const reportHtml = path.join(paths.reports, `${runId}.html`);

  // Extract baseUrl from collection variables
  const baseUrl = collection.variable?.find(v => v.key === "baseUrl")?.value || "";
  
  const itemCount = collection.item?.length || 0;
  console.log(`[Newman] Starting test run: ${runId}`);
  console.log(`[Newman] Base URL: ${baseUrl}`);
  console.log(`[Newman] Total requests: ${itemCount}`);

  // Dynamic timeout based on number of requests (30 seconds per request, min 60s)
  const dynamicTimeout = Math.max(60000, itemCount * 30000);

  return new Promise((resolve, reject) => {
    newman.run(
      {
        collection,
        envVar: [
          { key: "baseUrl", value: baseUrl }
        ],
        reporters: ["cli", "json", "htmlextra"],
        reporter: {
          json: { export: reportJson },
          htmlextra: { export: reportHtml }
        },
        timeout: dynamicTimeout, // Dynamic timeout based on batch size
        timeoutRequest: 30000, // 30 second timeout per request
        insecure: true, // Allow self-signed certs
        suppressExitCode: true // Don't exit on failures
      },
      (err, summary) => {
        if (err) {
          console.error(`[Newman] Error: ${err.message}`);
          reject(err);
        } else {
          console.log(`[Newman] Run completed. Requests: ${summary.run?.stats?.requests?.total || 0}`);
          resolve({ reportJson, reportHtml, summary });
        }
      }
    );
  });
}