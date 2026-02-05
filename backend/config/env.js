import dotenv from "dotenv";
dotenv.config();

export const env = {
  PORT: process.env.PORT || 5000,
  FASTAPI_URL: process.env.FASTAPI_URL,
  STORAGE_DIR: process.env.STORAGE_DIR
};