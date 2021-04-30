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

from copy import deepcopy
from random import shuffle

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

        #
        # Define styles & create stimuli
        #

        self.palette = {
            'grue': (025, 025, 28),  # mysteriously, leading zero throws a syntax error in last value
            'white': (255, 255, 255),
            'red': (255, 000, 000),
            'green': (000, 255, 000),
            'black': (000, 000, 000)
        }

        stim_size = {
            'cursor': deg_to_px(1),
            'fixation': [deg_to_px(1.4), deg_to_px(0.2)],
            'PVT_frame': [deg_to_px(6), deg_to_px(3)],
            'PVT_digits': deg_to_px(1.5)
        }

        # PVT digit text style
        self.txtm.add_style('PVT_digits', stim_size['PVT_digits'] * .75, self.palette['white'])

        # Visual assets
        self.assets = {
            'fixation': Annulus(
                diameter=stim_size['fixation'][0],
                thickness=stim_size['fixation'][1],
                fill=self.palette['white']
            ),
            'cursor': Circle(
                diameter=stim_size['cursor'],
                fill=self.palette['green']
            ),
            'PVT_frame': Rectangle(
                width=stim_size['PVT_frame'][0],
                height=stim_size['PVT_frame'][1],
                stroke=[2, self.palette['red'], STROKE_OUTER]
                ).render()
        }


        #
        # Initialize task parameters
        #
        self.task_params = {
            'poll_while_moving': True,          # Should PVT events occur during tracking?
            'poll_at_fixation': False,          # Should PVT events occur upon reaching centre?
            'exp_duration': 300,                # Duration of task in seconds
            'PVT_rate': 3,                      # Desired number of PVT events to be sampled from interval_bounds
            'PVT_interval_bounds': [10, 30],    # Set min/max durations that can elapse before next PVT event
            'PVT_timestamps': None,             # List of timepoints at which to present PVT, populated at runtime
            'reset_target_after_poll': True,    # Should cursor be re-centred following a PVT event?
            'x_bounds': [                       # To prevent cursor moving off screen
                int(0.5 * stim_size['cursor']),
                int(P.screen_x - 0.5 * stim_size['cursor'])
            ]
        }

        #
        # Initialize container to store dynamic properties
        #
        self.task_state = {
            'x_pos': P.screen_c[0],     # Stores current x-pos of cursor
            'do_PVT': False,            # When True, PVT is presented on current refresh
            'PVT_start': None,          # Stores timestamp of PVT onset
            'modifier_values': None,    # Populated with values used to generate additional buffeting forces
            'current_modifier': 0,      # Indexes which modifier value is to be used on current refresh
            'PVT_event_count': 0     # Stores running total of PVT events presented
        }

        # Generate modifier values using initial default values
        self.__compute_buffet_modifier_values()

        # Defines template for data recording
        # Each refresh a copy is made, populated, and inserted into database
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

        # Reassigned with copy of data_template on each call to refresh()
        self.event_data = None


    def generate_PVT_timestamps(self):
        # Generates time-points at which to present PVT events

        # Generate geometric sequence of interval durations
        intervals = np.around(
            np.geomspace(
                start=self.task_params['PVT_interval_bounds'][0],
                stop=self.task_params['PVT_interval_bounds'][1],
                num=self.task_params['PVT_rate']  # Desired number of intervals to return
            )
        ).astype(int)

        # Populate timestamps
        self.task_params['PVT_timestamps'] = intervals

        # Keep generating & adding intervals until running sum approaches experiment duration
        while np.sum(self.task_params['PVT_timestamps']) <= (self.task_params['exp_duration'] - np.sum(intervals)):
            self.task_params['PVT_timestamps'] = np.append(self.task_params['PVT_timestamps'], intervals)

        # Psuedo-randomize intervals
        shuffle(self.task_params['PVT_timestamps'])
        # Convert intervals into cumulative sum of preceding values
        self.task_params['PVT_timestamps'] = np.cumsum(self.task_params['PVT_timestamps'])



    def refresh(self, event_queue):
        # Handles event sequence for each refresh, called by experiment.py

        # Init event data container
        self.event_data = deepcopy(self.event_data_template)
        self.event_data['timestamp'] = now() - self.__init_time

        # Determine when next PVT event should occur
        next_PVT_event = self.task_params['PVT_timestamps'][self.task_state['PVT_event_count']] if self.task_state['PVT_event_count'] < len(self.task_params['PVT_timestamps']) else None

        # Determine if PVT event should occur this refresh
        if next_PVT_event is not None:
            if self.event_data['timestamp'] >= next_PVT_event and not self.task_state['do_PVT']:  # Don't do if doing
                self.task_state['PVT_start'] = now()
                self.task_state['PVT_event_count'] += 1
                self.task_state['do_PVT'] = True

        # Listen for PVT response
        self.__fetch_response(event_queue)
        # Compute buffeting forces
        self.__compute_forces()

        # If not PVT event, listen for mouse movement & update position accordingly
        if self.task_params['poll_while_moving'] or not self.task_state['do_PVT']:
            self.__capture_input(event_queue)
            self.position = self.position + self.event_data['total_force'] + self.event_data['user_input']

        # Write trial details to database
        self.__write_data()
        # Render stimuli
        self.__render()

    def __render(self):
        # Renders stimuli to screen

        # Paint & populate display
        fill(self.palette['grue'])

        # TODO: pretty sure I could set via self.assets.cursor.fill

        # Spawn & blit PVT display (if PVT event)
        if self.task_state['do_PVT']:
            digit_str = str((now() - self.task_state['PVT_start']) * 1000)[0:4]
            if digit_str[-1] == ".":
                digit_str = digit_str[0:3]
            digits = message(digit_str, 'PVT_digits', flip_screen=False, blit_txt=False)
            blit(self.assets['PVT_frame'], BL_CENTER, P.screen_c)
            blit(digits, BL_CENTER, P.screen_c)
        else:
            blit(self.assets['fixation'], BL_CENTER, P.screen_c)
            blit(self.assets['cursor'], BL_CENTER, [self.position, P.screen_c[1]])

        # Present display
        flip()


    def __compute_buffet_modifier_values(self, start=-2.0, stop=2.0, step=0.01):
        # Generates cyclical sequence of modifier terms used to generate additional buffeting forces
        modifiers = np.arange(start, stop, step)
        self.task_state['modifier_values'] = np.append(modifiers, modifiers[-1:1:-1])


    def __buffeting_force(self):
        # Generates constant buffeting force
        warren_buffett = 2 * \
         (
             sin(4 * self.event_data['timestamp']) +
             sin(0.3 * (2 * self.event_data['timestamp'])) +
             sin(0.6 * (2 * self.event_data['timestamp'])) +
             sin(0.9 * (2 * self.event_data['timestamp']))
         )
        return warren_buffett


    def __additional_buffeting_force(self):
        # Generates additional buffeting forces
        doris_buffett = self.task_state['modifier_values'][self.task_state['current_modifier']] * cos(self.event_data['timestamp'])

        if self.task_state['current_modifier'] == len(self.task_state['modifier_values']) - 1:
            self.task_state['current_modifier'] = 0
        else:
            self.task_state['current_modifier'] += 1

        return doris_buffett


    def __compute_forces(self):
        # Aggregates buffeting forces for current refresh
        self.event_data['buffeting_force'] = self.__buffeting_force()
        self.event_data['additional_force'] = self.__additional_buffeting_force()
        self.event_data['total_force'] = self.event_data['buffeting_force'] + self.event_data['additional_force']


    def __fetch_response(self, event_queue):
        # Captures PVT responses
        if not self.task_state['do_PVT']:  # Do nothing if nothing need doing
            return

        # Time elapsed since PVT onset
        rt = now() - self.task_state['PVT_start']

        if rt < 1:          # Until 1 sec has passed, listen for response
            for event in event_queue:
                if event.type == SDL_KEYDOWN:
                    key = event.key.keysym  # keyboard button event object
                    if key.sym is sdl2.keycode.SDLK_SPACE:
                        self.event_data['PVT_RT'] = rt  # Log time elapsed as RT

        else:  # Timeout after 1 second
            self.event_data['PVT_RT'] = 'TIMEOUT'

        # After response, or timeout, terminate PVT and reset cursor to screen center
        if self.event_data['PVT_RT'] != 'NA':
            self.task_state['do_PVT'] = False
            if self.task_params['reset_target_after_poll']:
                self.position = P.screen_c[0]


    def __capture_input(self, event_queue):
        # Captures mouse motion events

        for event in event_queue:
            if event.type == sdl2.SDL_MOUSEMOTION:
                # Censor grandiose mouse motion to prevent eclipsing buffeting forces
                # TODO: Cutoffs should be dynamically generated relative to forcing function
                if -7 < event.motion.xrel < 7:
                    self.event_data['user_input'] = event.motion.xrel
                elif event.motion.xrel < -7:
                    self.event_data['user_input'] = -7
                else:
                    self.event_data['user_input'] = 7

        # Maintain mouse cursor at screen center to ensure all movement is catchable (i.e., can't run off screen)
        mouse_pos(False, P.screen_c)


    def __write_data(self):
        # Writes event by event data to database
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
                'PVT_event': self.event_data['PVT_RT'] is not 'NA',
                'PVT_RT': self.event_data['PVT_RT']
            },
            'comp_track_data'
        )


    def get_last_entry(self, column):
        # Used to access currently recorded data by variable column
        # TODO: allow for specifying how many entries to queried
        try:
            val = self.db.query(
                "SELECT {} FROM comp_track_data ".format(column) +
                "WHERE ID = (SELECT MAX(ID) " +
                "AND participant_id = {} FROM comp_track_data)".format(P.participant_id),
                fetch_all=True)
            return float(val[0][0])
        except IndexError:
            return 0


    @property
    def position(self):
        # get current position of cursor
        return self.task_state['x_pos']

    @position.setter
    def position(self, val):
        # Set position of cursor, censors values which would place the cursor off screen

        if int(val) not in range(*self.task_params['x_bounds']):
            if val < self.task_params['x_bounds'][0]:
                val = self.task_params['x_bounds'][0]
            else:
                val = self.task_params['x_bounds'][1]

        self.task_state['x_pos'] = val
