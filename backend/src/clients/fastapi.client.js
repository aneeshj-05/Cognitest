import axios from "axios";
import { env } from "../../config/env.js";

export const fastapi = axios.create({
  baseURL: env.FASTAPI_URL,
  timeout: 300000 // 5 minutes for long operations like test analysis
});