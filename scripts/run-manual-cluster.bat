@echo off
echo ===================================================
echo Epicure - Manual Cluster Startup Script
echo This script will open multiple terminals to start 
echo all Java and Python nodes locally without Docker.
echo ===================================================
echo.

echo 1. Starting Qdrant Vector Database in Docker...
start "Qdrant DB" cmd /k "docker run -p 6333:6333 -p 6334:6334 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest"

echo 2. Starting Frontend Development Server...
start "Frontend (React)" cmd /k "cd frontend && npm install && npm run dev"

echo 3. Starting Python APIs...
start "Python LLM API (5000)" cmd /k ".\.venv\Scripts\Activate.ps1 && cd llm-node\python-llm-api && python -m uvicorn app:app --host 127.0.0.1 --port 5000"
start "Python ETL API (6000)" cmd /k ".\.venv\Scripts\Activate.ps1 && cd ETL-node\etl-api && python -m uvicorn app:app --host 127.0.0.1 --port 6000"

echo 4. Starting Java Coordinator Nodes...
start "Coordinator 1 (8080)" cmd /k "cd coordinator && mvn spring-boot:run -Dspring-boot.run.jvmArguments=\"-Dserver.port=8080 -DNODE_ID=localhost:8080\""
start "Coordinator 2 (8081)" cmd /k "cd coordinator && mvn spring-boot:run -Dspring-boot.run.jvmArguments=\"-Dserver.port=8081 -DNODE_ID=localhost:8081\""
start "Coordinator 3 (8082)" cmd /k "cd coordinator && mvn spring-boot:run -Dspring-boot.run.jvmArguments=\"-Dserver.port=8082 -DNODE_ID=localhost:8082\""

echo 5. Starting Java Recipe Nodes...
start "Recipe 1 (8100)" cmd /k "cd recipe-node && mvn spring-boot:run -Dspring-boot.run.jvmArguments=\"-Dserver.port=8100\""
start "Recipe 2 (8101)" cmd /k "cd recipe-node && mvn spring-boot:run -Dspring-boot.run.jvmArguments=\"-Dserver.port=8101\""
start "Recipe 3 (8102)" cmd /k "cd recipe-node && mvn spring-boot:run -Dspring-boot.run.jvmArguments=\"-Dserver.port=8102\""

echo 6. Starting Java LLM Nodes...
start "LLM 1 (8120)" cmd /k "cd llm-node && mvn spring-boot:run -Dspring-boot.run.jvmArguments=\"-Dserver.port=8120 -DPYTHON_LLM_API_BASE_URL=http://localhost:5000\""
start "LLM 2 (8121)" cmd /k "cd llm-node && mvn spring-boot:run -Dspring-boot.run.jvmArguments=\"-Dserver.port=8121 -DPYTHON_LLM_API_BASE_URL=http://localhost:5000\""

echo 7. Starting Java ETL Nodes...
start "ETL 1 (8140)" cmd /k "cd ETL-node && mvn spring-boot:run -Dspring-boot.run.jvmArguments=\"-Dserver.port=8140 -DPYTHON_ETL_API_BASE_URL=http://localhost:6000\""
start "ETL 2 (8141)" cmd /k "cd ETL-node && mvn spring-boot:run -Dspring-boot.run.jvmArguments=\"-Dserver.port=8141 -DPYTHON_ETL_API_BASE_URL=http://localhost:6000\""

echo.
echo Waiting 45 seconds for all Spring Boot applications to initialize...
timeout /t 45

echo.
echo 8. Binding the cluster together (cURL)...
echo Binding Coordinators...
curl.exe -X POST "http://localhost:8081/follow?id=localhost:8080"
curl.exe -X POST "http://localhost:8082/follow?id=localhost:8080"

echo Binding Recipe Nodes...
curl.exe -X POST "http://localhost:8080/apply?id=localhost:8100&type=db"
curl.exe -X POST "http://localhost:8080/apply?id=localhost:8101&type=db"
curl.exe -X POST "http://localhost:8080/apply?id=localhost:8102&type=db"

echo Binding LLM Nodes...
curl.exe -X POST "http://localhost:8080/apply?id=localhost:8120&type=llm"
curl.exe -X POST "http://localhost:8080/apply?id=localhost:8121&type=llm"

echo Binding ETL Nodes...
curl.exe -X POST "http://localhost:8080/apply?id=localhost:8140&type=etl"
curl.exe -X POST "http://localhost:8080/apply?id=localhost:8141&type=etl"

echo.
echo ===================================================
echo Cluster Setup Complete!
echo You can view the frontend at http://localhost:5173
echo ===================================================
pause
