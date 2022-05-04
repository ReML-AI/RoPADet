import os
import torch
from torch.utils.data import Dataset, DataLoader
from fairseq import checkpoint_utils, data, options, tasks
from fairseq.data import MelAudioDataset, AddTargetDataset, Dictionary
from fairseq.data.text_compressor import TextCompressionLevel, TextCompressor
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, confusion_matrix, roc_auc_score, auc, precision_recall_curve, roc_curve, average_precision_score, accuracy_score, precision_recall_fscore_support
from collections import defaultdict


def load_dataset(X, file_path, dir_path, label, id, offset=4):
    X[file_path] = X[file_path].apply(lambda x: dir_path + str(x))
    if offset == 0:
        feats = list(X[file_path].apply(lambda x: np.load(x + '_mel_2048_128.npy')).values)
    else:
        feats = list(X[file_path].apply(lambda x: np.load(x[:-offset] + '_mel_2048_128.npy')).values)

    return feats, X[label].values, X[id].values


def collate_fn(data):
    """
       data: is a list of tuples with (example, label, length)
             where 'example' is a tensor of arbitrary shape
             and label/length are scalars
    """
    ids, _, labels, lengths = zip(*data)
    max_len = max(lengths)
    n_ftrs = data[0][1].shape[0]
    features = torch.zeros((len(data), n_ftrs, max_len))
    labels = torch.tensor(labels)
    # lengths = torch.tensor(lengths)
    lengths = torch.zeros((len(data), max_len))

    for i in range(len(data)):
        j, k = data[i][1].shape[0], data[i][1].shape[1]
        # print(torch.from_numpy(data[i][0]).shape)
        # print(torch.zeros((j, max_len - k)).shape)
        features[i] = torch.cat([torch.from_numpy(data[i][1]), torch.zeros((j, max_len - k))], dim=1)
        lengths[i][:k] = 1

    return ids, features.float(), labels.long(), lengths.long()


class MyDataset(Dataset):
    def __init__(self, ids, data, targets):
        self.ids = ids
        self.data = data
        self.targets = torch.from_numpy(targets)

    def __getitem__(self, index):
        id = self.ids[index]
        x = self.data[index]
        y = self.targets[index]

        return id, x, y, x.shape[1]

    def __len__(self):
        return len(self.data)


# Parse command-line arguments for generation
parser = options.get_generation_parser(default_task='stft_audio_pretraining')
args = options.parse_args_and_arch(parser)


# Setup task
task = tasks.setup_task(args)
# Load model
print(f' | loading model from ${args.path}')
models, _model_args = checkpoint_utils.load_model_ensemble([args.path])
# models, _model_args = checkpoint_utils.load_model_ensemble([args.path], arg_overrides={'data': '/media/SSD/tungtk2/fairseq/data/orig_2048_128_aicovidvn_fold4'})
model = models[0].cuda()

print(model)

# NOTE: For COVID-19 dataset
# X = pd.read_csv('/host/ubuntu/tungtk2/aicovid/aicv115m_api_template/data/coughvid/df_fold.csv')
# coughvid_test_set_inp, coughvid_test_set_out = load_dataset(X[X['fold'] == 3], 'file_path', '/host/ubuntu/tungtk2/aicovid/aicv115m_api_template/data/coughvid/public_dataset/', 'label_covid', offset=5)

# X = pd.read_csv('/host/ubuntu/tungtk2/aicovid/aicv115m_api_template/data/aicv115m_final_public_train/public_train_metadata_fold.csv')
# aicvvn_test_set_inp, aicvvn_test_set_out = load_dataset(X, 'uuid', '/host/ubuntu/tungtk2/aicovid/aicv115m_api_template/data/aicv115m_final_public_train/public_train_audio_files/', 'assessment_result', offset=0)

