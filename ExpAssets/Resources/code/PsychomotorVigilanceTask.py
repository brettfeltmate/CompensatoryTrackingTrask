"""
Psychomotor Vigilance Task

Possible params:
    - Total duration
    - ISI range
    - Lapse threshold
    - Threshold for determining hypovigilance

On init:
    - Generates PVT event timestamps
    - Checks to ensure all timestamps fit within total duration
    - adjusts as necessary, likely via trimming

On each PVT trial:
    - Logs RT to respond
    - Labels RT as valid, lapse, or timeout

On finish (potentially):
    - Computes mean RT for session
    - Computes RT SD for session
    - Logs # (or %, or both) of committed lapses
    - Determines if overall PVT performance signals a hypovigilent state

Returns result of hypovigilance decision



"""
from copy import deepcopy
from random import shuffle

import numpy as np
import sdl2
from klibs.KLCommunication import *
from klibs.KLConstants import *
from klibs.KLEnvironment import EnvAgent
from klibs.KLGraphics.KLDraw import *
from klibs.KLUtilities import *

RED = (255, 000, 000)
GRUE = (45, 45, 48)
DIGITS = 'digits'
FRAME = 'frame'
INIT_TIME = 'init_time'
ITI = 'iti'
DURATION = 'duration'
LAPSE_THRESH = 'lapse_threshold'
HYPO_THRESH = 'hypovigilance_threshold'


class PVTask(EnvAgent):


    def __init__(self, duration=None, iti=None, lapse_threshold=None, hypovigilance_threshold=None):

        if duration is None:
            duration = 300
        if iti is None:
            iti = (1, 4)
        if lapse_threshold is None:
            lapse_threshold = 500
        if hypovigilance_threshold is None:
            hypovigilance_threshold = 1

        super(PVTask, self).__init__()

        self.task_params = {
            INIT_TIME: now(),
            DURATION: duration,
            ITI: iti,
            LAPSE_THRESH: lapse_threshold,
            HYPO_THRESH: hypovigilance_threshold
        }

        self.stim_sizes = {
            DIGITS: deg_to_px(1.5),  # height of PVT digits
            FRAME: [deg_to_px(6), deg_to_px(3)]  # width & height of encompassing frame
        }

        # PVT digit font style
        self.txtm.add_style(DIGITS, self.stim_sizes[DIGITS], RED)

        # PVT drawbject
        self.PVT = Rectangle(
            width=self.stim_sizes[FRAME][0],
            height=self.stim_sizes[FRAME][1],
            stroke=[2, RED, STROKE_OUTER]
        ).render()

        self.__run_PVT()


    def __run_PVT(self):
        """
        - Select a random value from range ITI
        - Wait until time equal to value selected elapses
        - Trigger PVT trial
        - Clear display & repeat
        - Log performance to DB as well as internal tally
        - Once full duration has elapsed, assess performance
        """

        self.__assess_performance()


    def __assess_performance(self):
        """
            - iterate over internal tally to compute lapse proportion
            - determine if lapse proportion constitutes hypovigilance


        :return: hypovigilance decision
        """

        return None
