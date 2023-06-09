# -*- coding: utf-8 -*-
"""BPM_FC_RC.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1j7v67Lk4hmLyWRkJECUF04tcYSKQRgoo
"""

from google.colab import drive
drive.mount('/content/drive')

! pip3 install transformers

# Commented out IPython magic to ensure Python compatibility.
# %cd /content/drive/MyDrive/BPM_FC_RC

from torch.utils.data import Dataset
import torch

class DataPrecessForSentence(Dataset):
    """
    Encoding sentences
    """
    def __init__(self, bert_tokenizer, df, max_seq_len = 50):
        super(DataPrecessForSentence, self).__init__()
        self.bert_tokenizer = bert_tokenizer
        self.max_seq_len = max_seq_len
        self.input_ids, self.attention_mask, self.token_type_ids, self.labels = self.get_input(df)
        
    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.input_ids[idx], self.attention_mask[idx], self.token_type_ids[idx], self.labels[idx]
        
    # Convert dataframe to tensor
    def get_input(self, df):
        sentences = df['p1'].values + str(df['p2']) + str(df['p3'])
        labels = df['similarity'].values
        


    # tokenizer
        tokens_seq = list(map(self.bert_tokenizer.tokenize, sentences)) # list of shape [sentence_len, token_len]
        
        # Get fixed-length sequence and its mask
        result = list(map(self.trunate_and_pad, tokens_seq))
        
        input_ids = [i[0] for i in result]
        attention_mask = [i[1] for i in result]
        token_type_ids = [i[2] for i in result]
        
        return (
               torch.Tensor(input_ids).type(torch.long), 
               torch.Tensor(attention_mask).type(torch.long),
               torch.Tensor(token_type_ids).type(torch.long), 
               torch.Tensor(labels).type(torch.long)
               )
    
    
    def trunate_and_pad(self, tokens_seq):
        
        # Concat '[CLS]' at the beginning
        tokens_seq = ['[CLS]'] + tokens_seq     
        # Truncate sequences of which the lengths exceed the max_seq_len
        if len(tokens_seq) > self.max_seq_len:
            tokens_seq = tokens_seq[0 : self.max_seq_len]           
        # Generate padding
        padding = [0] * (self.max_seq_len - len(tokens_seq))       
        # Convert tokens_seq to token_ids
        input_ids = self.bert_tokenizer.convert_tokens_to_ids(tokens_seq)
        input_ids += padding   
        # Create attention_mask
        attention_mask = [1] * len(tokens_seq) + padding     
        # Create token_type_ids
        token_type_ids = [0] * (self.max_seq_len)
        
        assert len(input_ids) == self.max_seq_len
        assert len(attention_mask) == self.max_seq_len
        assert len(token_type_ids) == self.max_seq_len
        
        return input_ids, attention_mask, token_type_ids

print(type('p1'))
print(type('p2'))
print(type('p3'))
print(type('p4'))

import torch
import torch.nn as nn
import time
from tqdm import tqdm
from sklearn.metrics import (
    roc_auc_score, 
    accuracy_score, 
    precision_score, 
    recall_score, 
    f1_score, 
    classification_report
)   

    
def Metric(y_true, y_pred):
    """
    compute and show the classification result
    """
    accuracy = accuracy_score(y_true, y_pred)
    macro_precision = precision_score(y_true, y_pred, average='macro')
    macro_recall = recall_score(y_true, y_pred, average='macro')
    weighted_f1 = f1_score(y_true, y_pred, average='macro')
    target_names = ['class_0', 'class_1']
    report = classification_report(y_true, y_pred, target_names=target_names, digits=3)

    print('Accuracy: {:.1%}\nPrecision: {:.1%}\nRecall: {:.1%}\nF1: {:.1%}'.format(accuracy, macro_precision,
                                           macro_recall, weighted_f1))
    print("classification_report:\n")
    print(report)
  
  
def correct_predictions(output_probabilities, targets):
    """
    Compute the number of predictions that match some target classes in the
    output of a model.
    Args:
        output_probabilities: A tensor of probabilities for different output
            classes.
        targets: The indices of the actual target classes.
    Returns:
        The number of correct predictions in 'output_probabilities'.
    """
    _, out_classes = output_probabilities.max(dim=1)
    correct = (out_classes == targets).sum()
    return correct.item()


