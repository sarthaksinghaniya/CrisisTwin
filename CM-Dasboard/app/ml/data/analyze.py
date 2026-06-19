import os
import json
import pandas as pd

# Define paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "processed")
MERGED_DATASET_PATH = os.path.join(PROCESSED_DATA_DIR, "merged_dataset.csv")
REPORT_PATH = os.path.join(PROCESSED_DATA_DIR, "class_distribution_report.json")

def analyze_imbalance():
    """
    Loads the merged dataset, calculates total samples, 
    class counts, and percentages, then prints and saves a JSON report.
    """
    if not os.path.exists(MERGED_DATASET_PATH):
        print(f"Error: Merged dataset not found at {MERGED_DATASET_PATH}")
        print("Run 'python -m app.ml.data.run_pipeline' first.")
        return

    print(f"Loading {MERGED_DATASET_PATH}...")
    df = pd.read_csv(MERGED_DATASET_PATH)
    
    if "label" not in df.columns:
        print("Error: 'label' column is missing from the dataset.")
        return
        
    total_samples = len(df)
    
    # Calculate counts using pandas value_counts
    counts = df["label"].value_counts().to_dict()
    
    print("\n" + "="*40)
    print("CLASS DISTRIBUTION ANALYSIS")
    print("="*40)
    print(f"Total Samples: {total_samples}")
    print("-" * 40)
    
    # Prepare JSON report dictionary
    report_data = {
        "total_samples": total_samples,
        "distribution": {}
    }
    
    # Iterate through sorted labels to print and store statistics
    for label_val, count in sorted(counts.items()):
        percentage = (count / total_samples) * 100
        
        # Human readable print (Label 0: 8000 (80%))
        print(f"Label {label_val}: {count} ({percentage:.1f}%)")
        
        # Update JSON dictionary
        report_data["distribution"][str(label_val)] = {
            "count": int(count),
            "percentage": round(percentage, 2)
        }
        
    print("="*40 + "\n")
    
    # Save the report
    try:
        with open(REPORT_PATH, "w") as f:
            json.dump(report_data, f, indent=4)
        print(f"Saved JSON distribution report to -> {REPORT_PATH}")
    except Exception as e:
        print(f"Failed to save JSON report: {e}")

if __name__ == "__main__":
    analyze_imbalance()
