# AskUHH
---

## Quickstart

### 1. Clone the repo

```bash
git clone https://git.informatik.uni-hamburg.de/3gorke/askuhh.git
cd askuhh
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your ports (make sure they are not already in use on the cluster):

```dotenv
FRONTEND_PORT=3123
BACKEND_PORT=8123
OLLAMA_PORT=11435
CUDA_VISIBLE_DEVICES=1
```

### 3. Start everything

```bash
docker compose up --build
```
The main containers will start: `askuhh-frontend`, `askuhh-backend`.

## 4. Ollama container

When not already started, the Ollama container can be started with

```bash
docker compose --profile ollama up -d ollama
```

The Ollama container will start: `askuhh-ollama`.

### 5. Access the app

From your **local machine**, open an SSH tunnel:

```bash
ssh -L 3123:localhost:3123 hcdsgpu2
```

Then open your browser at:

```
http://localhost:3123
```

### 6. Add documents

 Copy PDF files into `backend/data/docs/`

---