def train(model, dataloader, optimizer, epoch_number, max_gradient_norm):
    """
    Train a model for one epoch on some input data with a given optimizer and
    criterion.
    Args:
        model: A torch module that must be trained on some input data.
        dataloader: A DataLoader object to iterate over the training data.
        optimizer: A torch optimizer to use for training on the input model.
        epoch_number: The number of the epoch for which training is performed.
        max_gradient_norm: Max. norm for gradient norm clipping.
    Returns:
        epoch_time: The total time necessary to train the epoch.
        epoch_loss: The training loss computed for the epoch.
        epoch_accuracy: The accuracy computed for the epoch.
    """
    # Switch the model to train mode.
    model.train()
    device = model.device
    epoch_start = time.time()
    batch_time_avg = 0.0
    running_loss = 0.0
    correct_preds = 0
    tqdm_batch_iterator = tqdm(dataloader)
    for batch_index, (batch_seqs, batch_seq_masks, batch_seq_segments, batch_labels) in enumerate(tqdm_batch_iterator):
        batch_start = time.time()
        # Move input and output data to the GPU if it is used.
        seqs, masks, segments, labels = batch_seqs.to(device), batch_seq_masks.to(device), batch_seq_segments.to(device), batch_labels.to(device)
        optimizer.zero_grad()
        loss, logits, probabilities = model(seqs, masks, segments, labels)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_gradient_norm)
        optimizer.step()
        batch_time_avg += time.time() - batch_start
        running_loss += loss.item()
        correct_preds += correct_predictions(probabilities, labels)
        description = "Avg. batch proc. time: {:.4f}s, loss: {:.4f}"\
                      .format(batch_time_avg/(batch_index+1), running_loss/(batch_index+1))
        tqdm_batch_iterator.set_description(description)
    epoch_time = time.time() - epoch_start
    epoch_loss = running_loss / len(dataloader)
    epoch_accuracy = correct_preds / len(dataloader.dataset)
    return epoch_time, epoch_loss, epoch_accuracy


def validate(model, dataloader):
    """
    Compute the loss and accuracy of a model on some validation dataset.
    Args:
        model: A torch module for which the loss and accuracy must be
            computed.
        dataloader: A DataLoader object to iterate over the validation data.
    Returns:
        epoch_time: The total time to compute the loss and accuracy on the
            entire validation set.
        epoch_loss: The loss computed on the entire validation set.
        epoch_accuracy: The accuracy computed on the entire validation set.
        roc_auc_score(all_labels, all_prob): The auc computed on the entire validation set.
        all_prob: The probability of classification as label 1 on the entire validation set.
    """
    # Switch to evaluate mode.
    model.eval()
    device = model.device
    epoch_start = time.time()
    running_loss = 0.0
    running_accuracy = 0.0
    all_prob = []
    all_labels = []
    # Deactivate autograd for evaluation.
    with torch.no_grad():
        for (batch_seqs, batch_seq_masks, batch_seq_segments, batch_labels) in dataloader:
            # Move input and output data to the GPU if one is used.
            seqs = batch_seqs.to(device)
            masks = batch_seq_masks.to(device)
            segments = batch_seq_segments.to(device)
            labels = batch_labels.to(device)
            loss, logits, probabilities = model(seqs, masks, segments, labels)
            running_loss += loss.item()
            running_accuracy += correct_predictions(probabilities, labels)
            all_prob.extend(probabilities[:,1].cpu().numpy())
            all_labels.extend(batch_labels)
    epoch_time = time.time() - epoch_start
    epoch_loss = running_loss / len(dataloader)
    epoch_accuracy = running_accuracy / (len(dataloader.dataset))
    return epoch_time, epoch_loss, epoch_accuracy, roc_auc_score(all_labels, all_prob), all_prob


def test(model, dataloader):
    """
    Test the accuracy of a model on some labelled test dataset.
    Args:
        model: The torch module on which testing must be performed.
        dataloader: A DataLoader object to iterate over some dataset.
    Returns:
        batch_time: The average time to predict the classes of a batch.
        total_time: The total time to process the whole dataset.
        accuracy: The accuracy of the model on the input data.
        all_prob: The probability of classification as label 1 on the entire validation set.
    """
    # Switch the model to eval mode.
    model.eval()
    device = model.device
    time_start = time.time()
    batch_time = 0.0
    accuracy = 0.0
    all_prob = []
    all_labels = []
    # Deactivate autograd for evaluation.
    with torch.no_grad():
        for (batch_seqs, batch_seq_masks, batch_seq_segments, batch_labels) in dataloader:
            batch_start = time.time()
            # Move input and output data to the GPU if one is used.
            seqs, masks, segments, labels = batch_seqs.to(device), batch_seq_masks.to(device), batch_seq_segments.to(device), batch_labels.to(device)
            _, _, probabilities = model(seqs, masks, segments, labels)
            accuracy += correct_predictions(probabilities, labels)
            batch_time += time.time() - batch_start
            all_prob.extend(probabilities[:,1].cpu().numpy())
            all_labels.extend(batch_labels)
    batch_time /= len(dataloader)
    total_time = time.time() - time_start
    accuracy /= (len(dataloader.dataset))

    return batch_time, total_time, accuracy, all_prob

