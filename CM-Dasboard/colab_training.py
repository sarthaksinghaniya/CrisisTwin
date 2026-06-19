"""
Complaint Classification Fine-Tuning Pipeline
Designed to run in Google Colab or any local environment with PyTorch.

Prerequisites (Run this in Colab cell first):
!pip install transformers datasets evaluate scikit-learn torch
"""

import numpy as np
import evaluate
from datasets import load_dataset
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification, 
    TrainingArguments, 
    Trainer,
    pipeline
)
import torch

# ==========================================
# 1. Configuration
# ==========================================
MODEL_NAME = "distilbert-base-uncased"
OUTPUT_DIR = "./models/complaint-classifier"

# Paths to your actual dataset. Change to 'dataset.json' if using JSON.
DATASET_PATH = "complaint_dataset.csv" 

# Define your labels mapping
LABEL_MAPPINGS = {"low": 0, "medium": 1, "high": 2}
ID2LABEL = {v: k for k, v in LABEL_MAPPINGS.items()}

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

# ==========================================
# 2. Preprocessing & Tokenization
# ==========================================
def preprocess_function(examples):
    # Tokenize the text feature
    tokenized = tokenizer(examples["text"], padding="max_length", truncation=True, max_length=128)
    
    # Convert string labels to numerical IDs if necessary
    if isinstance(examples["label"][0], str):
        tokenized["label"] = [LABEL_MAPPINGS.get(lbl.lower(), 0) for lbl in examples["label"]]
    else:
        tokenized["label"] = examples["label"]
        
    return tokenized

def prepare_dataset():
    """Loads dataset from CSV or JSON and splits into train/test."""
    # To use JSON instead, change to: load_dataset("json", data_files=DATASET_PATH)
    try:
        dataset = load_dataset("csv", data_files=DATASET_PATH)
    except FileNotFoundError:
        # --- Fallback: Create a tiny dummy dataset if file isn't found ---
        print(f"Warning: {DATASET_PATH} not found. Creating a dummy dataset to test the pipeline...")
        import pandas as pd
        df = pd.DataFrame({
            "text": ["building is on fire", "minor leak in the kitchen", "severe earthquake hit the city", "lost dog found"],
            "label": ["high", "low", "high", "low"]
        })
        df.to_csv(DATASET_PATH, index=False)
        dataset = load_dataset("csv", data_files=DATASET_PATH)

    # 80/20 train-test split
    dataset = dataset["train"].train_test_split(test_size=0.2)
    
    # Apply tokenization
    tokenized_datasets = dataset.map(preprocess_function, batched=True)
    return tokenized_datasets["train"], tokenized_datasets["test"]

# ==========================================
# 3. Evaluation Metric
# ==========================================
accuracy_metric = evaluate.load("accuracy")

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    return accuracy_metric.compute(predictions=predictions, references=labels)

# ==========================================
# 4. Training Pipeline
# ==========================================
def train_model():
    print("Preparing dataset...")
    train_dataset, test_dataset = prepare_dataset()
    
    print("Loading pre-trained DistilBERT model...")
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, 
        num_labels=len(LABEL_MAPPINGS),
        id2label=ID2LABEL,
        label2id=LABEL_MAPPINGS
    )
    
    # Training configurations specified in requirements
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        num_train_epochs=3,
        weight_decay=0.01,
        load_best_model_at_end=True,
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
    )
    
    print("Starting training...")
    trainer.train()
    
    print(f"Saving fine-tuned model to {OUTPUT_DIR}...")
    trainer.save_model(OUTPUT_DIR)
    
    # Save tokenizer separately just in case
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("Training complete!")

# ==========================================
# 5. Inference Function
# ==========================================
def predict_complaint(text: str):
    """
    Predicts the complaint label and confidence for a given text 
    using the locally saved fine-tuned model.
    """
    try:
        # Load the inference pipeline pointing to our saved directory
        classifier = pipeline("text-classification", model=OUTPUT_DIR, tokenizer=OUTPUT_DIR)
        
        # Run inference
        result = classifier(text)[0]
        
        return {
            "text": text,
            "predicted_label": result["label"],
            "confidence": round(result["score"], 4)
        }
    except OSError:
        print("Model not found! Make sure you run train_model() first.")
        return None

# ==========================================
# Example Colab Execution Block
# ==========================================
if __name__ == "__main__":
    # Uncomment to train the model:
    # train_model()
    
    # Uncomment to test inference (only works AFTER training):
    # test_text = "A massive category 5 hurricane is approaching the coast."
    # prediction = predict_complaint(test_text)
    # print(f"Inference Result: {prediction}")
    pass
