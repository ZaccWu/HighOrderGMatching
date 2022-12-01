import pandas as pd
import numpy as np
import scipy.sparse as sp
import random
import math
import seaborn as sns
import matplotlib.pyplot as plt
import os

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)

def generate_network(uz):
    N = PARAM['num_nodes']
    A_dt = np.eye(N,N)
    for i in range(N):
        for j in range(i + 1, N):
            # use the data except the IDs
            zi, zj = np.array(uz.iloc[i,:]), np.array(uz.iloc[j,:])
            logit = np.exp(PARAM['alpha0'] - PARAM['alpha1'] * np.sqrt(np.square(zi-zj))[0]) * PARAM['network_density']
            friend = np.random.binomial(1, logit / (1 + logit))
            k = np.random.randint(0,N)
            if k == i or k == j:
                continue
            A_dt[i][k], A_dt[k][i], A_dt[j][k], A_dt[k][j] = friend, friend, friend, friend

    network_density.append(((A_dt.sum()-N)*2/(N*(N-1))))
    return pd.DataFrame(A_dt)

def spillover(A, T_binary):
    A = np.array(A)
    A = A - sp.dia_matrix((A.diagonal()[np.newaxis, :], [0]), shape=A.shape) # A-D
    N = len(T_binary) # num of the node
    friend_dict = {}    # dictionary: {'focal_id': [friends' id]}
    for i in range(N):     # construct the t vector for each node
        (col, friend_list) = np.where(A[i]>0)
        friend_dict[str(i)] = friend_list

    fof_dict = {}
    for key, value in friend_dict.items():
        fof = []
        for k in value:
            fof.extend(friend_dict[str(k)])
        fof_dict[key] = list(set(fof))

    spillover_estim = np.zeros(N)
    for j in range(N):
        denom = len(friend_dict[str(j)])
        if denom==0:
            spillover_estim[j] = 0
            continue
        numer_estim = sum(T_binary[fof_dict[str(j)]])
        spillover_estim[j] = numer_estim / denom

    return spillover_estim

def generate_Y(T, spill_estim, Z, set_columns, seed):
    np.random.seed(seed)
    # (1, treat_dim) * (treat_dim, num_nodes) -> (1, num_nodes)
    # Influence = np.matmul(np.array(PARAM['betaT'])[np.newaxis,:], np.array(T).T)
    # (1, featureX_dim) * (featureX_dim, num_nodes) -> (1, num_nodes)
    termZ = np.matmul(np.array(PARAM['betaZ'])[np.newaxis,:], np.array(Z).T)

    Spill = np.array([i*PARAM['beta2'] for i in spill_estim])
    Spill = Spill[np.newaxis,:].T.astype(float)
    eps = np.random.normal(0, PARAM['epsilon'], size=len(T))[np.newaxis,:].T
    Logit = PARAM['beta0'] + PARAM['beta1'] * T + Spill + termZ.T + eps
    # Logit: np.array(num_nodes, 1)
    # adopt_prob = np.exp(Logit)/(1+np.exp(Logit))
    # y_next = np.random.binomial(1, p=adopt_prob)
    y_next = Logit
    y_next.columns = set_columns
    return y_next

# def cal_ave_neighbor_z(z, neighbor):
#     ave_z = np.zeros(PARAM['num_nodes'])
#     for i in range(PARAM['num_nodes']):
#         indices = neighbor[i]
#         ave_neighbor_z = np.mean(z[indices])
#         ave_z[i] = ave_neighbor_z
#     return ave_z

def main():
    # generate the network A
    z = np.random.uniform(0,1,size=PARAM['num_nodes'])
    uz = pd.DataFrame(z, columns=['z'])
    A = generate_network(uz)    # todo: modified network generation
    D = sp.coo_matrix(np.array(A)-np.eye(PARAM['num_nodes']))
    # neighbor = {i: [] for i in range(PARAM['num_nodes'])}
    # for j in range(len(D.col)):
    #     neighbor[D.row[j]].append(D.col[j])
    # zn = cal_ave_neighbor_z(z,neighbor)
    # zn = pd.DataFrame(zn, columns=['zn'])

    A.to_csv(DATA_PATH['Unet'], index=False)   ## TODO: save files
    # generate y0
    # A, B, D, E
    T = pd.DataFrame(np.random.normal(PARAM['betaZ']*(z-0.5), 0.5, size=PARAM['num_nodes']), columns=['y0'])  # y(t-1)
    T_binary = T.copy()
    T_binary[T_binary<0]=0
    T_binary[T_binary>0]=1

    # generate spillover effect
    spillover_estim = spillover(A, np.array(T_binary).T[0])   # (num_nodes, treat_dim)

    # generate y
    y = pd.DataFrame(generate_Y(T_binary, spillover_estim, uz, set_columns=['y'], seed=seed))
    spillover_estim = pd.DataFrame(spillover_estim, columns=['influence_estim'])

    dt_train = pd.concat([uz, T_binary, y, spillover_estim], axis=1)
    dt_train.to_csv(DATA_PATH['save_file'], index=False)   ## TODO: save files


PARAM = {
    # 0. causal graph
    'causal_graph': 'A',

    # 1. net_param
    'alpha0': 0,
    'alpha1': 3,

    # 2. network size and dense
    'network_density': 0.1,
    'num_nodes': 100,

    # 3. network weight
    # describe how the network weights generated by z
    # N-No, U-Uniform, S-Square
    'weight': 'N',

    # All fixed
    'epsilon': 0.5, # fixed
    'beta0': 0,     # fixed
    'beta1': 1,   # fixed
    'beta2': 1,   # fixed
    'betaW': 0,   # 0 if B & C
    'betaZ': [1],  # fixed
}

if __name__ == "__main__":
    data = str(PARAM['causal_graph']) + '_' + str(PARAM['alpha0']) + '_' + str(PARAM['alpha1']) + '_' + str(PARAM['network_density']) + '_' + str(PARAM['num_nodes']) + '_' + str(PARAM['weight'])
    dir_dt = 'data/synthetic_dt/' + data
    if not os.path.isdir(dir_dt):
        os.makedirs(dir_dt)
    network_density = []
    for seed in range(11,21):
        set_seed(seed)
        DATA_PATH = {
            'Unet': dir_dt +'/net_' + str(seed) + '.csv',
            'save_file': dir_dt +'/gendt_' + str(seed) + '.csv',
        }
        print("generate network and data:",seed)
        main()
    print("average edge prob:", np.mean(network_density))