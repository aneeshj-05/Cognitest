def analyze_report(report):
    run = report.get("run", {})
    stats = run.get("stats", {})
    failures = run.get("failures", [])
    executions = run.get("executions", [])
    
    # Get request stats
    requests = stats.get("requests", {})
    requests_total = requests.get("total", 0)

    # Collect all failure messages
    failed_list = []
    failed_names = set()  # Track failed endpoint names
    
    for f in failures:
        src = f.get("source", {})
        err = f.get("error", {})
        name = src.get("name", "Unknown")
        message = err.get("message", "Unknown error")
        
        if name not in failed_names:
            failed_names.add(name)
            failed_list.append({
                "endpoint": name,
                "message": message
            })

    # Collect successful endpoints (those not in failures)
    success_list = []
    seen_success = set()
    
    for execution in executions:
        item = execution.get("item", {})
        name = item.get("name", "Unknown")
        
        # If this endpoint is not in failures, it's successful
        if name not in failed_names and name not in seen_success:
            seen_success.add(name)
            
            # Get response info if available
            response = execution.get("response", {})
            status_code = response.get("code", "N/A")
            response_time = response.get("responseTime", "N/A")
            
            success_list.append({
                "endpoint": name,
                "status": status_code,
                "responseTime": f"{response_time}ms" if response_time != "N/A" else "N/A"
            })

    return {
        "total": requests_total,
        "passed": len(success_list),
        "failed": len(failed_list),
        "successEndpoints": success_list,
        "failedEndpoints": failed_list
    }