import torch
from torch import nn
from transformers import (
    BertForSequenceClassification,
    AlbertForSequenceClassification,  
    AutoTokenizer
)


class AlbertModel(nn.Module):
    def __init__(self, requires_grad = True):
        super(AlbertModel, self).__init__()
        self.albert = AlbertForSequenceClassification.from_pretrained('albert-xxlarge-v2', num_labels = 2)
        self.tokenizer = AutoTokenizer.from_pretrained('albert-xxlarge-v2', do_lower_case=True)
        self.requires_grad = requires_grad
        self.device = torch.device("cuda")
        for param in self.albert.parameters():
            param.requires_grad = True  # Each parameter requires gradient

    def forward(self, batch_seqs, batch_seq_masks, batch_seq_segments, labels):
        loss, logits = self.albert(input_ids = batch_seqs, attention_mask = batch_seq_masks, 
                              token_type_ids=batch_seq_segments, labels = labels)[:2]
        probabilities = nn.functional.softmax(logits, dim=-1)
        return loss, logits, probabilities
        
     
        
class BertModel(nn.Module):
    def __init__(self, requires_grad = True):
        super(BertModel, self).__init__()
        self.bert = BertForSequenceClassification.from_pretrained('textattack/bert-base-uncased-SST-2',num_labels = 2)
        self.tokenizer = AutoTokenizer.from_pretrained('textattack/bert-base-uncased-SST-2', do_lower_case=True)
        self.requires_grad = requires_grad
        self.device = torch.device("cuda")
        for param in self.bert.parameters():
            param.requires_grad = requires_grad  # Each parameter requires gradient

    def forward(self, batch_seqs, batch_seq_masks, batch_seq_segments, labels):
        loss, logits = self.bert(input_ids = batch_seqs, attention_mask = batch_seq_masks, 
                              token_type_ids=batch_seq_segments, labels = labels)[:2]
        probabilities = nn.functional.softmax(logits, dim=-1)
        return loss, logits, probabilities

torch.cuda.memory_summary(device=None, abbreviated=False)

import torch
    torch.cuda.empty_cache()

import os
import pandas as pd
import torch
from torch.utils.data import DataLoader
from transformers import get_linear_schedule_with_warmup
from transformers.optimization import AdamW
from sys import platform

