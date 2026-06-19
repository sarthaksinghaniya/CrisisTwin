import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import logging
from sklearn.metrics import f1_score

logger = logging.getLogger(__name__)

class NNTrainer:
    """
    PyTorch-based training loop with Multi-Label support (BCEWithLogits), 
    Threshold Tuning, and LR Scheduler.
    """
    def __init__(self, input_dim: int, num_classes: int, class_weights: dict = None):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.num_classes = num_classes
        
        self.model = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        ).to(self.device)
        
        alpha = None
        if class_weights:
            sorted_weights = [class_weights[k] for k in sorted(class_weights.keys())]
            alpha = torch.tensor(sorted_weights, dtype=torch.float32).to(self.device)
            
        logger.info("Using BCEWithLogitsLoss for Multi-Label Classification...")
        self.criterion = nn.BCEWithLogitsLoss(pos_weight=alpha)
            
        self.optimizer = optim.AdamW(self.model.parameters(), lr=1e-3, weight_decay=1e-4)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(self.optimizer, mode='min', patience=2, factor=0.5)
        self.thresholds = np.full(num_classes, 0.5)

    def fit(self, X_train, y_train, X_val=None, y_val=None, epochs=20, batch_size=32, patience=5):
        # For multi-label, y must be float
        train_dataset = TensorDataset(torch.tensor(X_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.float32))
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        
        val_loader = None
        if X_val is not None and y_val is not None:
            val_dataset = TensorDataset(torch.tensor(X_val, dtype=torch.float32), torch.tensor(y_val, dtype=torch.float32))
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
            
        best_loss = float('inf')
        epochs_no_improve = 0
        
        logger.info(f"Starting PyTorch Training on {self.device}")
        for epoch in range(epochs):
            self.model.train()
            total_loss = 0
            
            for batch_X, batch_y in train_loader:
                batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                
                self.optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = self.criterion(outputs, batch_y)
                loss.backward()
                
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                
                self.optimizer.step()
                total_loss += loss.item()
                
            avg_train_loss = total_loss / len(train_loader)
            val_loss = avg_train_loss
            
            if val_loader:
                self.model.eval()
                val_total = 0
                with torch.no_grad():
                    for batch_X, batch_y in val_loader:
                        batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                        outputs = self.model(batch_X)
                        val_total += self.criterion(outputs, batch_y).item()
                val_loss = val_total / len(val_loader)
                
            self.scheduler.step(val_loss)
            logger.info(f"Epoch {epoch+1}/{epochs} | Train Loss: {avg_train_loss:.4f} | Val Loss: {val_loss:.4f}")
            
            if val_loss < best_loss:
                best_loss = val_loss
                epochs_no_improve = 0
            else:
                epochs_no_improve += 1
                if epochs_no_improve >= patience:
                    logger.info(f"Early stopping triggered at epoch {epoch+1}")
                    break
                    
        # Post-training: Tune thresholds on validation set
        if X_val is not None and y_val is not None:
            self.tune_thresholds(X_val, y_val)
            
        return self.model
        
    def tune_thresholds(self, X_val, y_val):
        logger.info("Tuning thresholds per class to maximize F1...")
        self.model.eval()
        X_tensor = torch.tensor(X_val, dtype=torch.float32).to(self.device)
        with torch.no_grad():
            outputs = self.model(X_tensor)
            probs = torch.sigmoid(outputs).cpu().numpy()
            
        best_thresholds = []
        for i in range(self.num_classes):
            best_t = 0.5
            best_f1 = 0
            for t in np.arange(0.1, 0.9, 0.1):
                preds = (probs[:, i] >= t).astype(int)
                f1 = f1_score(y_val[:, i], preds, zero_division=0)
                if f1 > best_f1:
                    best_f1 = f1
                    best_t = t
            best_thresholds.append(best_t)
            
        self.thresholds = np.array(best_thresholds)
        logger.info(f"Tuned Thresholds: {self.thresholds}")

    def predict(self, X):
        self.model.eval()
        X_tensor = torch.tensor(X, dtype=torch.float32).to(self.device)
        with torch.no_grad():
            outputs = self.model(X_tensor)
            probs = torch.sigmoid(outputs).cpu().numpy()
            
            # Apply tuned thresholds
            preds = (probs >= self.thresholds).astype(int)
            return preds, probs

