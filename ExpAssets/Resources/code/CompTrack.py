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

        self.stim_sizes = {
            'cursor': deg_to_px(1),
            'fixation': [deg_to_px(1.4), deg_to_px(0.2)],
            'PVT_frame': [deg_to_px(6), deg_to_px(3)],
            'PVT_digits': deg_to_px(1.5),
            'inner_ring': [P.screen_x * 0.3, deg_to_px(0.1)],
            'middle_ring': [P.screen_x * 0.6, deg_to_px(0.1)],
            'outer_ring': [P.screen_x * 0.9, deg_to_px(0.1)]
        }

        # PVT digit text style
        self.txtm.add_style('PVT_digits', self.stim_sizes['PVT_digits'] * .75, self.palette['white'])

        # Visual assets
        self.assets = {
            'fixation': Annulus(
                diameter=self.stim_sizes['fixation'][0],
                thickness=self.stim_sizes['fixation'][1],
                fill=self.palette['white']
            ),
            'inner_ring': Annulus(
                diameter=self.stim_sizes['inner_ring'][0],
                thickness=self.stim_sizes['inner_ring'][1],
                fill=self.palette['red']
            ),
            'middle_ring': Annulus(
                diameter=self.stim_sizes['middle_ring'][0],
                thickness=self.stim_sizes['middle_ring'][1],
                fill=self.palette['red']
            ),
            'outer_ring': Annulus(
                diameter=self.stim_sizes['outer_ring'][0],
                thickness=self.stim_sizes['outer_ring'][1],
                fill=self.palette['red']
            ),
            'cursor': Circle(
                diameter=self.stim_sizes['cursor'],
                fill=self.palette['green']
            ),
            'PVT_frame': Rectangle(
                width=self.stim_sizes['PVT_frame'][0],
                height=self.stim_sizes['PVT_frame'][1],
                stroke=[2, self.palette['red'], STROKE_OUTER]
                ).render()
        }


        #
        # Initialize task parameters
        #
        self.session_params = {
            'poll_while_moving': True,          # Should PVT events occur during tracking?
            'poll_at_fixation': False,          # Should PVT events occur upon reaching centre?
            'exp_duration': 300,                # Duration of task in seconds
            'PVT_ITI': [2, 10],                 # Min & max bounds defining inter-trial interval between PVT onsets
            'PVT_timestamps': None,             # List of timepoints at which to present PVT, populated at runtime
            'reset_target_after_poll': True,    # Should cursor be re-centred following a PVT event?
            'x_bounds': [                       # To prevent cursor moving off screen
                int(0.5 * self.stim_sizes['cursor']),
                int(P.screen_x - 0.5 * self.stim_sizes['cursor'])
            ],
            'additional_force': [],
            'lapse_threshold': None,            # RT cutoff to be labelled a lapse
            'window_width': None                # Width (i.e., # PVT responses) of window within which to compute metrics

        }

        #
        # Initialize container to store dynamic properties
        #
        self.current_state = {
            'x_pos': P.screen_c[0],     # Stores current x-pos of cursor
            'do_PVT': False,            # When True, PVT is presented on current refresh
            'PVT_start': None,          # Stores timestamp of PVT onset
            'current_modifier': 0,      # Indexes which modifier value is to be used on current refresh
            'PVT_event_count': 0        # Stores running total of PVT events presented
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

        # Initial list of timestamps is created to be of
        # length equal to total testing duration, divided by mean ITI value
        # i.e., a ballpark value of how many PVT events should be able to fit within exp_duration
        event_count = int(self.session_params['exp_duration'] / math.floor(np.mean(self.session_params['PVT_ITI'])))

        # Randomly & uniformly sample PVT timepoints of length event_count from ITI range
        timestamps = np.random.randint(
            low=self.session_params['PVT_ITI'][0],
            high=self.session_params['PVT_ITI'][1] + 1,
            size=event_count
        )

        # Ensure sum of PVT timepoints matches length of testing session
        # At least, pragmatically so. This will likely result in one too few or many events,
        # but that shouldn't matter.
        if np.sum(timestamps) < self.session_params['exp_duration']:
            # If sum of timestamps shorter than desired, iteratively append new values
            while np.sum(timestamps) < self.session_params['exp_duration']:
                timestamp = np.random.randint(
                    low=self.session_params['PVT_ITI'][0],
                    high=self.session_params['PVT_ITI'][1] + 1
                )
                np.append(timestamps, timestamp)

        elif np.sum(timestamps) > self.session_params['exp_duration']:
            # If sum longer than desired, iteratively trim values
            while np.sum(timestamps) < self.session_params['exp_duration']:
                timestamps = timestamps[:-1]

        # Convert timestamps into ascending values by setting each to the cumulative sum of itself and prior values.
        # And assign the resulting list as the finalized sequence of PVT events
        self.session_params['PVT_timestamps'] = np.cumsum(timestamps)


    def refresh(self, event_queue):
        # Handles event sequence for each refresh, called by experiment.py

        # Init event data container
        self.event_data = deepcopy(self.event_data_template)
        self.event_data['timestamp'] = now() - self.__init_time

        # Determine when next PVT event should occur
        if self.current_state['PVT_event_count'] < len(self.session_params['PVT_timestamps']):
            next_PVT_event = self.session_params['PVT_timestamps'][self.current_state['PVT_event_count']]
        else:
            next_PVT_event = None

        # If PVT event not currently in progress, and subsequent PVT events remain
        if not self.current_state['do_PVT'] and next_PVT_event is not None:
            # present PVT after the appropriate time has passed
            if self.event_data['timestamp'] >= next_PVT_event:
                self.current_state['PVT_start'] = now()
                self.current_state['PVT_event_count'] += 1
                self.current_state['do_PVT'] = True

        # Listen for PVT response (silently returns if PVT not in progress)
        self.__fetch_response(event_queue)

        # Compute buffeting forces
        self.__compute_forces()

        # If PVT not in progress, listen for & capture mouse input
        if not self.current_state['do_PVT']:
            self.__capture_input(event_queue)
            # Update cursor position, applying mouse input & buffeting forces
            self.position = self.position + self.event_data['total_force'] + self.event_data['user_input']

        # Write trial details to database
        self.__write_data()
        # Render stimuli
        self.__render()


    def __render(self):
        # Renders stimuli to screen

        # Paint & populate display
        fill(self.palette['grue'])

        # Spawn & blit PVT display (if PVT event)
        if self.current_state['do_PVT']:
            # Digit string represents milliseconds elapsed since PVT onset
            digit_str = str((now() - self.current_state['PVT_start']) * 1000)[0:4]
            if digit_str[-1] == ".":
                digit_str = digit_str[0:3]
            digits = message(digit_str, 'PVT_digits', flip_screen=False, blit_txt=False)
            blit(self.assets['PVT_frame'], BL_CENTER, P.screen_c)
            blit(digits, BL_CENTER, P.screen_c)
        # Otherwise, blit cursor to updated position
        else:
            blit(self.assets['fixation'], BL_CENTER, P.screen_c)
            blit(self.assets['inner_ring'], BL_CENTER, P.screen_c)
            blit(self.assets['middle_ring'], BL_CENTER, P.screen_c)
            blit(self.assets['outer_ring'], BL_CENTER, P.screen_c)
            blit(self.assets['cursor'], BL_CENTER, [self.position, P.screen_c[1]])

        # Present display
        flip()


    # TODO: Jon. Don't get me started on how frustrated it makes me that our
    #       prior efforts were basically tossed away (and likely to be revived).
    #       But also do get me started because it'll become relevant

    # TODO: This should be settable

    def __buffeting_force(self):
        # Generates variable buffeting force
        # Force equals sum of several sinusoidal functions

        # Note: when modifying these values

        # value in "sin( val * timestamp)" modifies periodicity of sin wave, but not amplitude
        # i.e., how long to reach min/max amplitude, lower vals mean wider/longer periods

        # value in "val * sin(timestamp)" modifies amplitude of sin wave, but not periodicity
        # i.e., scales resultant displacement value applied to cursor.

        t = self.event_data['timestamp']
        return sin(t) + sin(0.3*t) + sin(0.5*t) + sin(0.7*t) - sin(0.9*t)



    # TODO: will be implemented in conjunction with the below function to add an additional degree of randomness
    #       how to actually generate & employ these values is up for discussion
    #       which is to say, the use of tan() and geomspace() are literally just me fucking around.

    def __compute_buffet_modifier_values(self, start=0.1, stop=1.4, count=100):
        # Generates cyclical sequence of modifier terms used to generate additional buffeting forces
        modifiers = np.tan(np.geomspace(start, stop, count))

        # Make modifier list 'cyclical' by flipping sign & reversing order (also trim end points to remove duplicates)
        # TODO: come up with clever Missy Elliot reference then port to function
        flip_and_reverse = np.negative(modifiers[-1:1:-1])


        self.session_params['additional_force'] = np.append(modifiers, flip_and_reverse)

    # TODO: Currently not in use, as it remains to be decided how/why/when to generate additional forces.
    def __additional_buffeting_force(self):
        # Generates additional buffeting forces
        mod_idx = self.current_state['current_modifier']



        if self.current_state['current_modifier'] == len(self.session_params['additional_force']) - 1:
            self.current_state['current_modifier'] = 0
        else:
            self.current_state['current_modifier'] += 1

        return self.session_params['additional_force'][mod_idx]

    # TODO: Uncomment additional_force once procedure settled on.
    def __compute_forces(self):
        # Aggregates buffeting forces to be applied on next render
        self.event_data['buffeting_force'] = self.__buffeting_force()
        # self.event_data['additional_force'] = self.__additional_buffeting_force()
        self.event_data['total_force'] = self.event_data['buffeting_force']  # + self.event_data['additional_force']


    def __fetch_response(self, event_queue):
        # Captures PVT responses
        if not self.current_state['do_PVT']:  # Do nothing if nothing need doing
            return

        # Time elapsed since PVT onset
        rt = now() - self.current_state['PVT_start']

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
            self.current_state['do_PVT'] = False
            if self.session_params['reset_target_after_poll']:
                self.position = P.screen_c[0]


    def __capture_input(self, event_queue):
        # Captures mouse motion events

        for event in event_queue:
            if event.type == sdl2.SDL_MOUSEMOTION:
                # NOTE: Ray doesn't want mouse input to be censored, I'm on the fence about this
                # if -4 < event.motion.xrel < 4:
                #     self.event_data['user_input'] = event.motion.xrel
                # elif event.motion.xrel < -4:
                #     self.event_data['user_input'] = -4
                # else:
                #     self.event_data['user_input'] = 4

                self.event_data['user_input'] = event.motion.xrel
        # Maintain mouse cursor at screen center to ensure all movement is catchable (i.e., can't run off screen)
        mouse_pos(False, P.screen_c)


    # TODO: Jon, I rejigged how data is written. Now it all gets inserted into a single DB
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


    # Will be used to monitor running PVT performance, once the rules around that are decided.
    # TODO: After N trials, begin calling this function to query last N PVT responses
    #       Which will be used to either calculate the mean RT, or the number of lapses (what constitutes a lapse TBD)
    #       Once started, this will be performed after every PVT response to provide a 'moving window' of PVT performance
    #       Which will serve to monitor participants' vigilance state (threshold TBD)
    #       When hypovigilance (sub-optimal vigilance) is detected, a flag is registered, which will
    #       indicate to the program to begin some fatigue mitigation technique
    #       (i.e., auditory tone, shift in difficulty, pausing for break)
    def get_last_entry(self, column):
        # Used to access currently recorded data by variable column
        # TODO: allow for specifying how many entries to query
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
        return self.current_state['x_pos']

    @position.setter
    def position(self, val):
        # Set position of cursor, censors values which would place the cursor off screen
        if int(val) not in range(*self.session_params['x_bounds']):
            if val < self.session_params['x_bounds'][0]:
                val = self.session_params['x_bounds'][0]
            else:
                val = self.session_params['x_bounds'][1]

        self.current_state['x_pos'] = val