def model_train_validate_test(train_df, dev_df, test_df, target_dir, 
         max_seq_len=50,
         epochs=3,
         batch_size=32,
         lr=2e-05,
         patience=1,
         max_grad_norm=10.0,
         if_save_model=True,
         checkpoint=None):
    """
    Parameters
    ----------
    train_df : pandas dataframe of train set.
    dev_df : pandas dataframe of dev set.
    test_df : pandas dataframe of test set.
    target_dir : the path where you want to save model.
    max_seq_len: the max truncated length.
    epochs : the default is 3.
    batch_size : the default is 32.
    lr : learning rate, the default is 2e-05.
    patience : the default is 1.
    max_grad_norm : the default is 10.0.
    if_save_model: if save the trained model to the target dir.
    checkpoint : the default is None.

    """
    bertmodel = AlbertModel(requires_grad = True)
    tokenizer = bertmodel.tokenizer
    
    print(20 * "=", " Preparing for training ", 20 * "=")
    # Path to save the model, create a folder if not exist.
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    # -------------------- Data loading --------------------------------------#
    
    print("\t* Loading training data...")
    train_data = DataPrecessForSentence(tokenizer, train_df, max_seq_len = max_seq_len)
    train_loader = DataLoader(train_data, shuffle=True, batch_size=batch_size)

    print("\t* Loading validation data...")
    dev_data = DataPrecessForSentence(tokenizer,dev_df, max_seq_len = max_seq_len)
    dev_loader = DataLoader(dev_data, shuffle=True, batch_size=batch_size)
    
    print("\t* Loading test data...")
    test_data = DataPrecessForSentence(tokenizer,test_df, max_seq_len = max_seq_len) 
    test_loader = DataLoader(test_data, shuffle=False, batch_size=batch_size)
    
    # -------------------- Model definition ------------------- --------------#
    
    print("\t* Building model...")
    device = torch.device("cuda")
    model = bertmodel.to(device)
    
    # -------------------- Preparation for training  -------------------------#
    
    param_optimizer = list(model.named_parameters())
    no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
    optimizer_grouped_parameters = [
            {
                    'params':[p for n, p in param_optimizer if not any(nd in n for nd in no_decay)],
                    'weight_decay':0.01
            },
            {
                    'params':[p for n, p in param_optimizer if any(nd in n for nd in no_decay)],
                    'weight_decay':0.0
            }
    ]
    optimizer = AdamW(optimizer_grouped_parameters, lr=lr)

    ## Implement of warm up
    ## total_steps = len(train_loader) * epochs
    ## scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=60, num_training_steps=total_steps)
    
    # When the monitored value is not improving, the network performance could be improved by reducing the learning rate.
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.85, patience=0)

    best_score = 0.0
    start_epoch = 1
    # Data for loss curves plot
    epochs_count = []
    train_losses = []
    train_accuracies = []
    valid_losses = []
    valid_accuracies = []
    valid_aucs = []
    
    # Continuing training from a checkpoint if one was given as argument
    if checkpoint:
        checkpoint = torch.load(checkpoint)
        start_epoch = checkpoint["epoch"] + 1
        best_score = checkpoint["best_score"]
        print("\t* Training will continue on existing model from epoch {}...".format(start_epoch))
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        epochs_count = checkpoint["epochs_count"]
        train_losses = checkpoint["train_losses"]
        train_accuracy = checkpoint["train_accuracy"]
        valid_losses = checkpoint["valid_losses"]
        valid_accuracy = checkpoint["valid_accuracy"]
        valid_auc = checkpoint["valid_auc"]
        
     # Compute loss and accuracy before starting (or resuming) training.
    _, valid_loss, valid_accuracy, auc, _, = validate(model, dev_loader)
    print("\n* Validation loss before training: {:.4f}, accuracy: {:.4f}%, auc: {:.4f}".format(valid_loss, (valid_accuracy*100), auc))
    
    # -------------------- Training epochs -----------------------------------#
    
    print("\n", 20 * "=", "Training bert model on device: {}".format(device), 20 * "=")
    patience_counter = 0
    for epoch in range(start_epoch, epochs + 1):
        epochs_count.append(epoch)

        print("* Training epoch {}:".format(epoch))
        epoch_time, epoch_loss, epoch_accuracy = train(model, train_loader, optimizer, epoch, max_grad_norm)
        train_losses.append(epoch_loss)
        train_accuracies.append(epoch_accuracy)  
        print("-> Training time: {:.4f}s, loss = {:.4f}, accuracy: {:.4f}%".format(epoch_time, epoch_loss, (epoch_accuracy*100)))
        
        print("* Validation for epoch {}:".format(epoch))
        epoch_time, epoch_loss, epoch_accuracy , epoch_auc, _, = validate(model, dev_loader)
        valid_losses.append(epoch_loss)
        valid_accuracies.append(epoch_accuracy)
        valid_aucs.append(epoch_auc)
        print("-> Valid. time: {:.4f}s, loss: {:.4f}, accuracy: {:.4f}%, auc: {:.4f}\n"
              .format(epoch_time, epoch_loss, (epoch_accuracy*100), epoch_auc))
        
        # Update the optimizer's learning rate with the scheduler.
        scheduler.step(epoch_accuracy)
        ## scheduler.step()
        
        # Early stopping on validation accuracy.
        if epoch_accuracy < best_score:
            patience_counter += 1
        else:
            best_score = epoch_accuracy
            patience_counter = 0
            if (if_save_model):
                  torch.save({"epoch": epoch, 
                           "model": model.state_dict(),
                           "optimizer": optimizer.state_dict(),
                           "best_score": best_score,
                           "epochs_count": epochs_count,
                           "train_losses": train_losses,
                           "train_accuracy": train_accuracies,
                           "valid_losses": valid_losses,
                           "valid_accuracy": valid_accuracies,
                           "valid_auc": valid_aucs
                           },
                           os.path.join(target_dir, "best.pth.tar"))
                  print("save model succesfully!\n")
            
            # run model on test set and save the prediction result to csv
            print("* Test for epoch {}:".format(epoch))
            _, _, test_accuracy, _, all_prob = validate(model, test_loader)
            print("Test accuracy: {:.4f}%\n".format(test_accuracy))
            test_prediction = pd.DataFrame({'prob_1':all_prob})
            test_prediction['prob_0'] = 1-test_prediction['prob_1']
            test_prediction['prediction'] = test_prediction.apply(lambda x: 0 if (x['prob_0'] > x['prob_1']) else 1, axis=1)
            test_prediction = test_prediction[['prob_0', 'prob_1', 'prediction']]
            test_prediction.to_csv(os.path.join(target_dir,"test_prediction.csv"), index=False)
             
        if patience_counter >= patience:
            print("-> Early stopping: patience limit reached, stopping...")
            break


