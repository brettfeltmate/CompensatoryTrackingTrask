# CompTrack.py
# Brett Feltmate, 2021
# A reformulation of http://github.com/jmwmulle/PVTarget

# Presents a cursor/target which is horizontally buffeted by
# an undulating sinusoidal function. User, via mouse input,
# is tasked to maintain cursor position at screen center.

# At psuedo-random points a PVT counter is presented centre-screen
# to which to user must halt via pressing spacebar.

# Class functionality will eventually be expanded to allow for:
#  - dynamically setting difficulty conditional on PVT performance
#  - presenting alerting signals either randomly or conditionally

import copy
from random import randrange

import numpy as np
import sdl2
from klibs.KLCommunication import *
from klibs.KLConstants import *
from klibs.KLEnvironment import EnvAgent
from klibs.KLGraphics.KLDraw import *
from klibs.KLUtilities import *

sdl2.SDL_SetRelativeMouseMode(sdl2.SDL_TRUE)


class CompTrack(EnvAgent):

    def __init__(self):
        super(CompTrack, self).__init__()
        self.__init_time = now()
        self.x = P.screen_c[0]
        self.do_pvt = False
        self.pvt_start = None
        self.counter = 0

        # target position can't exceed a margin of half it's width from either screen edge
        self.x_bounds = [
            int(0.5 * self.exp.metrics['target_frame_w'][1]),
            int(P.screen_x - 0.5 * self.exp.metrics['target_frame_w'][1])
        ]

        self.txtm.add_style('target', self.exp.metrics['target_h'][1], self.exp.palette['red'])
        self.txtm.add_style('target_digits', self.exp.metrics['target_h'][1] * .75, self.exp.palette['white'])

        self.assets = {}
        self.assets['target'] = message('XXX', 'target', blit_txt=False)
        self.assets['target_wrapper'] = Rectangle(
            width=self.exp.metrics['target_frame_w'][1],
            height=self.exp.metrics['target_frame_h'][1],
            stroke=[2, self.exp.palette['red'], STROKE_OUTER]
        ).render()

        self.assets['fixation'] = Circle(diameter=self.exp.metrics['fixation_radius'][1],
                                         fill=self.exp.palette['white'])
        self.assets['cursor'] = Circle(diameter=self.exp.metrics['cursor'][1], fill=self.exp.palette['green'])

        modifiers = np.arange(-2.0, 2.0, 0.01)
        modifiers = np.append(modifiers, modifiers[-1:1:-1])
        self.current_modifier = 0

        # dev tool for logically controlling the influences on target velocity; should be removed for prod.
        self.params = {
            'mouse_input': True,
            'modifier_terms': modifiers,
            'acceleration': False,
            'track_input': False,
            'poll_while_moving': True,
            'poll_at_fixation': False,
            'exp_duration': 150,
            'trial_count': 9,
            'trial_interval_bounds': [10, 15],
            'PVT_intervals': [],
            'reset_target_after_poll': True,
            'PVT_event_count': 0
        }

        self.event_data_template = {
            'timestamp': 0,
            'buffeting_force': 0,
            'additional_force': 0,
            'total_force': 0,
            'user_input': 0,
            'displacement': 0,
            'PVT_event': False,
            'PVT_RT': 'NA'
        }

        self.event_data = None

    def __compute_forces(self, ):
        self.event_data['buffeting_force'] = 2 * \
                                             (
                                                     sin(4 * self.event_data['timestamp']) +
                                                     sin(0.3 * (2 * self.event_data['timestamp'])) +
                                                     sin(0.6 * (2 * self.event_data['timestamp'])) +
                                                     sin(0.9 * (2 * self.event_data['timestamp']))
                                             )

        self.event_data['additional_force'] = self.params['modifier_terms'][self.current_modifier] * cos(
            self.event_data['timestamp'])
        self.event_data['total_force'] = self.event_data['buffeting_force'] + self.event_data['additional_force']

        if self.current_modifier == len(self.params['modifier_term']) - 1:
            self.current_modifier = 0
        else:
            self.current_modifier += 1

    def __fetch_response(self, event_queue):
        if not self.do_pvt:
            return

        rt = now() - self.pvt_start
        if rt < 1:
            for event in event_queue:
                if event.type == SDL_KEYDOWN:
                    key = event.key.keysym  # keyboard button event object
                    if key.sym is sdl2.keycode.SDLK_SPACE:
                        self.event_data['PVT_RT'] = rt

        else:
            self.event_data['PVT_RT'] = 'TIMEOUT'

        if self.event_data['PVT_RT'] != 'NA':
            self.do_pvt = False
            if self.params['reset_target_after_poll']:
                self.position = P.screen_c[0]

    def __capture_input(self, event_queue):
        for event in event_queue:
            if event.type == sdl2.SDL_MOUSEMOTION:
                if -7 < event.motion.xrel < 7:
                    self.event_data['user_input'] = event.motion.xrel
                elif event.motion.xrel < -7:
                    self.event_data['user_input'] = -7
                else:
                    self.event_data['user_input'] = 7

                # elapsed = (now() - self.__init_time) - self.get_last_entry('timestamp')
                # try:
                #     self.event_data['user_input'] = event.motion.xrel / power(abs(event.motion.xrel), 1.0 / abs(event.motion.xrel))
                # except ZeroDivisionError:
                #     self.event_data['user_input'] = event.motion.xrel
        # because the mouse cursor is hidden, users can't tell when they've hit the window edge and are no longer
        # moving the cursor despite moving the mouse; so we warp the mouse back to screen center on every pass
        # such that all input translates to capturable cursor activity
        mouse_pos(False, P.screen_c)

    def generate_trials(self):
        interval_count = self.params['trial_count'] + 1  # because trials are bookended by intervals
        min_t, max_t = self.params['trial_interval_bounds'][0], self.params['trial_interval_bounds'][
            1]  # verbosity fail

        if min_t * interval_count > self.params['exp_duration']:
            raise ValueError('Minimum interval between trials too large; cannot be run within experiment duration.')

        # the * 1.0 is to prevent rounding errors
        if self.params['exp_duration'] * 1.0 / max_t > interval_count:
            raise ValueError('Maximum interval between trials too small; all trials will complete too soon.')

        max_t += 1  # otherwise this value can't be returned by randrange() below

        # generate enough intervals for each trial
        self.params['PVT_intervals'] = [randrange(min_t, max_t) for i in range(0, interval_count)]

        # adjust intervals at random, whether over exp_duration or under, until that exact value is reached
        while sum(self.params['PVT_intervals']) < self.params['exp_duration']:
            trial_index = randrange(0, len(self.params['PVT_intervals']))
            if self.params['PVT_intervals'][trial_index] <= self.params['trial_interval_bounds'][1]:
                self.params['PVT_intervals'][trial_index] += 1

        while sum(self.params['PVT_intervals']) > self.params['exp_duration']:
            trial_index = randrange(0, len(self.params['PVT_intervals']))
            if self.params['PVT_intervals'][trial_index] >= self.params['trial_interval_bounds'][0]:
                self.params['PVT_intervals'][trial_index] -= 1

    def __write_data(self):
        self.db.insert(
            {
                'participant_id': P.participant_id,
                'timestamp': self.event_data['timestamp'],
                'buffeting_force': self.event_data['buffeting_force'],
                'additional_force': self.event_data['additional_force'],
                'total_force': self.event_data['total_force'],
                'user_input': self.event_data['user_input'],
                'target_position': self.position,
                'displacement': line_segment_len(P.screen_c, [self.position, P.screen_c[1]]),
                'PVT_event': self.event_data['PVT_event'],
                'PVT_RT': self.event_data['PVT_RT']
            },
            'comp_track_data'
        )

    def refresh(self, event_queue):
        self.event_data = copy.deepcopy(self.event_data_template)
        self.event_data['timestamp'] = now() - self.__init_time

        if self.params['PVT_event_count'] != 0:
            next_PVT_event = sum(self.params['PVT_intervals'][0:self.params['PVT_event_count'] + 1])
        else:
            next_PVT_event = self.params['PVT_intervals'][0]

        if self.event_data['timestamp'] > next_PVT_event and not self.do_pvt:
            self.pvt_start = now()
            self.params['PVT_event_count'] += 1
            self.do_pvt, self.event_data['PVT_event'] = True, True

        self.__fetch_response(event_queue)
        self.__compute_forces()
        self.__refresh(event_queue)

    def __refresh(self, event_queue):
        self.counter += 1
        if self.params['poll_while_moving'] or not self.do_pvt:
            self.__capture_input(event_queue)
            self.position = self.position + self.event_data['total_force'] + self.event_data['user_input']

        self.__write_data()
        self.__render()

    def __render(self):
        target_loc = [self.position, P.screen_c[1]] if not self.do_pvt else P.screen_c

        fill(self.exp.palette['grue'])
        blit(self.assets['fixation'], BL_CENTER, P.screen_c)
        blit(self.assets['target_wrapper'], BL_CENTER, target_loc)

        if self.do_pvt:
            digit_str = str((now() - self.pvt_start) * 1000)[0:4]
            if digit_str[-1] == ".":
                digit_str = digit_str[0:3]
            digits = message(digit_str, 'target_digits', target_loc, flip_screen=False, blit_txt=False)
            blit(digits, BL_CENTER, target_loc)
        else:
            blit(self.assets['target'], BL_CENTER, target_loc)

        flip()

    def get_last_entry(self, column):
        try:
            val = self.db.query(
                "SELECT {0} FROM comp_track_data WHERE ID = (SELECT MAX(ID) AND participant_id = {1} FROM comp_track_data)".format(
                    column, P.participant_id), fetch_all=True)
            return float(val[0][0])
        except IndexError:
            return 0

    @property
    def position(self):
        return self.x

    @position.setter
    def position(self, val):
        if int(val) not in range(*self.x_bounds):
            val = self.x_bounds[0] if val < self.x_bounds[0] else self.x_bounds[1]

        self.x = val