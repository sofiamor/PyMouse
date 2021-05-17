# Object experiment
from typing import Any, Callable

# import numpy as np
from Experiments.VR import *
from Behavior import *
from Stimuli.VROdors import *
from utils.Generator import *

conditions = []

# define session parameters
session_params = {
    'trial_selection'        : 'staircase',
    'reward'                 : 'water',
    'noresponse_intertrial'  : True,
    'resp_cond'              : 'correct_loc',
    'max_reward'             : 3000,
    'staircase_window'       : 10,
    'stair_up'               : 0.7,
    'stair_down'             : 0.6
}

# define environment conditions
key = {
    'init_ready'            : 0,
    'delay_ready'           : 0,
    'resp_ready'            : 0,
    'intertrial_duration'   : 0,
    'response_duration'     : 30000,
    'reward_amount'         : 8,
    'reward_duration'       : 2000,
    'punish_duration'       : 1000,
    'x_max'                 : 10,
    'x_min'                 : 0,
    'y_max'                 : 10,
    'y_min'                 : 0,
}

o_conds = []
o_conds += factorize({**key, 'probe': [1]})

np.random.seed(0)
conditions += factorize({**key,
                        'difficulty'          : 1,
                        'odor_id'             : [[1, 2, 3, 4]],
                        'delivery_port'       : [[1, 2, 3, 4]],
                        'probe'               : 1,
                        'theta0'              : 0,
                        'x0'                  : 5,
                        'y0'                  : 5,
                        'trial_duration'      : 300000,
                        'intertrial_duration' : 0,
                        'fun'                 : 2,
                        'radius'              : 0.3,
                        'small_radius'        : 0.05,
                        'response_duration'   : 240000})


correct_loc = [(7,7)]
resp_loc_x = 7
resp_loc_y = 7


rand_theta = lambda: (np.random.randint(6)* np.pi) / 180
conditions += factorize({**key,
                         'difficulty'          : 2,
                         'odor_id'             : [[3, 4, 1, 2]],
                         'delivery_port'       : [[3, 4, 1, 2]],
                         'probe'               : 1,
                         'theta0'              : [[rand_theta()]],
                         'x0'                  : 5,
                         'y0'                  : 5,
                         'reward_amount'       : 8,
                         'trial_duration'      : 300000,
                         'intertrial_duration' : 0,
                         'fun'                 : 3,
                         'radius'              : 0.2,
                         'small_radius'        : 0.05,
                         'response_duration'   : 240000})

rand_theta = lambda: (np.random.randint(6)* np.pi) / 180
init_position = lambda: np.random.randint(10, size = (1))
conditions += factorize({**key,
                         'difficulty': 3,
                         'odor_id': [[1, 2, 3, 4]],
                         'delivery_port': [[1, 2, 3, 4]],
                         'probe': 1,
                         'theta0': [[rand_theta()]],
                         'x0': [[init_position()]],
                         'y0': [[init_position()]],
                         'reward_amount': 8,
                         'trial_duration': 300000,
                         'intertrial_duration': 0,
                         'fun': 3,
                         'radius': 0.2,
                         'small_radius': 0.05,
                         'response_duration': 240000})

# run experiments
exp = State()
exp.setup(logger, VRBehavior, VROdors, session_params, conditions)
exp.run()


