# -*- coding: utf-8 -*-

__author__ = "Brett Feltmate"

import klibs
from klibs import P
from klibs.KLGraphics import *
from klibs.KLUtilities import *
from klibs.KLUserInterface import *
from klibs.KLGraphics.KLNumpySurface import *
from CompTrack import *

import subprocess


class CompensatoryTrackingTask(klibs.Experiment):
	comp_track = None
	cursor = None
	assets = {}

	palette = {
		'grue': (025, 025, 28),  # mysteriously, leading zero throws a syntax error in last value
		'white': (255, 255, 255),
		'red': (255, 000, 000),
		'black': (000, 000, 000)
	}

	metrics = {
		'fixation_radius': [1, None, None],
		'target_frame_h': [3, None, None],
		'target_frame_w': [6, None, None],
		'target_h': [1.8, None, None],
		'cursor': [0.75, None, None]
	}

	def setup(self):
		# PVTarget's mouse velocity algo triggers OS X's Settings->Accessibility->Display->Shake Mouse Pointer To Locate
		if not P.development_mode:
			self.check_osx_mouse_shake_setting()

		self.txtm.add_style('UserAlert', 16, self.palette['red'])

		# all graphical aspects of the program are derived from an arbitrary base unit
		for asset in self.metrics:
			if asset is 'abs_unit':
				continue
			self.metrics[asset][1] = self.metrics['abs_unit'] * self.metrics[asset][0]
		self.comp_track = CompTrack()
		#######################################
		#
		# RAY, SETTINGS ARE HERE
		#
		#######################################
		self.comp_track.velocity_bounds = [5.0, 10.0]  # px/s  must be a float
		# this next one is measured in px/s, but is expressed here as 5% of the monitor in one step; any integer
		# is also fine as a value. warning: this gets crazy quickly, think small
		self.comp_track.max_velocity = 0.05 * P.screen_x
		self.comp_track.params['exp_duration'] = 150  # seconds
		self.comp_track.params['trial_count'] = 9
		self.comp_track.params['trial_interval_bounds'] = [10, 15]  # min/max, seconds
		self.comp_track.params['poll_while_moving'] = True
		self.comp_track.params['poll_at_fixation'] = True  # this overrides poll_while_moving
		self.comp_track.params['reset_target_after_poll'] = True  # sets target back to fixation after a response
		# self.comp_track.params['track_input'] = False  # decides whether cursor is visible
		# self.comp_track.params['mouse_input'] = True  # target will ignore user-input
		self.comp_track.generate_trials()

		clear()
		flip()
		mouse_pos(False, P.screen_c)
		hide_mouse_cursor()
		session_start = now()
		while (now() - session_start) < self.comp_track.params['exp_duration']:
			events = pump(True)
			self.comp_track.refresh(events)
			ui_request(queue=events)

		# self.db.export(table='comp_track_data')
		exit()

	def block(self):
		pass

	def setup_response_collector(self):
		pass

	def trial_prep(self):
		pass

	def trial(self):

		return {
			"block_num": P.block_number,
			"trial_num": P.trial_number
		}

	def trial_clean_up(self):
		pass

	def clean_up(self):
		pass


	def check_osx_mouse_shake_setting(self):
		p = subprocess.Popen(
			"defaults read ~/Library/Preferences/.GlobalPreferences CGDisableCursorLocationMagnification 1", shell=True)
		if p is 0:
			fill(self.palette['grue'])
			blit(NumpySurface(import_image_file('ExpAssets/Resources/image/accessibility_warning.png')), 5, P.screen_c)
			msg = 'Please ensure cursor shake-magnification is off before running this experiment.'
			x_pos = int((P.screen_y - 568) * 0.25) + 16
			message(msg, 'UserAlert', [P.screen_c[0], x_pos], 5)
			flip()
			any_key()
			quit()