# X = pd.read_csv('/host/ubuntu/tungtk2/aicovid/aicv115m_api_template/data/coswara/df_fold.csv')
# coswara_test_set_inp, coswara_test_set_out = load_dataset(X, 'file_path', '/host/ubuntu/tungtk2/aicovid/aicv115m_api_template/data/coswara/Coswara-Data_0511/', 'label_covid')

X_aicovidvn_new_min = pd.read_csv('/host/ubuntu/tungtk2/aicovid/aicv115m_api_template/data/aicv_new/assets/df_min.csv')
aicovidvn_new_min_inp, aicovidvn_new_min_out, aicovidvn_new_min_id = load_dataset(X_aicovidvn_new_min, 'file_path', '/host/ubuntu/tungtk2/aicovid/aicv115m_api_template/data/aicv_new/', 'label', 'id')

X_sounddr_min = pd.read_csv('/host/ubuntu/tungtk2/aicovid/aicv115m_api_template/data/sounddr/df_min.csv')
sounddr_min_inp, sounddr_min_out, sounddr_min_id = load_dataset(X_sounddr_min, 'file_path', '/host/ubuntu/tungtk2/aicovid/aicv115m_api_template/data/sounddr/', 'label', 'id')


# test_set_inp = [*coughvid_test_set_inp, *aicvvn_test_set_inp, *coswara_test_set_inp]
# test_set_out = np.concatenate((coughvid_test_set_out, aicvvn_test_set_out, coswara_test_set_out))

'''
# NOTE: PROFILING
def map_age(age):
    groups = [[0, 2], [3, 5], [6, 13], [14, 18], [19, 33], [34, 48], [49, 64], [65, 78], [79, 98]]
    for group in groups:
        if group[0] <= age <= group[1]:
            return f'group_{group[0]}_{group[1]}'
    print(age)
X['a'] = X['a'].apply(map_age)

def create_profile(row):
    age = row['a']
    gender = row['g']
    phase = 'train' if row['fold'] in [0, 1, 2] else 'valid' if row['fold'] == 3 else 'test'
    return age + '_' + gender + '_' + phase
def create_profile_by_id(row):
    id = row['id']
    phase = 'train' if row['fold'] in [1, 2, 3] else 'valid' if row['fold'] == 4 else 'test'
    return id + '_' + phase
X['profile'] = X.apply(create_profile_by_id, axis=1)

ids = list(X['profile'])
'''

test_set_inp = [*aicovidvn_new_min_inp, *sounddr_min_inp]
test_set_out = np.concatenate((aicovidvn_new_min_out, sounddr_min_out))
test_set_id = np.concatenate((aicovidvn_new_min_id, sounddr_min_id))

test_dataset = MyDataset(test_set_id, test_set_inp, test_set_out)
dataloader = DataLoader(test_dataset, batch_size=1, shuffle=False, num_workers=4, collate_fn=collate_fn)

model.eval()

profiles = defaultdict(list)

for ids, inputs, labels, lengths in dataloader:
    inputs = inputs.to('cuda', dtype=torch.float)
    labels = labels.to('cuda')
    lengths = lengths.unsqueeze(dim=1).to('cuda')

    with torch.no_grad():
        outs = model(inputs, lengths, features_only=True)

    outputs = outs['x']
    outputs = outputs.squeeze()
    outputs = torch.mean(outputs, dim=0)
    # print(outputs)
    # NOTE: only works for batch size = 1
    profiles[ids[0]].append(outputs)

# counter = defaultdict(int)
# for key, val in profiles.items():
#     counter[len(val)] += 1

count = 0
for key, val in profiles.items():
    # if len(val) > 1:
    #     print(key, len(val))
    print(key, len(val))
    count += len(val)
    profiles[key] = torch.mean(torch.stack(val), dim=0)
print(count)

SAVE_PATH = args.path[:args.path.rfind('/')] + '/profile.pt'
print("Saving profiles to: ", SAVE_PATH)
# print(counter)

torch.save(profiles, SAVE_PATH)
