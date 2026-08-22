# 3개 언어 산출물을 하나의 런타임 이미지로 합친다: Python(운영 진입점, 기본값 유지) +
# Java/Jena(그래프 러너, KG_ENGINE=jena 전환 시에만 기동) + Node/AirMCP(스캐폴딩, 아직 미기동).
# 기본 CMD는 이전과 동일한 `python -m adapters.mcp_sdk_server`다 — 이 파일은 "빌드 가능하게" 만드는
# 작업이며, 운영 기본 경로를 바꾸지 않는다.

FROM maven:3.9-eclipse-temurin-21 AS java-build
WORKDIR /build
COPY java/companyx-ontology/pom.xml ./pom.xml
RUN mvn -q -B dependency:go-offline || true
COPY java/companyx-ontology/src ./src
RUN mvn -q -B -DskipTests package

FROM node:20-slim AS air-build
WORKDIR /build
COPY mcp-air/package.json mcp-air/package-lock.json* ./
RUN npm ci
COPY mcp-air/tsconfig.json ./
COPY mcp-air/src ./src
RUN npm run build && npm prune --omit=dev

FROM python:3.12-slim
WORKDIR /app

# 최종 이미지에는 JRE(그래프 러너용)와 Node 런타임(Air 메인용)을 함께 둔다. 빌드 도구(JDK/Maven, npm)는
# 넣지 않는다 — 산출물만 복사한다.
RUN apt-get update && apt-get install -y --no-install-recommends \
      openjdk-21-jre-headless nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY --from=java-build /build/target/graph-runner.jar ./java/graph-runner.jar
COPY --from=air-build /build/dist ./mcp-air/dist
COPY --from=air-build /build/node_modules ./mcp-air/node_modules
COPY mcp-air/package.json ./mcp-air/package.json

# KG_ENGINE=jena로 전환 시 이 명령으로 그래프 러너를 띄운다(§P2/P3 실연결은 별도 라운드 스코프).
ENV JAVA_GRAPH_RUNNER_CMD="java -Dcompanyx.dataset=/app/data/graph -jar /app/java/graph-runner.jar --stdio"
# Air를 실제 진입점으로 켤 때 사용할 명령(§P5 전환 이전에는 미사용).
ENV AIR_MAIN_CMD="node /app/mcp-air/dist/index.js"

CMD ["python", "-m", "adapters.mcp_sdk_server"]
