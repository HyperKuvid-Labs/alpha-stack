from datasets import load_dataset

try:
    dataset = load_dataset("mbpp", "sanitized", split="test")
    print(f"Dataset size: {len(dataset)}")
    for i in range(min(10, len(dataset))):
        print(f"Index {i}: task_id {dataset[i]['task_id']}")
except Exception as e:
    print(f"Error: {e}")
