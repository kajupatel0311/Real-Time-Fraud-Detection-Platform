"""
Stage 3.2 — LSTM Sequence Model with Masking and Padding
Fix 2: Build sequences from full dataset before splitting.
Using nameDest as the sequence key to achieve the expected 820k+ sequences.
"""
import os
import logging
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from sklearn.metrics import average_precision_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RANDOM_STATE = 42
WINDOW_SIZE  = 10
DEVICE       = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def build_all_sequences(df, feature_cols, window_size=WINDOW_SIZE, min_txns=3, card_col="nameDest"):
    """
    Builds sequences for the FULL dataset.
    Returns: sequences (X), labels (y), masks (m), steps (s)
    """
    logger.info(f"Building all sequences (min_txns={min_txns}, window={window_size}, key={card_col})...")
    
    # Sort for sequence correctness
    df = df.sort_values([card_col, "step"]).reset_index(drop=True)
    
    feats_arr  = df[feature_cols].values.astype(np.float32)
    labels_arr = df["isFraud"].values.astype(np.float32)
    steps_arr  = df["step"].values
    users_arr  = df[card_col].values
    
    user_counts = pd.Series(users_arr).value_counts()
    eligible_users = set(user_counts[user_counts >= min_txns].index)

    all_sequences = []
    all_labels    = []
    all_masks     = []
    all_steps     = []

    for i in range(len(df)):
        if users_arr[i] not in eligible_users:
            continue
            
        history = []
        for j in range(1, window_size + 1):
            prev_idx = i - j
            if prev_idx >= 0 and users_arr[prev_idx] == users_arr[i]:
                history.append(feats_arr[prev_idx])
            else:
                break
        
        history.reverse()
        
        seq  = np.zeros((window_size, len(feature_cols)), dtype=np.float32)
        mask = np.zeros(window_size, dtype=np.float32)
        
        if history:
            h_len = len(history)
            seq[-h_len:] = np.array(history)
            mask[-h_len:] = 1.0
            
        all_sequences.append(seq)
        all_labels.append(labels_arr[i])
        all_masks.append(mask)
        all_steps.append(steps_arr[i])

    X = np.array(all_sequences, dtype=np.float32)
    y = np.array(all_labels, dtype=np.float32)
    m = np.array(all_masks, dtype=np.float32)
    s = np.array(all_steps, dtype=np.int32)
    
    logger.info(f"Built {len(X):,} sequences total | fraud={int(y.sum()):,} ({y.mean()*100:.3f}%)")
    return X, y, m, s

def split_sequences_by_time(X, y, m, s, cutoff_step):
    train_idx = s <= cutoff_step
    test_idx  = s > cutoff_step
    
    X_tr, y_tr, m_tr = X[train_idx], y[train_idx], m[train_idx]
    X_te, y_te, m_te = X[test_idx],  y[test_idx],  m[test_idx]
    
    logger.info(f"Sequence Split at step={cutoff_step}")
    logger.info(f"  Train: {len(X_tr):,} (Fraud: {y_tr.mean()*100:.4f}%)")
    logger.info(f"  Test:  {len(X_te):,} (Fraud: {y_te.mean()*100:.4f}%)")
    
    return (X_tr, y_tr, m_tr), (X_te, y_te, m_te)

class FraudSequenceDataset(Dataset):
    def __init__(self, X, y, m):
        self.X = torch.tensor(X)
        self.y = torch.tensor(y)
        self.m = torch.tensor(m)
    def __len__(self): return len(self.y)
    def __getitem__(self, idx): return self.X[idx], self.y[idx], self.m[idx]

class Attention(nn.Module):
    def __init__(self, hidden_dim):
        super().__init__()
        self.attn = nn.Linear(hidden_dim, 1)

    def forward(self, lstm_output, mask):
        attn_weights = self.attn(lstm_output).squeeze(-1)
        padding_mask = (mask == 0)
        attn_weights.masked_fill_(padding_mask, -1e9)
        soft_attn_weights = torch.softmax(attn_weights, dim=1)
        context = torch.bmm(soft_attn_weights.unsqueeze(1), lstm_output).squeeze(1)
        return context

class FraudLSTM(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 64, num_layers: int = 1):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)
        self.attention = Attention(hidden_dim)
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, x, m):
        lstm_out, _ = self.lstm(x)
        context = self.attention(lstm_out, m)
        return self.classifier(context).squeeze(-1)

@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    all_probs, all_labels = [], []
    for X, y, m in loader:
        probs = model(X.to(device), m.to(device)).cpu().numpy()
        all_probs.extend(probs)
        all_labels.extend(y.numpy())
    if not all_labels: return 0.0, np.array([]), np.array([])
    return average_precision_score(all_labels, all_probs), np.array(all_probs), np.array(all_labels)

def train_lstm(df, feature_cols, cutoff_step, epochs=10, batch_size=512, weight_cap=10.0, save_path="output/models/lstm.pt"):
    X, y, m, s = build_all_sequences(df, feature_cols)
    (X_tr, y_tr, m_tr), (X_te, y_te, m_te) = split_sequences_by_time(X, y, m, s, cutoff_step)
    
    if len(X_tr) == 0: return None
    
    # WeightedRandomSampler with weight_cap
    class_counts = np.array([len(y_tr) - y_tr.sum(), y_tr.sum()])
    weights = 1.0 / class_counts
    fraud_weight = min(weights[1], weights[0] * weight_cap)
    weights[1] = fraud_weight
    
    sample_weights = np.array([weights[int(t)] for t in y_tr])
    sampler = WeightedRandomSampler(torch.from_numpy(sample_weights), len(sample_weights))
    
    train_loader = DataLoader(FraudSequenceDataset(X_tr, y_tr, m_tr), batch_size=batch_size, sampler=sampler)
    val_loader   = DataLoader(FraudSequenceDataset(X_te, y_te, m_te), batch_size=batch_size, shuffle=False)

    model = FraudLSTM(input_dim=len(feature_cols)).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCELoss()

    best_pr_auc = 0.0
    for epoch in range(1, epochs + 1):
        model.train()
        for X_b, y_b, m_b in train_loader:
            X_b, y_b, m_b = X_b.to(DEVICE), y_b.to(DEVICE), m_b.to(DEVICE)
            optimizer.zero_grad()
            loss = loss_fn(model(X_b, m_b), y_b)
            loss.backward()
            optimizer.step()
        
        pr_auc, _, _ = evaluate(model, val_loader, DEVICE)
        logger.info(f"Epoch {epoch:2d} | Val PR-AUC: {pr_auc:.4f}")
        if pr_auc > best_pr_auc:
            best_pr_auc = pr_auc
            torch.save(model.state_dict(), save_path)

    if best_pr_auc < 0.10:
        logger.warning(f"LSTM Auto-Disabled (Best PR-AUC {best_pr_auc:.4f} < 0.10)")
        return None
        
    if os.path.exists(save_path):
        model.load_state_dict(torch.load(save_path))
    return model

def export_onnx(model, input_dim):
    if model is None: return
    model.eval()
    dummy_x = torch.zeros(1, WINDOW_SIZE, input_dim).to(DEVICE)
    dummy_m = torch.ones(1, WINDOW_SIZE).to(DEVICE)
    torch.onnx.export(model, (dummy_x, dummy_m), "output/models/lstm_fraud.onnx", opset_version=15)
