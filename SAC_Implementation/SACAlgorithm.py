import logging

import torch

import LogHelper
from SAC_Implementation.Networks import *
from SAC_Implementation.ReplayBuffer import ReplayBuffer


def initialize_nets_and_buffer(state_dim: int,
                               action_dim: int,
                               q_hidden: int,
                               policy_hidden: int,
                               learning_rates: dict,
                               replay_buffer_size: int,
                               gpu_device: int
                               ) -> (
        SoftQNetwork, SoftQNetwork, SoftQNetwork, SoftQNetwork, PolicyNetwork, ReplayBuffer):
    """
    Method to initialize the neural networks as well as the replay buffer
    :param state_dim: Dimension of the state space
    :param action_dim: Dimension of the action space
    :param q_hidden: Hidden Size of the Q networks
    :param policy_hidden: Hidden Size of the Policy Network
    :param learning_rates: Learning Rates in an dict with keys "critic"(q-networks) and "actor"(policy)
    :param replay_buffer_size: Size of the replayBuffer
    :return: Returns the networks (Soft1, soft2, target1,target2, Policy, Buffer)
    """
    # We need to networks: 1 for the value function first
    soft_q1 = SoftQNetwork(state_dim, action_dim, q_hidden, learning_rates.get('critic'), gpu_device)
    soft_q2 = SoftQNetwork(state_dim, action_dim, q_hidden, learning_rates.get('critic'), gpu_device)

    # Then another one for calculating the targets
    soft_q1_targets = SoftQNetwork(state_dim, action_dim, q_hidden, learning_rates.get('critic'), gpu_device)
    soft_q2_targets = SoftQNetwork(state_dim, action_dim, q_hidden, learning_rates.get('critic'), gpu_device)

    policy = PolicyNetwork(state_dim, action_dim, policy_hidden, learning_rates.get('actor'), gpu_device)

    # Initialize the Replay Buffer
    buffer = ReplayBuffer(state_dim, action_dim,
                          replay_buffer_size)

    return soft_q1, soft_q2, soft_q1_targets, soft_q2_targets, policy, buffer


class SACAlgorithm:
    def __init__(self, env, param: dict):
        """

        :param env:
        :param param: dict which needs following parameter:
            [hidden_dim, lr_critic, lr_policy, alpha, tau, gamma, sample_batch_size]
        """

        self.action_dim = env.action_space.shape[0]
        self.state_dim = env.observation_space.shape[0]
        self.device = torch.device(f'cuda:{param.get("gpu_device")}' if torch.cuda.is_available() else 'cpu')

        self.soft_q1, self.soft_q2, self.soft_q1_targets, self.soft_q2_targets, self.policy, self.buffer = initialize_nets_and_buffer(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            q_hidden=param.get('hidden_dim'),
            policy_hidden=param.get('hidden_dim'),
            learning_rates={
                'critic': param.get('lr_critic'),
                'actor': param.get('lr_actor')
            },
            replay_buffer_size=param.get('replay_buffer_size'),
            gpu_device=param.get('gpu_device')
        )
        self.sample_batch_size, self.alpha, self.tau, self.gamma = (param.get('sample_batch_size'),
                                                                    param.get('alpha'),
                                                                    param.get('tau'),
                                                                    param.get('gamma'))

    def _update_critic(self, state, action, y_hat):
        q1_forward = self.soft_q1(state.float(), action.float())
        q2_forward = self.soft_q2(state.float(), action.float())

        # Q1 Network
        q_loss = F.mse_loss(q1_forward.float(), y_hat.float().to(device=self.device)) +\
                 F.mse_loss(q2_forward.float(), y_hat.float().to(device=self.device))

        self.soft_q1.optimizer.zero_grad()
        self.soft_q2.optimizer.zero_grad()
        q_loss.backward()
        self.soft_q1.optimizer.step()
        self.soft_q2.optimizer.step()
        return q_loss

    def _calculate_target(self, state, action):
        y_hat_q1 = self.soft_q1_targets(state.float(), action.float())
        y_hat_q2 = self.soft_q2_targets(state.float(), action.float())
        return torch.min(y_hat_q1, y_hat_q2)

    def _update_policy(self, state):
        action_new, action_entropy_new = self.policy.sample(torch.Tensor(state))
        q1_forward = self.soft_q1(state.float(), action_new.float())
        q2_forward = self.soft_q2(state.float(), action_new.float())
        q_forward = torch.min(q1_forward, q2_forward)

        # Changed to an F.mse_loss from simple mean
        # policy_loss = F.mse_loss((self.alpha * action_entropy_new), q_forward)
        policy_loss = torch.abs((q_forward-(self.alpha * action_entropy_new)).mean())

        self.policy.zero_grad()
        policy_loss.backward()
        self.policy.optimizer.step()

        return policy_loss

    def update(self):

        # Sample from Replay buffer
        state, action, reward, new_state, done, _ = self.buffer.sample(batch_size=self.sample_batch_size)

        # Computation of targets
        # Here we are using 2 different Q Networks and afterwards choose the lower reward as regulator.
        action, action_entropy = self.policy.sample(torch.Tensor(new_state))

        y_hat_q = self._calculate_target(state, action)

        # We calculate the estimated reward for the next state
        # DISCOUNT FACTOR
        y_hat = reward + self.gamma * (1 - done) * (y_hat_q.cpu().data.numpy() - action_entropy.cpu().data.numpy())

        # # UPDATES OF THE CRITIC NETWORKS
        q_loss = self._update_critic(state, action, y_hat)

        # Update Policy Network (ACTOR)
        policy_loss = self._update_policy(state)

        self.soft_q1_targets.update_params(self.soft_q1.state_dict(), self.tau)
        self.soft_q2_targets.update_params(self.soft_q2.state_dict(), self.tau)

        # for graph
        return policy_loss.item(), q_loss.item()

    def sample_action(self, state: torch.Tensor):
        action, log_pi = self.policy.sample(state)
        return action.detach(), log_pi