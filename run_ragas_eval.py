#!/usr/bin/env python3
import argparse
import json
import sys
import time
from pathlib import Path

import httpx
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.run_config import RunConfig


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--testset",      required=True)
    p.add_argument("--backend",      default="http://localhost:8123")
    p.add_argument("--ollama-host",  default="http://localhost:11435")
    p.add_argument("--ollama-model", default="qwen3:8b")
    p.add_argument("--output",       default="ragas_results.json")
    p.add_argument("--timeout",      type=int, default=180)
    p.add_argument("--max-items",    type=int, default=None)
    return p.parse_args()


def query_rag(question: str, backend_url: str, timeout: int) -> dict:
    answer_parts = []
    contexts = []
    last_event = None

    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST",
                f"{backend_url}/query/stream",
                json={"question": question, "history": []},
                headers={"Accept": "text/event-stream"},
            ) as resp:
                resp.raise_for_status()
                for raw_line in resp.iter_lines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        last_event = line[6:].strip()
                        continue
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        try:
                            parsed = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        if last_event == "sources" and isinstance(parsed, list):
                            for src in parsed:
                                for chunk in src.get("chunks", []):
                                    text = chunk.get("text", "").strip()
                                    if text:
                                        contexts.append(text)
                        elif last_event == "token" and isinstance(parsed, str):
                            answer_parts.append(parsed)
                        elif last_event == "error":
                            raise RuntimeError(f"Backend error: {parsed}")
    except Exception as e:
        return {"answer": "", "contexts": [""], "error": str(e)}

    return {
        "answer":   "".join(answer_parts).strip(),
        "contexts": contexts if contexts else [""],
        "error":    None,
    }


def build_dataset(testset, backend_url, timeout, max_items):
    items = testset[:max_items] if max_items else testset
    print(f"Querying backend for {len(items)} questions...\n")

    questions, answers, contexts_list, ground_truths = [], [], [], []

    for i, item in enumerate(items, start=1):
        q, gt = item["question"], item["ground_truth"]
        print(f"[{i}/{len(items)}] {q[:80]}...")
        result = query_rag(q, backend_url, timeout)
        if result["error"]:
            print(f"  error: {result['error']}")
        else:
            print(f"  answer: {result['answer'][:80]}...")
            print(f"  contexts: {len(result['contexts'])} chunks")
        questions.append(q)
        answers.append(result["answer"])
        contexts_list.append(result["contexts"])
        ground_truths.append(gt)
        time.sleep(0.3)

    return Dataset.from_dict({
        "question":     questions,
        "answer":       answers,
        "contexts":     contexts_list,
        "ground_truth": ground_truths,
    })


def main():
    args = parse_args()

    with open(args.testset, encoding="utf-8") as f:
        testset = json.load(f)
    print(f"Loaded {len(testset)} Q&A pairs\n")

    dataset = build_dataset(testset, args.backend, args.timeout, args.max_items)

    llm = LangchainLLMWrapper(
        OllamaLLM(base_url=args.ollama_host, model=args.ollama_model, temperature=0, timeout=120)
    )
    embeddings = LangchainEmbeddingsWrapper(
        OllamaEmbeddings(base_url=args.ollama_host, model="snowflake-arctic-embed2")
    )

    metrics = [
        Faithfulness(llm=llm),
        AnswerRelevancy(llm=llm, embeddings=embeddings),
        ContextPrecision(llm=llm),
        ContextRecall(llm=llm),
    ]

    print(f"\nRunning RAGAS with {args.ollama_model}...\n")
    result = evaluate(dataset, metrics=metrics, run_config=RunConfig(timeout=300, max_workers=1))

    def safe_score(key):
        val = result[key]
        if isinstance(val, list):
            nums = [v for v in val if v is not None and v == v]
            return round(sum(nums) / len(nums), 4) if nums else None
        try:
            return float(val)
        except Exception:
            return None

    scores = {k: safe_score(k) for k in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]}

    try:
        per_item = result.to_pandas().to_dict(orient="records")
    except Exception:
        per_item = []

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"scores": scores, "n_items": len(dataset), "model": args.ollama_model, "per_item": per_item}, f, ensure_ascii=False, indent=2)

    print("\nResults:")
    for k, v in scores.items():
        print(f"  {k}: {v:.3f}" if v is not None else f"  {k}: N/A")
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
