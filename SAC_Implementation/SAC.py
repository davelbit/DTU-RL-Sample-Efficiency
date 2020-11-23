## Imports

from matplotlib import pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F

import json
import gym
from gym import wrappers

import logging

import dmc2gym
import log_helper


def show_replay():
    """
    Not-so-elegant way to display the MP4 file generated by the Monitor wrapper inside a notebook.
    The Monitor wrapper dumps the replay to a local file that we then display as a HTML video object.
    """
    import io
    import base64
    from IPython.display import HTML
    video = io.open('./gym-results/openaigym.video.%s.video000000.mp4' % env.file_infix, 'r+b').read()
    encoded = base64.b64encode(video)
    return HTML(data='''
        <video width="360" height="auto" alt="test" controls><source src="data:video/mp4;base64,{0}" type="video/mp4" /></video>'''
                .format(encoded.decode('ascii')))


def get_variable(x):
    """ Converts tensors to cuda, if available. """
    if torch.cuda.is_available():
        return x.cuda()
    return x


def get_numpy(x):
    """ Get numpy array for both cuda and not. """
    if torch.cuda.is_available():
        return x.cpu().data.numpy()
    return x.data.numpy()


##

def run_sac(hyperparameter_space: dict) -> None:
    """
    Method to to start the SAC algorithm on a certain problem
    :param hyperparameter_space: Dict with the hyperparameter from the Argument parser
    :return:
    """
    log_helper.print_big_log('Initialize Hyperparameter')

    ##
    environment_name = hyperparameter_space.get('env_name')
    #env = gym.make(environment_name)  # Create environment
    env = dmc2gym.make(domain_name="point_mass", task_name="easy", seed=1)

    s = env.reset()
    a = env.action_space.sample()
    logging.debug(f'sample state: {s}')
    logging.debug(f'sample action:{a}')
    ##
    # Hyperparameters
    action_dim = env.action_space.shape[0]
    # TODO Recheck change
    #  I changed it to this line due to an issue with the .shape[0] function
    #  action_dim = env.action_space.shape[0]
    state_dim = env.observation_space.shape[0]

    ##
    logging.debug(f'state shape: {state_dim}')
    logging.debug(f'action shape: {action_dim}')

    hidden_dim = hyperparameter_space.get('hidden_dim')
    learning_rate = hyperparameter_space.get('learning-rate')  # you know this by now
    discount_factor = hyperparameter_space.get('discount_factor')  # reward discount factor (gamma), 1.0 = no discount
    replay_buffer = hyperparameter_space.get('replay_buffer')
    n_hidden_layer = hyperparameter_space.get('n_hidden_layer')
    n_hidden = hyperparameter_space.get('n_hidden')
    target_smoothing = hyperparameter_space.get('target_smoothing')
    val_freq = hyperparameter_space.get('val_freq')  # validation frequency
    episodes = hyperparameter_space.get('episodes')
    # optimizer = optim.Adam(nn.parameters(), lr=learning_rate)

    # Print the hyperparameters
    log_helper.print_dict(hyperparameter_space, "Hyperparameter")
    log_helper.print_big_log("Start Training")

    for _episode in range(episodes):
        logging.debug(f"Episode {_episode}")

        # Observe state and action


        # Execute a in the environment
        # Check if it is terminal -> Save in Replay Buffer
        # ---> Reset if

    """import gym
    env = gym.make("Taxi-v3")
    observation = env.reset()
    for _ in range(1000):
      env.render()
      action = env.action_space.sample() # your agent here (this takes random actions)
      observation, reward, done, info = env.step(action)"""
