"""
Fine-tuning is NOT used in this setup.

All training data is loaded as in-context few-shot examples via knowledge.py.
The single model (gpt-5-mini) receives all 80 examples at inference time.

This file is kept as a stub so existing imports don't break.
"""


def main():
    print("Fine-tuning is not needed in this setup.")
    print("All 80 training examples are injected as few-shot context into gpt-5-mini.")
    print()
    print("Training data loaded at startup:")
    from knowledge import KNOWLEDGE_SUMMARY
    print(f"  {KNOWLEDGE_SUMMARY}")


if __name__ == "__main__":
    main()
