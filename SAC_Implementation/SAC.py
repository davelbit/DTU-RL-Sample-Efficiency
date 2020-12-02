## Imports

import pickle
import sys
from datetime import datetime
from typing import Dict

import numpy as np


import torch

from SAC_Implementation.SACAlgorithm import SACAlgorithm
from plotter import Plotter

from hyperopt import fmin, tpe, space_eval, Trials, STATUS_OK

import logging
import dmc2gym
import LogHelper
from SAC_Implementation.ReplayBuffer import ReplayBuffer
from SAC_Implementation.Networks import SoftQNetwork, PolicyNetwork


def initialize_environment(domain_name, task_name, seed, frame_skip):
    # env = dmc2gym.make(domain_name="walker",
    #                    task_name="walk",
    #                    seed=1,
    #                    frame_skip=1)

    LogHelper.print_step_log(f"Initialize Environment: {domain_name}/{task_name} ...")

    env = dmc2gym.make(domain_name=domain_name,
                       task_name=task_name,
                       seed=seed,
                       frame_skip=frame_skip)

    # Debug logging to check environment specs
    s = env.reset()
    a = env.action_space.sample()
    action_dim = env.action_space.shape[0]
    state_dim = env.observation_space.shape[0]

    logging.debug(f'Sample state: {s}')
    logging.debug(f'Sample action:{a}')
    logging.debug(f'State DIM: {state_dim}')
    logging.debug(f'Action DIM:{action_dim}')

    return env, action_dim, state_dim


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

def prepare_hyperparameter_tuning(hyperparameter_space, max_evals=2):
    try:
        trials = Trials()
        best = fmin(run_sac,
                    hyperparameter_space,
                    algo=tpe.suggest,
                    trials=trials,
                    max_evals=max_evals)

        logging.info("WE ARE DONE. THE BEST TRIAL IS:")
        LogHelper.print_dict({**hyperparameter_space, **best}, "Final Parameters")

        filename = datetime.now().strftime("%d_%m_%Y-%H_%M_%S")
        file_path = f"results/hp_result_{filename}.model"
        with open(file_path, 'wb') as f:
            pickle.dump(trials.results, f)
        f.close()
        logging.info("--------------------------------------------")
        logging.info(f"For more information see {file_path}")
        # return run_sac(hyperparameter_space)
    except KeyboardInterrupt as e:
        logging.error("KEYBOARD INTERRUPT")
        raise


def run_sac(hyperparameter_space: dict, video) -> Dict:
    """
    Method to to start the SAC algorithm on a certain problem
    :param video: video object
    :param hyperparameter_space: Dict with the hyperparameter from the Argument parser
    :return:
    """
    LogHelper.print_big_log('Initialize Hyperparameter')

    # Print the hyperparameters
    # Initialize the environment
    env, action_dim, state_dim = initialize_environment(domain_name=hyperparameter_space.get('env_domain'),
                                                        task_name=hyperparameter_space.get('env_task'),
                                                        seed=hyperparameter_space.get('seed'),
                                                        frame_skip=hyperparameter_space.get('frame_skip'))

    LogHelper.print_dict(hyperparameter_space, "Hyperparameter")
    LogHelper.print_big_log("Start Training")
    logging.debug(hyperparameter_space)
    sac = SACAlgorithm(env=env,
                       param={
                           "hidden_dim": hyperparameter_space.get('hidden_dim'),
                           "lr_critic": hyperparameter_space.get('lr_critic'),
                           "lr_actor": hyperparameter_space.get('lr_actor'),
                           "alpha": hyperparameter_space.get('alpha'),
                           "tau": hyperparameter_space.get('tau'),
                           "gamma": hyperparameter_space.get('gamma'),
                           "sample_batch_size": hyperparameter_space.get('sample_batch_size'),
                           "replay_buffer_size": hyperparameter_space.get('replay_buffer_size'),
                           "gpu_device": hyperparameter_space.get('gpu_device')
                       })

    # Init the Plotter
    plotter = Plotter(hyperparameter_space.get('episodes'))
    # initialize video

    video.init()
    recording_interval = hyperparameter_space.get('recording_interval')
    try:
        for _episode in range(hyperparameter_space.get('episodes')):

            # for graph
            ep_reward, policy_loss_incr, q_loss_incr, length = 0, 0, 0, 0
            logging.debug(f"Episode {_episode + 1}")

            # Observe state and action
            current_state = env.reset()
            logging.debug(f"Max Steps {hyperparameter_space.get('max_steps')}")



            for step in range(10000):  # range(hyperparameter_space.get('max_steps')):
                # Do the next step
                logging.debug(f"Episode {_episode + 1} | step {step}")

                if _episode > 10:
                    action_mean, _ = sac.sample_action(torch.Tensor(current_state))
                else:
                    action_mean = env.action_space.sample()

                logging.debug(f"Our action we chose is : {action_mean}")
                logging.debug(f"The state is : {current_state}")
                logging.debug(f"Our action we chose is : {action_mean}")
                #s1, r, done, _ = env.step(np.array(action_mean))
                # print("######################################")
                # logging.debug(action_mean)
                # print("######################################")
                s1, r, done, _ = env.step(np.array(action_mean))

                logging.debug(f"The reward we got is {r} | {done}")
                sac.buffer.add(obs=current_state,
                               action=action_mean,
                               reward=r,
                               next_obs=s1,
                               done=done)
                ep_reward += r

                _metric = sac.update()

                policy_loss_incr += _metric[0]
                q_loss_incr += _metric[1]
                length = step

                # Update current step
                current_state = s1

                if _episode % recording_interval == 0:
                    video.record(env)

                if bool(done):
                    logging.debug("Annd we are dead##################################################################")

                    break

            if _episode % recording_interval == 0:
                video.save(_episode)
                video.reset()


            # for graph
            plotter.add_to_lists(reward=ep_reward,
                                 length=length,
                                 policy_loss=policy_loss_incr,
                                 q_loss=q_loss_incr)

            if _episode % 5 == 0:
                logging.info(f"EPISODE {str(_episode).ljust(4)} | reward {ep_reward:.4f} | policy-loss {policy_loss_incr:.4f}")



    except KeyboardInterrupt as e:
        logging.error("KEYBOARD INTERRUPT")
        raise
    finally:
        plotter.plot()


    rew, _, q_losses, policy_losses = plotter.get_lists()

    # Give back the error which should be optimized by the hyperparameter tuner
    max_reward = max(np.array(rew))
    return {'loss': -max_reward,
            'status': STATUS_OK,
            'model': sac,
            'max_reward': max_reward,
            'q_losses': q_losses,
            'policy_losses': policy_losses,
            'rewards': rew}
