export function errorMiddleware(err, req, res, next) {
  console.error("Error:", err.message);
  
  // Handle axios errors from FastAPI
  if (err.response) {
    return res.status(err.response.status || 500).json({
      error: err.response.data?.detail || err.response.data?.message || err.message,
      source: "fastapi"
    });
  }
  
  // Handle connection errors
  if (err.code === "ECONNREFUSED") {
    return res.status(503).json({
      error: "Python service is not available. Please ensure FastAPI is running on port 8000.",
      source: "connection"
    });
  }
  
  // Handle file not found errors
  if (err.code === "ENOENT") {
    return res.status(404).json({
      error: "Resource not found. The requested run ID may not exist.",
      source: "filesystem"
    });
  }
  
  res.status(500).json({ 
    error: err.message || "An unexpected error occurred",
    source: "backend"
  });
}