def model_load_test(test_df, target_dir, test_prediction_dir, test_prediction_name, max_seq_len=50, batch_size=32):
    """
    Parameters
    ----------
    test_df : pandas dataframe of test set.
    target_dir : the path of pretrained model.
    test_prediction_dir : the path that you want to save the prediction result to.
    test_prediction_name : the file name of the prediction result.
    max_seq_len: the max truncated length.
    batch_size : the default is 32.
    
    """
    bertmodel = AlbertModel(requires_grad = False)
    tokenizer = bertmodel.tokenizer
    device = torch.device("cuda")
    
    print(20 * "=", " Preparing for testing ", 20 * "=")
    if platform == "linux" or platform == "linux2":
        checkpoint = torch.load(os.path.join(target_dir, "best.pth.tar"))
    else:
        checkpoint = torch.load(os.path.join(target_dir, "best.pth.tar"), map_location=device)
        
    print("\t* Loading test data...")    
    test_data = DataPrecessForSentence(tokenizer,test_df, max_seq_len = max_seq_len) 
    test_loader = DataLoader(test_data, shuffle=False, batch_size=batch_size)

    # Retrieving model parameters from checkpoint.
    print("\t* Building model...")
    model = bertmodel.to(device)
    model.load_state_dict(checkpoint["model"])
    print(20 * "=", " Testing BERT model on device: {} ".format(device), 20 * "=")
    
    batch_time, total_time, accuracy, all_prob = test(model, test_loader)
    print("\n-> Average batch processing time: {:.4f}s, total test time: {:.4f}s, accuracy: {:.4f}%\n".format(batch_time, total_time, (accuracy*100)))
    
    test_prediction = pd.DataFrame({'prob_1':all_prob})
    test_prediction['prob_0'] = 1-test_prediction['prob_1']
    test_prediction['prediction'] = test_prediction.apply(lambda x: 0 if (x['prob_0'] > x['prob_1']) else 1, axis=1)
    test_prediction = test_prediction[['prob_0', 'prob_1', 'prediction']]
    if not os.path.exists(test_prediction_dir):
        os.makedirs(test_prediction_dir)
    test_prediction.to_csv(os.path.join(test_prediction_dir, test_prediction_name), index=False)


if __name__ == "__main__":
    data_path = "/content/drive/MyDrive/BPM_FC_RC"
    train_df = pd.read_csv(os.path.join(data_path,"train.txt"),sep='\t',header=None, names=['similarity','p1', str('p2'), str('p3')])
    dev_df = pd.read_csv(os.path.join(data_path,"dev.txt"),sep='\t',header=None, names=['similarity','p1', str('p2'), str('p3')])
    test_df = pd.read_csv(os.path.join(data_path,"test.txt"),sep='\t',header=None, names=['similarity','p1', str('p2'), str('p3')])
    target_dir = "/content/drive/MyDrive/BPM_FC_RC"
    model_train_validate_test(train_df, dev_df, test_df, target_dir)

import pandas as pd
import os

data_path = "/content/drive/MyDrive/BPM_FC_RC"
train_df = pd.read_csv(os.path.join(data_path,"train.txt"),sep='\t',header=None, names=['similarity','p1', str('p2'), str('p3')])
dev_df = pd.read_csv(os.path.join(data_path,"dev.txt"),sep='\t',header=None, names=['similarity','p1', str('p2'), str('p3')])
test_df = pd.read_csv(os.path.join(data_path,"test.txt"),sep='\t',header=None, names=['similarity','p1', str('p2'), str('p3')])
target_dir = "/content/drive/MyDrive/BPM_FC_RC"

model_train_validate_test(train_df, dev_df, test_df, target_dir, 
         max_seq_len=50,
         epochs=3,
         batch_size=32,
         lr=2e-05,
         patience=1,
         max_grad_norm=10.0,
         if_save_model=True,
         checkpoint=None)

test_result = pd.read_csv(os.path.join(target_dir, 'test_prediction.csv'))
Metric(test_df.similarity, test_result.prediction)